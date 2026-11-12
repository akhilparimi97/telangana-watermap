const DATA = 'data/';
const ASSET_BASE = new URL('.', document.baseURI).href;
const TELANGANA = { center: [79.2, 17.85], zoom: 7, bounds: [[76.7, 15.4], [81.8, 20.1]] };
const SOURCE_CATEGORIES = ['Government source', 'Satellite-derived', 'DEM-inferred', 'Public/reference source'];
const EMPTY_FC = { type: 'FeatureCollection', features: [] };
const state = { datasets: {}, index: [], manifests: {}, enabled: {}, ownerToken: null, plotting: false, dragIndex: null, justDragged: false, routeCoordinates: [], ownerRoutes: [], seasonal: null };

const map = new maplibregl.Map({
  container: 'map',
  center: TELANGANA.center,
  zoom: TELANGANA.zoom,
  minZoom: 6,
  maxZoom: 17,
  maxBounds: TELANGANA.bounds,
  style: {
    version: 8,
    glyphs: `${ASSET_BASE}vendor/fonts/{fontstack}/{range}.pbf`,
    sources: {},
    layers: [{ id: 'background-base', type: 'background', paint: { 'background-color': '#071517' } }]
  }
});
map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
window.__mapErrors = [];
map.on('error', event => {
  const message = event?.error?.message || String(event?.error || 'Unknown map error');
  window.__mapErrors.push(message);
  document.querySelector('#load-message').textContent = `Map error: ${message}`;
});

const layerDefinitions = [
  { key: 'boundary', label: 'Telangana boundary', color: '#ffffff', default: true, ids: ['boundary-line'] },
  { key: 'rivers', label: 'Major rivers', color: '#4cb8ea', default: true, ids: ['rivers-line'] },
  { key: 'streams', label: 'Streams / drainage', color: '#81cfe7', default: true, ids: ['streams-line'] },
  { key: 'reservoirs', label: 'Government reservoirs', color: '#22bbb8', default: true, ids: ['reservoir-fill', 'reservoir-line'] },
  { key: 'projects', label: 'Irrigation projects', color: '#efb454', default: true, ids: ['project-points'] },
  { key: 'gravity', label: 'Natural gravity flow', color: '#33a8ed', default: true, ids: ['gravity-flow', 'gravity-flow-dots'] },
  { key: 'lift', label: 'Lift projects', color: '#ef5151', default: true, ids: ['lift-projects', 'documented-lift-routes', 'documented-lift-endpoints', 'documented-lift-dots', 'owner-routes'] },
  { key: 'candidates', label: 'Modelled/reference water bodies', color: '#ff7558', default: true, ids: ['candidate-points', 'osm-name-candidates', 'osm-name-candidate-labels'] },
  { key: 'seasonal', label: 'Selected satellite extent', color: '#6ce4ff', default: true, ids: ['seasonal-water-fill', 'seasonal-water-line'] },
  { key: 'waterbodies', label: 'Lakes / tanks / ponds', color: '#62cdd1', default: true, ids: ['waterbodies-main', 'waterbodies-micro', 'waterbody-labels'] },
  { key: 'canals', label: 'Canals / distribution', color: '#e9aa45', default: true, ids: ['canals-line'] }
];
layerDefinitions.forEach(item => { state.enabled[item.key] = item.default; });

const guidedSteps = [
  { title: 'Terrain', zoom: 7, copy: 'Terrain and elevation shape Telangana’s natural drainage toward the Godavari and Krishna systems.', show: ['boundary', 'rivers', 'gravity'] },
  { title: 'Drainage', zoom: 7.7, copy: 'Blue lines are mapped rivers and streams. Moving blue dots indicate direction along mapped drainage, interpreted with DEM context—not measured discharge.', show: ['boundary', 'rivers', 'streams', 'gravity'] },
  { title: 'Collection', zoom: 8.4, copy: 'Reservoirs, lakes and tanks collect monsoon and river water. Detailed water bodies appear as you zoom in.', show: ['boundary', 'rivers', 'reservoirs', 'waterbodies', 'candidates', 'seasonal'] },
  { title: 'Lifting', zoom: 8.4, copy: 'Red project markers identify lift schemes. A route appears only when an owner-edited or documented connection exists.', show: ['boundary', 'rivers', 'projects', 'lift'] },
  { title: 'Storage', zoom: 8.8, copy: 'Storage and balancing reservoirs connect natural drainage to engineered transfer systems.', show: ['boundary', 'reservoirs', 'projects', 'candidates'] },
  { title: 'Distribution', zoom: 10, copy: 'Amber canal lines reveal engineered distribution at regional and local zoom levels.', show: ['boundary', 'reservoirs', 'projects', 'canals'] }
];

function esc(value) { return String(value ?? '—').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character])); }
function first(properties, keys) { for (const key of keys) if (properties?.[key] !== undefined && properties[key] !== null && String(properties[key]).trim()) return properties[key]; return null; }
function titleFor(feature, kind = '') { const p = feature.properties || {}; const keys = kind === 'projects' ? ['Dam_Name', 'lift_metadata_name', 'Project', 'OLD_DAM_NA', 'Name'] : ['name', 'Name', 'res', 'TYPE', 'Stream_Nm', 'rivname', 'L_NAME']; return first(p, keys) || `${kind || 'Water'} feature`; }
function fetchJson(url) { return fetch(url).then(response => { if (!response.ok) throw new Error(`${response.status} ${url}`); return response.json(); }); }
function featureCenter(feature) { const geometry = feature.geometry || {}; if (geometry.type === 'Point') return geometry.coordinates; const flat = geometry.coordinates?.flat(4).filter(value => typeof value === 'number') || []; if (flat.length < 2) return TELANGANA.center; let lon = 0, lat = 0, count = 0; for (let i = 0; i < flat.length - 1; i += 2) { lon += flat[i]; lat += flat[i + 1]; count++; } return count ? [lon / count, lat / count] : TELANGANA.center; }
function elevationAt(grid, lon, lat) { const row = Math.max(0, Math.min(grid.rows - 1, Math.round((lat - grid.latitudes[0]) / (grid.latitudes.at(-1) - grid.latitudes[0]) * (grid.rows - 1)))); const col = Math.max(0, Math.min(grid.cols - 1, Math.round((lon - grid.longitudes[0]) / (grid.longitudes.at(-1) - grid.longitudes[0]) * (grid.cols - 1)))); return Math.round(grid.elevations[row * grid.cols + col]); }
function isLift(feature) { const p = feature.properties || {}; return p.is_lift === true || String(p.is_lift).toLowerCase() === 'true' || String(p.project_subtype || '').toLowerCase().includes('lift') || /\bLIS\b/i.test(String(p.Project || '')); }
function geometryPaths(feature) { const geometry = feature.geometry || {}; return geometry.type === 'LineString' ? [geometry.coordinates] : geometry.type === 'MultiLineString' ? geometry.coordinates : []; }

function addSourceLayer(sourceId, data, layers) { map.addSource(sourceId, { type: 'geojson', data }); layers.forEach(layer => map.addLayer({ ...layer, source: sourceId })); }
function installBasemaps() {
  map.addSource('satellite', { type: 'raster', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], tileSize: 256, attribution: '© Esri, Maxar, Earthstar Geographics' });
  map.addSource('street', { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' });
  map.addLayer({ id: 'satellite-basemap', type: 'raster', source: 'satellite' });
  map.addLayer({ id: 'street-basemap', type: 'raster', source: 'street', layout: { visibility: 'none' } });
}
function installVectorLayers() {
  map.addSource('waterbodies-vector', { type: 'vector', tiles: [`${ASSET_BASE}data/vector/waterbodies/{z}/{x}/{y}.pbf`], minzoom: 9, maxzoom: 13, bounds: [77.281232461, 15.915302417, 81.27222348, 19.913111884], attribution: 'Geometry © TGRAC · Names © OpenStreetMap contributors (ODbL)' });
  map.addLayer({ id: 'waterbodies-main', type: 'fill', source: 'waterbodies-vector', 'source-layer': 'waterbodies', minzoom: 9, filter: ['>=', ['get', 'area_ha'], 1], paint: { 'fill-color': '#58c8cd', 'fill-opacity': .42, 'fill-outline-color': '#8df0ed' } });
  map.addLayer({ id: 'waterbodies-micro', type: 'fill', source: 'waterbodies-vector', 'source-layer': 'waterbodies', minzoom: 13, filter: ['<', ['get', 'area_ha'], 1], paint: { 'fill-color': '#58c8cd', 'fill-opacity': .48, 'fill-outline-color': '#8df0ed' } });
  map.addLayer({ id: 'waterbody-labels', type: 'symbol', source: 'waterbodies-vector', 'source-layer': 'waterbodies', minzoom: 10, filter: ['!=', ['get', 'name'], 'Unnamed water body'], layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 14], 'text-variable-anchor': ['top', 'bottom', 'left', 'right'], 'text-radial-offset': .5, 'text-allow-overlap': false }, paint: { 'text-color': '#e8ffff', 'text-halo-color': '#0a292d', 'text-halo-width': 1.5 } });
  map.addSource('canals-vector', { type: 'vector', tiles: [`${ASSET_BASE}data/vector/canals/{z}/{x}/{y}.pbf`], minzoom: 10, maxzoom: 13, bounds: [77.514264526, 15.959720047, 79.935290297, 19.49888083], attribution: 'TGRAC HMDA distribution layer' });
  map.addLayer({ id: 'canals-line', type: 'line', source: 'canals-vector', 'source-layer': 'canals', minzoom: 10, paint: { 'line-color': '#e9aa45', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1.1, 14, 3], 'line-opacity': .8 } });
}
function normalizeCoreData(boundary, reservoirs, projects, rivers, streams, candidates, osmNameCandidates, waterbodyNames, grid, gravity, documentedLifts) {
  boundary.features.forEach(f => Object.assign(f.properties ||= {}, { source_category: 'Government source', source_name: 'TGRAC State Boundary' }));
  reservoirs.features.forEach(f => Object.assign(f.properties ||= {}, { source_category: 'Government source', source_name: 'TGRAC Reservoirs', feature_class: 'Reservoir' }));
  projects.features.forEach(f => { const coordinate = f.geometry.coordinates; Object.assign(f.properties ||= {}, { source_category: 'Government source', source_name: 'Telangana Irrigation & CAD', feature_class: isLift(f) ? 'Lift project' : 'Irrigation project', dem_elevation_m: elevationAt(grid, coordinate[0], coordinate[1]) }); });
  rivers.features.forEach(f => Object.assign(f.properties ||= {}, { source_category: 'Government source', source_name: 'Telangana Irrigation & CAD', feature_class: 'River' }));
  streams.features.forEach(f => Object.assign(f.properties ||= {}, { source_category: 'Government source', source_name: 'Telangana Irrigation & CAD', feature_class: 'Stream' }));
  candidates.features.forEach(f => Object.assign(f.properties ||= {}, { source_category: 'Public/reference source', source_name: f.properties.source || 'Public reference', feature_class: f.properties.feature_class || 'Reservoir modelled from imagery/reference' }));
  return { boundary, reservoirs, projects, rivers, streams, candidates, osmNameCandidates, waterbodyNames, grid, gravity, documentedLifts };
}

function buildFlowData(gravity) {
  const lineFeatures = gravity.features;
  const dots = [];
  lineFeatures.slice(0, 220).forEach((feature, index) => geometryPaths(feature).forEach(path => { if (path.length > 1) dots.push({ path, phase: (index * .173) % 1 }); }));
  state.flowDots = dots.slice(0, 260);
  return { type: 'FeatureCollection', features: lineFeatures };
}
function buildLiftData(routes) {
  state.liftDots = routes.features.map((feature, index) => ({ path: feature.geometry.coordinates, phase: (index * .217) % 1 }));
  const endpointFeatures = routes.features.flatMap(feature => {
    const coordinates = feature.geometry.coordinates;
    return [
      { type: 'Feature', properties: { ...feature.properties, endpoint_role: 'intake / origin', name: feature.properties.from_name }, geometry: { type: 'Point', coordinates: coordinates[0] } },
      { type: 'Feature', properties: { ...feature.properties, endpoint_role: 'destination', name: feature.properties.to_name }, geometry: { type: 'Point', coordinates: coordinates.at(-1) } }
    ];
  });
  return { endpoints: { type: 'FeatureCollection', features: endpointFeatures } };
}
function pointAlong(path, progress) { const target = ((progress % 1) + 1) % 1; const position = target * (path.length - 1); const index = Math.min(path.length - 2, Math.floor(position)); const amount = position - index; return [path[index][0] + (path[index + 1][0] - path[index][0]) * amount, path[index][1] + (path[index + 1][1] - path[index][1]) * amount]; }
function animateFlow(time = 0) {
  const gravity = map.getSource('gravity-dots');
  if (gravity && state.enabled.gravity) gravity.setData({ type: 'FeatureCollection', features: state.flowDots.map((dot, index) => ({ type: 'Feature', properties: { index }, geometry: { type: 'Point', coordinates: pointAlong(dot.path, dot.phase + time * .000025) } })) });
  const lift = map.getSource('documented-lift-dots-source');
  if (lift && state.enabled.lift) lift.setData({ type: 'FeatureCollection', features: (state.liftDots || []).map((dot, index) => ({ type: 'Feature', properties: { index }, geometry: { type: 'Point', coordinates: pointAlong(dot.path, dot.phase + time * .00006) } })) });
  requestAnimationFrame(animateFlow);
}

function addCoreLayers(data) {
  addSourceLayer('boundary', data.boundary, [{ id: 'boundary-line', type: 'line', paint: { 'line-color': '#ffffff', 'line-width': 2.2, 'line-opacity': .9 } }]);
  addSourceLayer('rivers', data.rivers, [{ id: 'rivers-line', type: 'line', minzoom: 6, paint: { 'line-color': '#33a8ed', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1.5, 11, 4], 'line-opacity': .9 } }]);
  addSourceLayer('streams', data.streams, [{ id: 'streams-line', type: 'line', minzoom: 8.5, paint: { 'line-color': '#7dcce6', 'line-width': 1.1, 'line-opacity': .65 } }]);
  addSourceLayer('reservoirs', data.reservoirs, [
    { id: 'reservoir-fill', type: 'fill', minzoom: 6, paint: { 'fill-color': '#27bfc0', 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 6, .28, 10, .56] } },
    { id: 'reservoir-line', type: 'line', paint: { 'line-color': '#8ff9f6', 'line-width': 1.1 } }
  ]);
  addSourceLayer('projects', data.projects, [
    { id: 'project-points', type: 'circle', minzoom: 6.5, filter: ['!', ['==', ['get', 'feature_class'], 'Lift project']], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 3.5, 11, 7], 'circle-color': '#efb454', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1 } },
    { id: 'lift-projects', type: 'circle', minzoom: 6.5, filter: ['==', ['get', 'feature_class'], 'Lift project'], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 4, 11, 8], 'circle-color': '#ef5151', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.2 } }
  ]);
  addSourceLayer('candidates', data.candidates, [{ id: 'candidate-points', type: 'circle', minzoom: 7.5, paint: { 'circle-radius': 6, 'circle-color': '#ff7558', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.3 } }]);
  addSourceLayer('osm-name-candidates-source', data.osmNameCandidates, [
    { id: 'osm-name-candidates', type: 'circle', minzoom: 10, paint: { 'circle-radius': 5, 'circle-color': '#ff7558', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.2 } },
    { id: 'osm-name-candidate-labels', type: 'symbol', minzoom: 11, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1], 'text-anchor': 'top', 'text-allow-overlap': false }, paint: { 'text-color': '#ffd4ca', 'text-halo-color': '#2b1512', 'text-halo-width': 1.3 } }
  ]);
  addSourceLayer('seasonal-water-source', EMPTY_FC, [
    { id: 'seasonal-water-fill', type: 'fill', minzoom: 8, paint: { 'fill-color': '#39cde8', 'fill-opacity': .58 } },
    { id: 'seasonal-water-line', type: 'line', minzoom: 8, paint: { 'line-color': '#c5f8ff', 'line-width': 2 } }
  ]);
  const gravityLines = buildFlowData(data.gravity);
  addSourceLayer('gravity-lines', gravityLines, [{ id: 'gravity-flow', type: 'line', minzoom: 6.5, paint: { 'line-color': '#168ed1', 'line-width': 1, 'line-opacity': .28, 'line-dasharray': [2, 3] } }]);
  addSourceLayer('gravity-dots', EMPTY_FC, [{ id: 'gravity-flow-dots', type: 'circle', minzoom: 6.5, paint: { 'circle-radius': 3, 'circle-color': '#39baff', 'circle-opacity': .95, 'circle-blur': .12 } }]);
  const liftData = buildLiftData(data.documentedLifts);
  addSourceLayer('documented-lifts-source', data.documentedLifts, [{ id: 'documented-lift-routes', type: 'line', minzoom: 7, paint: { 'line-color': '#ef5151', 'line-width': 3, 'line-opacity': .92, 'line-dasharray': [2, 1.3] } }]);
  addSourceLayer('documented-lift-endpoints-source', liftData.endpoints, [{ id: 'documented-lift-endpoints', type: 'circle', minzoom: 7, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 4, 11, 7], 'circle-color': '#ef5151', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5 } }]);
  addSourceLayer('documented-lift-dots-source', EMPTY_FC, [{ id: 'documented-lift-dots', type: 'circle', minzoom: 7, paint: { 'circle-radius': 3.2, 'circle-color': '#ff8c8c', 'circle-opacity': .98 } }]);
  addSourceLayer('owner-routes-source', EMPTY_FC, [{ id: 'owner-routes', type: 'line', minzoom: 7, paint: { 'line-color': '#ef5151', 'line-width': 3.2, 'line-dasharray': [2, 2], 'line-opacity': .92 } }]);
  addSourceLayer('route-draft', EMPTY_FC, [{ id: 'route-draft-line', type: 'line', paint: { 'line-color': '#ff8b8b', 'line-width': 3, 'line-dasharray': [1, 1] } }, { id: 'route-draft-points', type: 'circle', paint: { 'circle-color': '#fff', 'circle-stroke-color': '#ef5151', 'circle-stroke-width': 2, 'circle-radius': 5 } }]);
  animateFlow();
}

function buildIndex(data) { ['reservoirs', 'projects', 'rivers', 'streams', 'candidates', 'osmNameCandidates', 'waterbodyNames'].forEach(kind => data[kind].features.forEach(feature => state.index.push({ feature, kind, title: titleFor(feature, kind), search: JSON.stringify(feature.properties || {}).toLowerCase() }))); }
function renderLayerControls() { const container = document.getElementById('layer-list'); layerDefinitions.forEach(definition => { const label = document.createElement('label'); label.className = 'layer-row'; label.innerHTML = `<input type="checkbox" data-layer="${definition.key}" ${definition.default ? 'checked' : ''}><i class="swatch" style="background:${definition.color}"></i><span>${definition.label}</span>`; label.querySelector('input').addEventListener('change', event => { state.enabled[definition.key] = event.target.checked; updateLayerVisibility(definition); }); container.appendChild(label); }); }
function updateLayerVisibility(definition) { definition.ids.forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', state.enabled[definition.key] ? 'visible' : 'none'); }); }

function setStatus(message) { document.getElementById('load-message').textContent = message; }
function updateZoomBand() { const zoom = map.getZoom(); document.getElementById('zoom-band').textContent = zoom < 8 ? 'State view' : zoom < 9.5 ? 'Regional view' : zoom < 12 ? 'District view' : 'Local view'; }
function safeUrl(value) { try { const url = new URL(String(value)); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } }
function numericMetric(value, suffix = '', maximumFractionDigits = 2) { if (value === null || value === undefined) return null; if (typeof value === 'boolean') return null; if (typeof value === 'string' && value.trim() === '') return null; if (typeof value !== 'number' && typeof value !== 'string') return null; const number = Number(value); return Number.isFinite(number) ? `${number.toLocaleString('en-IN', { maximumFractionDigits })}${suffix}` : null; }
function openDetail(feature, kind) {
  const p = feature.properties || {};
  const sourceCategory = first(p, ['source_category']) || (kind === 'gravity' ? 'DEM-inferred' : null);
  const sourceName = first(p, ['source_name', 'source', 'source_dataset']);
  const area = numericMetric(p.area_ha, ' ha');
  const directElevation = numericMetric(p.dem_elevation_m, ' m');
  const startElevation = numericMetric(p.start_elevation_m);
  const endElevation = numericMetric(p.end_elevation_m, ' m');
  const elevation = directElevation || (startElevation && endElevation ? `${startElevation} → ${endElevation}` : null);
  const observedMaximum = numericMetric(p.percent_of_observed_maximum, '%', 1);
  const metrics = [['Class', first(p, ['feature_class', 'TYPE', 'Category', 'project_subtype'])], ['Area', area], ['Elevation', elevation], ['Seasonality', first(p, ['seasonality', 'permanence'])], ['Confidence', first(p, ['classification_confidence', 'direction_confidence', 'confidence'])], ['Observed maximum', observedMaximum], ['AOI valid coverage', numericMetric(p.aoi_valid_coverage_percent, '%', 2)], ['AOI cloud / shadow', numericMetric(p.aoi_cloud_shadow_percent, '%', 2)], ['Observed at', first(p, ['observed_at'])], ['Version', p.version]];
  const visibleMetrics = metrics.filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '');
  const evidence = safeUrl(first(p, ['evidence_url', 'source_url']));
  const limitation = first(p, ['limitation', 'classification_method', 'flow_direction_basis', 'method']) || (sourceCategory === 'DEM-inferred' ? 'Terrain interpretation, not measured discharge.' : null);
  const sourceParts = [];
  if (sourceName) sourceParts.push(`<strong>Source: ${esc(sourceName)}</strong>`);
  if (p.name_source) sourceParts.push(`Name source: ${esc(p.name_source)}${p.name_source_license ? ` (${esc(p.name_source_license)})` : ''}`);
  if (p.source_license) sourceParts.push(`Licence: ${esc(p.source_license)}`);
  const nameEvidence = safeUrl(p.name_source_url);
  if (nameEvidence) sourceParts.push(`<a href="${esc(nameEvidence)}" target="_blank" rel="noopener noreferrer">View name evidence ↗</a>`);
  if (p.source_date) sourceParts.push(`Source date: ${esc(p.source_date)}`);
  if (evidence) sourceParts.push(`<a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">View source evidence ↗</a>`);
  if (limitation) sourceParts.push(esc(limitation));
  if (observedMaximum) sourceParts.push('Water extent is not storage volume.');
  const kickerHtml = sourceCategory ? `<div class="detail-kicker">${esc(sourceCategory)}</div>` : '';
  const metricsHtml = visibleMetrics.length ? `<div class="detail-grid">${visibleMetrics.map(([key, value]) => `<div class="metric"><span>${esc(key)}</span><strong>${esc(value)}</strong></div>`).join('')}</div>` : '';
  const sourceHtml = sourceParts.length ? `<div class="source-line">${sourceParts.join('<br>')}</div>` : '';
  document.getElementById('detail-content').innerHTML = `${kickerHtml}<h2>${esc(titleFor(feature, kind))}</h2>${metricsHtml}${sourceHtml}`;
  document.getElementById('detail-card').hidden = false;
}
function interactiveLayerIds() { return ['reservoir-fill', 'project-points', 'lift-projects', 'candidate-points', 'osm-name-candidates', 'rivers-line', 'streams-line', 'gravity-flow', 'documented-lift-routes', 'documented-lift-endpoints', 'owner-routes', 'seasonal-water-fill', 'waterbody-labels', 'waterbodies-main', 'waterbodies-micro', 'canals-line'].filter(id => map.getLayer(id)); }

function renderStory() { const container = document.getElementById('story-steps'); guidedSteps.forEach((step, index) => { const button = document.createElement('button'); button.className = 'story-step'; button.textContent = `${index + 1}. ${step.title}`; button.addEventListener('click', () => { document.querySelectorAll('.story-step').forEach(item => item.classList.remove('active')); button.classList.add('active'); document.getElementById('story-copy').textContent = step.copy; layerDefinitions.forEach(def => { state.enabled[def.key] = step.show.includes(def.key); const checkbox = document.querySelector(`[data-layer="${def.key}"]`); if (checkbox) checkbox.checked = state.enabled[def.key]; updateLayerVisibility(def); }); map.flyTo({ center: TELANGANA.center, zoom: step.zoom, duration: 1300 }); }); container.appendChild(button); }); }
function search(term) { const container = document.getElementById('search-results'); if (!term.trim()) { container.classList.remove('show'); return; } const query = term.toLowerCase(); const results = state.index.filter(item => item.title.toLowerCase().includes(query) || item.search.includes(query)).slice(0, 9); container.innerHTML = results.length ? results.map((item, index) => `<button class="result" data-result="${index}"><strong>${esc(item.title)}</strong><small>${esc(item.feature.properties?.source_name || item.kind)}</small></button>`).join('') : '<div class="result">No indexed feature found.</div>'; container.classList.add('show'); container.querySelectorAll('[data-result]').forEach(button => button.addEventListener('click', () => { const item = results[Number(button.dataset.result)]; map.flyTo({ center: featureCenter(item.feature), zoom: 11, duration: 900 }); openDetail(item.feature, item.kind); container.classList.remove('show'); })); }

function updateSeasonalStatus() {
  const year = Number(document.getElementById('time-year').value), month = Number(document.getElementById('time-month').value);
  const monthName = new Date(2000, month - 1).toLocaleString('en', { month: 'long' });
  document.getElementById('year-output').value = year;
  document.getElementById('month-output').value = monthName.slice(0, 3);
  const found = state.seasonal?.observations?.filter(item => item.year === year && item.month === month) || [];
  const features = found.map(observation => { const { geometry, ...properties } = observation; return { type: 'Feature', properties: { ...properties, feature_class: 'Observed satellite water extent' }, geometry }; });
  map.getSource('seasonal-water-source')?.setData({ type: 'FeatureCollection', features });
  if (!found.length) {
    document.getElementById('observation-status').textContent = `No curated observation for ${monthName} ${year}. Missing data is not interpolated.`;
    return;
  }
  const observation = found[0];
  const comparison = observation.comparison_year_count >= 2 && observation.monthly_mean_area_ha !== undefined
    ? `monthly mean ${Number(observation.monthly_mean_area_ha).toLocaleString('en-IN')} ha (${observation.comparison_year_count} usable years)`
    : `acquired ${new Date(observation.observed_at).toLocaleDateString('en-IN')} · historical monthly comparison unavailable`;
  document.getElementById('observation-status').textContent = `${observation.name}: ${Number(observation.area_ha).toLocaleString('en-IN')} ha · ${observation.percent_of_observed_maximum}% of observed maximum · ${comparison} · AOI valid coverage ${observation.aoi_valid_coverage_percent}%.`;
}

async function loadOwnerRoutes() {
  try {
    const payload = await fetchJson('/api/routes');
    state.editingEnabled = payload.editing_enabled;
    state.ownerRoutes = payload.routes;
    const features = payload.routes.map(route => ({ type: 'Feature', properties: { ...route, source_category: 'Owner-edited', source_name: route.source || 'Owner route editor' }, geometry: { type: 'LineString', coordinates: route.coordinates } }));
    map.getSource('owner-routes-source')?.setData({ type: 'FeatureCollection', features });
    const select = document.getElementById('route-select');
    select.replaceChildren(new Option('New route…', ''), ...payload.routes.map(route => new Option(`${route.project_id} · v${route.version}`, route.project_id)));
  } catch { state.editingEnabled = false; }
}
async function ownerRequest(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${state.ownerToken}`, ...(options.headers || {}) } });
  let result; try { result = await response.json(); } catch { result = { error: `HTTP ${response.status}` }; }
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
function loadSelectedRoute() {
  const projectId = document.getElementById('route-select').value;
  const route = state.ownerRoutes.find(item => item.project_id === projectId);
  if (!route) return;
  document.getElementById('project-id').value = route.project_id;
  document.getElementById('edit-note').value = route.note || '';
  state.routeCoordinates = route.coordinates.map(point => [...point]);
  state.plotting = true;
  updateDraft();
  map.fitBounds(state.routeCoordinates.reduce((bounds, point) => bounds.extend(point), new maplibregl.LngLatBounds(state.routeCoordinates[0], state.routeCoordinates[0])), { padding: 90, maxZoom: 12 });
}
async function showRouteHistory() {
  const projectId = document.getElementById('route-select').value || document.getElementById('project-id').value.trim();
  if (!projectId) return alert('Select or enter a project ID.');
  try {
    const payload = await ownerRequest(`/api/routes/${encodeURIComponent(projectId)}/history`);
    const container = document.getElementById('history-list');
    container.replaceChildren(...payload.history.slice().reverse().map(record => { const row = document.createElement('div'); row.className = 'history-row'; const label = document.createElement('span'); label.textContent = `v${record.version} · ${record.edited_at}`; const button = document.createElement('button'); button.textContent = 'Revert'; button.addEventListener('click', () => revertRoute(projectId, record.version)); row.append(label, button); return row; }));
  } catch (error) { alert(error.message); }
}
async function revertRoute(projectId, version) {
  if (!confirm(`Create a new version of ${projectId} from version ${version}?`)) return;
  try { await ownerRequest(`/api/routes/${encodeURIComponent(projectId)}/revert`, { method: 'POST', body: JSON.stringify({ version }) }); await loadOwnerRoutes(); await showRouteHistory(); } catch (error) { alert(error.message); }
}
function updateDraft() { const features = state.routeCoordinates.length ? [{ type: 'Feature', properties: { role: 'route' }, geometry: { type: 'LineString', coordinates: state.routeCoordinates } }, ...state.routeCoordinates.map((coordinates, index) => ({ type: 'Feature', properties: { index, role: index === 0 ? 'intake' : index === state.routeCoordinates.length - 1 ? 'destination' : 'vertex' }, geometry: { type: 'Point', coordinates } }))] : []; map.getSource('route-draft')?.setData({ type: 'FeatureCollection', features }); document.getElementById('save-route').disabled = state.routeCoordinates.length < 2; }
function cancelRoute() { state.plotting = false; state.routeCoordinates = []; updateDraft(); map.getCanvas().style.cursor = ''; }
async function saveRoute() {
  const projectId = document.getElementById('project-id').value.trim();
  if (!projectId || state.routeCoordinates.length < 2) return alert('Project ID and at least two map points are required.');
  try {
    const result = await ownerRequest('/api/routes', { method: 'POST', body: JSON.stringify({ project_id: projectId, coordinates: state.routeCoordinates, note: document.getElementById('edit-note').value.trim(), source: 'Owner route editor' }) });
    cancelRoute(); await loadOwnerRoutes(); alert(`Saved ${projectId} version ${result.version}`);
  } catch (error) { alert(error.message); }
}

map.on('load', async () => {
  try {
    installBasemaps();
    installVectorLayers();
    const [boundary, reservoirs, projects, rivers, streams, candidates, osmNameCandidates, waterbodyNames, grid, gravity, documentedLifts, seasonal, waterManifest, canalManifest] = await Promise.all([
      fetchJson(`${DATA}state-boundary.geojson`), fetchJson(`${DATA}reservoirs.geojson`), fetchJson(`${DATA}maj_med.geojson`), fetchJson(`${DATA}home-map-rivers.geojson`), fetchJson(`${DATA}home-map-streams.geojson`), fetchJson(`${DATA}known-reservoir-candidates.geojson`), fetchJson(`${DATA}osm-named-waterbody-candidates.geojson`), fetchJson(`${DATA}waterbody-name-index.geojson`), fetchJson(`${DATA}elevation-grid.json`), fetchJson(`${DATA}gravity-flow.geojson`), fetchJson(`${DATA}documented-lift-routes.geojson`), fetchJson(`${DATA}seasonal-observations.json`), fetchJson(`${DATA}vector/waterbodies/manifest.json`), fetchJson(`${DATA}vector/canals/manifest.json`)
    ]);
    state.manifests = { waterbodies: waterManifest, canals: canalManifest };
    state.seasonal = seasonal;
    document.getElementById('coverage-note').textContent = seasonal.coverage_note;
    const normalized = normalizeCoreData(boundary, reservoirs, projects, rivers, streams, candidates, osmNameCandidates, waterbodyNames, grid, gravity, documentedLifts);
    state.datasets = normalized; buildIndex(normalized); addCoreLayers(normalized);
    await loadOwnerRoutes(); updateSeasonalStatus(); updateZoomBand();
    setStatus(`${state.index.length.toLocaleString('en-IN')} indexed · ${state.manifests.waterbodies.source_feature_count.toLocaleString('en-IN')} detailed water bodies available`);
  } catch (error) { setStatus(`Atlas load error: ${error.message}`); console.error(error); }
});
map.on('moveend', updateZoomBand);
map.on('click', event => { if (state.justDragged) { state.justDragged = false; return; } if (state.plotting) { state.routeCoordinates.push([Number(event.lngLat.lng.toFixed(6)), Number(event.lngLat.lat.toFixed(6))]); updateDraft(); return; } const features = map.queryRenderedFeatures(event.point, { layers: interactiveLayerIds() }); if (features[0]) { const layerId = features[0].layer.id; const kind = layerId.includes('project') ? 'projects' : layerId === 'gravity-flow' ? 'gravity' : layerId === 'canals-line' ? 'canals' : 'waterbody'; openDetail(features[0], kind); } });
map.on('mousedown', 'route-draft-points', event => { if (!state.plotting || !event.features?.length) return; event.preventDefault(); state.dragIndex = Number(event.features[0].properties.index); map.dragPan.disable(); map.getCanvas().style.cursor = 'grabbing'; });
map.on('mousemove', event => { if (state.dragIndex === null) return; state.routeCoordinates[state.dragIndex] = [Number(event.lngLat.lng.toFixed(6)), Number(event.lngLat.lat.toFixed(6))]; state.justDragged = true; updateDraft(); });
map.on('mouseup', () => { if (state.dragIndex === null) return; state.dragIndex = null; map.dragPan.enable(); map.getCanvas().style.cursor = 'crosshair'; });
map.on('mouseenter', () => { if (!state.plotting) map.getCanvas().style.cursor = 'crosshair'; });

renderLayerControls(); renderStory();
document.getElementById('menu-toggle').addEventListener('click', () => document.getElementById('sidebar').classList.toggle('closed'));
document.getElementById('reset-view').addEventListener('click', () => map.flyTo({ center: TELANGANA.center, zoom: TELANGANA.zoom }));
document.getElementById('close-detail').addEventListener('click', () => { document.getElementById('detail-card').hidden = true; });
document.getElementById('search').addEventListener('input', event => search(event.target.value));
['time-year', 'time-month'].forEach(id => document.getElementById(id).addEventListener('input', updateSeasonalStatus));
document.querySelectorAll('[data-basemap]').forEach(button => button.addEventListener('click', () => { const satellite = button.dataset.basemap === 'satellite'; map.setLayoutProperty('satellite-basemap', 'visibility', satellite ? 'visible' : 'none'); map.setLayoutProperty('street-basemap', 'visibility', satellite ? 'none' : 'visible'); document.querySelectorAll('[data-basemap]').forEach(item => item.classList.toggle('active', item === button)); }));
document.getElementById('owner-login').addEventListener('click', async () => {
  if (!state.editingEnabled) return alert('Owner editing is disabled. Start server.py with WATERMAP_OWNER_TOKEN configured.');
  const token = prompt('Owner token'); if (!token) return;
  state.ownerToken = token;
  try {
    await ownerRequest('/api/owner/session');
    document.getElementById('owner-tools').hidden = false;
    document.getElementById('owner-login').textContent = 'Owner editor unlocked for this browser session';
  } catch (error) { state.ownerToken = null; document.getElementById('owner-tools').hidden = true; alert(error.message); }
});
document.getElementById('load-route').addEventListener('click', loadSelectedRoute);
document.getElementById('route-history').addEventListener('click', showRouteHistory);
document.getElementById('undo-point').addEventListener('click', () => { state.routeCoordinates.pop(); updateDraft(); });
document.getElementById('start-route').addEventListener('click', () => { state.plotting = true; state.routeCoordinates = []; updateDraft(); map.getCanvas().style.cursor = 'crosshair'; });
document.getElementById('cancel-route').addEventListener('click', cancelRoute);
document.getElementById('save-route').addEventListener('click', saveRoute);
