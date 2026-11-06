"""Shared-lane closure (contraflow), hypothetical: the derived network, who is eligible, and that the two directions fit one pavement."""
import pytest

from simulation.contraflow import eligible_roads, kept_lane, lane_ids, shared_network, shifted_shape, strip_geometry
from simulation.network_registry import load_registered_network
from simulation.road_network import distance

A, B = "tagum_site_a", "tagum_site_b"


def test_only_wide_two_way_roads_that_are_long_enough_are_eligible():
    assert eligible_roads(load_registered_network(A)) == {"road0", "road1", "road2", "road3", "road5"}  # not the 24 m west stub (road4) or the side street (road6)
    assert eligible_roads(load_registered_network(B)) == {"road1"}  # Sobrecarey; Dao, Acacia and Bonifacio are narrow and the highway is one-way carriageways


def test_the_kept_lane_is_the_opposite_one():
    assert kept_lane("road2r") == "road2f" and kept_lane("road2f") == "road2r"


@pytest.mark.parametrize("shared", ["road2r", "road2f", "road0r", "road5f"])
def test_each_direction_gets_half_the_pavement_and_the_two_fit_inside_it(shared):
    network = load_registered_network(A)
    road = shared[:-1]
    base_width = network.lanes[shared].width
    derived = shared_network(network, {road: kept_lane(shared)})
    assert derived.id == network.id and set(derived.lanes) == set(network.lanes)  # same lane ids and topology
    assert [derived.lanes[lane].width for lane in lane_ids(road)] == [base_width/2]*2 and derived.fingerprint != network.fingerprint
    # Where the pavement is shared (away from the junction mouths) the two lane centres are half a pavement apart.
    forward, reverse = (derived.lanes[lane] for lane in lane_ids(road))
    apart = [min(distance(point, other) for other in reverse.shape) for point in forward.shape]
    assert max(apart) == pytest.approx(base_width/2, abs=0.4)
    # Two buses (2.5 m wide) side by side in the lanes keep a gap everywhere the lanes are fully apart.
    assert base_width/2 >= 2.5+0.4


def test_the_other_roads_and_the_junction_stop_lines_do_not_move():
    network = load_registered_network(A)
    derived = shared_network(network, {"road2": "road2f"})
    for lane in network.lanes:
        if not lane.startswith("road2"):
            assert derived.lanes[lane].shape == network.lanes[lane].shape and derived.lanes[lane].width == network.lanes[lane].width
    assert derived.clearance == network.clearance


def test_the_moved_centre_line_starts_and_ends_on_the_original_nodes():
    shape = [(0.0, 0.0), (200.0, 0.0)]
    moved = shifted_shape(shape, True, 3.3)
    assert moved[0] == (0.0, 0.0) and moved[-1] == (200.0, 0.0)
    assert min(y for _, y in moved) == pytest.approx(-3.3) and max(y for _, y in moved) <= 1e-9  # the right of an eastbound road is south (negative y)


def test_the_strip_geometry_names_both_lanes_for_drawing():
    geometry = strip_geometry(load_registered_network(A), "road2r")
    assert geometry["road_id"] == "road2" and geometry["shared_lane"] == "road2r" and geometry["kept_lane"] == "road2f"
    assert set(geometry["lanes"]) == {"road2f", "road2r"} and geometry["width"] == pytest.approx(3.3)


def test_an_ineligible_road_cannot_be_shared():
    with pytest.raises(ValueError, match="cannot share"):
        shared_network(load_registered_network(A), {"road6": "road6f"})
