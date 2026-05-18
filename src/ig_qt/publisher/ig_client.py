"""Thin wrapper around instagrapi with session persistence + safer error mapping."""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger


class IGClientError(Exception):
    """Generic publish error."""


class ChallengeRequiredError(IGClientError):
    """IG demands a challenge — manual resolution needed."""


class FeedbackBlockedError(IGClientError):
    """IG soft-block ('action blocked') — back off long."""


class LoginExpiredError(IGClientError):
    """Session expired."""


def _default_factory() -> Any:
    from instagrapi import Client

    return Client()


class IGClient:
    def __init__(
        self,
        *,
        session_path: Path,
        username: str,
        password: str,
        delay_range: tuple[float, float],
        fake_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._session_path = session_path
        self._username = username
        self._password = password
        self._delay_range = delay_range
        self._factory = fake_factory or _default_factory
        self._cl: Any = None

    def _build_client(self) -> Any:
        cl = self._factory()
        with contextlib.suppress(AttributeError):
            cl.delay_range = list(self._delay_range)
        return cl

    def ensure_logged_in(self) -> None:
        cl = self._build_client()
        if self._session_path.exists():
            try:
                cl.load_settings(self._session_path)
                cl.get_timeline_feed()
                self._cl = cl
                logger.info("ig_session_loaded path={}", self._session_path)
                return
            except Exception as exc:
                logger.warning("ig_session_invalid err={}", exc)

        try:
            cl.login(self._username, self._password)
            cl.dump_settings(self._session_path)
            self._cl = cl
            logger.info("ig_logged_in_fresh user={}", self._username)
        except Exception as exc:
            self._classify_and_raise(exc)

    def publish_feed(self, *, asset: Path, caption: str) -> str:
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            media = self._cl.photo_upload(str(asset), caption)
            return str(media.pk)
        except Exception as exc:
            self._classify_and_raise(exc)
            raise  # pragma: no cover

    def publish_story(self, *, asset: Path) -> str:
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            media = self._cl.photo_upload_to_story(str(asset))
            return str(media.pk)
        except Exception as exc:
            self._classify_and_raise(exc)
            raise  # pragma: no cover

    def warmup(self) -> None:
        """Light-touch read activity prior to publishing."""
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            self._cl.get_timeline_feed()
        except Exception as exc:
            logger.debug("ig_warmup_soft_fail err={}", exc)

    @staticmethod
    def _classify_and_raise(exc: Exception) -> None:
        name = type(exc).__name__
        if "Challenge" in name:
            raise ChallengeRequiredError(str(exc)) from exc
        if "Feedback" in name or "PleaseWait" in name or "ActionBlock" in name:
            raise FeedbackBlockedError(str(exc)) from exc
        if "Login" in name:
            raise LoginExpiredError(str(exc)) from exc
        raise IGClientError(str(exc)) from exc
