"""Terrain: the IGN's 5 m digital terrain model (MDT05, WCS, CC BY 4.0 scne.es) under every building and as a ground mesh.

The Aljarafe stands on a plateau 100–150 m above the Guadalquivir plain, so a flat model misplaces it badly.
The WCS serves the whole peninsula in UTM 30N only; a region in another zone (Barcelona, 31N) is sampled and
reprojected from it.

  data/base.parquet      ref → ground level of each building (lowest terrain under its outline, metres)
  web/data/terrain.bin   heightfield for the viewer, little-endian:
                         f32 x0, z0 (local frame, north-west corner), f32 step; u32 nx, nz;
                         i16 h[nz*nx] (decimetres); u8 muni[nz*nx] (municipality id, 255 outside)
"""
import json
import os
import math
import struct

import geopandas as gpd
import numpy as np
import rasterio
import requests
import shapely
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.transform import from_origin
from pyproj import Transformer
from rasterio.warp import Resampling, reproject, transform_bounds

from .municipios import ORDER
from .s00_fetch_catastro import chosen
from .region import DATA, REGION
from .s03_tiles import ORIGIN, OUT

WCS = ("https://servicios.idee.es/wcs-inspire/mdt?service=WCS&version=2.0.1&request=GetCoverage"
       "&CoverageId=Elevacion25830_{res}&format=image/tiff&subset=x({x0},{x1})&subset=y({y0},{y1})")
CACHE = DATA / "raw/mdt"
DEM_CRS = 25830
CHUNK = 8000          # metres per WCS request of the 5 m model, fetched only where there are buildings
CHUNK25 = 40000       # metres per request of the 25 m model, for the ground mesh over the whole area
PAD = 2500            # metres of terrain around the municipalities
MAX_VERTS = 450_000   # ground mesh budget
BASE = OUT.parent / "base.parquet" if os.environ.get("SITE_OUT") else DATA / "base.parquet"


def fetch(x0, y0, res=5, size=CHUNK):
    f = CACHE / (f"{x0}_{y0}.tif" if res == 5 else f"{x0}_{y0}_{res}.tif")
    if not f.exists():
        url = WCS.format(res=res, x0=x0, x1=x0 + size, y0=y0, y1=y0 + size)
        for attempt in range(5):
            try:
                r = requests.get(url, timeout=300)
                r.raise_for_status()
                if not r.headers.get("content-type", "").startswith("image/tiff"):
                    raise requests.RequestException(r.text[:200])
                f.write_bytes(r.content)
                break
            except requests.RequestException as e:
                print(f"  MDT {x0},{y0}: {e}; reintento", flush=True)
        else:
            raise SystemExit("El WCS del IGN no responde")
    return f


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    b = gpd.read_parquet(DATA / "buildings.parquet")
    b = b[b.muni.isin([ORDER.index(c) for c in chosen()])][["ref", "geometry"]]
    ground = json.loads((OUT / "ground.json").read_text())
    minx, miny, maxx, maxy = b.total_bounds
    for m in ground["munis"]:  # municipal boundaries are in the local frame
        for rings in m["rings"]:
            xs, zs = np.array(rings[0][0::2]), np.array(rings[0][1::2])
            minx, maxx = min(minx, xs.min() + ORIGIN[0]), max(maxx, xs.max() + ORIGIN[0])
            miny, maxy = min(miny, ORIGIN[1] - zs.max()), max(maxy, ORIGIN[1] - zs.min())
    minx, miny = math.floor((minx - PAD) / CHUNK) * CHUNK, math.floor((miny - PAD) / CHUNK) * CHUNK
    maxx, maxy = math.ceil((maxx + PAD) / CHUNK) * CHUNK, math.ceil((maxy + PAD) / CHUNK) * CHUNK

    # Ground level of each building: the lowest terrain under its outer ring, so that on a slope it sits into the hill.
    # One 5 m block at a time, only the blocks that hold buildings: a whole province would not fit merged in memory.
    xy, idx = shapely.get_coordinates(shapely.get_exterior_ring(
        shapely.get_geometry(b.geometry.values, 0)), return_index=True)
    if REGION.crs != DEM_CRS:
        xy = np.c_[Transformer.from_crs(REGION.crs, DEM_CRS, always_xy=True).transform(xy[:, 0], xy[:, 1])]
    keys = np.floor(xy / CHUNK).astype(np.int64) * CHUNK
    blocks = np.unique(keys, axis=0)
    print(f"  MDT05: {len(blocks)} bloques de {CHUNK / 1000:.0f} km con edificios", flush=True)
    base = np.full(len(b), np.inf)
    for kx, ky in blocks:
        sel = (keys[:, 0] == kx) & (keys[:, 1] == ky)
        with rasterio.open(fetch(int(kx), int(ky))) as src:
            dem = src.read(1)
            col, row = ~src.transform * (xy[sel, 0], xy[sel, 1])
        row = np.clip(row.astype(int), 0, dem.shape[0] - 1)
        col = np.clip(col.astype(int), 0, dem.shape[1] - 1)
        z = dem[row, col].astype(np.float64)
        z[z < -1000] = np.inf
        np.minimum.at(base, idx[sel], z)
    base[~np.isfinite(base)] = 0
    b.drop(columns="geometry").assign(base=base.round(1)).to_parquet(BASE)

    # Ground mesh: a coarser grid from the 25 m model, local frame, north-west corner first.
    W, H = maxx - minx, maxy - miny
    step = max(20.0, math.ceil(math.sqrt(W * H / MAX_VERTS) / 5) * 5)
    nx, nz = int(W // step) + 1, int(H // step) + 1
    dminx, dminy, dmaxx, dmaxy = transform_bounds(REGION.crs, DEM_CRS, minx, miny, maxx, maxy) if REGION.crs != DEM_CRS \
        else (minx, miny, maxx, maxy)
    x25, y25 = math.floor(dminx / CHUNK25) * CHUNK25, math.floor(dminy / CHUNK25) * CHUNK25
    files = [fetch(x, y, 25, CHUNK25) for x in range(x25, int(dmaxx), CHUNK25) for y in range(y25, int(dmaxy), CHUNK25)]
    srcs = [rasterio.open(f) for f in files]
    dem, tr = merge(srcs, nodata=-9999)
    for s in srcs:
        s.close()
    dem = dem[0].astype(np.float32)
    dem[dem < -1000] = 0
    grid = np.zeros((nz, nx), np.float32)
    gtr = from_origin(minx - step / 2, maxy + step / 2, step, step)
    reproject(dem, grid, src_transform=tr, src_crs=DEM_CRS, dst_transform=gtr, dst_crs=REGION.crs,
              resampling=Resampling.average if step >= 25 else Resampling.bilinear)
    utm = lambda r: np.c_[np.array(r[0::2]) + ORIGIN[0], ORIGIN[1] - np.array(r[1::2])]
    shapes = [(shapely.Polygon(utm(rings[0]), [utm(r) for r in rings[1:]]), m["id"])
              for m in ground["munis"] for rings in m["rings"]]
    muni = rasterize(shapes, out_shape=(nz, nx), transform=gtr, fill=255, dtype=np.uint8) if shapes \
        else np.full((nz, nx), 255, np.uint8)
    x0, z0 = minx - ORIGIN[0], -(maxy - ORIGIN[1])
    out = struct.pack("<3f2I", x0, z0, step, nx, nz)
    out += np.round(grid * 10).clip(-32000, 32000).astype("<i2").tobytes()
    out += muni.tobytes()
    (OUT / "terrain.bin").write_bytes(out)
    print(f"cotas de {len(b)} edificios ({base.min():.0f}–{base.max():.0f} m); "
          f"malla {nx}×{nz} cada {step:.0f} m, {len(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
