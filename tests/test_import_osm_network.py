"""The OpenStreetMap downloader fetches trunk roads and a small box around a study site."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.import_osm_network import download_roads, overpass_query, site_bbox


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class OsmDownloadTests(unittest.TestCase):
    def test_query_includes_trunk_roads(self):
        query = overpass_query("7.4577,125.7985,7.4658,125.8067")
        self.assertIn('"^(trunk|trunk_link|primary', query)
        self.assertIn("(7.4577,125.7985,7.4658,125.8067)", query)

    def test_site_box_is_centred_on_the_point(self):
        south, west, north, east = map(float, site_bbox(7.4617375, 125.8026196, 450).split(","))
        self.assertAlmostEqual((south + north) / 2, 7.4617375, places=5)
        self.assertAlmostEqual((west + east) / 2, 125.8026196, places=5)
        self.assertAlmostEqual(north - south, 2 * 450 / 111320, places=5)

    def test_a_box_over_the_size_limit_is_refused(self):
        with self.assertRaisesRegex(ValueError, "0.03 degrees"):
            site_bbox(7.46, 125.80, 2000)

    def test_download_keeps_attribution_and_query(self):
        body = json.dumps({"elements": [{"type": "node", "id": 1, "lat": 7.46, "lon": 125.80}]}).encode()
        with tempfile.TemporaryDirectory() as folder, \
                patch("tools.import_osm_network.urlopen", return_value=FakeResponse(body)):
            output = Path(folder) / "osm.json"
            download_roads(site_bbox(7.4617375, 125.8026196), output)
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(saved["smartflow_source"]["license"], "ODbL-1.0")
        self.assertIn("trunk", saved["smartflow_source"]["query"])


if __name__ == "__main__":
    unittest.main()
