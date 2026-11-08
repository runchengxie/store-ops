"""Owner CLI for the private offline evidence index."""
import argparse
import json
import sys
from app.services import emag_knowledge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('--library', required=True)
    commands.add_parser('status')
    search = commands.add_parser('search')
    search.add_argument('--query', required=True)
    search.add_argument('--limit', type=int, default=5)
    args = parser.parse_args()
    try:
        if args.command == 'import':
            result = emag_knowledge.import_library(args.library)
        elif args.command == 'search':
            result = emag_knowledge.search(args.query, args.limit)
        else:
            result = emag_knowledge.status()
    except (OSError, ValueError):
        parser.exit(2, 'Knowledge operation failed; check the library and private data directory.\n')
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == '__main__':
    main()
