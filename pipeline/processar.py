"""
SARamba - pipeline: NISAR GCOV (.h5) -> PNG + JSON leves para o app.

Para cada data do config.yaml:
  1. recorta a area de interesse (bbox) na grade UTM do produto;
  2. reduz a resolucao por media em potencia (multilook) e filtra speckle (Lee 5x5);
  3. converte para dB (10*log10), mascarando zeros/NaN;
  4. classifica em agua aberta / floresta alagada / nao alagado a partir do HH.
Depois, com todas as datas:
  5. km2 por classe e por data, com faixa de incerteza (limiar +/- incerteza_db);
  6. mapa de transicao entre a primeira e a ultima data;
  7. mapa de duracao: em quantas datas cada pixel foi classificado como floresta alagada;
  8. serie de HH por pixel, em resolucao reduzida, para o clique no mapa;
  9. exporta tudo para app/public/data/.

Uso:  python pipeline/processar.py

Os limiares de classificacao sao calculados UMA vez, com os pixels de todas as datas juntos,
para que a comparacao entre datas use sempre a mesma regra. Ficam registrados em stats.json.
A classificacao usa so HH, entao cenas dual-pol (HH+HV) e so-HH entram juntas.
"""

import csv
import json
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
import yaml
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import uniform_filter
from skimage.filters import threshold_multiotsu

RAIZ = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
SAIDA = RAIZ / "app" / "public" / "data"
GRADE = "/science/LSAR/GCOV/grids/frequencyA"   # caminho real, ver docs/gcov_estrutura.md

# Codigos das classes e cores (RGBA) usadas no app.
NODATA, TERRA, AGUA, ALAGADA = 0, 1, 2, 3
CORES_CLASSES = {
    NODATA: (0, 0, 0, 0),
    TERRA: (110, 118, 129, 150),      # cinza
    AGUA: (47, 123, 255, 255),        # #2F7BFF
    ALAGADA: (18, 194, 176, 255),     # #12C2B0
}
# Transicao entre a primeira e a ultima data.
T_SEM, T_SEGUE_ALAGADA, T_SECOU, T_AGUA_RECUOU, T_ALAGOU = 0, 1, 2, 3, 4
CORES_TRANSICAO = {
    T_SEM: (0, 0, 0, 0),
    T_SEGUE_ALAGADA: (18, 194, 176, 255),   # continua alagada
    T_SECOU: (255, 176, 32, 255),           # #FFB020: floresta alagada -> nao alagada
    T_AGUA_RECUOU: (232, 93, 58, 255),      # agua aberta -> nao agua (praias, bancos de areia)
    T_ALAGOU: (47, 123, 255, 255),          # passou a ser agua/alagada
}
# Rampa do mapa de duracao: de "alagado em 1 data" (amarelo claro) a "em todas" (azul escuro).
RAMPA_DURACAO = [(254, 240, 170), (18, 194, 176), (20, 70, 160)]
# Faixas de exibicao em dB para os PNG em tons de cinza.
FAIXA_DB = {"hh": (-22.0, 0.0), "hv": (-28.0, -6.0)}
# Serie por pixel: reducao extra e faixa de dB codificada em 1 byte (0 = sem dado).
SERIE_FATOR, SERIE_DB = 4, (-25.0, 0.0)


def cenas(datas):
    o = CFG["orbita"]
    with open(RAIZ / "nisar_cenas.csv", encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f)
                  if r["path"] == str(o["path"]) and r["frame"] == str(o["frame"])
                  and r["direcao"] == o["direcao"] and r["data"] in datas]
    return sorted(linhas, key=lambda r: r["data"])


def janela(h5):
    """Indices (linhas, colunas) do bbox na grade do produto e os cantos reais do recorte em lon/lat."""
    g = h5[GRADE]
    epsg = int(g["projection"][()])
    x, y = g["xCoordinates"][:], g["yCoordinates"][:]
    lon0, lat0, lon1, lat1 = CFG["bbox"]
    para_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = para_utm.transform([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1])
    c0, c1 = np.searchsorted(x, min(xs)), np.searchsorted(x, max(xs))
    l0, l1 = np.searchsorted(-y, -max(ys)), np.searchsorted(-y, -min(ys))   # y decresce
    m = int(CFG.get("multilook", 2))
    l1 -= (l1 - l0) % m
    c1 -= (c1 - c0) % m
    if l1 <= l0 or c1 <= c0:
        sys.exit("O bbox do config.yaml nao cai dentro da cena.")
    dx, dy = abs(x[1] - x[0]), abs(y[1] - y[0])
    # Bordas externas do recorte (as coordenadas do produto sao centros de pixel).
    oeste, leste = x[c0] - dx / 2, x[c1 - 1] + dx / 2
    norte, sul = y[l0] + dy / 2, y[l1 - 1] - dy / 2
    para_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    # Ordem pedida pelo MapLibre: sup-esq, sup-dir, inf-dir, inf-esq.
    cantos = [list(para_ll.transform(px, py)) for px, py in
              [(oeste, norte), (leste, norte), (leste, sul), (oeste, sul)]]
    return (slice(l0, l1), slice(c0, c1)), cantos, epsg, (float(dx * m), float(dy * m))


def multilook(a, m):
    """Media em blocos m x m, ignorando NaN. Corta as sobras da borda."""
    if m == 1:
        return a
    h, w = a.shape[0] // m * m, a.shape[1] // m * m
    blocos = a[:h, :w].reshape(h // m, m, w // m, m)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # blocos so com NaN viram NaN
        return np.nanmean(blocos, axis=(1, 3))


def lee(pot, tam=5):
    """Filtro de Lee em potencia. Pixels invalidos (NaN) ficam fora das medias."""
    valido = np.isfinite(pot)
    p = np.where(valido, pot, 0.0)
    peso = uniform_filter(valido.astype(np.float32), tam)
    with np.errstate(invalid="ignore", divide="ignore"):
        media = uniform_filter(p, tam) / peso
        media2 = uniform_filter(p * p, tam) / peso
        var = np.maximum(media2 - media ** 2, 0)
        # Variancia relativa do ruido estimada pela mediana da cena (areas homogeneas dominam).
        cv2 = var / (media ** 2)
        ruido = np.nanmedian(cv2[valido])
        k = np.clip(1 - ruido * media ** 2 / var, 0, 1)
        k = np.where(var > 0, k, 0)
        saida = media + k * (p - media)
    return np.where(valido, saida, np.nan)


def para_db(pot):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(pot) & (pot > 0), 10 * np.log10(pot), np.nan)


def ler_data(cena):
    """Le o recorte de uma cena e devolve HH (e HV, se existir) em dB, ja filtrados."""
    arq = RAIZ / "data" / f"{cena['cena']}.h5"
    if not arq.exists():
        sys.exit(f"Falta o arquivo {arq.name}. Rode: python scripts/inspecionar_gcov.py --baixar")
    m = int(CFG.get("multilook", 2))
    with h5py.File(arq, "r") as h5:
        jan, cantos, epsg, pixel = janela(h5)
        g = h5[GRADE]
        valido = g["mask"][jan]
        valido = (valido != 0) & (valido != 255)
        bandas = {}
        for nome, ds in (("hh", "HHHH"), ("hv", "HVHV")):
            if ds not in g:
                continue   # cenas so-HH nao tem HVHV
            pot = g[ds][jan].astype(np.float32)
            pot[~valido | ~(pot > 0)] = np.nan
            bandas[nome] = para_db(lee(multilook(pot, m)))
    return bandas, cantos, epsg, pixel


def calibrar_limiares(hhs):
    """Limiares de HH (dB) calibrados pelo histograma de todas as datas juntas.

    - Agua aberta: Otsu de 2 classes (agua x resto), que cai no vale largo entre os dois picos.
    - Floresta alagada: o histograma do "resto" tem um pico dominante (floresta nao alagada) e
      uma cauda brilhante (double-bounce). O limiar e moda + k * sigma, com sigma medido so no
      lado ESQUERDO do pico, que nao e contaminado pela floresta alagada.
      (Otsu de 3 classes foi testado e descartado: corta abaixo do pico da floresta nao alagada.)

    Os valores do config.yaml sao o ponto de partida e limitam o resultado a +/- tolerancia_db.
    """
    ini = CFG["limiares_db"]
    tol, k = float(ini.get("tolerancia_db", 4.0)), float(ini.get("k_sigma", 2.0))
    rng = np.random.default_rng(0)
    por_data = 4_000_000 // len(hhs)   # mesma quantidade de pixels de cada data
    partes = []
    for h in hhs:
        v = h[np.isfinite(h)].ravel()
        partes.append(rng.choice(v, min(por_data, v.size), replace=False))
    amostra = np.clip(np.concatenate(partes), -30, 5)

    t_agua = float(threshold_multiotsu(amostra, classes=2, nbins=256)[0])
    resto = amostra[amostra > t_agua]
    cont, bordas = np.histogram(resto, bins=np.arange(t_agua, 5.0, 0.05))
    suave = np.convolve(cont, np.ones(5) / 5, "same")
    moda = float(bordas[suave.argmax()] + 0.025)
    esquerda = resto[(resto < moda) & (resto > moda - 2.0)]
    sigma = float(np.sqrt(np.mean((esquerda - moda) ** 2)))
    t_alag = moda + k * sigma

    usado_agua = float(np.clip(t_agua, ini["agua_aberta_hh_max"] - tol, ini["agua_aberta_hh_max"] + tol))
    usado_alag = float(np.clip(t_alag, ini["floresta_alagada_hh_min"] - tol, ini["floresta_alagada_hh_min"] + tol))
    return {
        "metodo": "agua: Otsu 2 classes no HH (dB); floresta alagada: moda da floresta nao alagada + k*sigma "
                  "(sigma do lado esquerdo do pico); todas as datas juntas",
        "ponto_de_partida": {"agua_aberta_hh_max": ini["agua_aberta_hh_max"],
                             "floresta_alagada_hh_min": ini["floresta_alagada_hh_min"]},
        "calibrado_bruto": {"agua_aberta_hh_max": round(t_agua, 2), "floresta_alagada_hh_min": round(t_alag, 2)},
        "usados": {"agua_aberta_hh_max": round(usado_agua, 2), "floresta_alagada_hh_min": round(usado_alag, 2)},
        "terra_firme_moda_db": round(moda, 2), "terra_firme_sigma_db": round(sigma, 2),
        "k_sigma": k, "tolerancia_db": tol, "incerteza_db": float(ini.get("incerteza_db", 0.5)),
    }


def classificar(hh, lim):
    c = np.full(hh.shape, TERRA, np.uint8)
    c[hh <= lim["agua_aberta_hh_max"]] = AGUA
    c[hh >= lim["floresta_alagada_hh_min"]] = ALAGADA
    c[~np.isfinite(hh)] = NODATA
    return c


def transicao(c_ini, c_fim):
    t = np.full(c_ini.shape, T_SEM, np.uint8)
    t[(c_ini == ALAGADA) & (c_fim == ALAGADA)] = T_SEGUE_ALAGADA
    t[(c_ini == ALAGADA) & (c_fim == TERRA)] = T_SECOU
    t[(c_ini == AGUA) & (c_fim != AGUA)] = T_AGUA_RECUOU
    t[(c_ini == TERRA) & ((c_fim == ALAGADA) | (c_fim == AGUA))] = T_ALAGOU
    t[(c_ini == NODATA) | (c_fim == NODATA)] = T_SEM
    return t


def cores_duracao(n):
    """Tabela de cores para contagens 0..n (0 = transparente), interpolando a rampa."""
    lut = np.zeros((256, 4), np.uint8)
    pontos = np.array(RAMPA_DURACAO, float)
    for i in range(1, n + 1):
        f = (i - 1) / max(n - 1, 1) * (len(pontos) - 1)
        a = min(int(f), len(pontos) - 2)
        lut[i, :3] = np.round(pontos[a] + (pontos[a + 1] - pontos[a]) * (f - a))
        lut[i, 3] = 255
    return lut


def salvar_cinza(db, faixa, destino):
    """PNG em tons de cinza + alfa (transparente onde nao ha dado)."""
    lo, hi = faixa
    v = np.clip((db - lo) / (hi - lo), 0, 1)
    cinza = np.where(np.isfinite(db), np.round(v * 255), 0).astype(np.uint8)
    alfa = np.where(np.isfinite(db), 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([cinza, alfa]), "LA").save(destino, optimize=True)


def salvar_paleta(codigos, cores, destino):
    if isinstance(cores, dict):
        lut = np.zeros((256, 4), np.uint8)
        for cod, cor in cores.items():
            lut[cod] = cor
    else:
        lut = cores
    Image.fromarray(lut[codigos], "RGBA").save(destino, optimize=True)


def salvar_serie(hhs, destino):
    """HH de todas as datas em resolucao reduzida, 1 byte por pixel (0 = sem dado)."""
    lo, hi = SERIE_DB
    camadas = []
    for hh in hhs:
        r = multilook(hh, SERIE_FATOR)
        b = 1 + np.round(np.clip((r - lo) / (hi - lo), 0, 1) * 254)
        camadas.append(np.where(np.isfinite(r), b, 0).astype(np.uint8))
    destino.write_bytes(np.stack(camadas).tobytes())
    return camadas[0].shape


def main():
    lista = cenas(CFG["datas"])
    if len(lista) < 2:
        sys.exit("Precisa de pelo menos 2 datas da mesma orbita.")
    SAIDA.mkdir(parents=True, exist_ok=True)
    for velho in list(SAIDA.glob("hh_*.png")) + list(SAIDA.glob("hv_*.png")) + list(SAIDA.glob("classes_*.png")):
        velho.unlink()

    dados, cantos, epsg, pixel = {}, None, None, None
    for c in lista:
        print(f"Lendo {c['data']} ({c['pol']}) ...")
        dados[c["data"]], cantos_c, epsg, pixel = ler_data(c)
        if cantos is not None and not np.allclose(cantos, cantos_c, atol=1e-6):
            sys.exit(f"A grade de {c['data']} nao coincide com a das outras datas.")
        cantos = cantos_c

    limiares = calibrar_limiares([d["hh"] for d in dados.values()])
    usados, inc = limiares["usados"], limiares["incerteza_db"]
    print("Limiares usados (dB):", usados)
    km2_px = pixel[0] * pixel[1] / 1e6
    km2 = lambda mascara: round(float(mascara.sum() * km2_px), 1)

    classes, por_data = {}, []
    for c in lista:
        d, b = c["data"], dados[c["data"]]
        hh = b["hh"]
        classes[d] = classificar(hh, usados)
        salvar_cinza(hh, FAIXA_DB["hh"], SAIDA / f"hh_{d}.png")
        if "hv" in b:
            salvar_cinza(b["hv"], FAIXA_DB["hv"], SAIDA / f"hv_{d}.png")
        salvar_paleta(classes[d], CORES_CLASSES, SAIDA / f"classes_{d}.png")
        t = usados["floresta_alagada_hh_min"]
        por_data.append({
            "data": d, "cena": c["cena"], "pol": c["pol"], "tem_hv": "hv" in b,
            "km2": {"agua_aberta": km2(classes[d] == AGUA), "floresta_alagada": km2(classes[d] == ALAGADA),
                    "terra_firme": km2(classes[d] == TERRA), "sem_dado": km2(classes[d] == NODATA)},
            # Mesma classificacao com o limiar mais exigente (+inc) e menos exigente (-inc).
            "floresta_alagada_faixa_km2": [km2(hh >= t + inc), km2(hh >= t - inc)],
            "hh_db_mediana": round(float(np.nanmedian(hh)), 2),
        })
        print(f"  {d}: alagada {por_data[-1]['km2']['floresta_alagada']} km2 "
              f"(faixa {por_data[-1]['floresta_alagada_faixa_km2']}), agua {por_data[-1]['km2']['agua_aberta']} km2")

    d_ini, d_fim = lista[0]["data"], lista[-1]["data"]
    t = transicao(classes[d_ini], classes[d_fim])
    salvar_paleta(t, CORES_TRANSICAO, SAIDA / "transicao.png")

    # Duracao: em quantas datas o pixel foi classificado como floresta alagada.
    n = len(lista)
    contagem = np.sum([classes[c["data"]] == ALAGADA for c in lista], axis=0).astype(np.uint8)
    salvar_paleta(contagem, cores_duracao(n), SAIDA / "duracao.png")

    alt_s, larg_s = salvar_serie([dados[c["data"]]["hh"] for c in lista], SAIDA / "serie_hh.bin")

    altura, largura = t.shape
    (SAIDA / "bounds.json").write_text(json.dumps({
        "cantos_lonlat": cantos,
        "ordem": "superior-esquerdo, superior-direito, inferior-direito, inferior-esquerdo",
        "epsg_origem": epsg, "pixel_m": list(pixel), "largura": largura, "altura": altura,
    }, indent=2), encoding="utf-8")
    (SAIDA / "stats.json").write_text(json.dumps({
        "regiao": CFG["regiao"], "orbita": CFG["orbita"], "bbox": CFG["bbox"],
        "produto": "NISAR L2 GCOV (provisorio), frequencia A, gamma0 com correcao de terreno",
        "faixa_db_png": FAIXA_DB, "limiares": limiares, "datas": por_data,
        "transicao": {
            "de": d_ini, "ate": d_fim,
            "km2": {"segue_alagada": km2(t == T_SEGUE_ALAGADA), "alagada_para_terra_firme": km2(t == T_SECOU),
                    "agua_aberta_recuou": km2(t == T_AGUA_RECUOU), "passou_a_agua_ou_alagada": km2(t == T_ALAGOU)},
        },
        "duracao": {
            "n_datas": n,
            # km2_por_contagem[i] = area classificada como alagada em exatamente i datas.
            "km2_por_contagem": [km2(contagem == i) for i in range(n + 1)],
            "km2_alguma_vez": km2(contagem > 0),
            "rampa_rgb": RAMPA_DURACAO,
        },
        "serie": {
            "arquivo": "serie_hh.bin", "largura": int(larg_s), "altura": int(alt_s), "fator": SERIE_FATOR,
            "db_min": SERIE_DB[0], "db_max": SERIE_DB[1],
            "nota": "uint8 por pixel, uma camada por data na ordem de `datas`; 0 = sem dado; "
                    "dB = db_min + (v - 1) / 254 * (db_max - db_min)",
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(f.stat().st_size for f in SAIDA.iterdir()) / 1e6
    print(f"Saidas em {SAIDA} ({largura}x{altura} px, {n} datas, {total:.1f} MB no total)")


if __name__ == "__main__":
    main()
