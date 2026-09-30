"""
Construye data/ageb.geojson: precio mediano/promedio por AGEB urbana de INEGI,
uniendo los listings (data/listings/<slug>.json) contra los poligonos de AGEB
del Marco Geoestadistico 2025 de INEGI (paquete nacional integrado).

Requiere: shapely, pyshp, pyproj (pip install shapely pyshp pyproj).

Los shapefiles del paquete 2025 vienen en la proyeccion Lambert Conforme
Conica que usa INEGI (metros, no grados), asi que cada poligono se reproyecta
a WGS84 (lat/lon) antes de compararlo contra las coordenadas de los listings.

Uso:
    python3 build_ageb.py
"""
import io
import json
import statistics
import zipfile
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import Point, shape, mapping
from shapely.ops import transform as shp_transform
from shapely.strtree import STRtree

# Lambert Conforme Conica de INEGI (ver el .prj de cualquier NNa.shp del paquete 2025)
_INEGI_LCC = (
    "+proj=lcc +lat_1=17.5 +lat_2=29.5 +lat_0=12.0 +lon_0=-102.0 "
    "+x_0=2500000 +y_0=0 +ellps=GRS80 +units=m +no_defs"
)
_TRANSFORMER = Transformer.from_crs(_INEGI_LCC, "EPSG:4326", always_xy=True)


def reproyectar(geom):
    return shp_transform(lambda x, y: _TRANSFORMER.transform(x, y), geom)

ROOT = Path(__file__).parent
# INEGI le pone a este archivo un nombre críptico distinto cada vez que se
# descarga (ej. "794551163061_s.zip"); hay que renombrarlo a este nombre fijo
# despues de bajarlo. Ver instrucciones en build_mapas_instrucciones.md.
PAQUETE_NACIONAL = Path.home() / "Downloads" / "inegi_marco_geoestadistico_2025.zip"
WORKDIR = Path.home() / "Downloads" / "mg2025_extracted"
MIN_LISTINGS_POR_AGEB = 3
SIMPLIFY_TOLERANCE = 0.00015  # ~15m, reduce vertices sin deformar la forma

CODIGO_ESTADO = {
    "Aguascalientes": "01", "Baja California": "02", "Baja California Sur": "03",
    "Campeche": "04", "Coahuila": "05", "Colima": "06", "Chiapas": "07",
    "Chihuahua": "08", "Ciudad de México": "09", "Durango": "10",
    "Guanajuato": "11", "Guerrero": "12", "Hidalgo": "13", "Jalisco": "14",
    "Estado de México": "15", "Michoacán": "16", "Morelos": "17", "Nayarit": "18",
    "Nuevo León": "19", "Oaxaca": "20", "Puebla": "21", "Querétaro": "22",
    "Quintana Roo": "23", "San Luis Potosí": "24", "Sinaloa": "25", "Sonora": "26",
    "Tabasco": "27", "Tamaulipas": "28", "Tlaxcala": "29", "Veracruz": "30",
    "Yucatán": "31", "Zacatecas": "32",
}


def extraer_shapefiles_estado(nombre_estado: str) -> Path:
    """Descomprime (si hace falta) el zip del estado dentro del paquete
    nacional 794551163061_s.zip y devuelve la carpeta con los .shp sueltos."""
    cve = CODIGO_ESTADO[nombre_estado]
    destino = WORKDIR / cve
    if destino.exists():
        return destino
    destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(PAQUETE_NACIONAL) as z_nacional:
        inner_name = next(n for n in z_nacional.namelist() if n.startswith(f"{cve}_"))
        data = z_nacional.read(inner_name)
        with zipfile.ZipFile(io.BytesIO(data)) as z_estado:
            for n in z_estado.namelist():
                if n.startswith("conjunto_de_datos/") and not n.endswith("/"):
                    z_estado.extract(n, destino)
    # aplanar conjunto_de_datos/ -> destino/
    sub = destino / "conjunto_de_datos"
    if sub.exists():
        for f in sub.iterdir():
            f.rename(destino / f.name)
        sub.rmdir()
    return destino


def cargar_agebs(carpeta: Path, cve_estado: str):
    """Devuelve (lista_de_poligonos_shapely_con_cvegeo, dict cve_mun->nombre)."""
    sf_ageb = shapefile.Reader(str(carpeta / f"{cve_estado}a"), encoding="latin-1")
    poligonos = []
    for sr in sf_ageb.iterShapeRecords():
        geom = shape(sr.shape.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        geom = reproyectar(geom)
        poligonos.append((geom, sr.record["CVEGEO"]))

    municipios = {}
    mun_path = carpeta / f"{cve_estado}mun"
    if mun_path.with_suffix(".shp").exists():
        sf_mun = shapefile.Reader(str(mun_path), encoding="latin-1")
        for r in sf_mun.records():
            municipios[r["CVE_ENT"] + r["CVE_MUN"]] = r["NOMGEO"]
    return poligonos, municipios


def main():
    cities = json.loads((ROOT / "data" / "cities.json").read_text(encoding="utf-8"))
    por_estado = {}
    for c in cities:
        por_estado.setdefault(c["state"], []).append(c)

    # acumulador: cvegeo -> {"precios": [...], "municipio_nombre": str}
    acumulado = {}

    for estado, ciudades in sorted(por_estado.items()):
        print(f"=== {estado} ({len(ciudades)} ciudades) ===")
        carpeta = extraer_shapefiles_estado(estado)
        poligonos, municipios = cargar_agebs(carpeta, CODIGO_ESTADO[estado])
        geoms = [p[0] for p in poligonos]
        tree = STRtree(geoms)
        idx_to_cvegeo = {i: poligonos[i][1] for i in range(len(poligonos))}

        for c in ciudades:
            listings_path = ROOT / "data" / "listings" / f"{c['id']}.json"
            if not listings_path.exists():
                print(f"  (sin archivo de listings para {c['id']}, se salta)")
                continue
            puntos = json.loads(listings_path.read_text(encoding="utf-8"))
            asignados = 0
            for lat, lon, precio in puntos:
                if precio is None:
                    continue
                pt = Point(lon, lat)
                candidatos = tree.query(pt)
                cvegeo = None
                for i in candidatos:
                    i = int(i)
                    if geoms[i].contains(pt):
                        cvegeo = idx_to_cvegeo[i]
                        break
                if cvegeo is None:
                    continue
                asignados += 1
                entry = acumulado.setdefault(cvegeo, {"precios": [], "city_ids": set()})
                entry["precios"].append(precio)
                entry["city_ids"].add(c["id"])
            print(f"  {c['city']:30s} {asignados}/{len(puntos)} anuncios asignados a un AGEB")

    # construir features finales
    features = []
    total_agebs_con_datos = 0
    for estado, ciudades in sorted(por_estado.items()):
        carpeta = extraer_shapefiles_estado(estado)
        poligonos, municipios = cargar_agebs(carpeta, CODIGO_ESTADO[estado])
        for geom, cvegeo in poligonos:
            entry = acumulado.get(cvegeo)
            if not entry or len(entry["precios"]) < MIN_LISTINGS_POR_AGEB:
                continue
            precios = entry["precios"]
            cve_mun = cvegeo[:5]
            nombre_mun = municipios.get(cve_mun, cve_mun)
            ageb_id = cvegeo[-4:]
            geom_simpl = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            features.append({
                "type": "Feature",
                "properties": {
                    "cvegeo": cvegeo,
                    "nombre": f"{nombre_mun} · AGEB {ageb_id}",
                    "estado": estado,
                    "city_ids": sorted(entry["city_ids"]),
                    "n": len(precios),
                    "price_median": round(statistics.median(precios), 2),
                    "price_mean": round(statistics.mean(precios), 2),
                },
                "geometry": mapping(geom_simpl),
            })
            total_agebs_con_datos += 1

    geojson = {"type": "FeatureCollection", "features": features}
    out_path = ROOT / "data" / "ageb.geojson"
    out_path.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n{total_agebs_con_datos} AGEB con >= {MIN_LISTINGS_POR_AGEB} anuncios -> {out_path}")
    print(f"tamano del archivo: {out_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
