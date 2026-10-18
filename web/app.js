// Sevilla (Madrid, Barcelona…), edificio a edificio: a three.js city from the Catastro, coloured by age, use or floors,
// filtered by municipality. Data comes from pipeline/ (s03_tiles: packs + attrs.bin + city.json; s04_ground).
import * as THREE from './vendor/three.module.js';
import { MapControls } from './vendor/MapControls.js';

// The 3D colours of each theme (the page's colours are in styles.css): noche, a navy dusk; día, warm sand.
const THEMES = {
  noche: { sky: '#0e1522', land: '#223049', sel: '#2c3c5a', dim: '#162132', border: '#4a5f82', water: '#2b5f84',
    maquette: '#4a5468', future: '#26303f', tick: '#959cab', cursor: '#e7a73c', meta: '#0e1522' },
  dia: { sky: '#eee8dc', land: '#f7f2e8', sel: '#fffdf8', dim: '#e6dfd0', border: '#cfc2a8', water: '#a6c3c9',
    maquette: '#ebe5d8', future: '#ddd5c4', tick: '#6c6f78', cursor: '#c2552c', meta: '#eee8dc' },
};
let theme = THEMES[document.documentElement.dataset.theme] ? document.documentElement.dataset.theme : 'noche';
const C = () => THEMES[theme];
const SKY = C().sky, LAND = C().land, LAND_SEL = C().sel, LAND_DIM = C().dim, BORDER = C().border, WATER = C().water,
  MAQUETTE = C().maquette;
const ATTR_W = 256;
const WORKERS = Math.min(4, navigator.hardwareConcurrency || 2);
const MODE = { period: 0, use: 1, floors: 2, heritage: 3 };
const OLD = 1800; // years before this share a compressed strip at the left of the timeline

// A selection made before loading (the portal's #cargar=code,code…) fetches only those municipalities: their tiles,
// their parts of the table. Without it, everything.
const config = await fetch('data/city.json').then(r => r.json());
const REF_LEN = config.refLen || 14; // 17 in Bizkaia's foral cadastre
// the foral cadastres of the Basque Country keep their own references, viewers and credits
const FORAL = {
  bizkaia: { name: 'Catastro de Bizkaia', home: 'https://geo.bizkaia.eus/',
    credit: 'Catastro foral de Bizkaia, © Bizkaiko Foru Aldundia (INSPIRE Buildings).' },
  // ref = 7-digit parcel, a dash and the building's number; the viewer opens on the parcel
  gipuzkoa: { name: 'Catastro de Gipuzkoa', home: 'https://b5m.gipuzkoa.eus/',
    credit: 'Catastro foral de Gipuzkoa, CC BY-SA © Gipuzkoako Foru Aldundia (INSPIRE Buildings).',
    link: ref => `https://ssl6.gipuzkoa.net/Catastro/map.htm?id=69&RefCat=${encodeURIComponent(ref.split('-')[0])}&idioma=spa` },
}[config.cadastre] || null;
const want = (new URLSearchParams(location.hash.slice(1)).get('cargar') || '').split(',').filter(Boolean);
const chosen = config.municipios.filter(m => want.includes(m.code));
const PARTIAL = chosen.length > 0 && chosen.length < config.municipios.length;
const LOADED = new Set((PARTIAL ? chosen : config.municipios).map(m => m.id));
const N = config.stats.buildings, S = config.attrStride, F = config.attrFields;
// parts of the table: {file, start, end, munis}, or plain names in older builds (consecutive, all needed)
let at = 0;
const parts = (config.attrParts || ['attrs.bin']).map(p => typeof p === 'string' ? { file: p } : p)
  .filter(p => !PARTIAL || !p.munis || p.munis.some(id => LOADED.has(id)));
const attrBuf = new ArrayBuffer(N * S);
const [heritage, ground, tourism] = await Promise.all([
  fetch('data/monumentos.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
  fetch('data/ground.json').then(r => r.ok ? r.json() : { munis: [], water: [] }).catch(() => ({ munis: [], water: [] })),
  // the must-sees and walking routes (pipeline): optional, no file means no tourist mode
  fetch('data/turismo.json').then(r => r.ok ? r.json() : null).catch(() => null),
  ...parts.map(p => fetch(`data/${p.file}`).then(r => r.arrayBuffer()).then(buf => { p.buf = buf; })),
]);
const rowsLoaded = [];
for (const p of parts) {
  const start = p.start ?? at / S;
  new Uint8Array(attrBuf).set(new Uint8Array(p.buf), start * S);
  rowsLoaded.push([start, start + p.buf.byteLength / S]);
  at += p.buf.byteLength;
  delete p.buf;
}
const munis = config.municipios.filter(m => LOADED.has(m.id));
const periods = config.periods, uses = config.uses;
const muniById = Object.fromEntries(munis.map(m => [m.id, m]));
// the portal names a ready-made selection (#titulo=Aljarafe); otherwise a count of municipalities
const LABEL = new URLSearchParams(location.hash.slice(1)).get('titulo') ||
  (PARTIAL ? (munis.length === 1 ? munis[0].name : `${munis.length} municipios`) : config.label);
document.title = `${LABEL}, edificio a edificio`;
// where the heritage cards come from: the IAPH in Andalucía, Wikidata elsewhere (pipeline/region.py)
const IAPH = (config.heritage || 'iaph') === 'iaph', HSRC = IAPH ? 'IAPH' : 'Wikidata';
// haze starts further out when the whole area is wider than a city (a province)
const FOG = Math.max(1, config.home.span / 40000);
const fmt = n => n.toLocaleString('es-ES', { useGrouping: 'always' });

// ---------- Per-building table ----------
const dv = new DataView(attrBuf);
const B = {
  year: new Int16Array(N), muni: new Uint8Array(N), use: new Uint8Array(N), period: new Uint8Array(N),
  flag: new Uint8Array(N), floors: new Uint8Array(N), mon: new Uint8Array(N),
  ok: new Uint8Array(N), // loaded and in the selection; rows of other municipalities stay out of every count
};
for (const [a, z] of rowsLoaded) for (let i = a, o = a * S; i < z; i++, o += S) {
  B.muni[i] = dv.getUint8(o + F.muni);
  if (!LOADED.has(B.muni[i])) continue;
  B.ok[i] = 1;
  B.year[i] = dv.getInt16(o + F.year, true); B.use[i] = dv.getUint8(o + F.use);
  B.period[i] = dv.getUint8(o + F.period); B.flag[i] = dv.getUint8(o + F.flag); B.floors[i] = dv.getUint8(o + F.floors);
  B.mon[i] = dv.getUint8(o + F.mon);
}
// the legend's notes count the selection, not the whole build
const STATS = { rounded: 0, estimated: 0, redated: 0 };
for (let i = 0; i < N; i++) if (B.ok[i]) {
  if (B.flag[i] === 1) STATS.rounded++; else if (B.flag[i] === 2) STATS.estimated++; else if (B.flag[i] >= 3) STATS.redated++;
}
const ascii = new TextDecoder('ascii');
function building(i) {
  const o = i * S;
  return {
    i, ref: ascii.decode(new Uint8Array(attrBuf, o + F.ref, REF_LEN)).replace(/\0+$/, ''),
    muni: B.muni[i], use: B.use[i], flag: B.flag[i], floors: B.floors[i], below: dv.getUint8(o + F.below),
    period: B.period[i], year: B.year[i], dwell: dv.getUint16(o + F.dwell, true), h: dv.getUint16(o + F.h, true) / 10,
    area: dv.getUint32(o + F.area, true), x: dv.getFloat32(o + F.x, true), z: dv.getFloat32(o + F.z, true),
    lat: dv.getFloat32(o + F.lat, true), lon: dv.getFloat32(o + F.lon, true), ycat: dv.getInt16(o + F.ycat, true), base: dv.getFloat32(o + F.base, true), hsrc: dv.getUint8(o + F.hsrc),
    mon: heritage[i],
  };
}

// ---------- State ----------
const state = {
  mode: MODE.period, year: config.yearMax, muni: -1, only: false,
  periodMask: periods.map(() => 1), useMask: uses.map(() => 1),
};

// ---------- Scene ----------
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0); // the page's sky gradient shows through
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 10, 400000);
const controls = new MapControls(camera, canvas);
controls.enableDamping = true;
controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
controls.rotateSpeed = 0.6;
controls.maxPolarAngle = Math.PI * 0.47;
controls.minDistance = 60;
controls.maxDistance = Math.max(60000, config.home.span * 2);

function view(x, z, span, azimuth = 200, elevation = 40) {
  // a portrait screen sees less width at the same distance: step back so the area still fits
  const fit = Math.sqrt(Math.max(1, 1.3 * innerHeight / innerWidth));
  const az = THREE.MathUtils.degToRad(azimuth), el = THREE.MathUtils.degToRad(elevation), d = span * 0.9 * fit;
  const y = groundAt(x, z);
  return { target: new THREE.Vector3(x, y, z),
    position: new THREE.Vector3(x + d * Math.cos(el) * Math.sin(az), y + d * Math.sin(el), z + d * Math.cos(el) * Math.cos(az)) };
}
function jump(v) { controls.target.copy(v.target); camera.position.copy(v.position); controls.update(); }

// ---------- Ground: terrain, municipalities, water ----------
// The terrain is a heightfield (pipeline/s06_terreno.py) tinted by municipality; water and boundaries lie on it.
const terrain = await fetch('data/terrain.bin').then(r => r.ok ? r.arrayBuffer() : null).catch(() => null);
const T = terrain && (() => {
  const h = new DataView(terrain);
  const x0 = h.getFloat32(0, true), z0 = h.getFloat32(4, true), step = h.getFloat32(8, true);
  const nx = h.getUint32(12, true), nz = h.getUint32(16, true);
  return { x0, z0, step, nx, nz, h: new Int16Array(terrain, 20, nx * nz), muni: new Uint8Array(terrain, 20 + 2 * nx * nz, nx * nz) };
})();
// Ground level in metres at a local (x, z), bilinear on the grid.
function groundAt(x, z) {
  if (!T) return 0;
  const fx = Math.min(Math.max((x - T.x0) / T.step, 0), T.nx - 1.001), fz = Math.min(Math.max((z - T.z0) / T.step, 0), T.nz - 1.001);
  const i = Math.floor(fx), j = Math.floor(fz), u = fx - i, v = fz - j, k = j * T.nx + i;
  return ((T.h[k] * (1 - u) + T.h[k + 1] * u) * (1 - v) + (T.h[k + T.nx] * (1 - u) + T.h[k + T.nx + 1] * u) * v) / 10;
}
function shapeOf(rings) {
  const pts = r => { const a = []; for (let k = 0; k < r.length; k += 2) a.push(new THREE.Vector2(r[k], -r[k + 1])); return a; };
  const s = new THREE.Shape(pts(rings[0]));
  for (const h of rings.slice(1)) s.holes.push(new THREE.Path(pts(h)));
  return s;
}
function drapedGeo(polys, lift) {
  const g = new THREE.ShapeGeometry(polys.map(shapeOf));
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position;
  for (let k = 0; k < p.count; k++) p.setY(k, groundAt(p.getX(k), p.getZ(k)) + lift);
  return g;
}
const flat = new THREE.Group();
scene.add(flat);
const groundUniforms = {
  uMuni: { value: -1 }, uLand: { value: new THREE.Color(LAND) }, uSel: { value: new THREE.Color(LAND_SEL) },
  uDim: { value: new THREE.Color(LAND_DIM) }, uOut: { value: new THREE.Color(SKY) },
  uFogColor: { value: new THREE.Color(SKY) }, uFog: { value: new THREE.Vector2(9000 * FOG, 26000 * FOG) },
};
if (T) {
  const n = T.nx * T.nz, pos = new Float32Array(n * 3), mun = new Float32Array(n);
  for (let j = 0; j < T.nz; j++) for (let i = 0; i < T.nx; i++) {
    const k = j * T.nx + i;
    pos.set([T.x0 + i * T.step, T.h[k] / 10 - 0.6, T.z0 + j * T.step], k * 3);
    mun[k] = PARTIAL && T.muni[k] < 255 && !LOADED.has(T.muni[k]) ? 254 : T.muni[k];
  }
  const idx = new Uint32Array((T.nx - 1) * (T.nz - 1) * 6);
  let q = 0;
  for (let j = 0; j < T.nz - 1; j++) for (let i = 0; i < T.nx - 1; i++) {
    const a = j * T.nx + i, b = a + 1, c = a + T.nx, d = c + 1;
    idx.set([a, c, b, b, c, d], q); q += 6;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('muni', new THREE.BufferAttribute(mun, 1));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  flat.add(new THREE.Mesh(g, new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: groundUniforms,
    vertexShader: /* glsl */`
      in float muni;
      uniform float uMuni;
      uniform vec3 uLand, uSel, uDim, uOut;
      out vec3 vColor; out vec3 vWorld;
      void main() {
        vColor = muni > 254.5 ? uOut : muni > 253.5 ? uDim : uMuni < 0.0 ? uLand : abs(muni - uMuni) < 0.5 ? uSel : uDim;
        vec4 w = modelMatrix * vec4(position, 1.0);
        vWorld = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      uniform vec3 uFogColor; uniform vec2 uFog;
      in vec3 vColor; in vec3 vWorld;
      out vec4 outColor;
      void main() {
        vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
        // hillshade from the south-west, gentle: the Aljarafe scarp reads, the plain stays white
        float shade = 0.9 + 0.1 * dot(n, normalize(vec3(-0.5, 0.75, 0.55))) / 0.75;
        vec3 c = vColor * clamp(shade, 0.82, 1.03);
        c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, length(vWorld - cameraPosition)));
        outColor = vec4(c, 1.0);
      }`,
  })));
}
const borderMat = new THREE.LineBasicMaterial({ color: BORDER }), waterMat = new THREE.MeshBasicMaterial({ color: WATER, depthTest: false });
for (const m of ground.munis) for (const p of m.rings) {
  const r = p[0], pts = [];
  for (let k = 0; k < r.length; k += 2) pts.push(new THREE.Vector3(r[k], groundAt(r[k], r[k + 1]) + 2, r[k + 1]));
  flat.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), borderMat));
}
if (ground.water.length) {
  // Water lies over the terrain whatever the grid's averaging does at the banks.
  const water = new THREE.Mesh(drapedGeo(ground.water, 1), waterMat);
  water.renderOrder = 1;
  flat.add(water);
}

// ---------- Shaders ----------
const col = c => new THREE.Color(c);
const uniforms = {
  uYear: { value: config.yearMax },
  uMode: { value: MODE.period },
  uPalette: { value: periods.map(p => col(p.color)) },
  uPeriodMask: { value: state.periodMask },
  uUse: { value: uses.map(u => col(u.color)) },
  uUseMask: { value: state.useMask },
  uMuni: { value: -1 },
  uOnly: { value: 0 },
  uNow: { value: 0 },
  uRise: { value: 0.01 },
  uMaquette: { value: col(MAQUETTE) },
  uHover: { value: -1 },
  uSelected: { value: -1 },
  uFogColor: { value: col(SKY) },
  uFog: { value: new THREE.Vector2(9000 * FOG, 26000 * FOG) },
};

const VERT = /* glsl */`
  in float bld;
  uniform sampler2D uAttr;
  uniform float uYear, uMode, uHover, uSelected, uNow, uBorn, uRise, uMuni, uOnly;
  uniform vec3 uPalette[${periods.length}];
  uniform float uPeriodMask[${periods.length}];
  uniform vec3 uUse[${uses.length}];
  uniform float uUseMask[${uses.length}];
  uniform vec3 uMaquette;
  out vec3 vColor;
  out vec3 vWorld;
  out float vGid;
  out float vUp;

  vec3 floorsRamp(float f) {
    float t = clamp(log(max(f, 1.0)) / log(25.0), 0.0, 1.0);
    vec3 a = vec3(0.93, 0.87, 0.74), b = vec3(0.89, 0.62, 0.30), c = vec3(0.66, 0.20, 0.18), d = vec3(0.24, 0.07, 0.13);
    return t < 0.33 ? mix(a, b, t / 0.33) : t < 0.66 ? mix(b, c, (t - 0.33) / 0.33) : mix(c, d, (t - 0.66) / 0.34);
  }

  void main() {
    int i = int(bld + 0.5);
    ivec2 tc = ivec2(2 * (i % ${ATTR_W}), i / ${ATTR_W});
    vec4 a = texelFetch(uAttr, tc, 0);
    vec4 m = texelFetch(uAttr, tc + ivec2(1, 0), 0);
    float year = a.x;
    int pf = int(a.y + 0.5);
    int period = pf % 16;
    int flag = pf / 16;
    int use = int(m.y + 0.5);
    vGid = a.w;
    bool other = uMuni >= 0.0 && abs(m.x - uMuni) > 0.5;
    float vis = (uMode < 0.5 || uMode > 2.5) ? uPeriodMask[period] : uMode < 1.5 ? uUseMask[use] : 1.0;
    if (other && uOnly > 0.5) vis = 0.0;
    bool mon = m.z > 0.5;
    float g = clamp((uYear - year + 1.0) / uRise, 0.0, 1.0);
    if (g <= 0.003 || vis <= 0.003) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }

    // Tiles drop in from the sky as they load, each building from its own side.
    vec3 p = position;
    float seed = fract(sin(a.w * 12.9898) * 43758.5453);
    float fly = 1.0 - clamp((uNow - uBorn) / 0.9 - seed * 0.35, 0.0, 1.0);
    if (fly > 0.0) {
      float e = fly * fly * fly;
      float ang = seed * 6.2831853;
      p += vec3(cos(ang), 0.0, sin(ang)) * (1800.0 + 1600.0 * fract(seed * 7.13)) * e;
      p.y += (2600.0 + 2400.0 * fract(seed * 3.71)) * e;
    }
    vec3 c;
    if (uMode < 0.5 || uMode > 2.5) {
      c = uPalette[period];
      if (flag == 1 || flag == 2 || flag == 4) c = mix(c, uMaquette, 0.45);
      if (uMode > 2.5 && !mon) c = uMaquette;
    } else if (uMode < 1.5) {
      c = uUse[use];
    } else {
      c = floorsRamp(a.z);
    }
    if (other) c = mix(c, uMaquette, 0.85);
    if (vGid == uHover || vGid == uSelected) c = mix(c, vec3(0.0), 0.35);
    vColor = c;
    vUp = (p.y - m.w) / 10.0;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const FRAG = /* glsl */`
  precision highp float;
  uniform vec3 uFogColor;
  uniform vec2 uFog;
  in vec3 vColor;
  in vec3 vWorld;
  in float vGid;
  in float vUp;
  out vec4 outColor;
  void main() {
    #ifdef PICK
      float id = vGid + 1.0;
      outColor = vec4(mod(id, 256.0), mod(floor(id / 256.0), 256.0), floor(id / 65536.0), 255.0) / 255.0;
    #else
      vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
      // Andalusian afternoon: a high sun from the south-west, a soft sky from above.
      float sun = max(dot(n, normalize(vec3(-0.5, 0.75, 0.55))), 0.0);
      float light = n.y > 0.9 ? 1.04 : 0.64 + 0.36 * sun;
      float foot = mix(0.84, 1.0, clamp(vUp / 12.0, 0.0, 1.0));
      vec3 c = vColor * light * foot;
      float d = length(vWorld - cameraPosition);
      c = mix(c, uFogColor, smoothstep(uFog.x, uFog.y, d));
      outColor = vec4(c, 1.0);
    #endif
  }
`;

function makeMaterial(tex, pick, born) {
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { ...uniforms, uAttr: { value: tex }, uBorn: born },
    vertexShader: VERT, fragmentShader: FRAG,
    defines: pick ? { PICK: 1 } : {},
    side: THREE.DoubleSide,
  });
}

// ---------- Tiles ----------
const meshes = [];
let loaded = 0;
const queue = config.tiles.filter(t => t.muni === undefined || LOADED.has(t.muni));
const pool = Array.from({ length: WORKERS }, () => new Worker('worker.js', { type: 'module' }));
function addTile(m) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(m.pos, 3));
  g.setAttribute('bld', new THREE.BufferAttribute(m.bld, 1));
  g.setIndex(new THREE.BufferAttribute(m.idx, 1));
  const rows = Math.ceil(m.nB / ATTR_W);
  const data = new Float32Array(ATTR_W * 2 * rows * 4);
  data.set(m.attr);
  const tex = new THREE.DataTexture(data, ATTR_W * 2, rows, THREE.RGBAFormat, THREE.FloatType);
  tex.needsUpdate = true;
  const born = { value: performance.now() / 1000 };
  const mesh = new THREE.Mesh(g, makeMaterial(tex, false, born));
  mesh.userData = { draw: mesh.material, pick: makeMaterial(tex, true, born) };
  mesh.scale.setScalar(0.1);
  mesh.position.set(m.origin[0], 0, m.origin[1]);
  mesh.frustumCulled = false;
  scene.add(mesh);
  meshes.push(mesh);
}
const TILES = queue.length;
const packs = Object.fromEntries([...new Set(queue.map(t => t.pack))].map(name => [name, fetch(`data/${name}`).then(r => r.arrayBuffer())]));
for (const w of pool) {
  const next = async () => {
    const t = queue.shift();
    if (!t) return;
    const buf = (await packs[t.pack]).slice(t.offset, t.offset + t.length);
    w.postMessage({ buf, id: t.file }, [buf]);
  };
  w.onmessage = ({ data }) => {
    addTile(data);
    loaded++;
    document.getElementById('progress').textContent = Math.round(100 * loaded / TILES);
    if (loaded === TILES) document.getElementById('loading').hidden = true;
    next();
  };
  next();
}

// ---------- Picking ----------
const pickTarget = new THREE.WebGLRenderTarget(1, 1);
const pickPixel = new Uint8Array(4);
function pick(x, y) {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  camera.setViewOffset(w, h, x, y, 1, 1);
  for (const m of meshes) m.material = m.userData.pick;
  flat.visible = false;
  renderer.setRenderTarget(pickTarget);
  renderer.setClearColor(0x000000, 0);
  renderer.clear();
  renderer.render(scene, camera);
  renderer.readRenderTargetPixels(pickTarget, 0, 0, 1, 1, pickPixel);
  renderer.setRenderTarget(null);
  flat.visible = true;
  for (const m of meshes) m.material = m.userData.draw;
  camera.clearViewOffset();
  return pickPixel[0] + pickPixel[1] * 256 + pickPixel[2] * 65536 - 1;
}

// ---------- Filters and counts ----------
const inMuni = i => state.muni < 0 || B.muni[i] === state.muni;
function visible(i) {
  if (state.only && !inMuni(i)) return false;
  if ((state.mode === MODE.period || state.mode === MODE.heritage) && !state.periodMask[B.period[i]]) return false;
  if (state.mode === MODE.use && !state.useMask[B.use[i]]) return false;
  return true;
}
function counts() {
  const byPeriod = periods.map(() => 0), byUse = uses.map(() => 0), byFloors = new Array(26).fill(0);
  const monByPeriod = periods.map(() => 0);
  let bic = 0;
  const hist = new Map();
  let shown = 0, total = 0;
  for (let i = 0; i < N; i++) {
    if (!B.ok[i] || !inMuni(i)) continue;
    total++;
    byPeriod[B.period[i]]++; byUse[B.use[i]]++; byFloors[Math.min(B.floors[i], 25)]++;
    if (B.mon[i]) { monByPeriod[B.period[i]]++; if (heritage[i]?.pr === 'BIC') bic++; }
    if (!visible(i)) continue;
    if (state.mode === MODE.heritage && !B.mon[i]) continue;
    const y = B.year[i];
    const k = y < OLD ? Math.floor(y / 50) * 50 : y;
    let h = hist.get(k);
    if (!h) hist.set(k, h = new Uint32Array(periods.length));
    h[B.period[i]]++;
    if (y <= state.year) shown++;
  }
  return { byPeriod, monByPeriod, bic, byUse, byFloors, hist, shown, total };
}

// ---------- Panel ----------
const panel = document.getElementById('panel-body');
// On a phone the legend is a sheet folded to its title; a tap opens it.
const panelBox = document.getElementById('panel'), panelToggle = panelBox.querySelector('.panel-toggle');
const narrow = matchMedia('(max-width: 760px)');
function foldPanel(open) {
  panelBox.classList.toggle('open', open);
  panelToggle.setAttribute('aria-expanded', String(open));
}
panelToggle.onclick = () => foldPanel(!panelBox.classList.contains('open'));
foldPanel(!narrow.matches);
function renderPanel(c) {
  if (state.mode === MODE.period || state.mode === MODE.heritage) {
    const herit = state.mode === MODE.heritage, n = herit ? c.monByPeriod : c.byPeriod;
    panel.innerHTML = `<h2>${herit ? 'Patrimonio catalogado' : 'Época de construcción'}</h2><ul>${periods.map((p, k) => herit && !n[k] ? '' : `
      <li><button data-k="${k}" aria-pressed="${!!state.periodMask[k]}">
        <i class="swatch" style="background:${p.color}"></i>
        <span>${p.label}<br><span class="years">${p.from < 1000 ? `antes de ${p.to + 1}` : `${p.from}–${p.to > 2050 ? 'hoy' : p.to}`}</span></span>
        <span class="n">${fmt(n[k])}</span></button></li>`).join('')}</ul>
      ${herit ? `<p class="note">${fmt(n.reduce((a, b) => a + b, 0))} edificios con ficha ${IAPH ? `del Instituto Andaluz del Patrimonio
        Histórico` : 'en Wikidata'}, ${fmt(c.bic)} de ellos Bien de Interés Cultural. Fechados por su construcción, no por la última reforma.</p>`
      : `<p class="note">Más pálidos: año aproximado, redondeado en el Catastro (${fmt(STATS.rounded)}) o estimado a partir de los vecinos (${fmt(STATS.estimated)}).
        ${STATS.redated ? `Los ${fmt(STATS.redated)} edificios catalogados llevan la fecha ${IAPH ? 'del IAPH' : 'de Wikidata'}.` : ''}</p>`}`;
    panel.querySelectorAll('button').forEach(b => b.onclick = () => {
      state.periodMask[+b.dataset.k] ^= 1; update();
    });
  } else if (state.mode === MODE.use) {
    panel.innerHTML = `<h2>Uso principal</h2><ul>${uses.map((u, k) => c.byUse[k] ? `
      <li><button data-k="${k}" aria-pressed="${!!state.useMask[k]}">
        <i class="swatch" style="background:${u.color}"></i><span>${u.label}</span>
        <span class="n">${fmt(c.byUse[k])}</span></button></li>` : '').join('')}</ul>`;
    panel.querySelectorAll('button').forEach(b => b.onclick = () => {
      state.useMask[+b.dataset.k] ^= 1; update();
    });
  } else {
    const max = c.byFloors.reduce((m, n, k) => n ? k : m, 1);
    panel.innerHTML = `<h2>Plantas sobre rasante</h2>
      <div class="ramp" style="background:linear-gradient(90deg,#eddebc,#e39e4c,#a8332e,#3d1221)"></div>
      <div class="ramp-labels"><span>1</span><span>5</span><span>${max}${max >= 25 ? '+' : ''}</span></div>
      <p class="note">Altura dibujada: 3 m por planta más pretil. ${fmt(c.byFloors.slice(10).reduce((a, b) => a + b, 0))} edificios de 10 o más plantas.</p>`;
  }
}

// ---------- Timeline ----------
// A few dates that shaped each city, marked above the histogram (desktop only).
const MILESTONES = {
  sevilla: [[1755, 'Terremoto de Lisboa'], [1929, 'Exposición Iberoamericana'], [1961, 'Riada del Tamarguillo'],
    [1992, 'Expo 92'], [2008, 'Fin de la burbuja']],
  madrid: [[1860, 'Ensanche de Castro'], [1919, 'Primer metro'], [1936, 'Guerra civil'], [1975, 'Transición'],
    [2008, 'Fin de la burbuja']],
  barcelona: [[1859, 'Plan Cerdà'], [1888, 'Exposición Universal'], [1929, 'Exposición Internacional'],
    [1992, 'Juegos Olímpicos'], [2008, 'Fin de la burbuja']],
  valencia: [[1865, 'Derribo de la muralla'], [1909, 'Exposición Regional'], [1957, 'Riada'],
    [1998, 'Ciudad de las Ciencias']],
  salamanca: [[1729, 'Plaza Mayor'], [1988, 'Patrimonio de la Humanidad']],
  zaragoza: [[1808, 'Los Sitios'], [1908, 'Exposición Hispano-Francesa'], [2008, 'Expo 2008']],
  bilbao: [[1300, 'Fundación de la villa'], [1876, 'Ensanche'], [1983, 'Riada'], [1997, 'Museo Guggenheim']],
  malaga: [[1487, 'Conquista castellana'], [1891, 'Calle Larios'], [1959, 'Boom turístico'], [2003, 'Museo Picasso']],
  murcia: [[1394, 'Catedral'], [1879, 'Riada de Santa Teresa'], [2008, 'Fin de la burbuja']],
  palma: [[1229, 'Conquista de Jaime I'], [1902, 'Derribo de las murallas'], [1943, 'Plan Alomar'], [1960, 'Boom turístico']],
  'las-palmas': [[1478, 'Fundación'], [1883, 'Puerto de La Luz'], [1960, 'Boom turístico']],
  alicante: [[1858, 'Ferrocarril de Madrid'], [1938, 'Bombardeo del Mercado'], [1960, 'Boom turístico']],
  granada: [[1492, 'Toma de Granada'], [1895, 'Gran Vía de Colón'], [1984, 'Alhambra, Patrimonio de la Humanidad']],
  benidorm: [[1956, 'Plan General'], [2002, 'Gran Hotel Bali']],
  'san-sebastian': [[1813, 'Incendio de la ciudad'], [1864, 'Ensanche Cortázar'], [1999, 'Kursaal']],
  cordoba: [[1523, 'Catedral en la Mezquita'], [1859, 'Ferrocarril'], [1984, 'Patrimonio de la Humanidad']],
  toledo: [[1561, 'La corte se va a Madrid'], [1936, 'Asedio del Alcázar'], [1986, 'Patrimonio de la Humanidad']],
  santiago: [[1075, 'Catedral románica'], [1985, 'Patrimonio de la Humanidad'], [2011, 'Cidade da Cultura']],
  segovia: [[1474, 'Proclamación de Isabel I'], [1862, 'Incendio del Alcázar'], [1985, 'Patrimonio de la Humanidad']],
  merida: [[1910, 'Excavación del Teatro'], [1993, 'Patrimonio de la Humanidad']],
  avila: [[1090, 'Muralla'], [1985, 'Patrimonio de la Humanidad']],
  'alcala-de-henares': [[1499, 'Universidad de Cisneros'], [1977, 'Universidad refundada'], [1998, 'Patrimonio de la Humanidad']],
  baeza: [[1538, 'Universidad'], [2003, 'Patrimonio de la Humanidad']],
  caceres: [[1229, 'Conquista de Alfonso IX'], [1986, 'Patrimonio de la Humanidad']],
  cuenca: [[1177, 'Conquista de Alfonso VIII'], [1966, 'Museo de Arte Abstracto'], [1996, 'Patrimonio de la Humanidad']],
  ibiza: [[1554, 'Murallas renacentistas'], [1958, 'Aeropuerto'], [1999, 'Patrimonio de la Humanidad']],
  'la-laguna': [[1496, 'Fundación'], [1913, 'Catedral'], [1999, 'Patrimonio de la Humanidad']],
  tarragona: [[1171, 'Catedral'], [2000, 'Patrimonio de la Humanidad']],
  ubeda: [[1536, 'Capilla del Salvador'], [2003, 'Patrimonio de la Humanidad']],
}[config.city] || [];
const hist = document.getElementById('hist'), hctx = hist.getContext('2d');
const yMin = config.yearMin < OLD ? config.yearMin : Math.floor(config.yearMin / 10) * 10, yMax = config.yearMax;
const OLD_W = config.yearMin < OLD ? 0.12 : 0;
const NEW = Math.max(OLD, yMin); // first year of the linear part
const xOf = y => y < NEW ? OLD_W * (y - yMin) / Math.max(1, NEW - yMin) : OLD_W + (1 - OLD_W) * (y - NEW) / (yMax - NEW + 1);
const yearAt = f => f < OLD_W ? Math.round(yMin + (f / OLD_W) * (NEW - yMin)) : Math.round(NEW + (f - OLD_W) / (1 - OLD_W) * (yMax - NEW + 1));
let lastCounts = null;
function drawHist(c) {
  const dpr = Math.min(devicePixelRatio, 2), W = hist.clientWidth, H = hist.clientHeight;
  hist.width = W * dpr; hist.height = H * dpr;
  hctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  hctx.clearRect(0, 0, W, H);
  let peak = 1;
  for (const [k, h] of c.hist) { const s = h.reduce((a, b) => a + b, 0) / (k < OLD ? 50 : 1); if (k >= OLD) peak = Math.max(peak, s); }
  const top = H - 16;
  for (const [k, h] of c.hist) {
    const x0 = xOf(k) * W, x1 = Math.max(x0 + 1, xOf(k < OLD ? k + 50 : k + 1) * W);
    let y = top;
    for (let p = 0; p < h.length; p++) {
      if (!h[p]) continue;
      const hh = Math.max(0.5, Math.sqrt(h[p] / peak) * (top - (W >= 760 ? 16 : 4)) * (k < OLD ? 0.5 : 1));
      hctx.fillStyle = k > state.year ? C().future : periods[p].color;
      hctx.fillRect(x0, y - hh, x1 - x0 - (x1 - x0 > 3 ? 0.5 : 0), hh);
      y -= hh;
    }
  }
  hctx.fillStyle = C().tick; hctx.font = '600 11px "Manrope", sans-serif';
  hctx.textAlign = 'center';
  const ticks = W < 560 ? [1900, 1950, 1992, 2026] : [1900, 1929, 1950, 1975, 1992, 2008, 2026];
  if (OLD_W && W >= 560) ticks.unshift(OLD);
  for (const y of ticks) if (y >= yMin && y <= yMax) hctx.fillText(y, Math.min(W - 14, Math.max(14, xOf(y) * W)), H - 2);
  if (OLD_W) { hctx.textAlign = 'left'; hctx.fillText('antes', 0, H - 2); }
  if (W >= 760) {
    hctx.font = '600 10.5px "Manrope", sans-serif'; hctx.textAlign = 'left';
    for (const [y, label] of MILESTONES) {
      if (y < yMin || y > yMax) continue;
      const x = xOf(y) * W;
      hctx.fillStyle = C().tick; hctx.globalAlpha = 0.55; hctx.fillRect(x, 2, 1, top - 2); hctx.globalAlpha = 1;
      hctx.fillStyle = y <= state.year ? C().cursor : C().tick;
      hctx.fillText(label, Math.min(x + 4, W - hctx.measureText(label).width - 2), 10);
    }
  }
  const xs = xOf(state.year + 1) * W;
  hctx.fillStyle = C().cursor; hctx.fillRect(Math.min(W - 2, xs), 0, 2, top);
}
function scrub(e) {
  const r = hist.getBoundingClientRect();
  setYear(Math.max(yMin, Math.min(yMax, yearAt((e.clientX - r.left) / r.width))));
}
hist.addEventListener('pointerdown', e => { stopPlay(); hist.setPointerCapture(e.pointerId); scrub(e); });
hist.addEventListener('pointermove', e => { if (hist.hasPointerCapture(e.pointerId)) scrub(e); });

function setYear(y) {
  state.year = y;
  uniforms.uYear.value = y;
  update(false);
}

let playing = null;
const playIcon = document.getElementById('play-icon');
function stopPlay() { playing = null; uniforms.uRise.value = 0.01; playIcon.setAttribute('d', 'M4 2.5v11l9-5.5z'); }
document.getElementById('play').onclick = () => {
  if (playing) return stopPlay();
  const from = Math.max(yMin, 1850);
  playing = { t0: performance.now(), from };
  uniforms.uRise.value = 3;
  playIcon.setAttribute('d', 'M4 3h3v10H4zM9 3h3v10H9z');
};
function stepPlay(now) {
  if (!playing) return;
  const y = Math.round(playing.from + (now - playing.t0) / 1000 * 12);
  if (y >= yMax) { setYear(yMax); stopPlay(); } else if (y !== state.year) setYear(y);
}

// ---------- Update ----------
const yearEl = document.getElementById('year'), countEl = document.getElementById('count');
function update(full = true) {
  uniforms.uMode.value = state.mode;
  uniforms.uMuni.value = state.muni;
  uniforms.uOnly.value = state.only ? 1 : 0;
  const c = counts();
  lastCounts = c;
  if (full) renderPanel(c);
  drawHist(c);
  yearEl.textContent = state.year >= yMax ? 'Hoy' : state.year;
  countEl.textContent = fmt(c.shown);
  groundUniforms.uMuni.value = state.muni;
  writeHash();
}

// ---------- Municipality filter ----------
const select = document.getElementById('muni'), only = document.getElementById('only');
const title = document.getElementById('title');
select.innerHTML = (munis.length > 1 ? `<option value="-1">${PARTIAL ? 'Toda la selección' : 'Todos los municipios'} (${fmt(munis.reduce((s, m) => s + m.n, 0))})</option>` : '') +
  munis.map(m => `<option value="${m.id}">${m.name} (${fmt(m.n)})</option>`).join('');
function setMuni(id, fly = true) {
  state.muni = munis.length > 1 ? id : -1;
  select.value = String(munis.length > 1 ? id : munis[0].id);
  const m = muniById[id];
  title.textContent = m ? m.name : LABEL;
  title.classList.toggle('long', title.textContent.length > 16);
  only.parentElement.hidden = munis.length < 2 || id < 0;
  select.parentElement.hidden = munis.length < 2;
  if (fly) {
    if (m) flyTo(view(m.cx, m.cz, Math.min(Math.max(m.span, 1200), 16000)));
    else flyTo(view(HOME.x, HOME.z, HOME.span));
  }
  update();
}
select.onchange = () => setMuni(+select.value);
only.onchange = () => { state.only = only.checked; update(); };

// ---------- Modes ----------
const modeButtons = document.querySelectorAll('.modes [data-mode]');
function setMode(m) {
  state.mode = m;
  modeButtons.forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.mode === m)));
  update();
}
modeButtons.forEach(b => b.onclick = () => setMode(+b.dataset.mode));

const about = document.getElementById('about');
document.querySelector('.about-open').onclick = () => about.showModal();
about.querySelector('.about-close').onclick = () => about.close();
if (FORAL) document.getElementById('src-cadastre').textContent = 'Edificios, partes, plantas, año, uso y viviendas: '
  + FORAL.credit;

// ---------- Fly ----------
let flight = null;
function flyTo(v, ms = 1400) {
  flight = { t0: performance.now(), ms, from: { target: controls.target.clone(), position: camera.position.clone() }, to: v };
}
function stepFlight(now) {
  if (!flight) return;
  const t = Math.min(1, (now - flight.t0) / flight.ms), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  controls.target.lerpVectors(flight.from.target, flight.to.target, e);
  camera.position.lerpVectors(flight.from.position, flight.to.position, e);
  if (t >= 1) flight = null;
}
controls.addEventListener('start', () => { flight = null; });

// ---------- Card ----------
const card = document.getElementById('card');
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const periodOf = k => periods[k] || periods[0];
function cardHtml(i, pinned) {
  const b = building(i), p = periodOf(b.period), u = uses[b.use] || uses[0];
  // a heritage record, a must-see, or both (the record's fields win)
  const h = b.mon || SEE_BY_G.get(i) ? { ...SEE_BY_G.get(i), ...b.mon } : null;
  const stop = pinned && walk ? walk.stops.findIndex(s => s.g === i) : -1;
  // on a walk the stop's own name ("Catedral y Giralda"), elsewhere the heritage record's
  const name = stop >= 0 ? walk.stops[stop].n || h?.n : h?.n;
  const year = h?.y0 != null && b.flag >= 3 && h.y1 && h.y1 !== h.y0 ? `${h.y0}–${h.y1}` : (b.flag && b.flag !== 3 ? `c. ${b.year}` : b.year);
  const rows = [
    ['Municipio', muniById[b.muni]?.name ?? ''],
    ['Uso', u.label],
    ['Plantas', b.floors + (b.below ? ` + ${b.below} bajo rasante` : '')],
    b.hsrc ? ['Altura (LiDAR)', `${Math.round(b.h)} m`] : ['Altura aprox.', `${Math.round(b.h)} m`],
    ['Cota del suelo', `${Math.round(b.base)} m`],
    b.dwell ? ['Viviendas', fmt(b.dwell)] : null,
    b.area ? ['Superficie', `${fmt(b.area)} m²`] : null,
    h?.st ? ['Estilo', h.st] : null,
    h?.pr ? ['Protección', h.pr === 'BIC' ? 'Bien de Interés Cultural' : h.pr] : null,
    b.flag >= 3 && b.ycat !== b.year ? ['Año en Catastro', `${b.ycat} (reforma)`] : null,
    ['Ref. catastral', b.ref],
  ].filter(Boolean);
  const img = photo(h?.img);
  const ll = `${b.lat.toFixed(6)},${b.lon.toFixed(6)}`;
  return `${pinned ? '<button class="close" aria-label="Cerrar">×</button>' : ''}
    ${stop >= 0 ? stopHtml(stop) : ''}
    ${img}${name ? `<p class="name">${esc(name)}</p>` : ''}${h?.d ? `<p class="desc">${esc(h.d)}</p>` : ''}
    ${pinned && h?.wp ? '<p class="summary" aria-live="polite"></p>' : ''}
    <h3>${year}</h3>
    <p class="era"><i style="background:${p.color}"></i>${p.label}${['', ' · año redondeado', ' · año estimado', ` · fecha ${HSRC}`, ` · periodo ${HSRC}`][b.flag] || ''}</p>
    <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    ${pinned ? `<p class="links">
      ${FORAL ? `<a href="${FORAL.link ? FORAL.link(b.ref) : FORAL.home}" target="_blank" rel="noopener">${FORAL.name}</a>`
        : `<a href="https://www1.sedecatastro.gob.es/Cartografia/mapa.aspx?refcat=${encodeURIComponent(b.ref)}" target="_blank" rel="noopener">Catastro</a>`}
      <a href="https://www.google.com/maps/dir/?api=1&travelmode=walking&destination=${ll}" target="_blank" rel="noopener">Cómo llegar</a>
      <a href="https://www.google.com/maps/search/?api=1&query=${ll}" target="_blank" rel="noopener">Mapa</a>
      <a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${ll}" target="_blank" rel="noopener">Street View</a>
      ${h?.iaph ? `<a href="https://guiadigital.iaph.es/bien/inmueble/${h.iaph}" target="_blank" rel="noopener">IAPH</a>` : ''}
      ${h?.wd ? `<a href="https://www.wikidata.org/wiki/${encodeURIComponent(h.wd)}" target="_blank" rel="noopener">Wikidata</a>` : ''}
      ${h?.wp ? `<a href="${esc(h.wp)}" target="_blank" rel="noopener">Wikipedia</a>` : ''}
    </p>${h?.img ? '<p class="credit">Foto: Wikimedia Commons</p>' : ''}` : ''}`;
}
// Commons file names come plain from monumentos.json and sometimes already escaped from turismo.json
const unescape = f => { try { return decodeURIComponent(f); } catch (e) { return f; } };
const photo = file => file ? `<img class="photo" alt="" loading="lazy" src="https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(unescape(file))}?width=560">` : '';
// a square, a park, a bridge or a gate: no building under it, so only its name, picture and article
function spotHtml(p) {
  const stop = walk ? walk.stops.indexOf(p) : -1, ll = latlon(p);
  return `<button class="close" aria-label="Cerrar">×</button>
    ${stop >= 0 ? stopHtml(stop) : ''}${photo(p.img)}
    <h3 class="spot">${esc(p.n)}</h3>${p.d ? `<p class="desc">${esc(p.d)}</p>` : ''}
    ${p.wp ? '<p class="summary" aria-live="polite"></p>' : ''}
    <p class="links">
      <a href="https://www.google.com/maps/dir/?api=1&travelmode=walking&destination=${ll}" target="_blank" rel="noopener">Cómo llegar</a>
      <a href="https://www.google.com/maps/search/?api=1&query=${ll}" target="_blank" rel="noopener">Mapa</a>
      <a href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${ll}" target="_blank" rel="noopener">Street View</a>
      ${p.wd ? `<a href="https://www.wikidata.org/wiki/${encodeURIComponent(p.wd)}" target="_blank" rel="noopener">Wikidata</a>` : ''}
      ${p.wp ? `<a href="${esc(p.wp)}" target="_blank" rel="noopener">Wikipedia</a>` : ''}
    </p>${p.img ? '<p class="credit">Foto: Wikimedia Commons</p>' : ''}`;
}
// pinned: the building's row, -1 for none, PLACE while the card is a place's (pinnedSpot)
const PLACE = -2;
let hoverGid = -1, pinned = -1, pinnedSpot = null, pinSeq = 0;
function placeCard(x, y) {
  const w = card.offsetWidth, h = card.offsetHeight;
  card.style.left = `${Math.min(innerWidth - w - 12, x + 16)}px`;
  card.style.top = `${Math.max(12, Math.min(innerHeight - h - 12, y - h / 2))}px`;
}
function showCard(i, x, y) {
  if (pinned !== -1) return;
  if (i < 0) { card.hidden = true; return; }
  card.className = 'card';
  card.innerHTML = cardHtml(i, false);
  card.hidden = false;
  placeCard(x, y);
}
function pinCard(i, x, y, spot = null) {
  pinned = spot ? PLACE : i; pinnedSpot = spot;
  uniforms.uSelected.value = spot ? -1 : i;
  const seq = ++pinSeq;
  if (pinned === -1) { card.hidden = true; return; }
  card.className = 'card pinned';
  if (narrow.matches) foldPanel(false);
  card.innerHTML = spot ? spotHtml(spot) : cardHtml(i, true);
  card.hidden = false;
  placeCard(x, y);
  card.querySelector('.close').onclick = () => { if (walk) endWalk(); pinCard(-1); };
  card.querySelector('.stop')?.addEventListener('click', e => {
    const b = e.target.closest('[data-go]');
    if (b) b.dataset.go === 'fin' ? (endWalk(), pinCard(-1)) : goStop(walk.k + +b.dataset.go);
  });
  const sum = card.querySelector('.summary'), wp = spot ? spot.wp : { ...SEE_BY_G.get(i), ...heritage[i] }.wp;
  if (sum && wp) summary(wp).then(t => {
    if (seq !== pinSeq || !t) { sum.remove(); return; }
    sum.textContent = t;
    if (!narrow.matches) placeCard(x, y);
  });
}
// two or three sentences of the Wikipedia article (its REST summary allows any origin)
const summaries = new Map();
function summary(url) {
  if (!summaries.has(url)) {
    let u = null;
    try { u = new URL(url); } catch (e) { /* not a link */ }
    const title = u && u.pathname.startsWith('/wiki/') && u.pathname.slice(6);
    summaries.set(url, !title ? Promise.resolve('') : fetch(`${u.origin}/api/rest_v1/page/summary/${title}`)
      .then(r => r.ok ? r.json() : {}).then(j => {
        const parts = (j.extract || '').match(/[^.!?]+(?:[.!?]+(?=\s|$)|$)/g) || [];
        let out = '';
        for (const s of parts.slice(0, 3)) { if (out && (out + s).length > 420) break; out += s; }
        return out.trim();
      }).catch(() => ''));
  }
  return summaries.get(url);
}

let pointer = null, downAt = null;
canvas.addEventListener('pointermove', e => { pointer = e.pointerType === 'touch' ? null : [e.clientX, e.clientY]; });
canvas.addEventListener('pointerleave', () => { pointer = null; uniforms.uHover.value = -1; showCard(-1); });
canvas.addEventListener('pointerdown', e => { downAt = [e.clientX, e.clientY]; });
canvas.addEventListener('pointerup', e => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5 || e.button !== 0) return;
  const i = pick(e.clientX, e.clientY);
  if (i >= 0 && (!B.ok[i] || state.only && !inMuni(i))) return;
  pinCard(i, e.clientX, e.clientY);
});

// ---------- Search by cadastral reference ----------
const find = document.getElementById('find');
find.setAttribute('aria-label', `Buscar por referencia catastral (${REF_LEN} caracteres)`);
let refIndex = null;
find.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const q = find.value.trim().toUpperCase().replace(/\s+/g, '').slice(0, REF_LEN);
  if (!refIndex) {  // Gipuzkoa: the parcel alone finds its first building too
    refIndex = new Map();
    for (let i = 0; i < N; i++) if (B.ok[i]) {
      const r = building(i).ref;
      refIndex.set(r, i);
      if (r.includes('-') && !refIndex.has(r.split('-')[0])) refIndex.set(r.split('-')[0], i);
    }
  }
  const i = refIndex.get(q);
  find.classList.toggle('bad', i === undefined);
  if (i === undefined) return;
  const b = building(i);
  if (state.muni >= 0 && b.muni !== state.muni) setMuni(-1, false);
  if (b.year > state.year) setYear(yMax);
  flyTo(view(b.x, b.z, 500));
  setTimeout(() => pinCard(i, innerWidth / 2, innerHeight / 2), 1400);
});

// ---------- Tourist mode: what to see, walking routes ----------
// data/turismo.json (pipeline): must-sees by relevance, and routes of 5–12 stops in walking order. An entry is a
// building (g, its row) or a place with no building (x, z, y, lat, lon and m, its municipality: a square, a park).
// Only what is loaded counts; a route left with fewer than 3 stops is dropped.
const okRow = g => Number.isInteger(g) && g >= 0 && g < N && B.ok[g] === 1;
// Wikidata labels and descriptions in Spanish start in lower case ("plaza de España")
const cap = t => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;
function spotOf(e) {
  e = { ...e, n: cap(e.n), d: cap(e.d) };
  if (e.g != null) {
    if (!okRow(e.g)) return null;
    const b = building(e.g);
    return { ...e, x: b.x, z: b.z, lat: b.lat, lon: b.lon, muni: b.muni, top: new THREE.Vector3(b.x, b.base + b.h + 2, b.z) };
  }
  if (![e.x, e.z, e.lat, e.lon].every(Number.isFinite) || PARTIAL && !LOADED.has(e.m)) return null;
  return { ...e, g: -1, muni: e.m ?? -1, top: new THREE.Vector3(e.x, (Number.isFinite(e.y) ? e.y : groundAt(e.x, e.z)) + 6, e.z) };
}
const SEE = (tourism?.destacados || []).map(spotOf).filter(Boolean);
const SEE_BY_G = new Map(SEE.filter(s => s.g >= 0).map(s => [s.g, s]));
const ROUTES = (tourism?.rutas || []).map(r => ({ ...r, stops: (r.stops || []).map(spotOf).filter(Boolean) }))
  .filter(r => r.stops.length >= 3);
const seeBtn = document.getElementById('g-see'), routesBtn = document.getElementById('g-routes');
const routesBox = document.getElementById('routes'), labelsBox = document.getElementById('labels');
const lineSvg = document.getElementById('route-line'), lineUnder = lineSvg.querySelector('.under'), lineOver = lineSvg.querySelector('.over');
seeBtn.hidden = !SEE.length; routesBtn.hidden = !ROUTES.length;
const latlon = b => `${b.lat.toFixed(6)},${b.lon.toFixed(6)}`;

// fly to a building or a place and open its card; on a phone the card covers the lower half, so aim past it
let pinTimer = 0;
function goSpot(p, span = 650, az = 200) {
  if (state.muni >= 0 && p.muni !== state.muni) setMuni(-1, false);
  if (p.g >= 0 && B.year[p.g] > state.year) setYear(yMax);
  pinCard(-1);
  const s = narrow.matches ? span * 0.55 : 0, r = THREE.MathUtils.degToRad(az);
  flyTo(view(p.x + s * Math.sin(r), p.z + s * Math.cos(r), span, az, 38));
  clearTimeout(pinTimer);
  pinTimer = setTimeout(() => pinCard(p.g, innerWidth / 2, innerHeight / 2, p.g >= 0 ? null : p), 1400);
}

// "Qué ver": names over the must-sees, the most relevant first, as many as fit without overlapping
let seeOn = false;
function setSee(on) {
  seeOn = on && SEE.length > 0;
  seeBtn.setAttribute('aria-pressed', String(seeOn));
  // nothing to name from here: frame the dozen most relevant
  if (seeOn && !walk && drawOverlay() < 3) frame(SEE.filter(p => p.g < 0 || B.year[p.g] <= state.year).slice(0, 12).map(p => p.top));
}
// the view that takes in a set of points
function frame(pts, min = 1200) {
  if (!pts.length) return;
  const xs = pts.map(v => v.x), zs = pts.map(v => v.z);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
  flyTo(view((x0 + x1) / 2, (z0 + z1) / 2, Math.max(min, Math.max(x1 - x0, z1 - z0) * 1.3)));
}
seeBtn.onclick = () => setSee(!seeOn);
const tags = new Map(); // key → { el, w, h, shown }
const chrome = ['.masthead', '.tally', '.tools', '.find', '.dock', '#panel', '#routes', '#card'].map(q => document.querySelector(q));
function makeTag(key, html, cls, onclick, g = -1) {
  let t = tags.get(key);
  if (!t) {
    const el = document.createElement('button');
    el.className = cls; el.innerHTML = html; el.onclick = onclick;
    if (g >= 0) { el.onpointerenter = () => { uniforms.uHover.value = g; }; el.onpointerleave = () => { uniforms.uHover.value = -1; }; }
    labelsBox.append(el);
    t = { el, w: el.offsetWidth, h: el.offsetHeight, shown: true };
    tags.set(key, t);
  }
  return t;
}
const P = new THREE.Vector3();
function screenOf(v) {
  P.copy(v).applyMatrix4(camera.matrixWorldInverse);
  if (P.z > -camera.near) return null; // behind the camera
  P.applyMatrix4(camera.projectionMatrix);
  return [(P.x + 1) / 2 * innerWidth, (1 - P.y) / 2 * innerHeight];
}
function drawOverlay() {
  camera.updateMatrixWorld();
  const want = new Set(), placed = [];
  const place = (t, x, y) => { t.el.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`; want.add(t); };
  const fits = (x, y, w, h) => {
    if (x < 4 || y < 4 || x + w > innerWidth - 4 || y + h > innerHeight - 4) return false;
    for (const r of placed) if (x < r[0] + r[2] + 6 && x + w + 6 > r[0] && y < r[1] + r[3] + 4 && y + h + 4 > r[1]) return false;
    placed.push([x, y, w, h]);
    return true;
  };
  if (walk) {
    let d = '', pen = false;
    for (const v of walk.path) {
      const p = screenOf(v);
      if (!p) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`; pen = true;
    }
    lineUnder.setAttribute('d', d); lineOver.setAttribute('d', d);
    walk.stops.forEach((s, k) => {
      const p = screenOf(s.at);
      if (!p) return;
      const t = makeTag(`s${walk.r.id}:${k}`, String(k + 1), 'pin', () => goStop(k), s.g);
      t.el.classList.toggle('on', k === walk.k);
      placed.push([p[0] - t.w / 2, p[1] - t.h / 2, t.w, t.h]);
      place(t, p[0] - t.w / 2, p[1] - t.h / 2);
    });
  } else if (seeOn) {
    // names keep clear of the panels over the map
    for (const el of chrome) {
      const r = el.getBoundingClientRect();
      if (r.width && r.height) placed.push([r.left, r.top, r.width, r.height]);
    }
    const max = narrow.matches ? 9 : 14, far = uniforms.uFog.value.y * 0.7;
    let n = 0;
    for (const [k, d] of SEE.entries()) {
      if (n >= max) break;
      if (d.g >= 0 && (B.year[d.g] > state.year || d.g === pinned) || d === pinnedSpot) continue;
      if (state.only && state.muni >= 0 && d.muni !== state.muni) continue;
      if (camera.position.distanceTo(d.top) > far) continue;
      const p = screenOf(d.top);
      if (!p) continue;
      const t = makeTag(`see${k}`, `<span>${esc(d.n)}</span>`, d.g >= 0 ? 'tag' : 'tag place', () => goSpot(d), d.g);
      const x = p[0] - t.w / 2, y = p[1] - t.h - 12;
      if (!fits(x, y, t.w, t.h)) continue;
      place(t, x, y); n++;
    }
  }
  for (const t of tags.values()) {
    const on = want.has(t);
    if (on !== t.shown) { t.el.hidden = !on; t.shown = on; }
  }
  return want.size;
}

// "Rutas": the list, then a walk stop by stop: the camera flies to each, the card says why it is there
let walk = null;
const routesList = document.getElementById('routes-list');
const km = v => v.toLocaleString('es-ES', { maximumFractionDigits: 1 });
function renderRoutes() {
  routesList.innerHTML = ROUTES.map((r, k) => `<li><button data-k="${k}"${walk?.r === r ? ' aria-current="true"' : ''}>
    <span class="t">${esc(r.t)}</span>${r.d ? `<span class="d">${esc(r.d)}</span>` : ''}
    <span class="m">${r.km ? `${km(r.km)} km · ` : ''}${r.stops.length} paradas${walk?.r === r ? ' · en curso' : ''}</span></button></li>`).join('');
}
function openRoutes(open) {
  routesBox.hidden = !open;
  routesBtn.setAttribute('aria-expanded', String(open));
  if (!open) return;
  renderRoutes();
  pinCard(-1);
  if (narrow.matches) foldPanel(false);
}
routesBtn.onclick = () => openRoutes(routesBox.hidden);
routesBox.querySelector('.close').onclick = () => openRoutes(false);
routesList.onclick = e => {
  const b = e.target.closest('button[data-k]');
  if (b) startWalk(ROUTES[+b.dataset.k]);
};
function startWalk(r, k = 0) {
  const stops = r.stops.map(s => ({ ...s, at: new THREE.Vector3(s.x, groundAt(s.x, s.z) + 3, s.z) }));
  // a straight line between stops, laid on the ground every 30 m
  const path = [];
  for (let j = 0; j < stops.length - 1; j++) {
    const a = stops[j], c = stops[j + 1], n = Math.max(2, Math.ceil(Math.hypot(c.x - a.x, c.z - a.z) / 30));
    for (let q = 0; q < n; q++) {
      const x = a.x + (c.x - a.x) * q / n, z = a.z + (c.z - a.z) * q / n;
      path.push(new THREE.Vector3(x, groundAt(x, z) + 3, z));
    }
  }
  path.push(stops[stops.length - 1].at);
  walk = { r, stops, path, k: -1 };
  lineSvg.removeAttribute('hidden'); // an <svg> has no .hidden
  routesBtn.classList.add('walking');
  openRoutes(false);
  setOrbit(false);
  goStop(Math.min(Math.max(0, k), stops.length - 1));
}
function goStop(k) {
  if (!walk || k < 0 || k >= walk.stops.length) return;
  walk.k = k;
  // look ahead along the route: the camera stands on the side the walker comes from
  const s = walk.stops[k], a = walk.stops[k - 1], n = walk.stops[k + 1];
  const dx = a ? a.x - s.x : s.x - n.x, dz = a ? a.z - s.z : s.z - n.z;
  goSpot(s, 560, THREE.MathUtils.radToDeg(Math.atan2(dx, dz)));
  writeHash();
}
function endWalk() {
  walk = null;
  lineSvg.setAttribute('hidden', '');
  routesBtn.classList.remove('walking');
  writeHash();
}
function walkUrl(k) {
  // from this stop to the end; Google Maps takes up to 9 stops in between
  const rest = walk.stops.slice(k), mid = rest.slice(1, -1).slice(0, 9);
  const p = new URLSearchParams({ api: '1', travelmode: 'walking', origin: latlon(rest[0]), destination: latlon(rest[rest.length - 1]) });
  if (mid.length) p.set('waypoints', mid.map(latlon).join('|'));
  return `https://www.google.com/maps/dir/?${p.toString().replace(/%2C/g, ',').replace(/%7C/g, '|')}`;
}
function stopHtml(k) {
  const s = walk.stops[k], n = walk.stops.length;
  return `<div class="stop">
    <p class="stop-route">${esc(walk.r.t)} · ${k + 1} de ${n}</p>
    ${s.txt ? `<p class="stop-txt">${esc(s.txt)}</p>` : ''}
    <div class="stop-nav">
      <button data-go="-1"${k ? '' : ' disabled'}>← Anterior</button>
      ${k < n - 1 ? '<button data-go="1" class="next">Siguiente →</button>' : '<button data-go="fin" class="next">Terminar</button>'}
    </div>
    ${k < n - 1 ? `<a class="walk-link" href="${walkUrl(k)}" target="_blank" rel="noopener">Abrir a pie en Google Maps</a>` : ''}
  </div>`;
}

// ---------- URL ----------
function writeHash() {
  const m = muniById[state.muni];
  const h = new URLSearchParams();
  if (m && munis.length > 1) h.set('m', m.code);
  if (state.mode) h.set('modo', ['epoca', 'uso', 'plantas', 'patrimonio'][state.mode]);
  if (PARTIAL) h.set('cargar', munis.map(m => m.code).join(','));
  if (LABEL !== config.label && PARTIAL && munis.length > 1) h.set('titulo', LABEL);
  if (walk) { h.set('ruta', walk.r.id); if (walk.k > 0) h.set('parada', walk.k + 1); }
  const s = h.toString();
  history.replaceState(null, '', s ? `#${s.replace(/%2C/g, ',')}` : location.pathname + location.search);
}
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const m = munis.find(m => m.code === h.get('m'));
  state.mode = Math.max(0, ['epoca', 'uso', 'plantas', 'patrimonio'].indexOf(h.get('modo')));
  modeButtons.forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.mode === state.mode)));
  return m ? m.id : -1;
}

// ---------- Tools: home, orbit, theme, share, picture, keys ----------
const toast = document.getElementById('toast');
let toastTimer = 0;
function say(text) {
  toast.textContent = text; toast.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.hidden = true; }, 2200);
}
const goHome = () => walk ? (pinCard(-1), frame(walk.stops.map(s => s.at), 800)) : flyTo(home);
document.getElementById('t-home').onclick = goHome;
const orbitBtn = document.getElementById('t-orbit');
controls.autoRotateSpeed = -0.5;
function setOrbit(on) { controls.autoRotate = on; orbitBtn.setAttribute('aria-pressed', String(on)); }
orbitBtn.onclick = () => setOrbit(!controls.autoRotate);
const MOON = 'M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z';
const SUN = 'M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4M13.2 10a3.2 3.2 0 1 1-6.4 0 3.2 3.2 0 0 1 6.4 0z';
const themeBtn = document.getElementById('t-theme');
function setTheme(name) {
  theme = name;
  document.documentElement.dataset.theme = name;
  try { localStorage.setItem('tema', name); } catch (e) { /* private mode */ }
  const c = C();
  groundUniforms.uLand.value.set(c.land); groundUniforms.uSel.value.set(c.sel); groundUniforms.uDim.value.set(c.dim);
  groundUniforms.uOut.value.set(c.sky); groundUniforms.uFogColor.value.set(c.sky);
  uniforms.uFogColor.value.set(c.sky); uniforms.uMaquette.value.set(c.maquette);
  borderMat.color.set(c.border); waterMat.color.set(c.water);
  document.querySelector('meta[name="theme-color"]').content = c.meta;
  themeBtn.querySelector('path').setAttribute('d', name === 'noche' ? SUN : MOON);
  themeBtn.title = name === 'noche' ? 'Pasar a día (N)' : 'Pasar a noche (N)';
  if (lastCounts) drawHist(lastCounts);
}
themeBtn.onclick = () => setTheme(theme === 'noche' ? 'dia' : 'noche');
document.getElementById('t-share').onclick = async () => {
  // the view in the link: target, distance, azimuth and elevation
  const off = camera.position.clone().sub(controls.target), d = off.length();
  const az = THREE.MathUtils.radToDeg(Math.atan2(off.x, off.z)), el = THREE.MathUtils.radToDeg(Math.asin(off.y / d));
  const h = new URLSearchParams(location.hash.slice(1));
  h.set('v', [controls.target.x, controls.target.z, d, az, el].map(v => Math.round(v)).join(','));
  if (state.year < yMax) h.set('ano', state.year);
  if (pinned >= 0) h.set('ref', building(pinned).ref);
  const url = `${location.origin}${location.pathname}#${h.toString().replace(/%2C/g, ',')}`;
  try { await navigator.clipboard.writeText(url); say('Enlace copiado'); } catch (e) { prompt('Enlace a esta vista', url); }
};
document.getElementById('t-shot').onclick = () => {
  renderer.render(scene, camera); // the drawing buffer is only readable in the frame that drew it
  // the sky is the page's gradient behind a transparent canvas: paint it under the city, and sign the picture
  const out = document.createElement('canvas'), x = out.getContext('2d');
  out.width = canvas.width; out.height = canvas.height;
  const css = getComputedStyle(document.documentElement), g = x.createLinearGradient(0, 0, 0, out.height);
  g.addColorStop(0, css.getPropertyValue('--sky-top')); g.addColorStop(0.42, css.getPropertyValue('--sky'));
  g.addColorStop(1, css.getPropertyValue('--sky'));
  x.fillStyle = g; x.fillRect(0, 0, out.width, out.height);
  x.drawImage(canvas, 0, 0);
  const s = out.width / innerWidth;
  x.font = `700 ${Math.round(30 * s)}px Fraunces, Georgia, serif`; x.fillStyle = css.getPropertyValue('--ink');
  x.fillText(LABEL, 24 * s, 48 * s);
  x.font = `600 ${Math.round(13 * s)}px Manrope, sans-serif`; x.fillStyle = css.getPropertyValue('--accent');
  x.fillText(`${state.year >= yMax ? 'Hoy' : state.year} · spain-cities.quijada.uk · Juanma Quijada · ${FORAL ? FORAL.name : 'Catastro'}, IGN, OSM`, 24 * s, 72 * s);
  out.toBlob(blob => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${LABEL.toLowerCase().replace(/[^a-z0-9áéíóúñü]+/gi, '-')}-${state.year >= yMax ? 'hoy' : state.year}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    say('Imagen guardada');
  });
};
addEventListener('keydown', e => {
  if (e.target.closest('input, select, textarea') || e.metaKey || e.ctrlKey || e.altKey || about.open) return;
  const k = e.key.toLowerCase();
  if (k >= '1' && k <= '4') setMode(+k - 1);
  else if (k === ' ') { e.preventDefault(); document.getElementById('play').click(); }
  else if (k === 'h') goHome();
  else if (k === 'r') setOrbit(!controls.autoRotate);
  else if (k === 'n') setTheme(theme === 'noche' ? 'dia' : 'noche');
  else if (k === 'v' && SEE.length) setSee(!seeOn);
  else if (walk && (k === 'arrowright' || k === 'arrowleft')) { e.preventDefault(); goStop(walk.k + (k === 'arrowright' ? 1 : -1)); }
  else if (k === 'escape') { if (!routesBox.hidden) openRoutes(false); else { if (walk) endWalk(); pinCard(-1); } }
  else return;
});
// the legend starts below the masthead, whatever its height
const masthead = document.querySelector('.masthead');
new ResizeObserver(() => {
  panelBox.style.top = narrow.matches ? '' : `${masthead.getBoundingClientRect().bottom + 12}px`;
  panelBox.style.maxHeight = narrow.matches ? '' : `${innerHeight - masthead.getBoundingClientRect().bottom - 12 - 150}px`;
  routesBox.style.top = panelBox.style.top; routesBox.style.maxHeight = panelBox.style.maxHeight;
}).observe(masthead);
// the way back to the list of cities, when this map is one of the portal's
const portalLink = document.getElementById('portal-link');
if (document.body.dataset.portal) { portalLink.href = document.body.dataset.portal; portalLink.textContent = '← Todas las ciudades'; }
// and back to this city's municipality picker (#<key>&cargar=…), with the current selection already ticked
if (document.body.dataset.portal) {
  const change = document.getElementById('change'), key = location.pathname.split('/').filter(Boolean).pop();
  if (config.municipios.length > 1 && key) {
    change.href = `${document.body.dataset.portal}#${key}&cargar=${PARTIAL ? chosen.map(m => m.code).join(',') : '*'}`;
  } else {
    change.href = document.body.dataset.portal; change.textContent = '← Otras ciudades';
    portalLink.textContent = 'Ciudades de España'; // the button already says the same
  }
  change.hidden = false;
}

// ---------- Loop ----------
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (lastCounts) drawHist(lastCounts);
}
addEventListener('resize', resize);
// another selection means other files: start again
addEventListener('hashchange', () => {
  const w = (new URLSearchParams(location.hash.slice(1)).get('cargar') || '').split(',').filter(Boolean);
  if (w.join() !== (PARTIAL ? munis.map(m => m.code).join() : want.join())) location.reload();
});
resize();

// the hash as it came: setMuni below rewrites it, and ano, ref and ruta are read after that
const HASH0 = new URLSearchParams(location.hash.slice(1));
const start = readHash();
// home: the whole build, or the box around the chosen municipalities
const HOME = (() => {
  if (!PARTIAL) return config.home;
  // where the selection's buildings are: 2nd to 98th percentile of a sample, so marshes and stray barns don't count
  const xs = [], zs = [], step = Math.max(1, Math.floor(N / 40000));
  for (let i = 0; i < N; i += step) if (B.ok[i]) { xs.push(dv.getFloat32(i * S + F.x, true)); zs.push(dv.getFloat32(i * S + F.z, true)); }
  if (xs.length < 10) return config.home;
  const q = (a, f) => a[Math.floor(f * (a.length - 1))];
  xs.sort((a, b) => a - b); zs.sort((a, b) => a - b);
  const x0 = q(xs, 0.02), x1 = q(xs, 0.98), z0 = q(zs, 0.02), z1 = q(zs, 0.98);
  return { x: (x0 + x1) / 2, z: (z0 + z1) / 2, span: Math.max(1200, Math.max(x1 - x0, z1 - z0) * 1.05) };
})();
const home = view(HOME.x, HOME.z, HOME.span);
const shared = (new URLSearchParams(location.hash.slice(1)).get('v') || '').split(',').map(Number);
if (shared.length === 5 && shared.every(Number.isFinite)) jump(view(shared[0], shared[1], shared[2] / 0.9, shared[3], shared[4]));
else if (start >= 0) { const m = muniById[start]; jump(view(m.cx, m.cz, Math.min(Math.max(m.span, 1200), 16000))); }
else {
  // arrive from high above, then settle on the city
  jump(view(HOME.x, HOME.z, HOME.span * 2.4, 170, 62));
  flyTo(home, 2600);
}
setMuni(munis.length > 1 ? start : munis[0].id, false);
setTheme(theme);
{
  const h = HASH0;
  const y = +h.get('ano');
  if (y >= yMin && y < yMax) setYear(y);
  const r = ROUTES.find(r => r.id === h.get('ruta'));
  if (r) setTimeout(() => startWalk(r, (+h.get('parada') || 1) - 1), shared.length === 5 ? 300 : 2700);
  const ref = r ? null : h.get('ref');
  if (ref) {
    for (let i = 0; i < N; i++) if (B.ok[i] && building(i).ref === ref) {
      setTimeout(() => pinCard(i, innerWidth / 2, innerHeight / 2), shared.length === 5 ? 300 : 2700);
      break;
    }
  }
}

let lastPick = 0;
renderer.setAnimationLoop(now => {
  uniforms.uNow.value = now / 1000;
  stepPlay(now);
  stepFlight(now);
  controls.update();
  const d = camera.position.distanceTo(controls.target);
  uniforms.uFog.value.set(d * 1.6, d * 4.5);
  groundUniforms.uFog.value.copy(uniforms.uFog.value);
  if (pointer && pinned === -1 && now - lastPick > 60 && !flight) {
    lastPick = now;
    let i = pick(pointer[0], pointer[1]);
    if (i >= 0 && (!B.ok[i] || state.only && !inMuni(i))) i = -1;
    if (i !== hoverGid) { hoverGid = i; uniforms.uHover.value = i; showCard(i, pointer[0], pointer[1]); }
    else if (i >= 0) placeCard(pointer[0], pointer[1]);
  }
  renderer.render(scene, camera);
  if (walk || seeOn || tags.size) drawOverlay();
});
