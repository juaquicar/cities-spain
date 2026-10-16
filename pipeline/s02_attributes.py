"""Clean years, floors and heights; assign a period.

date_flag: 0 year from the Catastro; 1 a rounded year (the Catastro piles buildings on 1900, 1940, 1950…: a year
that holds over SPIKE times the mean of the four years either side, per municipality, is taken as approximate);
2 estimated from dated neighbours (Catastro has none, or an impossible one).
Heights: the Catastro gives floors per part, not metres. A floor counts 3 m, plus half a metre of parapet;
a part with no floor above ground (a courtyard roof, a basement under a square) is a 0.4 m slab.
"""
import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree

from .periods import period_of

FLOOR = 3.0
PARAPET = 0.5
SLAB = 0.4
NEIGHBOURS = 8
YEAR_MAX = 2026
SPIKE = 3.0


def part_height(floors):
    f = floors.fillna(0).clip(0, 60)
    return np.where(f > 0, f * FLOOR + PARAPET, SLAB)


def main():
    b = gpd.read_parquet("data/buildings_raw.parquet")
    p = gpd.read_parquet("data/parts.parquet")

    year = b.beginning.str.slice(0, 4)
    year = year.where(year.str.fullmatch(r"\d{4}")).astype(float)
    year = year.where((year >= 1000) & (year <= YEAR_MAX))
    b["date_flag"] = np.where(year.isna(), 2, 0).astype(np.uint8)

    # Undated buildings take the median year of their dated neighbours.
    c = np.c_[b.geometry.centroid.x, b.geometry.centroid.y]
    dated = year.notna().to_numpy()
    if (~dated).any() and dated.sum() >= NEIGHBOURS:
        tree = cKDTree(c[dated])
        _, idx = tree.query(c[~dated], k=NEIGHBOURS)
        year.iloc[np.flatnonzero(~dated)] = np.median(year.to_numpy()[dated][idx], axis=1).round()
    b["year"] = year.fillna(1980).astype(int)

    for _, grp in b[b.date_flag == 0].groupby("muni"):
        vc = grp.year.value_counts()
        around = lambda y: np.mean([vc.get(y + d, 0) for d in (-4, -3, -2, -1, 1, 2, 3, 4)])
        spikes = [y for y, n in vc.items() if n >= 10 and n > SPIKE * max(around(y), 1)]
        b.loc[grp.index[grp.year.isin(spikes)], "date_flag"] = 1
    b["period"] = b.year.map(period_of).astype(np.uint8)

    p["h"] = part_height(p.numberOfFloorsAboveGround)
    agg = p.groupby("ref").agg(floors=("numberOfFloorsAboveGround", "max"), height=("h", "max"),
                               below=("numberOfFloorsBelowGround", "max"))
    b = b.merge(agg, left_on="ref", right_index=True, how="left")
    b["floors"] = b.floors.fillna(1).clip(0, 255).astype(np.uint8)
    b["height"] = b.height.fillna(FLOOR + PARAPET)
    b["below"] = b.below.fillna(0).clip(0, 255).astype(np.uint8)
    b["dwellings"] = b.numberOfDwellings.fillna(0).clip(0, 65535).astype(int)
    b["area"] = b.value.fillna(0).clip(0, 2**31).astype(int)
    b["use"] = b.currentUse.fillna("").str.split("_").str[0].map(
        {"1": 1, "2": 2, "3": 3, "4": 4}).fillna(0).astype(np.uint8)
    # tertiary uses split: 4_1 office, 4_2 retail, 4_3 public services → 4, 5, 6
    b.loc[b.currentUse == "4_2_retail", "use"] = 5
    b.loc[b.currentUse == "4_3_publicServices", "use"] = 6
    b.to_parquet("data/buildings.parquet")
    p.to_parquet("data/parts.parquet")
    print(f"{len(b)} edificios; años redondeados: {(b.date_flag == 1).sum()}, estimados: {(b.date_flag == 2).sum()}; "
          f"rango {b.year.min()}–{b.year.max()}; plantas máx {b.floors.max()}")


if __name__ == "__main__":
    main()
