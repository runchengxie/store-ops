import json
import pytest
from app.evals.runner import load_cases


def test_duplicate_case_ids_are_refused(tmp_path):
    """报告是按 id 列行的。两个案例同名，看报告的人就分不清哪一行对应哪个 ——
    而评测报告的全部价值就是"哪里退步了"。"""



    folder = tmp_path / "ads"
    folder.mkdir(parents=True)
    for name in ("a.json", "b.json"):
        (folder / name).write_text(json.dumps({
            "id": "same-id", "prompt": "x", "input": {}, "expected_points": ["y"],
        }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="重复"):
        load_cases("ads", root=tmp_path)
