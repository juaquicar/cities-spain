# Ciudades de España, edificio a edificio

Cada edificio en pie de 29 ciudades españolas en 3D: las más pobladas, las más visitadas y las 15 del Grupo de Ciudades
Patrimonio de la Humanidad (Sevilla con el Aljarafe y el resto de la provincia, Madrid, Barcelona, Valencia, Málaga,
Granada, Córdoba, Toledo, Santiago, San Sebastián, Palma, Las Palmas…), coloreado por
época de construcción, uso o número de plantas, con filtro por municipio. Pipeline en Python que alimenta un visor
three.js sin build step.

**Portal:** [spain-cities.quijada.uk](https://spain-cities.quijada.uk): todas las ciudades; antes de cargar nada se
elige ciudad y, en las grandes, qué municipios, con el peso de la descarga a la vista.

**Sitios sueltos:** [sevilla.quijada.uk](https://sevilla.quijada.uk) · [aljarafe.quijada.uk](https://aljarafe.quijada.uk).
Los antiguos madrid, barcelona, tomares, sevilla-aljarafe y sevilla-provincia redirigen (301) a su sitio en el portal,
con la selección de municipios que mostraban.

## Autor y créditos

Hecho por **[Juanma Quijada](https://www.linkedin.com/in/juanmaquijada)**: proyecto personal sin ánimo de lucro.

Basado en [amsterdam-by-building](https://github.com/alexbarakov/amsterdam-by-building) (LAYRS: Amsterdam) de
[Alex Barakov](https://www.linkedin.com/in/alexanderbarakov), con licencia MIT, que a su vez sigue la arquitectura de
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
| `s05_monumentos` | Patrimonio: IAPH (datos abiertos Junta) + Wikidata en Andalucía; solo Wikidata en el resto |
| `s04_ground` | Términos municipales y agua de OpenStreetMap (Overpass) |
| `s06_terreno` | MDT 5 m del IGN (WCS): cota de cada edificio y malla de relieve |
| `s07_lidar` | Alturas LiDAR (MDSnE2,5 del CNIG) si hay ficheros en `data/raw/lidar/`; si no, plantas × 3 m |

## Uso

```bash
uv sync
uv run python -m pipeline.build tomares            # primer municipio
uv run python -m pipeline.build sevilla mairena    # añade más (se acumulan)
uv run python -m pipeline.build todos              # los 106 municipios de la provincia
REGION=madrid uv run python -m pipeline.build todos      # Madrid, en data/madrid/
REGION=barcelona uv run python -m pipeline.build todos   # Barcelona, en data/barcelona/ (igual valencia, zaragoza, bilbao, salamanca)
python3 -m http.server 8642 --directory web        # http://localhost:8642
uv run python -m pipeline.sites --deploy           # publica los siete sitios (tras `npx wrangler login`; con varias cuentas, CLOUDFLARE_ACCOUNT_ID)
uv run python -m pipeline.sites portal --deploy    # el portal, con los sitios que ya hay en dist/
```

### Portal y carga por municipios

`portal/` es la portada de spain-cities.quijada.uk. `pipeline.sites portal` copia cada área de `PORTAL` (en
`sites.py`) desde `dist/<sitio>/` a `dist/spain-cities/<clave>/` y escribe `cities.json` con los municipios, sus
contornos simplificados para el mapa del selector y los ficheros que necesita cada uno. Cloudflare no sirve
peticiones por rangos, así que `s03_tiles` deja las teselas, los packs y los tramos de `attrs*.bin` separados por
municipio; el visor lee `#cargar=41093,41094&titulo=…` y descarga solo esos. Sin `cargar`, carga todo.
Con muchas ciudades, las tarjetas se agrupan por comunidad autónoma y se filtran por etiqueta (columna `tags` de
`PORTAL`): `#grandes` (más de 300.000 habitantes), `#patrimonio` (Grupo de Ciudades Patrimonio de la Humanidad) y
`#costa` (costa e islas). El buscador encuentra ciudades, municipios y comunidades.

### Visor

Dos temas, noche (por defecto) y día, que se recuerdan en el navegador. Herramientas: vista inicial, dar la vuelta,
tema, copiar enlace a la vista (`#v=x,z,distancia,azimut,elevación`, más `ano` y `ref` si hay año o ficha), guardar
imagen. Atajos: `1`–`4` modos, `Espacio` reproducir, `H`, `R`, `N`, `V`, `←` `→`, `Esc`. Hitos de cada ciudad sobre el histograma.

Modo turismo, si el sitio trae `data/turismo.json`: «Qué ver» pone el nombre sobre los imprescindibles (los más
relevantes que caben sin pisarse) y «Rutas» abre paseos parada a parada, con la línea entre paradas, el texto de cada
una, Anterior/Siguiente y el enlace «Abrir a pie en Google Maps» (`#ruta=id&parada=n` en el enlace). Al fijar un
monumento con artículo, la ficha añade dos o tres frases del resumen de Wikipedia y «Cómo llegar».

### Sitios publicados

`pipeline/sites.py` rehace suelo, terreno y teselas para cada selección de municipios en `build/<sitio>/`, monta
`dist/<sitio>/` y lo publica como Worker de Cloudflare con assets estáticos (configuración en `sites/<sitio>.jsonc`):

| Sitio | Municipios | Worker |
|---|---|---|
| https://spain-cities.quijada.uk | Portal: Sevilla (provincia, con selecciones) y otras 28 ciudades, por comunidad | `spain-cities` |
| https://sevilla.quijada.uk | Sevilla | `sevilla-edificios` |
| https://aljarafe.quijada.uk | Los 31 del Aljarafe, sin la capital | `aljarafe` |
| tomares, sevilla-aljarafe, sevilla-provincia, madrid, barcelona .quijada.uk | 301 al portal (`REDIRECT` en sites.py) | los mismos |

Bilbao sale del catastro foral de Bizkaia (INSPIRE propio, `cadastre="bizkaia"` en region.py): solo edificios, sin
partes, con referencias de 17 caracteres. © Bizkaiko Foru Aldundia. San Sebastián sale del de Gipuzkoa
(`cadastre="gipuzkoa"`): un único GML de toda la provincia (1 GB, se lee en streaming y se queda Donostia), en EPSG:3042
con el norte primero; referencia `<parcela foral>-<edificio>`. CC BY-SA © Gipuzkoako Foru Aldundia.

### Regiones

`pipeline/region.py` define cada región (`REGION`, por defecto `sevilla`): oficina del Catastro, huso UTM del marco
local (Barcelona, Tarragona y Baleares van en 31N y Santiago en 29N; el MDT del IGN se pide en 30N y se reproyecta;
Canarias va entera en REGCAN95 / UTM 28N, EPSG:4083, igual que su MDT), punto de origen (Giralda, Puerta del Sol,
Plaça de Catalunya), municipios y fuente de patrimonio. Los periodos de la leyenda de cada región están en
`pipeline/periods.py` (las ciudades sin periodos propios usan una pauta común). Fuera de Andalucía el patrimonio viene solo de Wikidata: elementos con punto y declaración
patrimonial, estilo o fecha de inicio; los que solo tienen fecha cuentan únicamente si el punto cae dentro de un edificio.

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
Dirección General del Catastro como autora y titular; catastros forales de Bizkaia (© Bizkaiko Foru Aldundia) y
Gipuzkoa (CC BY-SA, © Gipuzkoako Foru Aldundia); IAPH, datos abiertos de la Junta de Andalucía; MDT05 y LiDAR
© IGN/CNIG (CC BY 4.0, scne.es); Wikidata CC0; fotos de Wikimedia Commons con su licencia; OpenStreetMap, ODbL.
