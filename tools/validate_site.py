"""Validate the no-signal model of a site against a reviewed Field Observer revision.

Each invocation writes a new immutable report to docs/reports/ (never overwriting an earlier attempt) and prints the
status with every measure and reason. Development seeds come from the criteria file and must be 101-110.
Exit status: 0 PASS, 3 INCONCLUSIVE, 4 FAIL, 1 refused input.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from services.site_validation import run_validation, validate_criteria

EXIT_CODES = {"PASS": 0, "INCONCLUSIVE": 3, "FAIL": 4}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", type=int, required=True)
    parser.add_argument("--revision", type=Path, required=True, help="Reviewed Field Observer revision folder")
    parser.add_argument("--mapping", type=Path, required=True, help="data/sites/<network_id>_mapping.json, completed by the team")
    parser.add_argument("--criteria", type=Path, required=True, help="data/sites/validation_criteria.json, frozen before held-out outcomes are inspected")
    parser.add_argument("--purpose", choices=("calibration", "validation"), required=True)
    parser.add_argument("--origin-s", type=float, required=True)
    parser.add_argument("--start-s", type=float, required=True)
    parser.add_argument("--end-s", type=float, required=True)
    parser.add_argument("--site", help="Site network id; defaults to the scenario's network")
    parser.add_argument("--ledger", type=Path, help="Study ledger proving independence (required for a validation to count)")
    parser.add_argument("--reports-dir", type=Path, default=Path(__file__).resolve().parents[1] / "docs" / "reports")
    args = parser.parse_args(argv)
    try:
        site = args.site
        if not site:
            scenario_row = database.get_scenario_by_id(args.scenario_id)
            if not scenario_row:
                raise ValueError(f"Scenario {args.scenario_id} does not exist")
            site = scenario_row["network_id"]
        sites = json.loads(args.criteria.read_text(encoding="utf-8")).get("sites") or {}
        if site not in sites:
            raise ValueError(f"The criteria file has no entry for site '{site}'")
        criteria = validate_criteria(sites[site])
        scenario = database.get_scenario_by_id(args.scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {args.scenario_id} does not exist")
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger else None
        report, path = run_validation(scenario=scenario, revision_dir=args.revision, mapping=mapping, criteria=criteria, purpose=args.purpose,
                                      origin_s=args.origin_s, start_s=args.start_s, end_s=args.end_s, reports_dir=args.reports_dir, ledger=ledger)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"error: {exc}\n")
    decision = report["decision"]
    print(f"{report['status']}  site={report['site']} purpose={report['purpose']} report={path}")
    for reason in decision["reasons"]:
        print(f"  - {reason}")
    for group, items in decision["comparisons"].items():
        for key, item in items.items():
            print(f"  {group} {key}: observed={item.get('observed')} simulated={item.get('simulated')} within={item.get('within')}")
    print(f"  safety_ok={decision['safety_ok']} hypothesis_ok={decision['hypothesis_ok']} gate_open={report['gate']['open']}")
    for reason in report["gate"]["reasons"]:
        print(f"  gate: {reason}")
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
