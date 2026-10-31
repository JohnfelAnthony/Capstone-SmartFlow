"""Calculate a provisional signal proposal from reviewed approach counts."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulation.network_registry import load_registered_network
from simulation.signal_design import flows_from_counts, plan_from_result, saturation_from_network, webster_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-id", required=True)
    parser.add_argument("--counts", type=Path, required=True, help="JSON approach → vehicle class → vehicles per hour")
    parser.add_argument("--junction", help="Junction ID; defaults to the first on the network")
    parser.add_argument("--phase-order", help="JSON phase array; defaults to opposite approaches and a walk phase")
    args = parser.parse_args(argv)
    try:
        network = load_registered_network(args.network_id)
        junction = args.junction or network.intersections[0]
        saturation = saturation_from_network(network, junction)
        counts = json.loads(args.counts.read_text(encoding="utf-8"))
        if args.phase_order:
            phases = json.loads(args.phase_order)
        else:
            phases = [group for pair in (("north", "south"), ("east", "west"))
                      if (group := [name for name in pair if name in saturation])]
            phases.append("pedestrian")
        result = webster_plan(phases, flows_from_counts(counts), saturation)
        output = {"network_id": network.id, "network_sha256": network.fingerprint, "junction": junction,
                  "result": asdict(result), "plan": plan_from_result(result, {}),
                  "status": "provisional; grouped phase support and field validation are incomplete"}
        print(json.dumps(output, indent=2, allow_nan=False))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(f"Signal design: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
