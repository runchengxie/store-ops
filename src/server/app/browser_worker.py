"""Run the single fixed read-only browser check using existing private settings."""
import argparse
from app.services import browser_tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('store_id')
    parser.add_argument('task_id')
    args = parser.parse_args()
    browser_tasks.run(args.store_id, args.task_id)


if __name__ == '__main__':
    main()
