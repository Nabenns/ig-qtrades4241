"""Telegram review service: send image + caption with inline approve/reject buttons,
poll callback updates, mark post status accordingly.

Architecture:
- After composer marks post.status='review', notifier_review picks it up
- Sends photo with caption + inline keyboard to Telegram
- Stores message_id in `review_messages` table
- A poller (driven by APScheduler) periodically calls getUpdates and processes
  callback_query payloads, updating post.status to approved/rejected
"""
from __future__ import annotations

import html as html_lib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import Engine, select
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.db import session_scope
from ig_qt.models import Post, ReviewMessage

# Telegram: photo caption hard cap 1024 chars (vs message text 4096).
# We attach the IG caption truncated as needed and add summary header.
_CAPTION_MAX = 1000


@dataclass(frozen=True, slots=True)
class TelegramReviewer:
    """Sends post review to a Telegram chat with inline approve/reject buttons."""

    bot_token: str
    chat_id: str
    timeout: float = 30.0

    @property
    def _api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            files = kwargs.pop("files", None)
            if files:
                data = kwargs.pop("data", {})
                resp = await client.post(
                    f"{self._api_base}/{method}", data=data, files=files
                )
            else:
                resp = await client.post(f"{self._api_base}/{method}", json=kwargs)
            if resp.status_code >= 400:
                logger.error(
                    "telegram_api_error method={} status={} body={}",
                    method,
                    resp.status_code,
                    resp.text[:600],
                )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            return payload

    async def send_review(
        self,
        *,
        post_id: int,
        image_path: Path,
        ig_caption: str,
        topic_tag: str,
        post_type: str,
        confidence: float,
    ) -> tuple[str, int] | None:
        """Send photo + caption + inline keyboard. Returns (chat_id, message_id) on success."""
        if not image_path.exists():
            logger.warning("review_image_missing path={}", image_path)
            return None

        # Use HTML parse mode (more permissive than Markdown w/r/t special chars)
        header = (
            f"📝 <b>POST REVIEW #{post_id}</b>\n"
            f"<i>{html_lib.escape(topic_tag)}</i> · {html_lib.escape(post_type)} · "
            f"conf {confidence:.2f}\n\n"
        )
        # Trim caption to fit telegram photo caption limit
        budget = _CAPTION_MAX - len(header) - 12  # safety margin
        body_text = ig_caption[:budget]
        if len(ig_caption) > budget:
            body_text = body_text.rstrip() + "..."
        # Escape HTML special characters in user-generated text
        caption = header + html_lib.escape(body_text)

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"approve:{post_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{post_id}"},
                ],
                [
                    {"text": "📋 Copy Caption", "callback_data": f"caption:{post_id}"},
                    {"text": "🔄 Regen Image", "callback_data": f"regen:{post_id}"},
                ],
                [
                    {"text": "✏️ Edit Caption", "callback_data": f"edit:{post_id}"},
                ],
            ]
        }

        try:
            with image_path.open("rb") as f:
                payload = await self._post(
                    "sendPhoto",
                    files={"photo": (image_path.name, f, "image/jpeg")},
                    data={
                        "chat_id": self.chat_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "reply_markup": _json_dumps(keyboard),
                    },
                )
        except Exception as exc:
            logger.warning("telegram_review_send_failed err={}", exc)
            return None

        result = payload.get("result", {}) if payload.get("ok") else {}
        message_id = result.get("message_id")
        if message_id is None:
            logger.warning("telegram_review_no_message_id payload={}", str(payload)[:300])
            return None
        logger.info(
            "review_sent post_id={} chat_id={} message_id={}",
            post_id,
            self.chat_id,
            message_id,
        )
        return (self.chat_id, int(message_id))

    async def edit_caption(
        self, *, chat_id: str, message_id: int, new_caption: str
    ) -> bool:
        """Edit the caption of a previously-sent review message (after decision)."""
        try:
            await self._post(
                "editMessageCaption",
                chat_id=chat_id,
                message_id=message_id,
                caption=new_caption[: _CAPTION_MAX],
                parse_mode="HTML",
                reply_markup={"inline_keyboard": []},  # remove buttons
            )
            return True
        except Exception as exc:
            logger.warning("telegram_edit_caption_failed err={}", exc)
            return False

    async def answer_callback(
        self, *, callback_id: str, text: str | None = None
    ) -> bool:
        """Acknowledge inline button click (removes Telegram client spinner)."""
        try:
            await self._post(
                "answerCallbackQuery",
                callback_query_id=callback_id,
                **({"text": text} if text else {}),
            )
            return True
        except Exception:
            return False

    async def get_updates(self, *, offset: int = 0) -> list[dict[str, Any]]:
        """Long-poll Telegram for new updates. Returns list of update objects."""
        try:
            payload = await self._post(
                "getUpdates",
                offset=offset,
                timeout=20,
                allowed_updates=["callback_query", "message"],
            )
        except Exception as exc:
            logger.debug("telegram_getupdates_failed err={}", exc)
            return []
        if not payload.get("ok"):
            return []
        result = payload.get("result", [])
        return list(result) if isinstance(result, list) else []


def _json_dumps(obj: Any) -> str:
    """Compact JSON for Telegram payload fields that need string-encoded JSON."""
    import json

    return json.dumps(obj, separators=(",", ":"))


async def send_pending_reviews(
    *,
    engine: Engine,
    reviewer: TelegramReviewer,
) -> int:
    """Find posts with status='review' that don't have a ReviewMessage yet, send them."""
    sent = 0
    with session_scope(engine) as s:
        # Find posts that need review sent
        rows = list(
            s.execute(
                select(Post)
                .outerjoin(ReviewMessage, Post.id == ReviewMessage.post_id)
                .where(Post.status == "review", ReviewMessage.id.is_(None))
                .order_by(Post.id)
            ).scalars()
        )
        for p in rows:
            s.expunge(p)

    for post in rows:
        # Pull draft confidence + topic
        with session_scope(engine) as s:
            from ig_qt.models import PostDraft

            draft = (
                s.execute(
                    select(PostDraft).where(PostDraft.id == post.draft_id)
                ).scalar_one_or_none()
                if post.draft_id
                else None
            )
            confidence = draft.confidence if draft else 0.0
            topic_tag = draft.topic_tag if draft else "unknown"

        result = await reviewer.send_review(
            post_id=post.id,
            image_path=Path(post.asset_path),
            ig_caption=post.caption_final,
            topic_tag=topic_tag,
            post_type=post.post_type,
            confidence=confidence,
        )
        if result is None:
            continue

        chat_id, message_id = result
        with session_scope(engine) as s:
            s.add(
                ReviewMessage(
                    post_id=post.id,
                    chat_id=chat_id,
                    message_id=message_id,
                )
            )
        sent += 1
    if sent:
        logger.info("review_send_done sent={}", sent)
    return sent


async def poll_review_callbacks(
    *,
    engine: Engine,
    reviewer: TelegramReviewer,
    update_state_path: Path,
) -> int:
    """Poll Telegram getUpdates and process callback_query for approve/reject/regen.

    `update_state_path`: file path to persist last update_id (offset) between runs.
    Returns count of decisions processed.
    """
    last_offset = _read_offset(update_state_path)
    updates = await reviewer.get_updates(offset=last_offset + 1)
    if not updates:
        return 0

    processed = 0
    new_offset = last_offset
    for upd in updates:
        update_id = int(upd.get("update_id", 0))
        new_offset = max(new_offset, update_id)

        # Edit-caption reply path: a normal Telegram `message` reply to a
        # prior "EDIT POST #N" prompt. We process it before callback_query
        # because it's not a button click.
        msg = upd.get("message")
        if msg and not upd.get("callback_query"):
            handled = await _maybe_handle_edit_reply(
                engine=engine, reviewer=reviewer, msg=msg
            )
            if handled:
                processed += 1
            continue

        cq = upd.get("callback_query")
        if not cq:
            continue

        callback_id = cq.get("id", "")
        data = cq.get("data") or ""
        message = cq.get("message") or {}
        msg_chat = str(message.get("chat", {}).get("id") or "")
        msg_id = int(message.get("message_id") or 0)
        from_user = cq.get("from", {})
        username = from_user.get("username") or from_user.get("id", "?")

        action, _, post_id_str = data.partition(":")
        try:
            post_id = int(post_id_str)
        except ValueError:
            await reviewer.answer_callback(callback_id=callback_id, text="invalid")
            continue

        decision_text = await _handle_decision(
            engine=engine,
            reviewer=reviewer,
            post_id=post_id,
            action=action,
            chat_id=msg_chat,
            message_id=msg_id,
            username=str(username),
        )
        await reviewer.answer_callback(callback_id=callback_id, text=decision_text)
        processed += 1

    _write_offset(update_state_path, new_offset)
    logger.info("review_callbacks_processed processed={} new_offset={}", processed, new_offset)
    return processed


async def _send_caption_only(
    *,
    engine: Engine,
    reviewer: TelegramReviewer,
    post_id: int,
    chat_id: str,
) -> None:
    """Send the full IG caption + hashtags as a separate plain-text message for easy copy."""
    with session_scope(engine) as s:
        post = s.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            return
        caption = post.caption_final or ""
    # Telegram text message limit 4096 chars; split if needed
    remaining = caption
    while remaining:
        chunk = remaining[:3900]
        try:
            await reviewer._post(
                "sendMessage",
                chat_id=chat_id,
                text=chunk,
            )
        except Exception as exc:
            logger.warning("send_caption_only_failed err={}", exc)
            break
        remaining = remaining[3900:]


# Marker we embed in the edit-prompt message so the poller can identify
# replies that target a specific post. Looks ugly intentionally to avoid
# accidental matches on real captions.
_EDIT_PROMPT_MARKER = "✏️ EDIT POST #"


async def _send_edit_prompt(
    *,
    reviewer: TelegramReviewer,
    post_id: int,
    chat_id: str,
) -> None:
    """Send a prompt asking the user to reply with the new caption.

    Uses Telegram's `force_reply` so the mobile client opens a reply box
    automatically. The poller scans incoming messages for replies whose
    quoted text contains the EDIT marker.
    """
    text = (
        f"{_EDIT_PROMPT_MARKER}{post_id}\n\n"
        "Balas pesan ini dengan caption baru. "
        "Hashtag + disclaimer bawaan akan tetap dipertahankan otomatis."
    )
    try:
        await reviewer._post(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            reply_markup={"force_reply": True, "selective": True},
        )
    except Exception as exc:
        logger.warning("edit_prompt_send_failed err={}", exc)


async def _maybe_handle_edit_reply(
    *,
    engine: Engine,
    reviewer: TelegramReviewer,
    msg: dict[str, Any],
) -> bool:
    """If `msg` is a reply to an edit prompt, apply the new caption.

    Returns True when handled (regardless of success), False otherwise so the
    poller knows whether to attribute the update to a processed action.
    """
    reply_to = msg.get("reply_to_message") or {}
    reply_text = str(reply_to.get("text") or "")
    if _EDIT_PROMPT_MARKER not in reply_text:
        return False

    # Extract post_id from the marker line: "✏️ EDIT POST #42"
    try:
        first_line = reply_text.splitlines()[0]
        post_id = int(first_line.rsplit("#", 1)[1].strip())
    except (IndexError, ValueError):
        logger.warning("edit_reply_marker_unparseable text={!r}", reply_text[:200])
        return True

    new_caption = str(msg.get("text") or "").strip()
    if not new_caption:
        return True

    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    from_user = msg.get("from") or {}
    username = from_user.get("username") or from_user.get("id", "?")

    # Apply the new caption. We re-merge dynamic + brand hashtags so the user
    # only has to focus on body text.
    with session_scope(engine) as s:
        post = s.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            logger.warning("edit_reply_post_missing post_id={}", post_id)
            return True
        # Preserve trailing hashtags + disclaimer if user only sent body text.
        # Heuristic: append hashtag block (and disclaimer line) from the old
        # caption when the new caption doesn't already contain '#'.
        merged = _merge_caption_with_existing_hashtags(
            new_body=new_caption, old_caption=post.caption_final or ""
        )
        post.caption_final = merged

    # Acknowledge by sending a confirmation message.
    try:
        await reviewer._post(
            "sendMessage",
            chat_id=chat_id,
            text=(
                f"✅ Caption updated for post #{post_id} by @{username}.\n"
                f"New length: {len(merged)} chars."
            ),
        )
    except Exception as exc:
        logger.warning("edit_reply_ack_failed err={}", exc)

    logger.info("review_edit_caption post_id={} by={} chars={}", post_id, username, len(merged))
    return True


def _merge_caption_with_existing_hashtags(*, new_body: str, old_caption: str) -> str:
    """Reattach the hashtag + disclaimer block from `old_caption` if `new_body`
    doesn't already include hashtags. Keeps brand consistency on quick edits.
    """
    if "#" in new_body:
        return new_body
    # Split old caption at first '#': everything before it is body, after is tail.
    if "#" not in old_caption:
        return new_body
    tail_idx = old_caption.find("#")
    # Walk back to the start of the line containing the first hashtag.
    line_start = old_caption.rfind("\n", 0, tail_idx)
    if line_start == -1:
        line_start = 0
    tail = old_caption[line_start:].lstrip("\n")
    return new_body.rstrip() + "\n\n" + tail


async def _handle_decision(
    *,
    engine: Engine,
    reviewer: TelegramReviewer,
    post_id: int,
    action: str,
    chat_id: str,
    message_id: int,
    username: str,
) -> str:
    """Apply decision to the post + edit telegram message to reflect outcome."""
    now = datetime.now(UTC)
    decision_short = ""
    new_caption_suffix = ""

    if action == "approve":
        new_status = "approved"
        decision_short = "approved — siap post manual"
        new_caption_suffix = (
            f"\n\n✅ <b>APPROVED</b> by @{html_lib.escape(username)}"
            f"\n📲 <i>Caption + image siap di-post manual ke IG</i>"
        )
    elif action == "reject":
        new_status = "rejected"
        decision_short = "rejected"
        new_caption_suffix = (
            f"\n\n❌ <b>REJECTED</b> by @{html_lib.escape(username)}"
        )
    elif action == "regen":
        new_status = "review"  # back to review queue, image_gen happens elsewhere
        decision_short = "regenerate queued"
        new_caption_suffix = (
            f"\n\n🔄 <b>REGEN REQUESTED</b> by @{html_lib.escape(username)}"
            " (will regenerate)"
        )
    elif action == "caption":
        # Special action: send caption as a new message (easy copy from telegram)
        # No status change — just send full caption text
        await _send_caption_only(
            engine=engine, reviewer=reviewer, post_id=post_id, chat_id=chat_id
        )
        return "caption sent"
    elif action == "edit":
        # Prompt user to reply with replacement caption.
        # The reply gets picked up by poll_review_callbacks which detects
        # "EDIT POST #<id>" markers in the prompt message text.
        await _send_edit_prompt(
            reviewer=reviewer, post_id=post_id, chat_id=chat_id
        )
        return "edit prompt sent"
    else:
        return "unknown action"

    with session_scope(engine) as s:
        post = s.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            return "post not found"
        post.status = new_status
        rm = s.execute(
            select(ReviewMessage).where(ReviewMessage.post_id == post_id)
        ).scalar_one_or_none()
        if rm is not None:
            rm.decided_at = now
            rm.decision = action

    # Best-effort: edit the message to remove buttons + show outcome
    try:
        with session_scope(engine) as s:
            post = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            from ig_qt.models import PostDraft

            draft = (
                s.execute(
                    select(PostDraft).where(PostDraft.id == post.draft_id)
                ).scalar_one_or_none()
                if post.draft_id
                else None
            )
            confidence = draft.confidence if draft else 0.0
            topic_tag = draft.topic_tag if draft else "unknown"
            cap = post.caption_final[:600]
        new_caption = (
            f"📝 <b>POST REVIEW #{post_id}</b>\n"
            f"<i>{html_lib.escape(topic_tag)}</i> · {html_lib.escape(post.post_type)} · "
            f"conf {confidence:.2f}"
            f"{new_caption_suffix}\n\n{html_lib.escape(cap)}"
        )
        await reviewer.edit_caption(
            chat_id=chat_id, message_id=message_id, new_caption=new_caption
        )
    except Exception as exc:
        logger.debug("review_edit_caption_skip err={}", exc)

    logger.info("review_decision post_id={} action={} by={}", post_id, action, username)
    return decision_short


def _read_offset(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return 0


def _write_offset(path: Path, offset: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(offset), encoding="utf-8")


def build_reviewer(
    *, enabled: bool, bot_token: str | None, chat_id: str | None
) -> TelegramReviewer | None:
    if not enabled or not bot_token or not chat_id:
        return None
    return TelegramReviewer(bot_token=bot_token, chat_id=chat_id)