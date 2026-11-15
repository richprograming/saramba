"""
SARamba - imagem optica Sentinel-2 L2A (cor verdadeira) na MESMA grade dos PNG de radar.

Busca no STAC publico Earth Search (AWS), sem login, e reamostra o asset `visual` (TCI)
para o recorte definido em app/public/data/bounds.json (gerado por processar.py).

Uso:
  python pipeline/optico.py --listar                 # mostra as datas e a % de nuvem no recorte
  python pipeline/optico.py --data 2026-06-10        # grava optico.png + optico.json no app
  python pipeline/optico.py --data 2026-06-10 --previa   # grava so em data/optico_previa/
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio
import requests
import yaml
from PIL import Image
from pyproj import Transformer
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

RAIZ = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
SAIDA = RAIZ / "app" / "public" / "data"
STAC = "https://earth-search.aws.element84.com/v1/search"
GDAL = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="1")
# Classes do SCL (Scene Classification) contadas como nuvem: sombra, nuvem media/alta, cirrus.
SCL_NUVEM = (3, 8, 9, 10)


def grade():
    """Grade de destino: a mesma do recorte de radar (EPSG, transformacao afim, largura, altura)."""
    b = json.loads((SAIDA / "bounds.json").read_text(encoding="utf-8"))
    t = Transformer.from_crs(4326, b["epsg_origem"], always_xy=True)
    (oeste, norte), (leste, sul) = t.transform(*b["cantos_lonlat"][0]), t.transform(*b["cantos_lonlat"][2])
    return b["epsg_origem"], from_bounds(oeste, sul, leste, norte, b["largura"], b["altura"]), b["largura"], b["altura"]


def buscar(inicio, fim):
    r = requests.post(STAC, json={"collections": ["sentinel-2-l2a"], "bbox": CFG["bbox"],
                                  "datetime": f"{inicio}T00:00:00Z/{fim}T23:59:59Z", "limit": 200}, timeout=120)
    r.raise_for_status()
    por_data = defaultdict(list)
    for f in r.json()["features"]:
        por_data[f["properties"]["datetime"][:10]].append(f)
    return dict(sorted(por_data.items()))


def reamostrar(itens, asset, bandas, metodo):
    """Mosaico dos tiles de uma data, reamostrado para a grade do radar. Zero = sem dado."""
    epsg, afim, larg, alt = grade()
    saida = np.zeros((bandas, alt, larg), np.uint8)
    with rasterio.Env(**GDAL):
        for it in itens:
            with rasterio.open(it["assets"][asset]["href"]) as src:
                parcial = np.zeros_like(saida)
                reproject(rasterio.band(src, list(range(1, bandas + 1))), parcial, dst_transform=afim,
                          dst_crs=f"EPSG:{epsg}", resampling=metodo, src_nodata=0, dst_nodata=0)
                vazio = saida.max(axis=0) == 0
                saida[:, vazio] = parcial[:, vazio]
    return saida


def nuvem_no_recorte(itens):
    scl = reamostrar(itens, "scl", 1, Resampling.nearest)[0]
    valido = scl > 0
    return (float(np.isin(scl, SCL_NUVEM).sum()) / max(int(valido.sum()), 1) * 100, float(valido.mean() * 100))


def main():
    args = sys.argv[1:]
    primeira = CFG["datas"][0]
    if "--listar" in args:
        ano, mes = primeira[:4], int(primeira[5:7])
        datas = buscar(f"{ano}-{mes - 1:02d}-15", f"{ano}-{mes + 1:02d}-20")
        print("data        nuvem_no_recorte  cobertura  tiles (nuvem do tile inteiro)")
        for d, itens in datas.items():
            nuvem, cobre = nuvem_no_recorte(itens)
            tiles = ", ".join(f"{i['id'].split('_')[1]} {i['properties']['eo:cloud_cover']:.0f}%" for i in itens)
            print(f"{d}      {nuvem:5.1f}%        {cobre:5.1f}%   {tiles}")
        return

    if "--data" not in args:
        sys.exit(__doc__)
    data = args[args.index("--data") + 1]
    itens = buscar(data, data).get(data)
    if not itens:
        sys.exit(f"Nenhuma cena Sentinel-2 em {data}.")
    rgb = reamostrar(itens, "visual", 3, Resampling.average)
    nuvem, cobre = nuvem_no_recorte(itens)
    destino = (RAIZ / "data" / "optico_previa") if "--previa" in args else SAIDA
    destino.mkdir(parents=True, exist_ok=True)
    nome = f"optico_{data}.png" if "--previa" in args else "optico.png"
    alfa = np.where(rgb.max(axis=0) > 0, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([*rgb, alfa]), "RGBA").save(destino / nome, optimize=True)
    if "--previa" not in args:
        (SAIDA / "optico.json").write_text(json.dumps({
            "data": data, "fonte": "ESA Copernicus Sentinel-2 L2A (cor verdadeira, TCI), via Earth Search / AWS",
            "cenas": [i["id"] for i in itens],
            "nuvem_no_recorte_pct": round(nuvem, 1), "cobertura_do_recorte_pct": round(cobre, 1),
            "nota": "Nuvem = classes SCL 3, 8, 9 e 10 (sombra, nuvem media/alta, cirrus).",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{destino / nome}: nuvem {nuvem:.1f}% | cobertura {cobre:.1f}%")


if __name__ == "__main__":
    main()
