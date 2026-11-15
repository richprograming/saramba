"""
SARamba - baixa as imagens de previa (browse PNG) das cenas do config.yaml.

As previas sao publicas (nao precisam de login) e servem para conferir a cobertura
e escolher a area de interesse antes de baixar os .h5 de ~1,9 GB.
Saida: data/browse/<data>_LATLON.png e uma copia reduzida <data>_small.jpg.
"""

import csv
from pathlib import Path

import requests
import yaml
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
SAIDA = RAIZ / "data" / "browse"


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    o = CFG["orbita"]
    datas = CFG["datas"]
    with open(RAIZ / "nisar_cenas.csv", encoding="utf-8") as f:
        cenas = [r for r in csv.DictReader(f)
                 if r["path"] == str(o["path"]) and r["frame"] == str(o["frame"]) and r["data"] in datas]
    for c in sorted(cenas, key=lambda r: r["data"]):
        url = c["url"].replace("/NISAR/", "/BROWSE/").replace(".h5", "_LATLON.png")
        destino = SAIDA / f"{c['data']}_LATLON.png"
        if not destino.exists():
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            destino.write_bytes(r.content)
        im = Image.open(destino)
        print(c["data"], im.size, im.mode)
        escala = 1000 / max(im.size)
        im.convert("RGB").resize((int(im.width * escala), int(im.height * escala))).save(
            SAIDA / f"{c['data']}_small.jpg", quality=85)


if __name__ == "__main__":
    main()
