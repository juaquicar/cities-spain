// One binary tile (pipeline/s03_tiles.py) as typed arrays over its buffer: shared by the worker that meshes it and by
// the camera view, which reads the footprints again around where one stands.
export function parse(buf) {
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
