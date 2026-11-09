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


def test_all_drawn_text_stays_inside_canvas(tmp_path, monkeypatch):
    from PIL import ImageDraw

    original = ImageDraw.ImageDraw.text
    boxes = []

    def capture(self, xy, text, *args, **kwargs):
        boxes.append(self.textbbox(xy, text, font=kwargs["font"]))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    r = report()
    r["store_id"] = "W" * 80
    visual.render(r, tmp_path / "wide.png")
    assert boxes and all(left >= 0 and right <= 1120 for left, top, right, bottom in boxes)


def test_english_font_checks_chinese_product_label(tmp_path):
    from pathlib import Path

    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        pytest.skip("System Latin font not installed")
    r = report()
    r["locale"] = "en"
    r["metrics"] = {"products": {"current": {"top": [{"label": "商品一", "units": 1}]}}}
    with pytest.raises(ValueError, match="font"):
        visual.render(r, tmp_path / "mixed.png", font_path=str(font))


def test_financial_scope_time_and_superseded_estimate_are_visible(tmp_path, monkeypatch):
    from PIL import ImageDraw

    drawn = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    r = report()
    r["reconciliation"] = {
        "scopes": [
            {
                "company": "Example",
                "currency": "RON",
                "coverage": "partial",
                "captured_at": "2026-09-01T10:00:00+00:00",
                "payouts": [
                    {
                        "id": "estimate",
                        "status": "estimated",
                        "payout_date": "2026-09-03",
                        "net_amount": "100",
                        "superseded_by_processed": "processed",
                    },
                    {
                        "id": "processed",
                        "status": "processed",
                        "payout_date": "2026-09-03",
                        "net_amount": "95",
                        "superseded_by_processed": None,
                    },
                ],
            }
        ]
    }
    visual.render(r, tmp_path / "finance.png")
    combined = " ".join(drawn)
    assert "2026-09-01" in combined and "部分覆盖" in combined
    assert "已被处理记录替代" in combined and "processed" in combined


def test_priority_section_stops_before_financial_heading(tmp_path, monkeypatch):
    from PIL import ImageDraw

    drawn = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    r = report()
    r["markdown"] = "# 周报\n## 优先检查\n- 库存待查\n## 费用与结算\n- FINANCIAL_NOT_AN_ACTION"
    visual.render(r, tmp_path / "sections.png")
    assert "库存待查" in " ".join(drawn)
    assert "FINANCIAL_NOT_AN_ACTION" not in " ".join(drawn)


def test_english_report_with_latin_font_has_no_hidden_chinese_literals(tmp_path):
    from pathlib import Path

    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        pytest.skip("System Latin font not installed")
    r = report()
    r["locale"] = "en"
    r["freshness"] = "stale"
    r["metrics"] = {"products": {"current": {"top": [{"label": "ASCII sku", "units": 1}], "cutoff_tied_products": 2}}}
    visual.render(r, tmp_path / "english.png", font_path=str(font))


def test_missing_glyph_outside_single_probe_is_rejected(tmp_path):
    r = report()
    r["store_id"] = "sku🧑"
    with pytest.raises(ValueError, match="font"):
        visual.render(r, tmp_path / "unknown-glyph.png")


def test_known_zero_panels_and_bars_are_distinct_from_unknown(tmp_path, monkeypatch):
    from PIL import ImageDraw

    drawn = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    r = report()
    r["metrics"] = {"orders": {"current": 0, "current_statuses": {}}, "products": {"current": {"units": 0, "top": []}}}
    r["visual"] = {
        "trend": {
            "dates": ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"],
            "values": [0] * 7,
        }
    }
    visual.render(r, tmp_path / "zero.png")
    assert "本期无订单。" in drawn and "本期无已完成订单商品。" in drawn
    assert drawn.count("0") >= 7
    drawn.clear()
    r["metrics"] = {}
    r["visual"] = {}
    visual.render(r, tmp_path / "unknown.png")
    assert "本期无订单。" not in drawn and "本期无已完成订单商品。" not in drawn
    assert any("待核对" in line for line in drawn)
