"""
SARamba - Etapa 2: acessar e inspecionar as cenas NISAR GCOV escolhidas.

Dois modos:
  python scripts/inspecionar_gcov.py            # remoto: le so a estrutura via HTTP (rapido, poucos MB)
  python scripts/inspecionar_gcov.py --baixar   # baixa os .h5 inteiros para data/ (1,5 a 1,9 GB cada)

Em ambos, grava docs/gcov_estrutura.md com os caminhos reais encontrados no arquivo.

Precisa do token do Earthdata na variavel de ambiente EARTHDATA_TOKEN
(gere em https://urs.earthdata.nasa.gov -> Generate Token). Nunca coloque o token no codigo.
"""

import csv
import os
import sys
from pathlib import Path

import h5py
import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))


def token():
    t = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not t:
        sys.exit("Defina a variavel de ambiente EARTHDATA_TOKEN antes de rodar.")
    return t


def cenas_escolhidas(datas):
    """Linhas de nisar_cenas.csv que batem com a orbita e as datas do config.yaml."""
    o = CFG["orbita"]
    with open(RAIZ / "nisar_cenas.csv", encoding="utf-8") as f:
        linhas = [
            r for r in csv.DictReader(f)
            if r["path"] == str(o["path"]) and r["frame"] == str(o["frame"])
            and r["direcao"] == o["direcao"] and r["data"] in datas
        ]
    faltando = set(datas) - {r["data"] for r in linhas}
    if faltando:
        sys.exit(f"Datas sem cena na orbita: {sorted(faltando)}")
    return sorted(linhas, key=lambda r: r["data"])


def url_assinada(url):
    """Troca a URL do ASF por uma URL temporaria (assinada) que aceita leitura por faixas de bytes."""
    r = requests.get(url, headers={"Authorization": f"Bearer {token()}"}, allow_redirects=False, timeout=60)
    destino = r.headers.get("Location", "")
    if r.status_code in (301, 302, 303, 307) and "urs.earthdata.nasa.gov" not in destino:
        return destino
    if r.status_code == 200:
        return url
    sys.exit(f"Acesso negado (HTTP {r.status_code}). Confira o token e se aceitou os termos do ASF no Earthdata.")


def abrir_remoto(url):
    import fsspec
    fs = fsspec.filesystem("http", block_size=4 * 1024 * 1024)
    return h5py.File(fs.open(url_assinada(url), "rb"), "r")


def baixar(cena):
    destino = RAIZ / "data" / f"{cena['cena']}.h5"
    if destino.exists() and destino.stat().st_size > 1e8:
        print(f"Ja existe: {destino.name}")
        return destino
    destino.parent.mkdir(exist_ok=True)
    parcial = destino.with_suffix(".h5.part")
    with requests.get(url_assinada(cena["url"]), stream=True, timeout=120) as r:
        r.raise_for_status()
        total, feito = int(r.headers.get("Content-Length", 0)), 0
        with open(parcial, "wb") as f:
            for bloco in r.iter_content(8 * 1024 * 1024):
                f.write(bloco)
                feito += len(bloco)
                if total:
                    print(f"\r{cena['data']}: {feito / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)
    print()
    parcial.rename(destino)
    return destino


def descrever(h5, nome_cena):
    """Percorre o arquivo e devolve o texto markdown com grupos, datasets, formas e atributos principais."""
    linhas = [f"## {nome_cena}", "", "| Caminho | Forma | Tipo | Chunks |", "|---|---|---|---|"]

    def visita(nome, obj):
        if isinstance(obj, h5py.Dataset):
            linhas.append(f"| `/{nome}` | {obj.shape} | {obj.dtype} | {obj.chunks} |")

    h5.visititems(visita)

    # Destaques: grade da frequencia A, onde ficam HHHH / HVHV e as coordenadas.
    linhas += ["", "### Grade da frequencia A", ""]
    grades = [n for n in _grupos(h5) if n.endswith("grids/frequencyA")]
    for g in grades:
        linhas.append(f"Grupo: `/{g}`")
        for nome, ds in h5[g].items():
            if isinstance(ds, h5py.Dataset):
                extra = ""
                if ds.shape == () or ds.size <= 4:
                    extra = f" = `{ds[()]}`"
                elif ds.ndim == 1:
                    extra = f" de `{ds[0]}` a `{ds[-1]}`"
                atrs = {k: _txt(v) for k, v in ds.attrs.items() if k in ("units", "_FillValue", "description", "long_name")}
                linhas.append(f"- `{nome}` {ds.shape} {ds.dtype}{extra} {atrs if atrs else ''}")
    return "\n".join(linhas)


def _grupos(h5):
    nomes = []
    h5.visititems(lambda n, o: nomes.append(n) if isinstance(o, h5py.Group) else None)
    return nomes


def _txt(v):
    return v.decode() if isinstance(v, bytes) else str(v)


def main():
    modo_baixar = "--baixar" in sys.argv
    datas = CFG["datas"]
    cenas = cenas_escolhidas(datas)
    partes = [
        "# Estrutura real dos arquivos NISAR GCOV usados",
        "",
        "Gerado por `scripts/inspecionar_gcov.py`. Caminhos lidos do arquivo, nao da documentacao.",
        "",
    ]
    for i, c in enumerate(cenas):
        print(f"{c['data']}  {c['cena']}")
        h5 = h5py.File(baixar(c), "r") if modo_baixar else abrir_remoto(c["url"])
        if i == 0:  # a estrutura e a mesma entre datas da mesma orbita; documenta a primeira por inteiro
            partes.append(descrever(h5, c["cena"]))
        else:
            partes += ["", f"## {c['cena']}", "", "Mesma orbita; datasets da frequencia A:", ""]
            for g in [n for n in _grupos(h5) if n.endswith("grids/frequencyA")]:
                partes += [f"- `/{g}/{n}` {d.shape}" for n, d in h5[g].items() if isinstance(d, h5py.Dataset)]
        h5.close()
    saida = RAIZ / "docs" / "gcov_estrutura.md"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text("\n".join(partes) + "\n", encoding="utf-8")
    print(f"Estrutura documentada em {saida}")


if __name__ == "__main__":
    main()
