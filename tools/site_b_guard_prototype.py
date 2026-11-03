"""Experimental test-only guard. It is not registered in the application.

Not safe for use: 300 s synthetic trials have produced stuck junction vehicles,
and the brute-force scans have not passed the performance or full-suite checks.
"""
import argparse
import json
import math
from pathlib import Path
from simulation import road_network
from simulation.footprints import rectangle, rectangles_overlap
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine
import tools.mixed_traffic_report as report


class PrototypeCurvedLaneGuard(TrafficEngine):
    def approach_sweep(self, vehicle):
        lane = self.network.lanes[vehicle.lane_id]
        if vehicle.connector is not None:
            return []
        remaining = max(0., lane.length - vehicle.position)
        steps = max(1, math.ceil(remaining/.5))
        return [self._lane_body(vehicle, lane, vehicle.position+remaining*i/steps, vehicle.lateral, 0.) for i in range(steps+1)]

    def _sweep_blocked(self, vehicle, node):
        if super()._sweep_blocked(vehicle, node):
            return True
        sweep = self.approach_sweep(vehicle)
        x, y, _ = self._pose(vehicle)
        reach = self.network.lanes[vehicle.lane_id].length-vehicle.position+vehicle.length+12
        for other in self.vehicles.values():
            if other is vehicle:
                continue
            ox, oy, heading = self._pose(other)
            if math.hypot(ox-x,oy-y) > reach:
                continue
            body = rectangle(ox, oy, heading, other.length, other.width)
            if any(rectangles_overlap(body, sample) for sample in sweep):
                return True
            if other.reserved_junction == node and len(other.route) > 1 and other.lane_id != vehicle.lane_id:
                other_connector = self._sweeps.get(other.id, [])
                own_connector = self._sweep_for(vehicle, vehicle.lateral, self._exit_lateral(vehicle))
                other_approach = self.approach_sweep(other)
                if any(rectangles_overlap(a, b) for a in sweep for _, b, _ in other_connector):
                    return True
                if any(rectangles_overlap(a, b) for _, a, _ in own_connector for b in other_approach):
                    return True
        return False

    def _step_lateral(self, vehicle, lane):
        before = (vehicle.lateral, vehicle.lateral_speed, vehicle.yaw, vehicle.lateral_target, vehicle.lateral_cooldown_until)
        super()._step_lateral(vehicle, lane)
        if before[:3] == (vehicle.lateral, vehicle.lateral_speed, vehicle.yaw):
            return
        body = self._lane_body(vehicle, lane, vehicle.position, vehicle.lateral, vehicle.yaw)
        for other in self.vehicles.values():
            if other is vehicle:
                continue
            x, y, heading = self._pose(other)
            if rectangles_overlap(body, rectangle(x, y, heading, other.length, other.width)):
                vehicle.lateral, vehicle.lateral_speed, vehicle.yaw, vehicle.lateral_target, vehicle.lateral_cooldown_until = before
                return

    def _sweep_clear_travel(self, vehicle, lane, travel):
        travel = super()._sweep_clear_travel(vehicle, lane, travel)
        if travel <= 0:
            return 0
        neighbours = []
        x0, y0, _ = self._pose(vehicle)
        own_radius = math.hypot(vehicle.length, vehicle.width)/2
        for other in self.vehicles.values():
            if other is vehicle:
                continue
            x, y, heading = self._pose(other)
            if math.hypot(x-x0, y-y0) > own_radius+math.hypot(other.length, other.width)/2+travel+1:
                continue
            neighbours.append(rectangle(x, y, heading, other.length, other.width))
        if not neighbours:
            neighbours = []
        current = self._lane_body(vehicle, lane, vehicle.position, vehicle.lateral, vehicle.yaw)
        reserved = []
        for other in self.vehicles.values():
            if other is vehicle or not other.reserved_junction or other.connector is not None or other.lane_id == vehicle.lane_id:
                continue
            other_lane = self.network.lanes[other.lane_id]
            if other_lane.target not in (lane.source, lane.target):
                continue
            ox, oy, _ = self._pose(other)
            if math.hypot(ox-x0, oy-y0) > other_lane.length-other.position+vehicle.length+other.length+12:
                continue
            sweep = self.approach_sweep(other)
            # A body already in the protected area must be allowed to leave;
            # the direct check below still keeps its next step collision-free.
            if not any(rectangles_overlap(current, body) for body in sweep):
                reserved.extend(sweep)
        for step in (travel, travel/2, travel/4, travel/8, travel/16):
            body = self._lane_body(vehicle, lane, vehicle.position+step, vehicle.lateral, vehicle.yaw)
            if not any(rectangles_overlap(body, other) for other in neighbours+reserved):
                return step
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', type=Path, required=True, help='Uninstalled candidate network JSON')
    parser.add_argument('--out', type=Path, required=True, help='New report path; existing files are preserved')
    parser.add_argument('--seconds', type=float, default=120)
    parser.add_argument('--seeds', default='101,102')
    parser.add_argument('--case', choices=[name for name in report.CASES if name.startswith('siteB-')], default='siteB-medium-nosignal')
    parser.add_argument('--experimental-clearance-m', type=float, help='Override minimum junction clipping only within this experiment')
    args = parser.parse_args()
    if args.out.exists() or args.network.resolve() == args.out.resolve():
        parser.error('Choose a new output file')
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('Duration must be positive and finite')
    if args.experimental_clearance_m is not None:
        if not math.isfinite(args.experimental_clearance_m) or not 9 <= args.experimental_clearance_m <= 30:
            parser.error('Experimental clearance must be between 9 and 30 metres')
        road_network.JUNCTION_CLEARANCE_M = args.experimental_clearance_m
    try:
        seeds = [int(seed) for seed in args.seeds.split(',')]
    except ValueError:
        parser.error('Seeds must be comma-separated integers')
    network = RoadNetwork(json.loads(args.network.read_text(encoding='utf-8')))
    if network.id != 'tagum_site_b':
        parser.error('Expected a Site B network')
    report._network_cache['siteB'] = network
    report.TrafficEngine = PrototypeCurvedLaneGuard
    results = {'status': 'synthetic experiment; guard is not an accepted engine', 'network_fingerprint': network.fingerprint,
               'experimental_minimum_junction_clearance_m': args.experimental_clearance_m,
               'geometry_warning': 'Clearance override changes generated lanes without changing the source network fingerprint; this is not the installed engine geometry.' if args.experimental_clearance_m is not None else None,
               'case_name': args.case, 'seconds': args.seconds, 'seeds': seeds, 'cases': {}}
    for seed in seeds:
        network_name, density, mix, options = report.case_options(args.case)
        print(f'case {args.case}@{seed}', flush=True)
        result = report.run_case(network_name, density, mix, args.seconds, seed, **options)
        results['cases'][str(seed)] = result
        print(f'finished seed {seed}: overlaps={result["max_overlapping_pairs"]}, stuck={result["max_stuck_junction_vehicles"]}, completed={result["completed"]}, unfinished={result["unfinished_vehicles"]}', flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as output:
        json.dump(results, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
