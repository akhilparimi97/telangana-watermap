from pathlib import Path
import json, time, urllib.parse, urllib.request

ROOT = Path(__file__).parents[1] / 'apps' / 'web' / 'data'
ROOT.mkdir(parents=True, exist_ok=True)
BASE = 'https://tgrac.telangana.gov.in/arcgis/rest/services/TGIIC_Folder/BaseLayers/MapServer/14'

def convert(g):
    if not g or 'rings' not in g:
        return None
    return {'type': 'MultiPolygon', 'coordinates': [[ring] for ring in g['rings']]}

features = []
for offset in range(0, 40000, 1000):
    params = urllib.parse.urlencode({
        'where': '1=1', 'outFields': '*', 'returnGeometry': 'true',
        'outSR': '4326', 'f': 'json', 'resultRecordCount': 1000,
        'resultOffset': offset,
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(BASE + '/query?' + params, timeout=60) as response:
                payload = json.load(response)
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3)
    page = payload.get('features', [])
    features.extend({'type': 'Feature', 'properties': f.get('attributes', {}), 'geometry': convert(f.get('geometry'))}
                     for f in page if convert(f.get('geometry')))
    print(f'offset={offset} page={len(page)} total={len(features)}', flush=True)
    if len(page) < 1000:
        break

out = {'type': 'FeatureCollection', 'features': features}
target = ROOT / 'lakes-ponds-tanks.geojson'
target.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
print(f'wrote={target} features={len(features)} bytes={target.stat().st_size}', flush=True)
