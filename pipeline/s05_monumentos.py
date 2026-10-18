"""Heritage buildings from the IAPH (Patrimonio Inmueble de Andalucía, open data of the Junta) and Wikidata.

The Catastro dates a church by its last major works; the IAPH dates it by its construction: Iglesia de San Gil,
Catastro 1950-something, IAPH 1300–1399, Gothic-Mudéjar. Each architectural or ethnological heritage item of the
chosen municipalities is placed on the building under its point (or the nearest within NEAR metres), and gives that
building its name, dating, style and protection. Wikidata adds a photo and the Spanish Wikipedia article.
Outside Andalucía (REGION.heritage == "wikidata") Wikidata alone is the source: every item of the area with a point
and a heritage designation, an architectural style or an inception date; a point counts only inside a building
unless the item is protected or has a style (a street or a company with a date must not name the house beside it).

Output: data/monumentos.parquet (one row per building ref). s03_tiles applies the years and writes monumentos.json.
"""
import csv
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from .region import DATA, REGION
from .s00_fetch_catastro import chosen
from .s04_ground import INE

BASE = "http://www.juntadeandalucia.es/datosabiertos/portal/iaph/dataset/bien/inmueble"
LOCATOR = ("https://www.juntadeandalucia.es/datosabiertos/portal/iaph/dataset/dataset/c0d5ed60-ee01-4b7c-9871-cd5d4ef4f7d8"
           "/resource/eb3186ce-1c38-4ced-80f1-97f2d359b9a0/download/localizador.csv")
WIKIDATA = "https://query.wikidata.org/sparql"
CACHE = DATA / ("raw/iaph" if REGION.heritage == "iaph" else "raw/wikidata")
NEAR = 30.0
NEAR_BIC = 150.0  # a BIC point often marks the middle of a large complex (Plaza de España: the square itself)
UA = {"User-Agent": "sevilla-edificios/0.1 (open-data map; contact via repository)"}
KINDS = ("Arquitectónica", "Etnológica")


def get(url, **kw):
    for attempt in range(5):
        try:
            r = requests.get(url, headers=UA, timeout=120, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"  {url[:90]}: {e}; reintento", flush=True)
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"No responde: {url}")


def listing():
    """Every immovable item in Andalucía (id, code, name, characterisation), 1000 per page, cached."""
    docs, page = [], 0
    while True:
        f = CACHE / f"list_{page}.json"
        if not f.exists():
            f.write_text(get(BASE, params=dict(page=page, rows=1000, format="json")).text)
        r = json.loads(f.read_text())["response"]
        docs += r["docs"]
        page += 1
        if r["start"] + len(r["docs"]) >= r["numFound"] or not r["docs"]:
            return docs


def detail(i):
    f = CACHE / "bien" / f"{i}.json"
    if not f.exists():
        f.write_text(get(f"{BASE}/{i}", params=dict(format="json")).text)
        time.sleep(0.1)
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return {}


def locator():
    f = CACHE / "localizador.csv"
    if not f.exists():
        f.write_bytes(get(LOCATOR).content)
    rows = csv.DictReader(io.StringIO(f.read_bytes().decode("utf-8", "replace")))
    return {r["PI_ID"]: (float(r["LONGITUD"]), float(r["LATITUD"])) for r in rows if r["LONGITUD"] and r["LATITUD"]}


def wikidata():
    """IAPH id → (Commons image, Spanish Wikipedia URL, inception year, (lon, lat)), for items in Sevilla province."""
    f = CACHE / "wikidata2.json"
    if not f.exists():
        q = """SELECT ?iaph ?img ?art ?inc ?coord WHERE {
          ?item wdt:P3318 ?iaph ; wdt:P131* wd:%s .
          OPTIONAL { ?item wdt:P18 ?img }
          OPTIONAL { ?item wdt:P571 ?inc }
          OPTIONAL { ?item wdt:P625 ?coord }
          OPTIONAL { ?art schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }
        }""" % REGION.wikidata
        f.write_text(get(WIKIDATA, params=dict(query=q, format="json")).text)
    out = {}
    for b in json.loads(f.read_text())["results"]["bindings"]:
        k = b["iaph"]["value"].lstrip("i")
        img = b.get("img", {}).get("value", "").rsplit("/", 1)[-1]
        art = b.get("art", {}).get("value", "")
        inc = b.get("inc", {}).get("value", "")
        inc = int(inc[:5].rstrip("-")) if inc[:1] in "-0123456789" and inc[:4].lstrip("-").isdigit() else None
        pt = b.get("coord", {}).get("value", "")
        pt = tuple(map(float, pt[6:-1].split())) if pt.startswith("Point(") else None
        old = out.get(k, ("", "", None, None))
        out[k] = (old[0] or unquote(img), old[1] or art,
                  min(x for x in (old[2], inc) if x is not None) if old[2] is not None or inc is not None else None,
                  old[3] or pt)
    return out


# Start of an IAPH period, for items dated only by period. Christian Sevilla begins in 1248.
PERIOD_START = {"Edad Media": 1248, "Plena Edad Media": 1248, "Baja Edad Media": 1248, "Edad Moderna": 1500}


def coords(d, loc, i):
    """The detail's own point (its latitud_s/longitud_s are swapped in the source), else the locator's."""
    a, b = d.get("latitud_s"), d.get("longitud_s")
    for lon, lat in ((a, b), (b, a)):
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)) and -8 < lon < -1 and 35 < lat < 39:
            return lon, lat
    return loc.get(i)


def dating(d):
    tips = (d.get("tipologiaList") or {}).get("tipologia") or []
    if isinstance(tips, dict):
        tips = [tips]
    ini = [t["crono_ini"] for t in tips if isinstance(t.get("crono_ini"), int)]
    fin = [t["crono_fin"] for t in tips if isinstance(t.get("crono_fin"), int)]
    styles = sorted({t["den_estilo"] for t in tips if t.get("den_estilo")})
    periods = sorted({t["periodos"] for t in tips if t.get("periodos")})
    types = sorted({t["den_tipologia"] for t in tips if isinstance(t.get("den_tipologia"), str)})
    return (min(ini) if ini else None, max(fin) if fin else None, ", ".join(styles)[:120],
            ", ".join(periods)[:120], ", ".join(types)[:120])


def protection(d):
    p = (d.get("proteccionList") or {}).get("proteccion") or []
    p = [p] if isinstance(p, dict) else p
    figs = [x.get("figura") for x in p if x.get("figura")]
    return "BIC" if "BIC" in figs else (figs[0] if figs else "")


def iaph_rows():
    (CACHE / "bien").mkdir(parents=True, exist_ok=True)
    ine = {INE.get(c, c) for c in chosen()}
    items = [d for d in listing() if d.get("codigo", "").zfill(11)[2:7] in ine
             and any(k in d.get("caracterizacion", "") for k in KINDS)]
    print(f"  {len(items)} bienes inmuebles en los municipios elegidos", flush=True)
    with ThreadPoolExecutor(4) as ex:
        details = list(ex.map(lambda d: detail(d["id"]), items))
    loc, wd = locator(), wikidata()

    rows = []
    for it, d in zip(items, details):
        xy = coords(d, loc, it["id"])
        img, art, inc, pt = wd.get(it["id"], ("", "", None, None))
        xy = xy or pt
        if not xy:
            continue
        y0, y1, style, period, types = dating(d)
        approx = False
        if y0 is None and inc is not None:
            y0 = inc
        elif y0 is None and period:
            starts = [PERIOD_START[p.strip()] for p in period.split(",") if p.strip() in PERIOD_START]
            y0, approx = (min(starts), True) if starts else (None, False)
        rows.append(dict(iaph=int(it["id"]), name=it["denominacion"], y0=y0, y1=y1, style=style, period=period,
                         types=types, prot=protection(d), img=img, wp=art, approx=approx, strong=True, geometry=Point(xy)))
    return rows


# Designations that the card calls Bien de Interés Cultural (Catalonia: bé cultural d'interès nacional)
BIC = ("bien de interés cultural", "bien cultural de interés nacional")
# Wikidata items that stand on or in a building without being it: their dates are not the building's. GONE (also for
# protected items): buildings no longer there, whose point now falls on whatever replaced them, art and whole places.
GONE = re.compile(r"placa|estatua|busto|escultura|desaparecid|ya no existe|demolid|ciudad|distrito|barrio|municipio|"
                  r"fuente|calle|plaza\b|jardín|parque", re.I)
# listings that are not protection: Barcelona's public art and "small landscapes"
NOT_PROTECTION = re.compile(r"arte público|paisajes", re.I)
NOT_A_BUILDING = re.compile(r"placa|estatua|retrato|busto|escultura|grupo escultórico|obra de arte|monumento|fuente|"
                            r"lámina de agua|reja|organizaci|fundación|organismo|empresa|club|asociación|institu|"
                            r"academia|biblioteca|archivo|colección|restaurante|bar\b|tienda|estación|instalación|"
                            r"cementerio|parque|jardín|calle|plaza\b|barrio|desaparecid|ya no existe|demolid|ruinas|"
                            r"mural|grafiti|árbol|línea|vía\b", re.I)


def wikidata_rows():
    """Every item of REGION.wikidata with a point and a designation, style or inception, one row per item."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"items_{REGION.wikidata}.json"
    if not f.exists():
        q = """SELECT ?item ?itemLabel ?coord ?inc ?img ?art ?art_ca ?styleLabel ?herLabel ?typeLabel WHERE {
          ?item wdt:P131* wd:%s ; wdt:P625 ?coord .
          { ?item wdt:P1435 [] } UNION { ?item wdt:P571 [] } UNION { ?item wdt:P149 [] }
          OPTIONAL { ?item wdt:P571 ?inc }
          OPTIONAL { ?item wdt:P18 ?img }
          OPTIONAL { ?item wdt:P149 ?style }
          OPTIONAL { ?item wdt:P1435 ?her }
          OPTIONAL { ?item wdt:P31 ?type }
          OPTIONAL { ?art schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }
          OPTIONAL { ?art_ca schema:about ?item ; schema:isPartOf <https://ca.wikipedia.org/> }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "es,ca,en". }
        }""" % REGION.wikidata
        f.write_text(get(WIKIDATA, params=dict(query=q, format="json")).text)
    items = {}
    for b in json.loads(f.read_text())["results"]["bindings"]:
        v = lambda k: b.get(k, {}).get("value", "")
        qid = v("item").rsplit("/", 1)[-1]
        pt = v("coord")
        if not pt.startswith("Point("):
            continue
        it = items.setdefault(qid, dict(name=v("itemLabel"), pt=tuple(map(float, pt[6:-1].split())), inc=set(),
                                        img="", wp="", style=set(), her=set(), types=set()))
        inc = v("inc")
        if inc[:1] in "-0123456789" and inc[:5].lstrip("-")[:4].isdigit():
            it["inc"].add(int(inc[:5].rstrip("-")))
        it["img"] = it["img"] or unquote(v("img").rsplit("/", 1)[-1])
        it["wp"] = it["wp"] or v("art") or v("art_ca")
        for k, key in (("styleLabel", "style"), ("herLabel", "her"), ("typeLabel", "types")):
            if v(k) and not (v(k).startswith("Q") and v(k)[1:].isdigit()):
                it[key].add(v(k))
    rows = []
    for qid, it in items.items():
        if it["name"] == qid:  # no label in any of the languages
            continue
        if any(GONE.search(t) for t in it["types"]):
            continue
        if not any(not NOT_PROTECTION.search(h) for h in it["her"]) and any(NOT_A_BUILDING.search(t) for t in it["types"]) and not any(
                re.search(r"edificio|iglesia|palacio|convento|monasterio|casa|teatro|rascacielos|torre", t, re.I)
                and not re.search(r"desaparecid|ya no existe|demolid", t, re.I) for t in it["types"]):
            continue
        her = sorted(h for h in it["her"] if not NOT_PROTECTION.search(h))
        prot = "BIC" if any(h.lower().startswith(BIC) for h in her) else (her[0][:1].upper() + her[0][1:] if her else "")
        y0 = min(it["inc"]) if it["inc"] else None
        rows.append(dict(wd=qid, name=it["name"], y0=y0, y1=None, style=", ".join(sorted(it["style"]))[:120], period="",
                         types=", ".join(sorted(it["types"]))[:120], prot=prot, img=it["img"], wp=it["wp"],
                         approx=False, strong=bool(her or it["style"]), geometry=Point(it["pt"])))
    print(f"  {len(rows)} elementos de Wikidata con punto en {REGION.wikidata}", flush=True)
    return rows


def main():
    rows = iaph_rows() if REGION.heritage == "iaph" else wikidata_rows()
    m = gpd.GeoDataFrame(rows, crs=4326).to_crs(REGION.crs)
    b = gpd.read_parquet(DATA / "buildings.parquet")[["ref", "geometry"]]
    hit = gpd.sjoin(m, b, predicate="within", how="left").drop(columns="index_right")
    miss = hit[hit.ref.isna()].drop(columns="ref")
    miss = miss[miss.strong]
    near = gpd.sjoin_nearest(miss, b, max_distance=NEAR, how="inner", distance_col="d").drop(columns="index_right")
    key = "iaph" if REGION.heritage == "iaph" else "wd"
    far = miss[(miss.prot == "BIC") & ~miss[key].isin(near[key])]
    far = gpd.sjoin_nearest(far, b, max_distance=NEAR_BIC, how="inner", distance_col="d").drop(columns="index_right")
    m = pd.concat([hit[hit.ref.notna()], near, far]).drop(columns="d")
    # one item per building: protected first, then the oldest
    m = m.assign(bic=m.prot == "BIC").sort_values(["bic", "y0"], ascending=[False, True], na_position="last")
    m = m.drop_duplicates("ref").drop(columns=["geometry", "bic", "strong"])
    pd.DataFrame(m).to_parquet(DATA / "monumentos.parquet")
    print(f"{len(m)} edificios con ficha {'del IAPH' if key == 'iaph' else 'de Wikidata'} ({int(m.y0.notna().sum())} con datación, "
          f"{int((m.prot == 'BIC').sum())} BIC, {int((m.img != '').sum())} con foto)")


if __name__ == "__main__":
    main()
