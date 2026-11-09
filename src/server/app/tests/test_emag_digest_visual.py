from PIL import Image
import pytest
from app.services import emag_digest_visual as visual


def report():
    return {
        "schema_version": 1,
        "store_id": "test-ro",
        "snapshot_id": "snapshot-1",
        "kind": "weekly",
        "locale": "zh-CN",
        "period": {"start": "2026-11-02", "end": "2026-11-09"},
        "timezone": "Europe/Bucharest",
        "captured_at": "2026-11-09T01:00:00+00:00",
        "freshness": "fresh",
        "date_basis": "platform_calendar",
        "metrics": {},
        "markdown": "# 周报\n\n## 优先检查\n- 核对库存",
    }


def test_render_unknown_and_long_labels(tmp_path):
    r = report()
    r["store_id"] = "test-" + ("long" * 50)
    path = tmp_path / "report.png"
    visual.render(r, path)
    with Image.open(path) as image:
        assert image.width == 1120 and 1500 <= image.height <= 5000 and image.format == "PNG"


def test_explicit_missing_font_fails(tmp_path):
    with pytest.raises(ValueError, match="font"):
        visual.render(report(), tmp_path / "report.png", font_path="/missing/font.ttf")


def test_trend_missing_snapshot_is_unknown():
    assert visual.build_visual(None, report())["trend"]["values"] is None


def test_trend_uses_digest_calendar_contract(monkeypatch):
    from app.services import emag_digest

    calls = []

    def counts(evidence, prefix, window, start, end, calendar_allowed=False):
        calls.append((start, end, calendar_allowed))
        return {"current": 2 if len(calls) == 1 else 0, "basis": "platform_calendar"}

    monkeypatch.setattr(emag_digest, "_counts", counts)
    monkeypatch.setattr(emag_digest, "_calendar_contract", lambda *args: True)
    result = visual.build_visual({"snapshot_id": "snapshot-1", "store_id": "test-ro", "data": {}}, report())
    assert result["trend"]["values"] == [2, 0, 0, 0, 0, 0, 0] and len(calls) == 7


def test_snapshot_identity_mismatch_rejected():
    with pytest.raises(ValueError):
        visual.build_visual({"snapshot_id": "other", "store_id": "test-ro"}, report())


def test_latin_only_font_cannot_silently_render_chinese(tmp_path):
    from pathlib import Path

    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        pytest.skip("System Latin font not installed")
    with pytest.raises(ValueError, match="font"):
        visual.render(report(), tmp_path / "report.png", font_path=str(font))
