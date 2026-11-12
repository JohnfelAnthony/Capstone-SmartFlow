"""Each study-site approach as its (entry boundary, exit boundary); scenario demand and other tests rely on it."""
import unittest

from services.movement_counts import approach_boundaries
from simulation.network_registry import load_registered_network


class ApproachBoundaryTests(unittest.TestCase):
    def test_split_highway_exits_match_their_leg_by_direction(self):
        # Site B's highway legs enter and leave through different boundary nodes, and one leg runs through the neighboring junction.
        mapping = approach_boundaries(load_registered_network("tagum_site_b"))
        self.assertEqual(sorted(mapping.values()), sorted([("boundary_0", "boundary_0"), ("boundary_1", "boundary_1"), ("boundary_5", "boundary_4"), ("boundary_9", "boundary_8")]))

    def test_multi_junction_networks_are_refused(self):
        with self.assertRaisesRegex(ValueError, "study site"):
            approach_boundaries(load_registered_network("tagum_network"))


if __name__ == "__main__":
    unittest.main()
