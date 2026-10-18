"""Whole pipeline in one go. Names add municipalities to the ones already built:

    uv run python -m pipeline.build tomares
    uv run python -m pipeline.build sevilla mairena bormujos
    uv run python -m pipeline.build todos
    uv run python -m pipeline.build            # rebuild what is already chosen
"""
from . import s00_fetch_catastro, s01_load, s02_attributes, s03_tiles, s04_ground, s05_monumentos, s06_terreno, s07_lidar, s08_turismo


def main():
    s00_fetch_catastro.main()
    for step in (s01_load, s02_attributes, s05_monumentos, s04_ground, s06_terreno, s07_lidar, s08_turismo, s03_tiles):
        print(f"— {step.__name__.split('.')[-1]}", flush=True)
        step.main()


if __name__ == "__main__":
    main()
