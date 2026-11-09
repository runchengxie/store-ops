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
        db.execute(
            "CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT DEFAULT '2026-11-09T09:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO deliveries (id,status,message_id,payload) VALUES (?,?,?,?)",
            ("key", "delivered", "om_text", json.dumps({"report": report})),
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
        db.execute(
            "CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT DEFAULT '2026-11-09T09:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO deliveries (id,status,message_id,payload) VALUES (?,?,?,?)",
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
        db.execute(
            "CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT DEFAULT '2026-11-09T09:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO deliveries (id,status,message_id,payload) VALUES (?,?,?,?)",
            ("key", "delivered", "om_text", json.dumps({"report": {"snapshot_id": "s"}})),
        )
    monkeypatch.setattr(d, "_execute", lambda *args: pytest.fail("Legacy image attempted upload"))
    assert (
        d._deliver_image(
            {"state_dir": str(tmp_path), "image_legacy_before": NOW.isoformat()},
            NOW,
            {"delivery_id": "key", "status": "delivered"},
        )["image_status"]
        == "skipped_legacy"
    )
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        assert json.loads(db.execute("SELECT payload FROM deliveries").fetchone()[0]) == {
            "report": {"snapshot_id": "s"}
        }
        assert db.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 0


@pytest.mark.parametrize(
    "visual",
    [
        {"schema_version": 99, "snapshot_id": "s"},
        {"schema_version": 1, "snapshot_id": "other"},
        {"status": "omitted_size_limit"},
    ],
)
def test_explicit_invalid_or_omitted_visual_stays_unavailable(tmp_path, monkeypatch, visual):
    payload = json.dumps({"report": {"snapshot_id": "s", "visual": visual}})
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute(
            "CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT DEFAULT '2026-11-09T09:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO deliveries (id,status,message_id,payload) VALUES (?,?,?,?)",
            ("key", "delivered", "om_text", payload),
        )
    monkeypatch.setattr(d, "_execute", lambda *args: pytest.fail("Invalid visual attempted upload"))
    assert (
        d._deliver_image({"state_dir": str(tmp_path)}, NOW, {"delivery_id": "key", "status": "delivered"})[
            "image_status"
        ]
        == "unavailable"
    )
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        assert db.execute("SELECT payload FROM deliveries").fetchone()[0] == payload
        assert db.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("skipped_legacy", 0),
        ("delivered", 0),
        ("unavailable", 1),
        ("render_failed", 1),
        ("unknown", 1),
        ("rejected", 1),
    ],
)
def test_delivery_cli_treats_only_legacy_skip_as_successful_migration(tmp_path, monkeypatch, capsys, status, expected):
    from app import emag_digest_delivery as cli

    config = tmp_path / "config.json"
    config.write_text("{}")
    monkeypatch.setattr(d, "run", lambda *a, **kw: [{"status": "delivered", "image_status": status}])
    assert cli.main(["--config", str(config)]) == expected
    assert json.loads(capsys.readouterr().out)[0]["image_status"] == status


@pytest.mark.parametrize(
    "created_at", ["2026-11-09T10:00:00+00:00", "2026-11-09T11:00:00+00:00", "invalid", "2026-11-08T09:00:00"]
)
def test_fresh_or_invalid_created_at_cannot_be_legacy(tmp_path, monkeypatch, created_at):
    from app import emag_digest_cli as source_cli

    original = {
        "store_id": "shop",
        "markdown": "Operations",
        "details_markdown": "x" * 31850,
        "generated_at": "2020-01-01T00:00:00Z",
    }
    result = source_cli._fit_optional(original, original, {"payload": "x" * 32000}, False)
    assert "visual" not in result
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?,?)",
            ("key", "delivered", "om_text", json.dumps({"report": result}), created_at),
        )
    monkeypatch.setattr(d, "_execute", lambda *a: pytest.fail("Fresh omission attempted upload"))
    receipt = d._deliver_image(
        {"state_dir": str(tmp_path), "image_legacy_before": NOW.isoformat()},
        NOW,
        {"delivery_id": "key", "status": "delivered"},
    )
    assert receipt["image_status"] == "unavailable"


@pytest.mark.parametrize("cutoff", [None, "invalid", "2026-11-09T09:30:00", "2026-11-10T00:00:00+00:00"])
def test_no_valid_opt_in_cutoff_never_skips_missing_visual(tmp_path, cutoff):
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?,?)",
            ("key", "delivered", "om_text", json.dumps({"report": {"snapshot_id": "s"}}), "2026-11-08T09:00:00Z"),
        )
    config = {"state_dir": str(tmp_path)}
    if cutoff is not None:
        config["image_legacy_before"] = cutoff
    assert d._deliver_image(config, NOW, {"delivery_id": "key", "status": "delivered"})["image_status"] == "unavailable"


@pytest.mark.parametrize("cutoff", ["invalid", "2026-11-09T09:30:00", "2026-11-10T00:00:00+00:00"])
def test_bad_migration_cutoff_is_rejected_before_any_external_call(tmp_path, monkeypatch, cutoff):
    config = {
        "enabled": True,
        "store_id": "shop",
        "app_id": "cli_test",
        "recipient_open_id": "ou_test",
        "timezone": "Europe/Bucharest",
        "locale": "zh-CN",
        "state_dir": str(tmp_path),
        "cli_command": ["/fake"],
        "source_commands": {"daily": ["/source"], "weekly": ["/source"]},
        "image_legacy_before": cutoff,
    }
    monkeypatch.setattr(d, "_execute", lambda *a: pytest.fail("Invalid migration config performed external I/O"))
    with pytest.raises(ValueError, match="image_legacy_before"):
        d.run(config, NOW, kind="daily")


def test_explicit_financial_omission_cannot_be_legacy_even_before_cutoff(tmp_path):
    with sqlite3.connect(tmp_path / "delivery.sqlite3") as db:
        db.execute("CREATE TABLE deliveries (id TEXT,status TEXT,message_id TEXT,payload TEXT,created_at TEXT)")
        db.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?,?)",
            (
                "key",
                "delivered",
                "om_text",
                json.dumps({"report": {"reconciliation": {"status": "omitted_size_limit"}}}),
                "2026-11-08T09:00:00Z",
            ),
        )
    assert (
        d._deliver_image(
            {"state_dir": str(tmp_path), "image_legacy_before": NOW.isoformat()},
            NOW,
            {"delivery_id": "key", "status": "delivered"},
        )["image_status"]
        == "unavailable"
    )
