"""Generate a bounded daily/weekly digest from saved evidence; never collect."""
import argparse
from datetime import datetime, timezone
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--store-id', required=True)
    parser.add_argument('--kind', choices=('daily', 'weekly'), required=True)
    parser.add_argument('--timezone', default='Europe/Bucharest')
    parser.add_argument('--locale', choices=('en', 'zh-CN'), default='en')
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args(argv)
    try:
        from app.services import emag_digest, store_artifacts
        try:
            snapshot = store_artifacts.read_snapshot(args.store_id)
        except FileNotFoundError:
            snapshot = None
        result = emag_digest.build(snapshot, args.kind, datetime.now(timezone.utc), args.timezone,
                                   args.locale, store_id=args.store_id)
        if args.save and snapshot:
            report = store_artifacts.save_report(args.store_id, snapshot['snapshot_id'],
                                                 'eMAG ' + args.kind + ' digest', result['details_markdown'])
            result['report_id'] = report['report_id']
        output = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(output.encode('utf-8')) > 32000:
            raise ValueError('Oversized digest')
    except Exception:
        sys.stdout.write('{"error":"digest_unavailable"}\n')
        return 2
    sys.stdout.write(output + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
