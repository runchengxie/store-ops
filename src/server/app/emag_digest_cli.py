"""Generate a bounded daily/weekly digest from saved evidence; never collect."""
import argparse
from datetime import datetime, timezone
import json
import sys


def _fit_optional(original, enriched, visual, saving):
    """Budget the actual CLI encoding, reserving the persisted report identifier."""
    def fits(candidate):
        serialized = {**candidate, 'report_id': '0' * 32} if saving else candidate
        return (len(json.dumps(serialized, ensure_ascii=False, allow_nan=False).encode('utf-8')) <= 32000
                and len(candidate['markdown'].encode('utf-8')) <= 16000)

    candidate = {**enriched, 'visual': visual}
    if fits(candidate):
        return candidate
    # Optional finance metadata and its appended prose are removed together. Keep
    # the entire original operational report rather than trimming its metrics.
    finance_marker = {'schema_version': 1, 'store_id': original['store_id'],
                      'status': 'omitted_size_limit', 'scopes': []}
    candidate = {**original, 'reconciliation': finance_marker, 'visual': visual}
    if fits(candidate):
        return candidate
    candidate = {**original, 'reconciliation': finance_marker,
                 'visual': {'status': 'omitted_size_limit'}}
    if fits(candidate):
        return candidate
    if fits(original):
        return dict(original)
    raise ValueError('Operational report exceeds serialization bound')


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
        original = result
        from app.services import emag_reconciliation
        result = emag_reconciliation.attach_digest(original, args.store_id, args.locale)
        from app.services.emag_digest_visual import build_visual
        visual = build_visual(snapshot, result)
        result = _fit_optional(original, result, visual, bool(args.save and snapshot))
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
