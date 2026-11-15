"""
SARamba - busca automatica de cenas NISAR GCOV (NASA Space Apps 2026)

O que faz:
  1. Procura cenas NISAR GCOV nas 3 regioes candidatas (Anavilhanas, Mamiraua, Pantanal)
     desde 17/06/2026 (inicio dos produtos calibrados).
  2. Agrupa por orbita (path + frame + direcao), porque so cenas da MESMA orbita
     podem ser comparadas entre datas.
  3. Diz qual regiao/orbita tem mais datas e salva tudo em nisar_cenas.csv.
  4. (Opcional) Baixa ate 4 cenas espalhadas no tempo da melhor orbita.

Como rodar no Google Colab:
  - Celula 1:  !pip install -q asf_search
  - Celula 2:  cole este arquivo inteiro e rode
  - Para baixar: defina BAIXAR = True e cole seu token do Earthdata em EARTHDATA_TOKEN
    (gere em https://urs.earthdata.nasa.gov -> Generate Token)

A busca NAO precisa de login. So o download precisa.
"""

import csv
from collections import defaultdict

import asf_search as asf

INICIO = "2026-06-17"
BAIXAR = False          # mude para True para baixar as cenas
EARTHDATA_TOKEN = ""    # cole o token aqui se BAIXAR = True
MAX_DOWNLOADS = 4

# Retangulos aproximados (lon, lat). Ajuste se quiser.
REGIOES = {
    "Anavilhanas (Rio Negro)": (-61.20, -3.00, -60.40, -2.30),
    "Mamiraua (Solimoes)": (-65.00, -3.20, -64.30, -2.50),
    "Pantanal (Corumba)": (-57.60, -19.40, -56.60, -18.40),
}


def wkt(b):
    x1, y1, x2, y2 = b
    return f"POLYGON(({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"


def eh_gcov(p):
    campos = [p.get("processingLevel"), p.get("fileID"), p.get("sceneName"), p.get("fileName")]
    return any(c and "GCOV" in str(c).upper() for c in campos)


def tamanho_mb(p):
    """Tamanho do .h5 principal. O ASF devolve 'bytes' como dict {arquivo: {bytes, format}}."""
    b = p.get("bytes")
    if isinstance(b, dict):
        principal = f"{p.get('fileID')}.h5"
        if principal in b:
            b = b[principal].get("bytes")
        else:
            b = max((v.get("bytes") or 0 for v in b.values() if v.get("format") == "HDF5"), default=0)
    return round((b or 0) / 1e6, 1)


def polarizacao(p):
    """Extrai modo e polarizacao do nome da cena (ex.: 2005_DHDH = dual HH+HV; SHSH = so HH)."""
    partes = str(p.get("sceneName") or p.get("fileID") or "").split("_")
    # NISAR_L2_PR_GCOV_ciclo_path_dir_frame_MODO_POL_...
    return (partes[8], partes[9]) if len(partes) > 9 else ("?", "?")


def buscar(nome, bbox):
    res = asf.search(dataset=asf.DATASET.NISAR, processingLevel="GCOV",
                     intersectsWith=wkt(bbox), start=INICIO)
    gcov = [r for r in res if eh_gcov(r.properties)]
    grupos = defaultdict(list)
    for r in gcov:
        p = r.properties
        chave = (p.get("pathNumber"), p.get("frameNumber"), p.get("flightDirection"))
        grupos[chave].append(r)
    print(f"\n=== {nome} ===")
    print(f"Resultados NISAR: {len(res)} | GCOV: {len(gcov)}")
    if not gcov and res:
        tipos = sorted({str(r.properties.get('processingLevel')) for r in res})
        print(f"Nenhum GCOV identificado. Tipos encontrados: {tipos}")
    for (path, frame, dirc), itens in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        datas = sorted({str(i.properties.get("startTime"))[:10] for i in itens})
        pols = sorted({polarizacao(i.properties)[1] for i in itens})
        print(f"  path {path} frame {frame} {dirc} [{'/'.join(pols)}]: {len(datas)} datas -> {', '.join(datas)}")
    return grupos


def main():
    linhas, melhor = [], None
    for nome, bbox in REGIOES.items():
        grupos = buscar(nome, bbox)
        for (path, frame, dirc), itens in grupos.items():
            datas = sorted({str(i.properties.get("startTime"))[:10] for i in itens})
            if melhor is None or len(datas) > melhor[0]:
                melhor = (len(datas), nome, path, frame, dirc, itens)
            for i in itens:
                p = i.properties
                linhas.append({
                    "regiao": nome, "path": path, "frame": frame, "direcao": dirc,
                    "data": str(p.get("startTime"))[:10], "cena": p.get("sceneName") or p.get("fileID"),
                    "modo": polarizacao(p)[0], "pol": polarizacao(p)[1],
                    "tamanho_MB": tamanho_mb(p), "url": p.get("url"),
                })

    with open("nisar_cenas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["regiao", "path", "frame", "direcao", "data", "cena", "modo", "pol", "tamanho_MB", "url"])
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda l: (l["regiao"], l["data"])))
    print("\nTabela completa salva em nisar_cenas.csv")

    if not melhor:
        print("\nNenhuma cena GCOV encontrada. Mande este resultado para revisar a busca.")
        return

    n, nome, path, frame, dirc, itens = melhor
    print(f"\nMELHOR OPCAO: {nome}, path {path} frame {frame} {dirc}, com {n} datas.")
    print("Regra: 3 ou mais datas da mesma orbita = regiao confirmada." if n >= 3
          else "Menos de 3 datas: considere outra regiao ou ampliar a area.")

    if BAIXAR:
        if not EARTHDATA_TOKEN:
            print("Defina EARTHDATA_TOKEN para baixar.")
            return
        sessao = asf.ASFSession().auth_with_token(EARTHDATA_TOKEN)
        itens = sorted(itens, key=lambda i: str(i.properties.get("startTime")))
        passo = max(1, len(itens) // MAX_DOWNLOADS)
        escolhidas = itens[::passo][:MAX_DOWNLOADS]
        print(f"Baixando {len(escolhidas)} cenas para ./dados ...")
        import os
        os.makedirs("dados", exist_ok=True)
        asf.ASFSearchResults(escolhidas).download(path="dados", session=sessao)
        print("Download concluido.")


if __name__ == "__main__":
    main()
