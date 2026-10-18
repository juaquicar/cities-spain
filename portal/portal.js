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

// ---------- Android app: offered everywhere but inside the app itself and on iPhone ----------
$('apk').hidden = /CiudadesApp|iPhone|iPad/.test(navigator.userAgent);

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
  document.querySelectorAll('#spain .dot').forEach(g => g.classList.toggle('off', !!t && !g.dataset.tags.split(' ').includes(t)));
  $('spain').relabel?.();
  $('cities').querySelectorAll('.ccaa').forEach(hd => {
    let el = hd.nextElementSibling, n = 0;
    for (; el && el.classList.contains('city'); el = el.nextElementSibling) n += !el.hidden;
    hd.hidden = !n;
    hd.querySelector('span').textContent = n;
  });
}
$('cities').onclick = e => {
  const b = e.target.closest('.city');
  if (b) openCity(cities.find(c => c.key === b.dataset.key));
};

// ---------- Map of Spain: a red dot per city, its area by the number of buildings ----------
// A city of many municipalities (the province of Sevilla) is its capital's dot plus a small one per municipality.
// Wheel, pinch or the buttons zoom; dragging pans once zoomed; dots and names keep their size on screen.
const spain = await fetch('spain.json').then(r => r.json()).catch(() => null);
const spainSvg = $('spain'), spainTip = $('spain-tip');
const TIP = spainTip.textContent;
const openCity = c => { if (c.municipios.length > 1) location.hash = c.key; else location.href = `${c.key}/`; };
if (spain && cities.some(c => c.pt)) {
  // the dots: one per single-municipality city; the capital and the other municipalities of the larger areas
  const dots = [];
  for (const c of cities.filter(c => c.pt)) {
    if (c.municipios.length === 1) { dots.push({ c, n: c.buildings, pt: c.pt, main: true }); continue; }
    const capital = c.municipios.reduce((a, m) => (m.n > a.n ? m : a));
    dots.push({ c, n: capital.n, pt: c.pt, main: true, m: capital });
    for (const m of c.municipios) if (m !== capital && m.pt) dots.push({ c, n: m.n, pt: m.pt, m });
  }
  const most = Math.max(...dots.map(d => d.n));
  const radius = d => (d.main ? 5 : 1.5) + 22 * Math.sqrt(d.n / most);
  dots.sort((a, b) => b.n - a.n);  // the big ones drawn first, so a small one on top of them can still be touched
  const [cx, cy, cw, ch] = spain.canarias;
  spainSvg.setAttribute('viewBox', `0 0 ${spain.w} ${spain.h}`);
  spainSvg.innerHTML = `<path class="near" d="${spain.context}"/>
    ${spain.ccaa.map(r => `<path class="ccaa-shape" d="${r.d}"/>`).join('')}
    <rect class="frame" x="${cx}" y="${cy}" width="${cw}" height="${ch}" rx="10"/>
    ${dots.map((d, k) => {
      const r = radius(d), label = d.main ? d.c.name : d.m.name;
      return `<g class="dot${d.main ? '' : ' muni'}" data-k="${k}"
        data-tags="${(d.c.tags || []).join(' ')}" transform="translate(${d.pt[0]} ${d.pt[1]})" ${d.main ? 'tabindex="0" role="link"' : ''}
        aria-label="${esc(label)}, ${fmt(d.n)} edificios"><circle r="${r.toFixed(2)}"/>
        <text>${esc(label)}</text></g>`;
    }).join('')}`;
  $('spain-fig').hidden = false;
  const dotOf = e => { const g = e.target.closest('.dot'); return g && dots[+g.dataset.k]; };
  const tipOf = d => d.main
    ? `<b>${esc(d.c.name)}</b> · ${fmt(d.c.buildings)} edificios · ${esc(d.c.sub)}`
    : `<b>${esc(d.m.name)}</b> · ${fmt(d.n)} edificios · ${esc(d.c.name)}`;
  let dragged = false;
  spainSvg.onclick = e => {
    if (dragged) return;
    const d = dotOf(e);
    if (!d) return;
    if (d.main) openCity(d.c);
    else { preselect = new Set([d.m.code]); location.hash = d.c.key; }
  };
  spainSvg.onkeydown = e => { if (e.key === 'Enter') spainSvg.onclick(e); };
  spainSvg.onmouseover = e => { const d = dotOf(e); spainTip.innerHTML = d ? tipOf(d) : TIP; };
  spainSvg.onmouseleave = () => { spainTip.textContent = TIP; };

  // ----- zoom and pan, by the viewBox -----
  const W = spain.w, H = spain.h, MAXK = 12;
  let k = 1, vx = 0, vy = 0;
  const groups = [...spainSvg.querySelectorAll('.dot')];

  // ----- names: biggest first, each beside its dot on the first free side, or not at all -----
  // Municipality names join from k >= 3. Boxes are in drawing units; a name may not cover another name or a city's dot.
  const texts = groups.map(g => g.querySelector('text'));
  let widths = [];
  const measure = () => { widths = texts.map(t => t.getComputedTextLength() + 4); };
  const SIDES = [['start', 1, 0], ['end', -1, 0], ['middle', 0, -1], ['middle', 0, 1]];
  function place(s) {
    const w = W / k, h = H / k, x0 = vx, y0 = vy, x1 = vx + w, y1 = vy + h;
    const shown = (d, g) => !g.classList.contains('off') && d.pt[0] > x0 && d.pt[0] < x1 && d.pt[1] > y0 && d.pt[1] < y1;
    const taken = [];
    const free = b => b[0] > x0 && b[2] < x1 && b[1] > y0 && b[3] < y1
      && !taken.some(t => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
    groups.forEach((g, i) => {
      const d = dots[i];
      if (d.main && shown(d, g)) {
        const r = radius(d) * s;
        taken.push([d.pt[0] - r, d.pt[1] - r, d.pt[0] + r, d.pt[1] + r]);
      }
    });
    const order = groups.map((g, i) => i).sort((a, b) => (dots[b].main - dots[a].main) || (dots[b].n - dots[a].n));
    for (const i of order) {
      const d = dots[i], g = groups[i], t = texts[i];
      let ok = false;
      if (shown(d, g) && (d.main || k >= 3)) {
        const fs = d.main ? 25 : 16, r = radius(d), tw = widths[i], gap = 5;
        for (const [anchor, sx, sy] of SIDES) {
          // the box and the baseline, in the dot's own units (scaled by s on screen)
          const bx = sx > 0 ? r + gap : sx < 0 ? -(r + gap) - tw : -tw / 2;
          const by = sy < 0 ? -(r + gap) - fs * .95 : sy > 0 ? r + gap : -fs * .5;
          const b = [d.pt[0] + bx * s, d.pt[1] + by * s, d.pt[0] + (bx + tw) * s, d.pt[1] + (by + fs * .95) * s];
          if (!free(b)) continue;
          taken.push(b);
          t.setAttribute('text-anchor', anchor);
          t.setAttribute('x', (sx > 0 ? r + gap : sx < 0 ? -(r + gap) : 0).toFixed(1));
          t.setAttribute('y', (by + fs * .74).toFixed(1));
          ok = true;
          break;
        }
      }
      g.classList.toggle('lab', ok);
    }
  }
  spainSvg.relabel = () => apply();
  function apply() {
    k = Math.min(MAXK, Math.max(1, k));
    const w = W / k, h = H / k;
    vx = Math.min(W - w, Math.max(0, vx)); vy = Math.min(H - h, Math.max(0, vy));
    spainSvg.setAttribute('viewBox', `${vx} ${vy} ${w} ${h}`);
    const s = 1 / Math.pow(k, 0.8);
    groups.forEach(g => { const d = dots[+g.dataset.k]; g.setAttribute('transform', `translate(${d.pt[0]} ${d.pt[1]}) scale(${s})`); });
    place(s);
    spainSvg.style.touchAction = k > 1 ? 'none' : 'pan-y';
    $('spain-reset').hidden = k === 1;
  }
  // zoom by f around a point given in client pixels
  function zoomAt(f, clientX, clientY) {
    const r = spainSvg.getBoundingClientRect();
    const px = vx + (clientX - r.left) / r.width * (W / k), py = vy + (clientY - r.top) / r.height * (H / k);
    const k2 = Math.min(MAXK, Math.max(1, k * f));
    vx = px - (px - vx) * k / k2; vy = py - (py - vy) * k / k2; k = k2;
    apply();
  }
  const centre = () => { const r = spainSvg.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  $('spain-in').onclick = () => zoomAt(1.8, ...centre());
  $('spain-out').onclick = () => zoomAt(1 / 1.8, ...centre());
  $('spain-reset').onclick = () => { k = 1; vx = vy = 0; apply(); };
  spainSvg.addEventListener('wheel', e => {
    e.preventDefault();
    zoomAt(Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0018)), e.clientX, e.clientY);
  }, { passive: false });
  const pts = new Map();
  let last = null;
  spainSvg.addEventListener('pointerdown', e => {
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    dragged = false; last = null;
  });
  spainSvg.addEventListener('pointermove', e => {
    if (!pts.has(e.pointerId)) return;
    const prev = pts.get(e.pointerId);
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    const r = spainSvg.getBoundingClientRect();
    if (pts.size === 2) {
      const [a, b] = [...pts.values()], dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (last) zoomAt(dist / last, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      last = dist; dragged = true;
    } else if (pts.size === 1 && k > 1) {
      const dx = e.clientX - prev[0], dy = e.clientY - prev[1];
      if (Math.abs(dx) + Math.abs(dy) > 0) {
        if (!dragged && Math.hypot(dx, dy) < 2) return;
        dragged = true;
        spainSvg.setPointerCapture?.(e.pointerId);
        vx -= dx / r.width * (W / k); vy -= dy / r.height * (H / k);
        apply();
      }
    }
  });
  const up = e => { pts.delete(e.pointerId); if (pts.size < 2) last = null; };
  spainSvg.addEventListener('pointerup', up);
  spainSvg.addEventListener('pointercancel', up);
  measure();
  apply();
  document.fonts?.ready.then(() => { measure(); apply(); });
}

// ---------- Cerca de mí: the city around you, opened with the camera ready (the viewer's "Ver con la cámara") ----------
// The municipalities within 6 km of the nearest centre load (a big one's centre can be far from its edge); 25 km at most.
const near = $('near'), nearMsg = $('near-msg');
near.hidden = !navigator.geolocation || !matchMedia('(pointer: coarse)').matches;
const kmTo = (a, b) => Math.hypot((a[0] - b[0]) * 111.3 * Math.cos(b[1] * Math.PI / 180), (a[1] - b[1]) * 111.3);
near.onclick = () => {
  nearMsg.hidden = false; nearMsg.textContent = 'Buscando dónde estás…';
  navigator.geolocation.getCurrentPosition(pos => {
    const me = [pos.coords.longitude, pos.coords.latitude], spots = [];
    for (const c of cities) {
      if (c.municipios.length > 1) { for (const m of c.municipios) if (m.ll) spots.push({ c, m, d: kmTo(m.ll, me) }); }
      else if (c.ll) spots.push({ c, d: kmTo(c.ll, me) });
    }
    spots.sort((a, b) => a.d - b.d);
    const best = spots[0];
    if (!best || best.d > 25) {
      nearMsg.textContent = best ? `No hay ninguna ciudad a mano: la más cercana es ${best.c.name}, a ${Math.round(best.d)} km.` : 'Sin ciudades.';
      return;
    }
    nearMsg.textContent = `Abriendo ${best.m ? best.m.name : best.c.name}…`;
    if (!best.m) { location.href = `${best.c.key}/#ar=1`; return; }
    const codes = spots.filter(s => s.c === best.c && s.m && s.d < best.d + 6).slice(0, 4).map(s => s.m.code);
    location.href = `${best.c.key}/#cargar=${codes.join(',')}&ar=1`;
  }, err => {
    nearMsg.textContent = err.code === 1 ? 'Hace falta permiso de ubicación.' : 'No se pudo saber dónde estás.';
  }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
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
