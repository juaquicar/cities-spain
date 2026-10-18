// The portal: a list of cities (cities.json, written by pipeline/sites.py) and, for the ones with many municipalities,
// a picker that says how much the map will download before it loads anything. Each city's map lives in <key>/ and
// reads the choice from its hash (#cargar=code,code…&titulo=…).
const cities = await fetch('cities.json').then(r => r.json());
const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString('es-ES', { useGrouping: 'always' });
const mb = b => `${(b / 1e6).toLocaleString('es-ES', { maximumFractionDigits: b < 1e7 ? 1 : 0 })} MB`;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const plain = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// what a selection downloads: the fixed files, plus each pack and part of the table once
function weight(city, codes) {
  const files = new Set();
  for (const m of city.municipios) if (codes.has(m.code)) { m.packs.forEach(f => files.add(f)); m.parts.forEach(f => files.add(f)); }
  let bytes = city.base;
  for (const f of files) bytes += city.files[f] || 0;
  return bytes;
}
const grade = b => b < 25e6 ? ['ligero', 'Ligero'] : b < 60e6 ? ['medio', 'Medio'] : ['pesado', 'Pesado: mejor en ordenador'];

// ---------- Theme ----------
const themeBtn = $('theme');
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  themeBtn.textContent = t === 'noche' ? 'Día' : 'Noche';
  document.querySelector('meta[name="theme-color"]').content = t === 'noche' ? '#0e1522' : '#eee8dc';
  try { localStorage.setItem('tema', t); } catch (e) { /* private mode */ }
}
themeBtn.onclick = () => setTheme(document.documentElement.dataset.theme === 'noche' ? 'dia' : 'noche');
setTheme(document.documentElement.dataset.theme === 'dia' ? 'dia' : 'noche');

// ---------- Cards ----------
const nMunis = cities.reduce((s, c) => s + c.municipios.length, 0);
$('totals').innerHTML = `<span>${fmt(cities.reduce((s, c) => s + c.buildings, 0))}</span> edificios ·
  <span>${cities.length}</span> ${cities.length === 1 ? 'ciudad' : 'ciudades'} · <span>${nMunis}</span> municipios`;
const svgOf = (c, cls = '') => `<svg viewBox="0 0 ${c.view[0]} ${c.view[1]}" class="${cls}" aria-hidden="true">${
  c.municipios.map(m => `<path d="${m.d}"/>`).join('')}</svg>`;
// cards grouped by autonomous community once there are many, biggest first inside each; the chips filter by tag
const TAGS = [['grandes', 'grande', 'Grandes ciudades'], ['patrimonio', 'patrimonio', 'Ciudades Patrimonio'],
  ['costa', 'costa', 'Costa e islas']].filter(([, t]) => cities.some(c => c.tags?.includes(t)));
const GROUPED = cities.length >= 12;
const byCcaa = new Map();
for (const c of [...cities].sort((a, b) => (a.ccaa || '').localeCompare(b.ccaa || '', 'es') || b.buildings - a.buildings)) {
  if (!byCcaa.has(c.ccaa)) byCcaa.set(c.ccaa, []);
  byCcaa.get(c.ccaa).push(c);
}
const cardOf = c => {
  const all = weight(c, new Set(c.municipios.map(m => m.code)));
  const many = c.municipios.length > 1;
  return `<button class="city" data-key="${c.key}" data-tags="${(c.tags || []).join(' ')}">
    ${svgOf(c)}
    <div class="body">
      <h3>${esc(c.name)}</h3>
      <p class="sub">${esc(GROUPED ? c.sub.split(' · ')[0] : c.sub)}${c.tags?.includes('patrimonio')
        ? ' · <span class="badge" title="Grupo de Ciudades Patrimonio de la Humanidad de España">Patrimonio de la Humanidad</span>' : ''}</p>
      <p class="facts"><span><b>${fmt(c.buildings)}</b> edificios</span>
        ${many ? `<span><b>${c.municipios.length}</b> municipios</span>` : ''}
        ${c.monuments ? `<span class="heritage"><b>${fmt(c.monuments)}</b> con ficha de patrimonio</span>` : ''}
        <span class="size">${mb(all)}${many ? ' en total' : ''}</span></p>
      <span class="act">${many ? 'Elegir municipios →' : 'Abrir el mapa →'}</span>
    </div></button>`;
};
$('cities').innerHTML = GROUPED
  ? [...byCcaa].map(([ccaa, cs]) => `<h2 class="ccaa" data-ccaa="${esc(ccaa)}">${esc(ccaa)} <span>${cs.length}</span></h2>${cs.map(cardOf).join('')}`).join('')
  : cities.map(cardOf).join('');
let tag = '';
const chips = $('chips');
chips.hidden = !TAGS.length;
chips.innerHTML = [['', '', 'Todas', cities.length], ...TAGS.map(([h, t, l]) => [h, t, l, cities.filter(c => c.tags?.includes(t)).length])]
  .map(([h, , l, n]) => `<button data-h="${h}">${l} <span>${n}</span></button>`).join('');
chips.onclick = e => {
  const b = e.target.closest('button');
  if (b) location.hash = b.dataset.h;
};
function setTag(h) {
  tag = h;
  const t = (TAGS.find(([k]) => k === h) || [])[1];
  chips.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.h === h)));
  $('cities').querySelectorAll('.city').forEach(b => { b.hidden = !!t && !b.dataset.tags.split(' ').includes(t); });
  $('cities').querySelectorAll('.ccaa').forEach(hd => {
    let el = hd.nextElementSibling, n = 0;
    for (; el && el.classList.contains('city'); el = el.nextElementSibling) n += !el.hidden;
    hd.hidden = !n;
    hd.querySelector('span').textContent = n;
  });
}
$('cities').onclick = e => {
  const b = e.target.closest('.city');
  if (!b) return;
  const c = cities.find(c => c.key === b.dataset.key);
  if (c.municipios.length > 1) location.hash = c.key;
  else location.href = `${c.key}/`;
};

// ---------- Search: cities and municipalities ----------
const q = $('q'), hits = $('hits');
q.oninput = () => {
  const s = plain(q.value.trim());
  if (s.length < 2) { hits.hidden = true; return; }
  const found = [];
  for (const c of cities) {
    if (plain(c.name).includes(s) || plain(c.ccaa || '').includes(s)) found.push({ c, label: c.name, where: c.sub });
    for (const m of c.municipios) if (c.municipios.length > 1 && plain(m.name).includes(s)) found.push({ c, m, label: m.name, where: c.name });
  }
  hits.innerHTML = found.slice(0, 10).map((f, k) => `<li><button data-k="${k}"><span>${esc(f.label)}</span>
    <span class="where">${esc(f.where)}${f.m ? ` · ${fmt(f.m.n)} edificios` : ''}</span></button></li>`).join('')
    || '<li class="muted" style="padding:8px 12px">Aún no está. Pronto habrá más ciudades.</li>';
  hits.hidden = false;
  hits.onclick = e => {
    const b = e.target.closest('button');
    if (!b) return;
    const f = found[+b.dataset.k];
    hits.hidden = true; q.value = '';
    if (f.m) { preselect = new Set([f.m.code]); location.hash = f.c.key; }
    else if (f.c.municipios.length > 1) location.hash = f.c.key;
    else location.href = `${f.c.key}/`;
  };
};
q.onkeydown = e => { if (e.key === 'Enter') hits.querySelector('button')?.click(); if (e.key === 'Escape') hits.hidden = true; };
addEventListener('click', e => { if (!e.target.closest('.search, .hits')) hits.hidden = true; });

// ---------- Picker ----------
let city = null, chosen = new Set(), preselect = null, presetName = '';
const map = $('map'), list = $('list');
function openPicker(c) {
  city = c;
  chosen = preselect || new Set(c.presets.length ? c.presets[0].codes : [c.municipios[0].code]);
  preselect = null;
  presetName = !chosen.size ? '' : (c.presets.find(p => same(p.codes)) || {}).name || '';
  $('picker-title').textContent = c.name;
  $('picker-sub').textContent = `${c.sub} · ${c.municipios.length} municipios · ${fmt(c.buildings)} edificios`;
  map.setAttribute('viewBox', `0 0 ${c.view[0]} ${c.view[1]}`);
  map.innerHTML = c.municipios.map(m => `<path d="${m.d}" data-code="${m.code}"><title>${esc(m.name)}</title></path>`).join('');
  $('presets').innerHTML = c.presets.map((p, k) => `<button data-k="${k}">${esc(p.name)}</button>`).join('');
  $('filter').value = '';
  renderList();
  $('cities').hidden = true; document.querySelector('.hero').hidden = true; $('picker').hidden = false;
  scrollTo(0, 0);
  render();
}
function closePicker() {
  city = null;
  $('cities').hidden = false; document.querySelector('.hero').hidden = false; $('picker').hidden = true;
}
const same = codes => {
  const set = codes.length ? new Set(codes) : new Set(city.municipios.map(m => m.code));
  return set.size === chosen.size && [...set].every(c => chosen.has(c));
};
function renderList() {
  const s = plain($('filter').value.trim());
  list.innerHTML = city.municipios.filter(m => !s || plain(m.name).includes(s)).map(m => `<li><label>
    <input type="checkbox" data-code="${m.code}" ${chosen.has(m.code) ? 'checked' : ''}>
    <span>${esc(m.name)}</span><span class="n">${fmt(m.n)}</span></label></li>`).join('');
}
function render() {
  map.querySelectorAll('path').forEach(p => p.classList.toggle('on', chosen.has(p.dataset.code)));
  list.querySelectorAll('input').forEach(i => { i.checked = chosen.has(i.dataset.code); });
  const pre = city.presets.findIndex(p => same(p.codes));
  $('presets').querySelectorAll('button').forEach((b, k) => b.setAttribute('aria-pressed', String(k === pre)));
  presetName = pre >= 0 ? city.presets[pre].name : '';
  const n = city.municipios.filter(m => chosen.has(m.code)).reduce((s, m) => s + m.n, 0);
  const bytes = weight(city, chosen), [cls, txt] = grade(bytes);
  $('summary').innerHTML = chosen.size
    ? `<b>${chosen.size}</b> ${chosen.size === 1 ? 'municipio' : 'municipios'} · <b>${fmt(n)}</b> edificios · ≈ ${mb(bytes)}
       <span class="weight ${cls}">${txt}</span>`
    : 'Elige al menos un municipio.';
  const open = $('open');
  open.setAttribute('aria-disabled', String(!chosen.size));
  const all = chosen.size === city.municipios.length;
  const h = new URLSearchParams();
  if (!all) h.set('cargar', [...chosen].join(','));
  if (presetName && !all) h.set('titulo', presetName);
  open.href = `${city.key}/${h.toString() ? `#${h.toString().replace(/%2C/g, ',')}` : ''}`;
}
map.onclick = e => {
  const p = e.target.closest('path');
  if (!p) return;
  chosen.has(p.dataset.code) ? chosen.delete(p.dataset.code) : chosen.add(p.dataset.code);
  render();
};
map.onmousemove = e => {
  const p = e.target.closest('path');
  const m = p && city.municipios.find(m => m.code === p.dataset.code);
  $('map-tip').textContent = m ? `${m.name} · ${fmt(m.n)} edificios` : 'Toca un municipio en el mapa o en la lista.';
};
list.onchange = e => {
  const c = e.target.dataset.code;
  e.target.checked ? chosen.add(c) : chosen.delete(c);
  render();
};
$('presets').onclick = e => {
  const b = e.target.closest('button');
  if (!b) return;
  const p = city.presets[+b.dataset.k];
  chosen = new Set(p.codes.length ? p.codes : city.municipios.map(m => m.code));
  render();
};
$('filter').oninput = renderList;
$('none').onclick = () => { chosen = new Set(); render(); };
$('back').onclick = () => { location.hash = tag; };

// ---------- Route: #<city key> opens its picker, #grandes / #patrimonio / #costa filter the cards ----------
// a map's "Cambiar municipios" comes back as #<key>&cargar=code,code… (or * for all of them), ticked as it was
function route() {
  const [key, rest = ''] = location.hash.slice(1).split('&', 2);
  const c = cities.find(c => c.key === key);
  const back = new URLSearchParams(rest).get('cargar');
  if (c && back) {
    const codes = back === '*' ? c.municipios.map(m => m.code) : back.split(',').filter(k => c.municipios.some(m => m.code === k));
    if (codes.length) preselect = new Set(codes);
    history.replaceState(null, '', `#${c.key}`);
  }
  if (c && c.municipios.length > 1) openPicker(c);
  else { closePicker(); if (!c) setTag(TAGS.some(([h]) => h === key) ? key : ''); }
}
addEventListener('hashchange', route);
route();
