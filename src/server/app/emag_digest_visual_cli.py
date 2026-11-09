"""Render a saved digest JSON as a local PNG; never upload or send."""

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--report", required=True)
    parser.add_argument("--font")
    parser.add_argument("--output-id", required=True)
    args = parser.parse_args(argv)
    try:
        from app.services import store_artifacts
        from app.services.emag_digest_visual import render

        name = store_artifacts.validate_id(args.output_id)
        source = Path(args.report)
        if source.stat().st_size > 32000:
            raise ValueError("Oversized source")
        report = json.loads(source.read_text(encoding="utf-8-sig"))
        store_artifacts.validate_id(report["store_id"])
        if report.get("snapshot_id") is not None:
            store_artifacts.validate_id(report["snapshot_id"])
        destination = store_artifacts._root() / "digest-images" / report["store_id"] / (name + ".png")
        if destination.exists():
            raise ValueError("Output already exists")
        metadata = render(report, destination, font_path=args.font)
        sys.stdout.write(json.dumps(metadata, ensure_ascii=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        sys.stdout.write('{"error":"digest_visual_unavailable"}\n')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
