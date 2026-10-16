// Turns one binary tile (pipeline/s03_tiles.py) into a mesh. Positions stay in decimetres from the tile origin.
// Every part is a prism standing on the building's ground level: walls from each ring, a flat roof at the part's height.
import { ShapeUtils, Vector2 } from './vendor/three.core.js';

function parse(buf) {
  const h = new DataView(buf);
  const nB = h.getUint32(4, true), nP = h.getUint32(8, true), nR = h.getUint32(12, true), nV = h.getUint32(16, true);
  const origin = [h.getFloat32(20, true), h.getFloat32(24, true)];
  let o = 28;
  const take = (Type, n) => { const a = new Type(buf, o, n); o += Math.ceil(n * Type.BYTES_PER_ELEMENT / 4) * 4; return a; };
  return {
    nB, origin,
    gid: take(Uint32Array, nB), year: take(Int16Array, nB), flag: take(Uint8Array, nB), period: take(Uint8Array, nB),
    floors: take(Uint8Array, nB), muni: take(Uint8Array, nB), use: take(Uint8Array, nB), mon: take(Uint8Array, nB),
    base: take(Int16Array, nB),
    partStart: take(Uint32Array, nB + 1),
    height: take(Float32Array, nP), ringStart: take(Uint32Array, nP + 1),
    vertStart: take(Uint32Array, nR + 1), hole: take(Uint8Array, nR), xz: take(Int16Array, 2 * nV),
  };
}

function build(t) {
  let nVert = 0, nIdx = 0;
  for (let r = 0; r < t.hole.length; r++) {
    const n = t.vertStart[r + 1] - t.vertStart[r];
    // walls 6 per edge; the roof triangulates to (vertices + 2 × holes − 2) triangles, so a hole costs 6 more
    nVert += n * 5; nIdx += n * 9 + 6;
  }
  const pos = new Int16Array(nVert * 3), bld = new Uint16Array(nVert), idx = new Uint32Array(nIdx);
  let v = 0, k = 0;
  for (let b = 0; b < t.nB; b++) {
    const g = t.base[b];
    for (let p = t.partStart[b]; p < t.partStart[b + 1]; p++) {
      const top = g + Math.round(t.height[p] * 10);
      const contour = [], holes = [];
      for (let r = t.ringStart[p]; r < t.ringStart[p + 1]; r++) {
        const s = t.vertStart[r], n = t.vertStart[r + 1] - s;
        const ring = [];
        for (let i = 0; i < n; i++) {
          const a = s + i, c = s + ((i + 1) % n);
          const ax = t.xz[2 * a], az = t.xz[2 * a + 1], cx = t.xz[2 * c], cz = t.xz[2 * c + 1];
          pos.set([ax, g, az, cx, g, cz, cx, top, cz, ax, top, az], v * 3);
          bld.fill(b, v, v + 4);
          idx.set([v, v + 1, v + 2, v, v + 2, v + 3], k);
          v += 4; k += 6;
          ring.push(new Vector2(ax, az));
        }
        if (!t.hole[r] && !contour.length) contour.push(...ring);
        else holes.push(ring);
      }
      if (contour.length < 3) continue;
      const roofStart = v;
      for (const pt of contour.concat(...holes)) { pos.set([pt.x, top, pt.y], v * 3); bld[v] = b; v++; }
      for (const tri of ShapeUtils.triangulateShape(contour, holes)) {
        idx.set([roofStart + tri[0], roofStart + tri[1], roofStart + tri[2]], k); k += 3;
      }
    }
  }
  // Per-building lookup, two texels: [year, period + 16*flag, floors, global id], [municipality, use, heritage, ground level dm].
  const attr = new Float32Array(t.nB * 8);
  for (let b = 0; b < t.nB; b++) {
    attr.set([t.year[b], t.period[b] + 16 * t.flag[b], t.floors[b], t.gid[b], t.muni[b], t.use[b], t.mon[b], t.base[b]], b * 8);
  }
  return { pos: pos.subarray(0, v * 3), bld: bld.subarray(0, v), idx: idx.subarray(0, k), attr, origin: t.origin, nB: t.nB };
}

self.onmessage = ({ data: { buf, id } }) => {
  const m = build(parse(buf));
  self.postMessage({ id, ...m }, [m.pos.buffer, m.bld.buffer, m.idx.buffer, m.attr.buffer]);
};
