"""Bounded JSON interface for the fixed read-only supervisor worker."""
import argparse
from contextlib import redirect_stdout
import io
import json
import sys

from app.services import supervisor_bridge as bridge


class _Discard(io.TextIOBase):
    def write(self, text):
        return len(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--action', required=True, choices=('status', 'run', 'cancel', 'receipt'))
    parser.add_argument('--store-id', required=True)
    parser.add_argument('--job-id')
    args = parser.parse_args(argv)
    if (args.action == 'status') != (args.job_id is None):
        parser.error('job-id is required only for run, cancel and receipt')
    try:
        with redirect_stdout(_Discard()):
            if args.action == 'status':
                result = bridge.status(args.store_id)
            else:
                result = getattr(bridge, args.action)(args.store_id, args.job_id)
        output = json.dumps(result, allow_nan=False)
        if len(output.encode('utf-8')) > 65536:
            raise ValueError('Oversized response')
    except Exception:
        # Fixed diagnostic only: storage/HTTP errors may include credentials.
        sys.stdout.write('{"error":"bridge_unavailable"}\n')
        return 2
    sys.stdout.write(output + '\n')
    return 0 if args.action != 'run' or result['status'] in {'complete', 'paused'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
