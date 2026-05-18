"""Tests for IGClient (instagrapi wrapper)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ig_qt.publisher.ig_client import IGClient


class _FakeIG:
    """Stand-in for instagrapi.Client."""

    def __init__(self) -> None:
        self.delay_range: list[int] = []
        self.username: str | None = None
        self.password: str | None = None
        self._session: dict[str, Any] | None = None
        self.timeline_calls = 0
        self.feed_uploads: list[tuple[str, str]] = []
        self.story_uploads: list[str] = []
        self.login_attempts = 0

    def load_settings(self, path: Path) -> None:
        self._session = json.loads(Path(path).read_text())

    def dump_settings(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"device": "x"}))

    def login(self, username: str, password: str) -> bool:
        self.login_attempts += 1
        self.username = username
        self.password = password
        return True

    def get_timeline_feed(self) -> dict[str, Any]:
        self.timeline_calls += 1
        return {"feed_items": []}

    def photo_upload(self, path: str, caption: str, **_: Any) -> Any:
        self.feed_uploads.append((path, caption))

        class M:
            pk = "999"

        return M()

    def photo_upload_to_story(self, path: str, **_: Any) -> Any:
        self.story_uploads.append(path)

        class M:
            pk = "888"

        return M()


def test_load_or_login_uses_existing_session(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"device": "y"}))
    client = IGClient(
        fake_factory=lambda: fake,
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    assert fake.login_attempts == 0
    assert fake.timeline_calls == 1


def test_load_or_login_logs_in_when_no_session(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "session.json"
    client = IGClient(
        fake_factory=lambda: fake,
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    assert fake.login_attempts == 1
    assert session_path.exists()


def test_publish_feed_calls_photo_upload(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps({"device": "z"}))
    client = IGClient(
        fake_factory=lambda: fake,
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    pk = client.publish_feed(asset=Path("a.jpg"), caption="cap")
    assert pk == "999"
    assert fake.feed_uploads == [("a.jpg", "cap")]


def test_publish_story_calls_photo_upload_to_story(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps({"device": "z"}))
    client = IGClient(
        fake_factory=lambda: fake,
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    pk = client.publish_story(asset=Path("a.jpg"))
    assert pk == "888"
