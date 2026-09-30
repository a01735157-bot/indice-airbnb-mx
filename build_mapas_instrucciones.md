# Cómo regenerar los mapas (ageb.geojson / alcaldias.geojson)

Estos dos scripts cruzan los anuncios de Airbnb (`data/listings/*.json`) contra
los polígonos oficiales de INEGI y calculan precio mediano/promedio por zona:

- `build_ageb.py` → genera `data/ageb.geojson` (las 60 ciudades, nivel AGEB)
- `build_alcaldias.py` → genera `data/alcaldias.geojson` (solo CDMX, nivel alcaldía)

No hace falta correrlos para que los mapas funcionen — `data/ageb.geojson` y
`data/alcaldias.geojson` ya están en el repo, listos. Esto es solo para
cuando haya una ronda de scraping nueva y haya que refrescar los mapas.

## 1. Instalar dependencias

```bash
pip install shapely pyshp pyproj
```

## 2. Descargar el paquete de INEGI

1. Ir a <https://www.inegi.org.mx/temas/mg/#Descargas>
2. Colección: **Marco geoestadístico** (ya viene así por default)
3. Click en **Consultar**
4. En la tabla de resultados, buscar la fila **"Marco Geoestadístico 2025"**
   (edición 2025, ~2.7 GB) y click en el botón morado **SHP**
5. El archivo descargado va a tener un nombre críptico distinto cada vez
   (INEGI le pone un ID interno, ej. `794551163061_s.zip`). **Renombrarlo a:**

   ```
   ~/Downloads/inegi_marco_geoestadistico_2025.zip
   ```

   Si no se renombra exactamente así, los scripts no lo van a encontrar
   (buscan ese nombre fijo en `PAQUETE_NACIONAL`, arriba de `build_ageb.py`).

## 3. Correr los scripts

Desde la carpeta del repo (`repo_indice_airbnb/` o como se llame tu clon):

```bash
python3 build_ageb.py
python3 build_alcaldias.py
```

La primera corrida tarda varios minutos: descomprime ~31 shapefiles
(uno por estado) dentro del zip de 2.7 GB y cruza cada anuncio por
coordenada contra los polígonos. Corridas siguientes son más rápidas
porque cachea los shapefiles ya extraídos en `~/Downloads/mg2025_extracted/`.

Al terminar, quedan actualizados `data/ageb.geojson` y
`data/alcaldias.geojson` — hacer commit y push normal de esos dos archivos.

## Notas

- Si `data/listings/*.json` cambió (nueva ronda de scraping), hay que volver
  a correr ambos scripts para que los mapas reflejen los datos nuevos.
- El umbral mínimo de anuncios por AGEB es 3 (`MIN_LISTINGS_POR_AGEB` en
  `build_ageb.py`) — AGEB con menos se descartan por dato poco confiable.
- Holbox queda sin cobertura en el mapa por AGEB: INEGI todavía no lo
  clasifica como localidad urbana pese al turismo. No es un bug del script.
