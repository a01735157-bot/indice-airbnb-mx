"""
Reconstruye data/alcaldias.geojson: precio mediano/promedio por alcaldia de
CDMX, usando la capa de municipios (que para CDMX son las 16 alcaldias) del
Marco Geoestadistico 2025 de INEGI. Reemplaza la version anterior, que citaba
INEGI 2020, para que todo el sitio use la misma edicion.

Requiere: shapely, pyshp, pyproj (las mismas que build_ageb.py).

Uso:
    python3 build_alcaldias.py
"""
import json
import statistics

from shapely.geometry import Point, shape, mapping
from shapely.strtree import STRtree
import shapefile

from build_ageb import ROOT, CODIGO_ESTADO, extraer_shapefiles_estado, reproyectar

CVE_CDMX = CODIGO_ESTADO["Ciudad de México"]
MIN_LISTINGS_POR_ALCALDIA = 1


def main():
    carpeta = extraer_shapefiles_estado("Ciudad de México")
    sf_mun = shapefile.Reader(str(carpeta / f"{CVE_CDMX}mun"), encoding="latin-1")

    poligonos = []
    for sr in sf_mun.iterShapeRecords():
        geom = shape(sr.shape.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        geom = reproyectar(geom)
        poligonos.append((geom, sr.record["NOMGEO"]))

    geoms = [p[0] for p in poligonos]
    tree = STRtree(geoms)
    idx_to_nombre = {i: poligonos[i][1] for i in range(len(poligonos))}

    puntos = json.loads(
        (ROOT / "data" / "listings" / "ciudad-de-mexico-ciudad-de-mexico.json").read_text(encoding="utf-8")
    )
    acumulado = {}
    fuera = 0
    for lat, lon, precio in puntos:
        if precio is None:
            continue
        pt = Point(lon, lat)
        candidatos = tree.query(pt)
        nombre = None
        for i in candidatos:
            i = int(i)
            if geoms[i].contains(pt):
                nombre = idx_to_nombre[i]
                break
        if nombre is None:
            fuera += 1
            continue
        acumulado.setdefault(nombre, []).append(precio)

    print(f"{fuera}/{len(puntos)} anuncios ({fuera/len(puntos)*100:.1f}%) cayeron fuera de las 16 alcaldias")

    features = []
    for geom, nombre in poligonos:
        precios = acumulado.get(nombre, [])
        if len(precios) < MIN_LISTINGS_POR_ALCALDIA:
            continue
        geom_simpl = geom.simplify(0.00005, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "nombre": nombre,
                "n": len(precios),
                "price_median": round(statistics.median(precios), 2),
                "price_mean": round(statistics.mean(precios), 2),
            },
            "geometry": mapping(geom_simpl),
        })

    geojson = {"type": "FeatureCollection", "features": features}
    out_path = ROOT / "data" / "alcaldias.geojson"
    out_path.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(features)} alcaldias -> {out_path}")
    print(f"tamano del archivo: {out_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
