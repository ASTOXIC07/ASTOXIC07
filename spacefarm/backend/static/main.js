let map = L.map('map').setView([10, 10], 2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const state = {
  fields: [],
  alerts: [],
  markers: {},
};

function riskToColor(risk) {
  if (!risk || risk.risk_type === 'normal') return 'green';
  if (risk.severity >= 75) return 'red';
  if (risk.severity >= 40) return 'yellow';
  return 'green';
}

function createCircle(lat, lon, color) {
  return L.circleMarker([lat, lon], {
    radius: 8,
    color,
    fillColor: color,
    fillOpacity: 0.8,
    weight: 2,
  });
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

async function loadFields() {
  const fields = await fetchJSON('/api/fields');
  state.fields = fields;
  const list = document.getElementById('field-list');
  list.innerHTML = '';

  fields.forEach(f => {
    const color = riskToColor(f.last_risk);
    const marker = state.markers[f.id] || createCircle(f.latitude, f.longitude, color).addTo(map);
    marker.setStyle({ color, fillColor: color });
    marker.bindPopup(`<b>${f.name}</b><br/>(${f.latitude.toFixed(3)}, ${f.longitude.toFixed(3)})<br/>` +
      (f.last_risk ? `${f.last_risk.message}<br/><i>Severity ${f.last_risk.severity}</i>` : 'No data'));
    state.markers[f.id] = marker;

    const li = document.createElement('li');
    const badgeClass = color === 'red' ? 'red' : (color === 'yellow' ? 'yellow' : 'green');
    li.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
      <div>
        <div><strong>${f.name}</strong></div>
        <div style="font-size:12px;color:#6b7280;">${f.latitude.toFixed(4)}, ${f.longitude.toFixed(4)}</div>
        <div style="font-size:12px;margin-top:4px;">${f.last_risk ? f.last_risk.message : 'No significant risk detected'}</div>
      </div>
      <span class="badge ${badgeClass}">${f.last_risk ? f.last_risk.risk_type : 'normal'}</span>
    </div>`;
    list.appendChild(li);
  });
}

async function loadAlerts() {
  const alerts = await fetchJSON('/api/alerts');
  state.alerts = alerts;
  const list = document.getElementById('alert-list');
  list.innerHTML = '';

  alerts.slice(0, 15).forEach(a => {
    const color = a.risk_type === 'flood' ? 'red' : (a.risk_type === 'drought' ? 'yellow' : 'red');
    const li = document.createElement('li');
    li.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
      <div>
        <div><strong>${a.field_name}</strong> <span style="font-size:12px;color:#6b7280;">${new Date(a.created_at).toLocaleString()}</span></div>
        <div style="font-size:12px;margin-top:4px;">${a.message}</div>
      </div>
      <span class="badge ${a.severity >= 75 ? 'red' : 'yellow'}">${a.risk_type} • ${a.severity}</span>
    </div>`;
    list.appendChild(li);
  });
}

async function recompute() {
  await fetchJSON('/api/recompute', { method: 'POST' });
  await loadFields();
  await loadAlerts();
}

// Form handling
const form = document.getElementById('add-field-form');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('field-name').value.trim();
  const latitude = parseFloat(document.getElementById('field-lat').value);
  const longitude = parseFloat(document.getElementById('field-lon').value);
  if (!name || isNaN(latitude) || isNaN(longitude)) return;
  await fetchJSON('/api/fields', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, latitude, longitude }) });
  form.reset();
  await loadFields();
  await loadAlerts();
});

document.getElementById('recompute').addEventListener('click', async () => {
  await recompute();
});

map.on('click', (ev) => {
  const { lat, lng } = ev.latlng;
  document.getElementById('field-lat').value = lat.toFixed(6);
  document.getElementById('field-lon').value = lng.toFixed(6);
});

async function init() {
  try {
    await loadFields();
    await loadAlerts();
  } catch (e) {
    console.error(e);
  }
  setInterval(() => {
    loadFields();
    loadAlerts();
  }, 30000);
}

init();