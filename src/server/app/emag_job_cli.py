"""Manually collect, compare and report; --from-latest replays offline evidence."""
import argparse
import json
import sqlite3
import httpx
from app.services import emag_jobs, emag_business, emag_readonly
from app.services.windows_credentials import read_emag_credentials


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store-id',required=True)
    parser.add_argument('--days',type=int,choices=range(1,30),default=29)
    parser.add_argument('--from-latest',action='store_true')
    args=parser.parse_args(argv)
    def collect():
        user,password=read_emag_credentials()
        try:
            with httpx.Client(timeout=35,follow_redirects=False) as client:
                evidence=emag_business.collect(client,httpx.BasicAuth(user,password),args.days,secrets=(user,password))
            return emag_readonly.redact(evidence,(user,password))
        finally:
            del user,password
    try: receipt=emag_jobs.run(args.store_id,None if args.from_latest else collect)
    except (ValueError,OSError,sqlite3.Error):
        print('Job unavailable: invalid store, storage error, or another run holds the lock.');return 2
    print(json.dumps(receipt,ensure_ascii=False))
    return 0 if receipt['status'] in ('complete','paused') else 1


if __name__=='__main__':raise SystemExit(main())
