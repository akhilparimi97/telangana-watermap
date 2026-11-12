import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "apps" / "web"


class FinalAtlasContractTests(unittest.TestCase):
    def test_maplibre_shell_exposes_final_controls(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("maplibre-gl", html.lower())
        for element_id in ("map", "time-year", "time-month", "story-steps", "layer-list", "owner-login"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertNotIn("leaflet", html.lower())

    def test_zoom_hierarchy_and_required_source_categories_are_declared(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        for phrase in (
            "Government source",
            "Satellite-derived",
            "DEM-inferred",
            "Public/reference source",
            "minzoom",
            "gravity-flow",
            "lift-projects",
            "guidedSteps",
        ):
            self.assertIn(phrase, js)

    def test_map_style_boots_without_waiting_for_remote_raster_tiles(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("background-base", js)
        self.assertIn("installBasemaps", js)

    def test_large_inventories_use_real_vector_tiles(self):
        water = json.loads((WEB / "data" / "vector" / "waterbodies" / "manifest.json").read_text(encoding="utf-8"))
        canals = json.loads((WEB / "data" / "vector" / "canals" / "manifest.json").read_text(encoding="utf-8"))
        self.assertGreater(water["source_feature_count"], 30000)
        self.assertEqual(canals["source_feature_count"], 9000)
        self.assertEqual(water["format"], "Mapbox Vector Tile")
        self.assertLess(max(path.stat().st_size for path in (WEB / "data" / "vector").rglob("*.pbf")), 300_000)
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("type: 'vector'", js)
        self.assertNotIn("waterbody-tiles/manifest.json", js)

    def test_open_waterbody_names_are_matched_and_labelled(self):
        enriched = json.loads((WEB / "data" / "lakes-ponds-tanks-enriched.geojson").read_text(encoding="utf-8"))
        named = [feature for feature in enriched["features"] if feature.get("properties", {}).get("name")]
        self.assertGreater(len(named), 100)
        self.assertTrue(all(feature["properties"].get("name_source") for feature in named))
        self.assertNotIn("Pranhita", {feature["properties"]["name"] for feature in named})
        self.assertNotIn("Medigadda pump house approach canal", {feature["properties"]["name"] for feature in named})
        self.assertNotIn("uppugal checkdam", {feature["properties"]["name"] for feature in named})
        self.assertNotIn("kunta", {feature["properties"]["name"] for feature in named})
        manifest = json.loads((WEB / "data" / "vector" / "waterbodies" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["named_feature_count"], len(named))
        candidates = json.loads((WEB / "data" / "osm-named-waterbody-candidates.geojson").read_text(encoding="utf-8"))
        self.assertGreater(len(candidates["features"]), 10)
        statuses = {feature["properties"]["candidate_status"] for feature in candidates["features"]}
        self.assertIn("Needs geometry reconciliation", statuses)
        self.assertIn("Name conflict with TGRAC polygon", statuses)
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("waterbody-labels", js)
        self.assertIn("waterbody-name-index.geojson", js)

    def test_seasonal_control_has_explicit_missing_state(self):
        observation_path = WEB / "data" / "seasonal-observations.json"
        observations = json.loads(observation_path.read_text(encoding="utf-8"))
        self.assertEqual(observations["period"]["start_year"], 2015)
        self.assertEqual(observations["missing_policy"], "unavailable")
        self.assertEqual(observations["reference_aoi_method"], "union_of_unscreened_monthly_candidate_extents")
        self.assertLess(observation_path.stat().st_size, 1_000_000)
        self.assertGreater(len(observations["observations"]), 0)
        for observation in observations["observations"]:
            self.assertGreater(observation["area_ha"], 0)
            self.assertGreater(observation["percent_of_observed_maximum"], 0)
            self.assertGreaterEqual(observation["aoi_valid_coverage_percent"], 90)
            self.assertLessEqual(observation["aoi_cloud_shadow_percent"], 5)
            self.assertLessEqual(observation["aoi_nodata_percent"], 1)
            if observation["comparison_year_count"] < 2:
                self.assertNotIn("monthly_mean_area_ha", observation)
            self.assertIn("geometry", observation)
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="coverage-note"', html)
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("seasonal-water-source", js)
        self.assertIn("percent_of_observed_maximum", js)
        self.assertIn("coverage_note", js)
        builder = (ROOT / "tools" / "build_seasonal_observations.py").read_text(encoding="utf-8")
        self.assertIn("unary_union", builder)

    def test_frontend_dependencies_are_local_and_csp_is_declared(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("unpkg.com", html)
        self.assertIn("vendor/maplibre-gl.css", html)
        self.assertIn("vendor/maplibre-gl.js", html)
        self.assertTrue((WEB / "vendor" / "maplibre-gl.css").is_file())
        self.assertTrue((WEB / "vendor" / "maplibre-gl.js").is_file())
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", server)

    def test_browser_acceptance_covers_timeline_transitions(self):
        script = (ROOT / "tests" / "browser_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("sync_playwright", script)
        self.assertIn("seasonal-water-fill", script)
        self.assertIn("Missing data is not interpolated", script)

    def test_detail_card_omits_missing_properties(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("visibleMetrics", js)
        self.assertIn("sourceParts", js)
        self.assertIn("Number.isFinite", js)
        self.assertIn("typeof value === 'boolean'", js)
        self.assertIn("value.trim() === ''", js)
        self.assertIn("p.source_license", js)
        self.assertNotIn("Named source unavailable", js)

    def test_gravity_flow_is_dem_oriented_and_disclosed(self):
        flow = json.loads((WEB / "data" / "gravity-flow.geojson").read_text(encoding="utf-8"))
        self.assertGreater(len(flow["features"]), 100)
        for feature in flow["features"]:
            properties = feature["properties"]
            self.assertEqual(properties["source_category"], "DEM-inferred")
            self.assertEqual(properties["flow_direction_basis"], "endpoint elevations from sampled DEM grid")
            self.assertGreaterEqual(properties["start_elevation_m"], properties["end_elevation_m"])
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("gravity-flow.geojson", js)

    def test_documented_lift_routes_have_evidence_and_conceptual_geometry_labels(self):
        routes = json.loads((WEB / "data" / "documented-lift-routes.geojson").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(routes["features"]), 7)
        for feature in routes["features"]:
            properties = feature["properties"]
            self.assertEqual(properties["source_category"], "Government source")
            self.assertTrue(properties["source_url"].startswith("https://"))
            self.assertIn("conceptual", properties["geometry_status"])
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("documented-lift-routes.geojson", js)
        self.assertIn("documented-lift-dots", js)


class OwnerRouteStoreContractTests(unittest.TestCase):
    def test_owner_token_is_required_and_route_versions_are_preserved(self):
        from tools.owner_route_store import RouteStore, Unauthorized

        with tempfile.TemporaryDirectory() as directory:
            store = RouteStore(Path(directory) / "routes.json", owner_token="secret-token")
            with self.assertRaises(Unauthorized):
                store.save("wrong", {"project_id": "lift-1", "coordinates": [[78.0, 18.0], [78.2, 18.2]], "note": "draft"})
            first = store.save("secret-token", {"project_id": "lift-1", "coordinates": [[78.0, 18.0], [78.2, 18.2]], "note": "draft"})
            second = store.save("secret-token", {"project_id": "lift-1", "coordinates": [[78.0, 18.0], [78.3, 18.3]], "note": "corrected"})
            self.assertEqual(first["version"], 1)
            self.assertEqual(second["version"], 2)
            self.assertEqual(len(store.history("lift-1")), 2)
            reverted = store.revert("secret-token", "lift-1", 1)
            self.assertEqual(reverted["version"], 3)
            self.assertEqual(reverted["coordinates"], first["coordinates"])

    def test_route_schema_is_canonical_and_rejects_invalid_geojson(self):
        from tools.owner_route_store import RouteStore

        with tempfile.TemporaryDirectory() as directory:
            store = RouteStore(Path(directory) / "routes.json", owner_token="secret-token")
            saved = store.save("secret-token", {
                "project_id": "  lift-1  ",
                "coordinates": [[78, 18], [78.2, 18.2]],
                "note": "  checked  ",
                "source": "Owner route editor",
            })
            self.assertEqual(saved["project_id"], "lift-1")
            self.assertEqual(saved["coordinates"], [[78.0, 18.0], [78.2, 18.2]])
            self.assertEqual(saved["note"], "checked")
            self.assertNotIn("unexpected", saved)
            for coordinates in (
                [["78", 18], [78.2, 18.2]],
                [[True, 18], [78.2, 18.2]],
                [[95, 18], [78.2, 18.2]],
            ):
                with self.assertRaises(ValueError):
                    store.save("secret-token", {"project_id": "lift-2", "coordinates": coordinates})

    def test_server_declares_bounded_authenticated_owner_api(self):
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("MAX_BODY_BYTES", server)
        self.assertIn("/api/owner/session", server)
        self.assertIn("HTTPStatus.REQUEST_ENTITY_TOO_LARGE", server)

    def test_owner_editor_verifies_login_and_exposes_version_controls(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        js = (WEB / "app.js").read_text(encoding="utf-8")
        for element_id in ("route-select", "load-route", "route-history", "undo-point"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("/api/owner/session", js)
        self.assertIn("/history", js)
        self.assertIn("/revert", js)
        self.assertIn("dragIndex", js)


if __name__ == "__main__":
    unittest.main()
