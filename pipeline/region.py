"""The region the pipeline works on, from REGION (default `sevilla`): its data folder, frame and sources.

    REGION=madrid uv run python -m pipeline.build todos
    uv run python -m pipeline.sites madrid barcelona --deploy     # pipeline.sites sets REGION per site

Sevilla keeps its data in data/; any other region in data/<region>/. Each region has its own local frame (metres from
a landmark, in the UTM zone it lies in), its Catastro territorial office, its municipalities and its heritage source:
the IAPH in Andalucía, Wikidata elsewhere.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Region:
    key: str
    crs: int                      # ETRS89 / UTM zone of the local frame
    landmark: tuple               # lon, lat of the frame's origin
    office: str                   # Catastro territorial office (feed folder)
    bbox: str                     # south, west, north, east: Overpass searches municipalities inside it
    label: str                    # page title when a site shows several municipalities
    heritage: str                 # "iaph" or "wikidata"
    wikidata: str = ""            # Wikidata item of the area, for heritage
    ine: dict = field(default_factory=dict)   # Catastro code → INE code, where they differ
    municipios: tuple = ()        # (code, name, feed folder); empty = the Sevilla list in municipios.py
    lidar_year: int = 2015


REGIONS = {
    "sevilla": Region("sevilla", 25830, (-5.99260, 37.38620), "41", "36.8,-6.6,38.25,-4.6", "Provincia de Sevilla",
                      "iaph", "Q95088",
                      ine={"41900": "41091", "41103": "41901", "41104": "41902", "41105": "41903", "41106": "41904"}),
    # Puerta del Sol, kilometre zero
    "madrid": Region("madrid", 25830, (-3.70358, 40.41670), "28", "40.25,-3.95,40.7,-3.5", "Madrid",
                     "wikidata", "Q2807", ine={"28900": "28079"}, municipios=(("28900", "Madrid", "MADRID"),)),
    # Plaça de Catalunya; Barcelona lies in UTM zone 31
    "barcelona": Region("barcelona", 25831, (2.17000, 41.38700), "08", "41.30,2.04,41.48,2.24", "Barcelona",
                        "wikidata", "Q1492", ine={"08900": "08019"}, municipios=(("08900", "Barcelona", "BARCELONA"),)),
}

REGION = REGIONS[os.environ.get("REGION", "sevilla")]
DATA = Path("data") if REGION.key == "sevilla" else Path("data") / REGION.key
