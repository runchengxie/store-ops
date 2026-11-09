"""Optional evidence cannot displace a deliverable operational report."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from app import emag_digest_cli as cli
from app.services import emag_digest, emag_digest_visual, emag_reconciliation as reconciliation, store_artifacts


def test_actual_financial_import_final_serialization_budget(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(store_artifacts, "_root", lambda: tmp_path)
    for i in range(3):
        reconciliation.import_batch(
            "shop",
            {
                "schema_version": 1,
                "company": str(i) + "c" * 59,
                "counterparty": "platform",
                "marketplace": "RO",
                "currency": "RON",
                "captured_at": "2026-11-10T10:00:00Z",
                "source_ref": "s" * 500,
                "source_kind": "manual",
                "review_status": "reviewed",
                "coverage": "partial",
                "records": [
                    {
                        "kind": "payout",
                        "id": f"estimate-{j}",
                        "revision": "v1",
                        "status": "estimated",
                        "payout_date": "2026-11-17",
                        "components": {str(k) + "x" * 55: "0.00" for k in range(30)},
                        "net_amount": "0.00",
                    }
                    for j in range(3)
                ],
            },
        )
    original = emag_digest.build(None, "weekly", datetime.now(timezone.utc), locale="zh-CN", store_id="shop")
    original["snapshot_id"] = "snap"
    original["captured_at"] = "2026-11-10T10:00:00Z"
    enriched = reconciliation.attach_digest(original, "shop", "zh-CN")
    padding = 30990 - len(json.dumps(enriched, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())
    assert padding > 0
    original["details_markdown"] += "x" * padding
    enriched = reconciliation.attach_digest(original, "shop", "zh-CN")
    assert enriched["reconciliation"]["status"] == "available"
    snapshot = {"store_id": "shop", "snapshot_id": "snap", "captured_at": original["captured_at"], "data": {}}
    overloaded = {**enriched, "visual": emag_digest_visual.build_visual(snapshot, enriched)}
    assert len(json.dumps(overloaded, ensure_ascii=False, allow_nan=False).encode()) > 32000
    monkeypatch.setattr(emag_digest, "build", lambda *a, **kw: deepcopy(original))
    monkeypatch.setattr(store_artifacts, "read_snapshot", lambda *a: snapshot)
    for save in (False, True):
        args = ["--store-id", "shop", "--kind", "weekly", "--locale", "zh-CN"] + (["--save"] if save else [])
        assert cli.main(args) == 0
        output = capsys.readouterr().out.strip()
        result = json.loads(output)
        assert len(output.encode()) <= 32000
        assert result["metrics"] == original["metrics"]
        assert result["markdown"] == original["markdown"]
        assert result["details_markdown"] == original["details_markdown"]
        assert result["reconciliation"]["status"] == "omitted_size_limit"
        if save:
            saved = store_artifacts.read_report(result["report_id"])
            assert saved["markdown"] == result["details_markdown"]


def test_large_optional_visual_is_omitted_without_trimming_operations():
    original = {
        "store_id": "shop",
        "markdown": "Operational text",
        "details_markdown": "Complete original evidence",
        "metrics": {"orders": {"current": 7}},
    }
    result = cli._fit_optional(original, original, {"schema_version": 1, "payload": "x" * 32000}, False)
    assert result["visual"]["status"] == "omitted_size_limit"
    assert result["markdown"] == original["markdown"] and result["metrics"] == original["metrics"]
    assert result["details_markdown"] == original["details_markdown"]
