# Ciudades de España, edificio a edificio

Los edificios en pie de las ciudades y pueblos de España en 3D, uno a uno: coloreados por época de construcción, uso, número de plantas o
patrimonio, con filtro por municipio. Empezó con Sevilla y su provincia y crece casi a diario (capitales, las ciudades
más pobladas y más visitadas, las del Grupo de Ciudades Patrimonio de la Humanidad, pueblos…); la meta es el país
entero. Pipeline en Python (Catastro, IGN, OSM, IAPH, Wikidata) que alimenta un visor three.js sin build step.

Tres formas de verlo:

- **En el mapa 3D** (navegador o móvil): la ciudad entera por épocas, con la línea del tiempo, las fichas de cada
  edificio y el patrimonio; buscador de direcciones y referencias catastrales y, si se quiere, mapa base (OSM u
  ortofoto PNOA) bajo los edificios.
- **De turismo**: los imprescindibles de cada ciudad y rutas a pie parada a parada, con el resumen de Wikipedia.
- **En la calle, con la cámara** (patrimonio aumentado): sobre la imagen de la cámara, un punto en la fachada de
  cada edificio que tienes a la vista a 25 m o menos, con su época, su año y su ficha; también guía las rutas. Funciona en el navegador del móvil y en la
  **app Android** (`android/`, descargable desde el portal), que pide de entrada los permisos de cámara y ubicación.

**Portal:** [spain-cities.quijada.uk](https://spain-cities.quijada.uk): todas las ciudades; antes de cargar nada se
elige ciudad (en el buscador, en las tarjetas o en el mapa de España, con un punto por ciudad según su número de
edificios; los pueblos no van en ese mapa, se eligen al entrar en la ciudad o la provincia) y, en las grandes, qué
municipios, con el peso de la descarga a la vista. El mapa base sale de Natural Earth
(`pipeline/spain_map.py` escribe `portal/spain.json`).

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
imagen. Atajos: `1`–`4` modos, `Espacio` reproducir, `H`, `R`, `N`, `V`, `B`, `Esc`. Hitos de cada ciudad sobre el histograma.
Con el teclado: las flechas desplazan el mapa (adelante, atrás y a los lados de la vista), `Mayús` + flechas giran e
inclinan y `+` `−` acercan; se puede mantener la tecla. En una ruta, `←` `→` siguen pasando de parada.

Mapa base (botón de capas o `B`), apagado por defecto y recordado en el navegador: OpenStreetMap o la ortofoto PNOA
del IGN (solo fuentes abiertas). Son teselas Web Mercator puestas sobre los mismos vértices que el relieve
(las celdas del terreno bajo cada tesela, con lo que sobra descartado en el shader), así que ni flotan ni se hunden; el
uv es un ajuste afín de x, z locales sobre las cuatro esquinas (lon/lat → UTM con la serie de Krüger). El huso del
marco no está en `city.json`: sale de comparar la lon/lat de un edificio con su x, z. Se piden primero las más cercanas;
mientras llegan se ve la tesela de tres niveles más arriba o, en su defecto, unas pocas gruesas de toda la ciudad. De
noche se oscurecen para que manden los colores de los edificios.

Buscador: una referencia catastral abre su edificio; cualquier otra cosa es una dirección. Las sugerencias mientras se
escribe salen de [Photon](https://photon.komoot.io) (datos de OSM, pensado para autocompletar) dentro de la caja de la
ciudad y cerca del centro de la vista; `Intro` sin sugerencia elegida pregunta una vez a Nominatim (su política de uso
no permite autocompletar). Al elegir un portal, vuela al edificio que cae debajo (o al más cercano a 25 m) y abre su
ficha; una calle o un lugar, solo vuela.

Modo turismo, si el sitio trae `data/turismo.json`: «Qué ver» pone el nombre sobre los imprescindibles (los más
relevantes que caben sin pisarse) y «Rutas» abre paseos parada a parada, con la línea entre paradas, el texto de cada
una, Anterior/Siguiente y el enlace «Abrir a pie en Google Maps» (`#ruta=id&parada=n` en el enlace). Al fijar un
monumento con artículo, la ficha añade dos o tres frases del resumen de Wikipedia y «Cómo llegar».

### Ver con la cámara (patrimonio aumentado)

En el móvil, «Ver con la cámara» pone la cámara de fondo y encima la ciudad vista desde donde estás: el GPS da la
posición (pasada al marco local con un ajuste por mínimos cuadrados sobre los edificios cercanos, que llevan lon/lat y
x/z), la brújula y el giroscopio la orientación (`deviceorientationabsolute` en Android, `webkitCompassHeading` en iOS) y
el ojo va a 1,6 m sobre la mediana de las cotas de los edificios de alrededor. Sobre la cámara solo va lo que tienes
cerca y a la vista: un punto por cada edificio cuya fachada está a 25 m o menos (`NEAR` en `web/app.js`), del color de
su época, puesto en esa fachada (el punto de su planta más cercano a ti, a la altura del primer piso) y solo si ninguna
otra planta se cruza en la línea hasta él; «3D» dibuja además esos edificios, transparentes. Lo demás no se pinta.

Para que los puntos caigan en su sitio pese al GPS (5–20 m entre edificios) y la brújula (10–20°), todo con datos
abiertos y código propio, sin servicios externos: las plantas del Catastro alrededor se leen otra vez de las teselas
(`web/tile.js`, compartido con el worker); una posición que cae dentro de un edificio sale a la calle, a 1,2 m de su
pared más cercana; y cada 0,7 s se compara la silueta de la cámara con la de las plantas. La de la cámara sale de una
copia de 64 columnas: en cada una, hasta dónde baja el cielo (un tramo claro y liso desde arriba; si arriba no hay cielo,
la columna no cuenta). La de las plantas, del borde superior de las paredes que corta cada acimut desde donde estás.
Se prueban giros de ±20° y pasos de 4 m; si alguna combinación encaja claramente mejor (error medio < 2,5° y medio grado
mejor que como está), se gira la brújula un 60 % de lo hallado y se desplaza la posición la mitad (hasta 12 m). Sin
cielo (de noche, bajo soportales, con árboles delante) o en una plaza abierta no corrige nada. La barra de estado dice
«ajustado por la silueta» mientras funciona.

La escena sirve para saber qué edificio hay bajo la retícula («Estás mirando»: nombre, año, época,
plantas, distancia) y si cada monumento con nombre está a la vista o detrás de algo. En una ruta empieza por la parada
más cercana, una flecha en el borde señala la siguiente y al llegar (25 m) abre su ficha. Deslizar a los lados corrige la
brújula; tocar un edificio abre su ficha. `#ar=demo` simula estar junto al primer imprescindible, sin cámara ni sensores.
En el portal, «Estoy en la calle» busca la ciudad y los municipios más cercanos y abre el visor con la cámara a punto
(`#ar=1`).

### Sitios publicados

`pipeline/sites.py` rehace suelo, terreno y teselas para cada selección de municipios en `build/<sitio>/`, monta
`dist/<sitio>/` y lo publica como Worker de Cloudflare con assets estáticos (configuración en `sites/<sitio>.jsonc`):

| Sitio | Municipios | Worker |
|---|---|---|
| https://spain-cities.quijada.uk | Portal: todas las ciudades, por comunidad; Sevilla con su provincia y selecciones | `spain-cities` |
| https://sevilla.quijada.uk | Sevilla | `sevilla-edificios` |
| https://aljarafe.quijada.uk | Los 31 del Aljarafe, sin la capital | `aljarafe` |
| tomares, sevilla-aljarafe, sevilla-provincia, madrid, barcelona .quijada.uk | 301 al portal (`REDIRECT` en sites.py) | los mismos |

Bilbao sale del catastro foral de Bizkaia (INSPIRE propio, `cadastre="bizkaia"` en region.py): solo edificios, sin
partes, con referencias de 17 caracteres. © Bizkaiko Foru Aldundia. San Sebastián sale del de Gipuzkoa
(`cadastre="gipuzkoa"`): un único GML de toda la provincia (1 GB, se lee en streaming y se queda Donostia), en EPSG:3042
con el norte primero; referencia `<parcela foral>-<edificio>`. CC BY-SA © Gipuzkoako Foru Aldundia.

### App Android

`android/` es una app mínima (WebView, sin dependencias, ~13 kB) que abre el portal a pantalla completa. Al abrirla
por primera vez explica para qué sirve cada permiso y pide cámara y ubicación (GPS); la brújula y el giroscopio no
llevan permiso, pero comprueba que el móvil tenga brújula (si no, avisa de que se orienta deslizando) y, si la
ubicación está apagada, ofrece activarla. Si se le dice que no, los vuelve a pedir cuando «Ver con la cámara» los
necesita. Las páginas del portal se quedan en la app y cualquier otro enlace (Wikipedia, Google Maps, LinkedIn) se abre en el navegador; acepta
enlaces a spain-cities.quijada.uk. El portal la ofrece en `app/ciudades-de-espana.apk` (botón «App Android», oculto
dentro de la propia app, que se identifica con `CiudadesApp` en el user agent).

    cd android && JAVA_HOME=<JDK 17> gradle assembleRelease     # Gradle 8.14, Android SDK 35
    uv run python -m pipeline.sites portal --deploy             # copia el APK al portal

La firma sale de `~/.android/cities-spain.properties` (fuera del repo); hay que conservar esa clave para que las
actualizaciones se instalen encima.

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
© IGN/CNIG (CC BY 4.0, scne.es); ortofoto PNOA © IGN; Wikidata CC0; fotos de Wikimedia Commons con su licencia; OpenStreetMap, ODbL.
