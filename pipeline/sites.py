"""One published site per selection of municipalities, each on its own Cloudflare Worker (static assets).

    uv run python -m pipeline.sites                 # build every site into dist/<site>/
    uv run python -m pipeline.sites --deploy        # … and publish them
    uv run python -m pipeline.sites tomares --deploy

The common steps (pipeline.build) must have run first for all the municipalities a site needs; this only redoes the
per-site outputs (ground, terrain, tiles) with SITE_MUNIS / SITE_OUT, then copies the viewer next to them.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .municipios import ORDER

ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID")  # unset: wrangler takes the logged-in account
# name, municipality codes (None = all built), domain, worker, title
SITES = [
    ("tomares", ["41093"], "tomares.quijada.uk", "tomares", None),
    ("sevilla", ["41900"], "sevilla.quijada.uk", "sevilla-edificios", None),
    ("aljarafe", [c for c in ORDER if c != "41900"], "aljarafe.quijada.uk", "aljarafe", "Aljarafe"),
    ("sevilla-aljarafe", None, "sevilla-aljarafe.quijada.uk", "sevilla-aljarafe", None),
]
STEPS = ["pipeline.s04_ground", "pipeline.s06_terreno", "pipeline.s03_tiles"]


def build(name, codes, label=None):
    out = Path("build") / name / "data"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SITE_OUT=str(out), SITE_MUNIS=",".join(codes or ORDER), SITE_LABEL=label or "")
    for step in STEPS:
        print(f"— {name}: {step.split('.')[-1]}", flush=True)
        subprocess.run([sys.executable, "-m", step], env=env, check=True)
    dist = Path("dist") / name
    shutil.rmtree(dist, ignore_errors=True)
    shutil.copytree("web", dist, ignore=shutil.ignore_patterns("data"))
    shutil.copytree(out, dist / "data", ignore=shutil.ignore_patterns("*.parquet"))
    return dist


def config(name, domain, worker):
    f = Path("sites") / f"{name}.jsonc"
    f.parent.mkdir(exist_ok=True)
    cfg = dict(
        name=worker, compatibility_date="2026-10-12",
        assets=dict(directory=f"../dist/{name}"),
        routes=[dict(pattern=domain, custom_domain=True)],
    )
    if ACCOUNT:
        cfg["account_id"] = ACCOUNT
    f.write_text(json.dumps(cfg, indent=2) + "\n")
    return f


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    deploy = "--deploy" in sys.argv
    for name, codes, domain, worker, label in SITES:
        if args and name not in args:
            continue
        dist = build(name, codes, label)
        size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
        print(f"{name}: {size / 1e6:.1f} MB en {dist}", flush=True)
        if deploy:
            subprocess.run(["npx", "wrangler", "deploy", "-c", str(config(name, domain, worker))], check=True)


if __name__ == "__main__":
    main()
