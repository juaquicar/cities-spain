# Sevilla y Aljarafe, edificio a edificio

Cada edificio en pie de Sevilla y el Aljarafe en 3D, coloreado por época de construcción, uso o número de plantas,
con filtro por municipio. Pipeline en Python que alimenta un visor three.js sin build step.

**En vivo:** [sevilla-aljarafe.quijada.uk](https://sevilla-aljarafe.quijada.uk) ·
[sevilla.quijada.uk](https://sevilla.quijada.uk) · [aljarafe.quijada.uk](https://aljarafe.quijada.uk) ·
[tomares.quijada.uk](https://tomares.quijada.uk)

## Créditos

Basado en [amsterdam-by-building](https://github.com/alexbarakov/amsterdam-by-building) (LAYRS: Amsterdam) de
Alex Barakov, con licencia MIT, que a su vez sigue la arquitectura de
[Paris, building by building](https://paris.bogachev.fr) de Sasha Bogachev. El mérito de la arquitectura original
es suyo; este fork la adapta a Catastro, IAPH, IGN y OSM, añade el enriquecimiento patrimonial, el relieve y el
despliegue en varios sitios.

```
Catastro INSPIRE + OSM ──► pipeline/ (Python) ──► web/data/ (teselas binarias + JSON) ──► web/ (three.js)
```

| Paso | Qué hace |
|---|---|
| `s00_fetch_catastro` | Descarga el GML de edificios del Catastro por municipio; guarda la selección en `data/municipios.json` |
| `s01_load` | Building + BuildingPart → parquet, reproyectado a ETRS89 / UTM 30N |
| `s02_attributes` | Años (marca los redondeados, estima los que faltan), plantas → altura, uso, época |
| `s03_tiles` | Teselas de 600 m en packs, `attrs.bin` por edificio, `city.json` |
| `s05_monumentos` | Patrimonio inmueble del IAPH (datos abiertos Junta) + Wikidata: nombre, datación, estilo, BIC, foto |
| `s04_ground` | Términos municipales y agua de OpenStreetMap (Overpass) |
| `s06_terreno` | MDT 5 m del IGN (WCS): cota de cada edificio y malla de relieve |
| `s07_lidar` | Alturas LiDAR (MDSnE2,5 del CNIG) si hay ficheros en `data/raw/lidar/`; si no, plantas × 3 m |

## Uso

```bash
uv sync
uv run python -m pipeline.build tomares            # primer municipio
uv run python -m pipeline.build sevilla mairena    # añade más (se acumulan)
uv run python -m pipeline.build todos              # Sevilla + todo el Aljarafe
python3 -m http.server 8642 --directory web        # http://localhost:8642
uv run python -m pipeline.sites --deploy           # publica los cuatro sitios (tras `npx wrangler login`; con varias cuentas, CLOUDFLARE_ACCOUNT_ID)
```

### Sitios publicados

`pipeline/sites.py` rehace suelo, terreno y teselas para cada selección de municipios en `build/<sitio>/`, monta
`dist/<sitio>/` y lo publica como Worker de Cloudflare con assets estáticos (configuración en `sites/<sitio>.jsonc`):

| Sitio | Municipios | Worker |
|---|---|---|
| https://tomares.quijada.uk | Tomares | `tomares` |
| https://sevilla.quijada.uk | Sevilla | `sevilla-edificios` |
| https://aljarafe.quijada.uk | Los 31 del Aljarafe, sin la capital | `aljarafe` |
| https://sevilla-aljarafe.quijada.uk | Sevilla + Aljarafe (32) | `sevilla-aljarafe` |

### Alturas LiDAR

El Centro de Descargas del CNIG no permite descargas automatizadas: baja a mano
*Modelos digitales de elevaciones → MDSnE2,5 (2ª cobertura) → buscar por mapa*, dibujando un rectángulo sobre la
zona, y deja los ficheros (GeoTIFF o ASC, cualquier huso) en `data/raw/lidar/`. Después:
`uv run python -m pipeline.s07_lidar && uv run python -m pipeline.sites --deploy`.

Los municipios disponibles están en `pipeline/municipios.py` (código INE/Catastro, nombre, carpeta del feed).
Se aceptan códigos o nombres sin tildes. La URL guarda el filtro: `#m=41093&modo=plantas`.

## Decisiones sobre los datos

- **Alturas.** Con LiDAR: percentil 85 de las celdas de edificación dentro de cada parte catastral (si el edificio
  es anterior al vuelo). Sin LiDAR: 3 m por planta + 0,5 m de pretil. LoD 1, sin tejados.
- **Relieve.** Cada edificio se asienta en la cota más baja del MDT bajo su planta.
- **Patrimonio.** La fecha del IAPH (o Wikidata) sustituye a la del Catastro cuando es anterior.
- **Años.** El año del Catastro suele ser el de la última reforma integral, sobre todo en el casco histórico
  (la Catedral no aparece como gótica). Los años que el Catastro amontona (1900, 1940, 1950…) se marcan como
  redondeados; los que faltan toman la mediana de los 8 vecinos con fecha. Ambos se dibujan más pálidos.
- **Ruinas.** Fuera.

## Licencias

Código: MIT (derivado de amsterdam-by-building, © 2026 alexbarakov). Datos: Catastro, uso libre citando a la
Dirección General del Catastro como autora y titular; IAPH, datos abiertos de la Junta de Andalucía; MDT05 y LiDAR
© IGN/CNIG (CC BY 4.0, scne.es); Wikidata CC0; fotos de Wikimedia Commons con su licencia; OpenStreetMap, ODbL.
