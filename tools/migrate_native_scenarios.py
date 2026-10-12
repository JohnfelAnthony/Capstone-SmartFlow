"""Dry-run or transactionally upgrade scenario storage without starting the API."""
import argparse
import json
import sqlite3
from pathlib import Path

from services.scenario_migration import migrate_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = args.database.resolve()
    if args.report.resolve() == path:
        parser.error('--report must be a separate file from --database')
    uri = path.as_uri() + ('?mode=rw' if args.apply else '?mode=ro')
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        if args.apply:
            conn.execute('BEGIN IMMEDIATE')
        else:
            conn.execute('PRAGMA query_only=ON')
        report = migrate_connection(conn, apply=args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    counts = {status: sum(item['status'] == status for item in report['scenarios']) for status in ('ready','blocked','unchanged')}
    print(json.dumps({'applied': args.apply, **counts, 'report': str(args.report)}))
    return 2 if counts['blocked'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
