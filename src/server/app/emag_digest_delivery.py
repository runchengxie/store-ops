"""Run private daily/weekly delivery; preview is explicit and never sends."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--config', required=True)
    parser.add_argument('--kind', choices=('daily', 'weekly'))
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--correction-id', help='Explicit manual correction to a confirmed delivered period')
    args = parser.parse_args(argv)
    if args.correction_id and not args.kind:
        parser.error('--correction-id requires --kind')
    try:
        from app.services.emag_digest_delivery import run
        config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
        result = run(config, datetime.now(timezone.utc), args.kind, args.preview, correction_id=args.correction_id)
    except Exception:
        sys.stdout.write('{"error":"digest_delivery_unavailable"}\n')
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
    return 0 if all(r['status'] in ('delivered', 'preview') and r.get('image_status', 'delivered') == 'delivered' for r in result) else 1


if __name__ == '__main__':
    raise SystemExit(main())
