import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "apps" / "web"


class WaterMapSmokeTests(unittest.TestCase):
    def test_web_shell_exists_with_watermap_contract(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div id="map"', html)
        self.assertIn("Telangana WaterMap", html)
        self.assertIn("app.js", html)

    def test_frontend_declares_official_water_layers(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        for url_fragment in (
            "home-map-rivers.geojson",
            "home-map-streams.geojson",
            "maj_med.geojson",
        ):
            self.assertIn(url_fragment, js)
        self.assertIn("Reservoirs", js)

    def test_frontend_has_provenance_and_layer_controls(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("Source &amp; data quality", html)
        self.assertIn("control.layers", js)
        self.assertIn("TGRAC", js)


if __name__ == "__main__":
    unittest.main()
