"""Import bounded manual financial evidence or read a local reconciliation report."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--store-id',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    load=commands.add_parser('import',allow_abbrev=False)
    load.add_argument('--file',required=True)
    report=commands.add_parser('report',allow_abbrev=False)
    report.add_argument('--locale',choices=('en','zh-CN'),default='en')
    commands.add_parser('history',allow_abbrev=False)
    args=parser.parse_args(argv)
    try:
        from app.services import emag_reconciliation as service
        if args.command=='import':
            path=Path(args.file)
            with path.open('rb') as stream:raw=stream.read(service.MAX_BYTES+1)
            if len(raw)>service.MAX_BYTES:raise ValueError('Oversized evidence')
            def pairs(items):
                result={}
                for key,value in items:
                    if key in result:raise ValueError('Duplicate JSON key')
                    result[key]=value
                return result
            result=service.import_batch(args.store_id,json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs))
        elif args.command=='history':result={'history':service.history(args.store_id)}
        else:
            result=service.reconcile(args.store_id)
            result['markdown']=service.render(result,args.locale)
        output=json.dumps(result,ensure_ascii=False,allow_nan=False)
    except Exception:
        sys.stdout.write('{"error":"reconciliation_unavailable"}\n')
        return 2
    sys.stdout.write(output+'\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
