"""Headless browser acceptance for the atlas timeline.

Run with:
  uv run --with playwright python tests/browser_acceptance.py

Install the matching browser once if needed:
  uv run --with playwright python -m playwright install chromium
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parents[1]
SCREENSHOT = ROOT / "runtime" / "browser-acceptance.png"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(url, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"server did not start: {url}")


def wait_for_no_rendered_seasonal(page, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        count = page.evaluate("map.queryRenderedFeatures({layers:['seasonal-water-fill']}).length")
        if count == 0:
            return
        page.wait_for_timeout(200)
    raise AssertionError("stale seasonal water pixels did not disappear within 10 seconds")


def find_rendered_seasonal_point(page, year, month, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        point = page.evaluate("""([expectedYear, expectedMonth]) => {
            for (let y = 100; y < 850; y += 10) for (let x = 360; x < 1120; x += 10) {
                const features = map.queryRenderedFeatures([x, y], {layers:interactiveLayerIds()});
                const top = features[0];
                if (top?.layer.id === 'seasonal-water-fill' && Number(top.properties.year) === expectedYear && Number(top.properties.month) === expectedMonth) return {x, y};
            }
            return null;
        }""", [year, month])
        if point is not None:
            return point
        page.wait_for_timeout(200)
    raise AssertionError("seasonal water layer did not repaint within 10 seconds")


def find_named_label_point(page, expected_name, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        point = page.evaluate("""expectedName => {
            for (let y = 100; y < 850; y += 8) for (let x = 360; x < 1120; x += 8) {
                const label = map.queryRenderedFeatures([x, y], {layers:['waterbody-labels']})[0];
                if (label?.properties.name === expectedName) return {x, y};
            }
            return null;
        }""", expected_name)
        if point is not None:
            return point
        page.wait_for_timeout(250)
    raise AssertionError(f"named waterbody label did not render: {expected_name}")


def main():
    port = free_port()
    base_url = f"http://127.0.0.1:{port}/"
    environment = os.environ.copy()
    environment.update({
        "WATERMAP_PORT": str(port),
        "WATERMAP_OWNER_TOKEN": secrets.token_urlsafe(24),
        "PYTHONUNBUFFERED": "1",
    })
    process = subprocess.Popen(
        [sys.executable, "server.py"], cwd=ROOT, env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server(base_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            response = page.goto(base_url, wait_until="domcontentloaded", timeout=60_000)
            assert response and "default-src 'self'" in response.headers.get("content-security-policy", "")
            deadline = time.time() + 90
            while time.time() < deadline:
                if "detailed water bodies available" in page.locator("#load-message").inner_text():
                    break
                page.wait_for_timeout(250)
            else:
                raise AssertionError("atlas did not finish loading within 90 seconds")
            assert "quality-screened 2025 Mid Manair" in page.locator("#coverage-note").inner_text()
            assert page.evaluate("map.getSource('seasonal-water-source')._data.features.length") == 1
            page.evaluate("""(() => {
                const coordinates = map.getSource('seasonal-water-source')._data.features[0].geometry.coordinates.flat(Infinity);
                const pairs = []; for (let i = 0; i < coordinates.length; i += 2) pairs.push([coordinates[i], coordinates[i + 1]]);
                const xs = pairs.map(pair => pair[0]), ys = pairs.map(pair => pair[1]);
                map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], {padding:160, duration:0});
            })()""")
            page.wait_for_timeout(3000)
            find_rendered_seasonal_point(page, 2025, 12)
            page.locator("#time-month").evaluate("""element => {
                element.value = '8';
                element.dispatchEvent(new Event('input', {bubbles:true}));
            }""")
            assert "Missing data is not interpolated" in page.locator("#observation-status").inner_text()
            assert page.evaluate("map.getSource('seasonal-water-source')._data.features.length") == 0
            wait_for_no_rendered_seasonal(page)
            page.locator("#time-month").evaluate("""element => {
                element.value = '12';
                element.dispatchEvent(new Event('input', {bubbles:true}));
            }""")
            assert page.evaluate("map.getSource('seasonal-water-source')._data.features.length") == 1
            click_point = find_rendered_seasonal_point(page, 2025, 12)
            status = page.locator("#observation-status").inner_text()
            assert "historical monthly comparison unavailable" in status
            assert "AOI valid coverage" in status
            assert page.evaluate("""point => {
                const top = map.queryRenderedFeatures([point.x, point.y], {layers:interactiveLayerIds()})[0];
                return top?.layer.id === 'seasonal-water-fill' && Number(top.properties.year) === 2025 && Number(top.properties.month) === 12;
            }""", click_point)
            page.mouse.click(click_point["x"], click_point["y"])
            page.wait_for_selector("#detail-card:not([hidden])")
            assert "AOI VALID COVERAGE" in page.locator("#detail-content").inner_text()
            page.evaluate("openDetail({type:'Feature',properties:{name:'Only Name',area_ha:null,dem_elevation_m:null,percent_of_observed_maximum:null,aoi_valid_coverage_percent:''},geometry:{type:'Point',coordinates:[79,18]}}, 'waterbody')")
            assert page.locator("#detail-content").inner_text().strip() == "Only Name"
            page.evaluate("openDetail({type:'Feature',properties:{name:'Zero Area',area_ha:0,source_name:'OpenStreetMap contributors',source_license:'ODbL 1.0'},geometry:{type:'Point',coordinates:[79,18]}}, 'waterbody')")
            zero_detail = page.locator("#detail-content").inner_text()
            assert "0 ha" in zero_detail and "Licence: ODbL 1.0" in zero_detail
            page.evaluate("void map.jumpTo({center:[79.4199,17.99879],zoom:12})")
            label_point = find_named_label_point(page, "Dharmasagar Lake")
            page.mouse.click(label_point["x"], label_point["y"])
            page.wait_for_timeout(300)
            detail = page.locator("#detail-content").inner_text()
            assert "Dharmasagar Lake" in detail
            assert "Name source: OpenStreetMap contributors (ODbL 1.0)" in detail
            assert "—" not in detail
            page.locator("#search").fill("Shamirpet Lake")
            page.wait_for_timeout(100)
            assert "Shamirpet Lake" in page.locator("#search-results").inner_text()
            SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SCREENSHOT), full_page=True)
            errors = page.evaluate("window.__mapErrors || []")
            assert not errors, errors
            browser.close()
        print(f"browser acceptance passed; screenshot: {SCREENSHOT}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
