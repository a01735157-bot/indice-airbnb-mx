// Utilidades compartidas por los 3 mapas
const RAMP = ['#d9b48a', '#c08a52', '#96602e', '#6b3f1a', '#45280f'];

function hexToRgb(hex){
  hex = hex.replace('#','');
  return [parseInt(hex.slice(0,2),16), parseInt(hex.slice(2,4),16), parseInt(hex.slice(4,6),16)];
}
function rgbToHex(rgb){
  return '#' + rgb.map(c => Math.round(Math.max(0,Math.min(255,c))).toString(16).padStart(2,'0')).join('');
}
function interpolateRamp(t){
  t = Math.max(0, Math.min(1, t));
  const stops = RAMP.map(hexToRgb);
  const n = stops.length - 1;
  const pos = t * n;
  const i = Math.min(n - 1, Math.floor(pos));
  const f = pos - i;
  const a = stops[i], b = stops[i+1];
  return rgbToHex([a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f]);
}

const fmtMoney = new Intl.NumberFormat('es-MX', { style:'currency', currency:'MXN', maximumFractionDigits:0 });
const fmtInt = new Intl.NumberFormat('es-MX');
function fmtPct(v){ return v == null ? '—' : (v*100).toFixed(1) + '%'; }
function fmtRating(v){ return v == null ? '—' : v.toFixed(2); }

const BASEMAP_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
const BASEMAP_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

function baseMap(el, center, zoom){
  const map = L.map(el, { zoomControl: false, attributionControl: true }).setView(center, zoom);
  L.tileLayer(BASEMAP_URL, { attribution: BASEMAP_ATTR, subdomains: 'abcd', maxZoom: 19 }).addTo(map);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  return map;
}
