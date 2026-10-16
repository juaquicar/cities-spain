"""Building heights from PNOA LiDAR, where the files are on disk; floors × 3 m elsewhere.

Input: data/raw/lidar/ — any GeoTIFF / ESRI ASCII rasters of the CNIG's normalised building surface model
(MDSnE2,5, building class, height above ground in metres, 2.5 m cells), in any CRS (Aljarafe sheets come in
UTM 29, Sevilla in UTM 30). The CNIG download centre does not allow scripted downloads: fetch the sheets by hand
(Modelos digitales de elevaciones → MDSnE2,5 2ª cobertura → buscar por mapa, rectangle over the area).

For every Catastro building part, the 85th percentile of the building cells whose centres fall inside it becomes its
height, when there are at least MIN_CELLS of them and the building is older than the flight (LIDAR_YEAR): a newer
building was not there yet. Output: data/lidar.parquet (part localId → height), read by s03_tiles.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds

RAW = Path("data/raw/lidar")
PCT = 85
MIN_CELLS = 3
LIDAR_YEAR = 2015   # second PNOA LiDAR coverage over Sevilla
MAX_H = 200.0


def heights_from(path, parts):
    out = {}
    with rasterio.open(path) as src:
        crs = src.crs or 25830
        p = parts.to_crs(crs)
        l, b, r, t = src.bounds
        p = p.cx[l:r, b:t]
        if p.empty:
            return out
        w = from_bounds(*p.total_bounds, transform=src.transform)
        win = Window(int(np.floor(w.col_off)), int(np.floor(w.row_off)), int(np.ceil(w.width)) + 2, int(np.ceil(w.height)) + 2)
        win = win.intersection(Window(0, 0, src.width, src.height))
        z = src.read(1, window=win, masked=True).filled(0).astype(np.float32)
        tr = src.window_transform(win)
    ids = np.arange(1, len(p) + 1, dtype=np.int32)
    lab = rasterize(zip(p.geometry, ids), out_shape=z.shape, transform=tr, fill=0, dtype=np.int32)
    sel = (lab > 0) & (z > 1.0) & (z < MAX_H)
    lab, z = lab[sel], z[sel]
    if not len(lab):
        return out
    order = np.argsort(lab, kind="stable")
    lab, z = lab[order], z[order]
    cuts = np.flatnonzero(np.diff(lab)) + 1
    for k, vals in zip(lab[np.r_[0, cuts]], np.split(z, cuts)):
        if len(vals) >= MIN_CELLS:
            out[p.localId.iloc[k - 1]] = float(np.percentile(vals, PCT))
    return out


def main():
    files = sorted(f for f in RAW.glob("**/*") if f.suffix.lower() in (".tif", ".tiff", ".asc"))
    if not files:
        print("  sin ficheros LiDAR en data/raw/lidar: alturas por plantas")
        pd.DataFrame(columns=["localId", "h_lidar"]).to_parquet("data/lidar.parquet")
        return
    parts = gpd.read_parquet("data/parts.parquet")[["localId", "ref", "geometry"]]
    years = gpd.read_parquet("data/buildings.parquet", columns=["ref", "year"]).set_index("ref").year
    parts = parts[parts.ref.map(years).fillna(9999) <= LIDAR_YEAR].reset_index(drop=True)
    h = {}
    for f in files:
        got = heights_from(f, parts)
        h.update(got)
        print(f"  {f.name}: {len(got)} partes", flush=True)
    pd.DataFrame({"localId": list(h), "h_lidar": list(h.values())}).to_parquet("data/lidar.parquet")
    print(f"{len(h)} de {len(parts)} partes con altura LiDAR")


if __name__ == "__main__":
    main()
