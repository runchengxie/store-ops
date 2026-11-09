"""Independent image claims use stored text payload and never resend text."""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest
from app.services import emag_digest_delivery as d


NOW = datetime(2026, 11, 9, 10, tzinfo=timezone.utc)


def test_image_unknown_is_terminal(tmp_path, monkeypatch):
    config = {
        "image_enabled": True,
        "state_dir": str(tmp_path),
        "cli_command": ["/fake"],
        "recipient_open_id": "ou_test",
        "font_path": None,
    }
    report = {"snapshot_id": "s1", "visual": {"schema_version": 1, "snapshot_id": "s1"}}
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?)", ("key", "delivered", "om_text", json.dumps({"report": report}))
        )
    from app.services import emag_digest_visual

    def render(r, p, **kwargs):
        Path(p).write_bytes(b"fake png")

    monkeypatch.setattr(emag_digest_visual, "render", render)
    monkeypatch.setattr(d, "_verify_bot", lambda c: None)
    calls = []

    def execute(*args):
        calls.append(args)
        raise ValueError("unknown")

    monkeypatch.setattr(d, "_execute", execute)
    first = d._deliver_image(config, NOW, {"delivery_id": "key", "status": "delivered"})
    assert first["image_status"] == "unknown"
    assert d._deliver_image(config, NOW, {"delivery_id": "key", "status": "delivered"})["image_status"] == "unknown"
    assert len(calls) == 1


def test_upload_success_is_not_message_success(tmp_path, monkeypatch):
    config = {
        "image_enabled": True,
        "state_dir": str(tmp_path),
        "cli_command": ["/fake"],
        "recipient_open_id": "ou_test",
    }
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?)",
            (
                "key",
                "delivered",
                "om_text",
                json.dumps({"report": {"snapshot_id": "s", "visual": {"schema_version": 1, "snapshot_id": "s"}}}),
            ),
        )
    from app.services import emag_digest_visual

    monkeypatch.setattr(emag_digest_visual, "render", lambda r, p, **kw: Path(p).write_bytes(b"png"))
    monkeypatch.setattr(d, "_verify_bot", lambda c: None)
    results = iter(
        [
            (0, {"ok": True, "identity": "bot", "data": {"image_key": "img_test"}}),
            (0, {"ok": True, "identity": "user", "data": {"message_id": "om_image"}}),
        ]
    )
    monkeypatch.setattr(d, "_execute", lambda *args: next(results))
    assert d._deliver_image(config, NOW, {"delivery_id": "key", "status": "delivered"})["image_status"] == "unknown"


def test_preview_does_not_render_or_claim(monkeypatch):
    monkeypatch.setattr(d, "_run_text", lambda *a, **kw: [{"status": "preview"}])
    monkeypatch.setattr(d, "_deliver_image", lambda *a: pytest.fail("preview attempted image"))
    assert d.run({"image_enabled": True}, NOW, preview=True) == [{"status": "preview"}]


def test_legacy_source_never_uploads_incomplete_image(tmp_path, monkeypatch):
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?)",
            ("key", "delivered", "om_text", json.dumps({"report": {"snapshot_id": "s"}})),
        )
    monkeypatch.setattr(d, "_execute", lambda *args: pytest.fail("Legacy image attempted upload"))
    assert (
        d._deliver_image({"state_dir": str(tmp_path)}, NOW, {"delivery_id": "key", "status": "delivered"})[
            "image_status"
        ]
        == "unavailable"
    )
