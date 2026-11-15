"""
SARamba - cota (nivel) do Rio Negro em Manaus, para cruzar com a area alagada.

Fonte oficial: ANA (Agencia Nacional de Aguas e Saneamento Basico), servico publico de telemetria,
estacao 14990000 (Manaus). O servico devolve leituras a cada 15 min ou 1 h, em centimetros;
aqui viram media diaria em metros.

Uso:  python pipeline/cota.py
Saida: app/public/data/cota.json  e  data/cota_manual.csv (mesmos valores, cabecalho data,cota_m)

Se o servico estiver fora do ar, preencha data/cota_manual.csv a mao e rode com --manual.
"""

import csv
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
SAIDA = RAIZ / "app" / "public" / "data"
MANUAL = RAIZ / "data" / "cota_manual.csv"
ESTACAO = "14990000"
URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"


def baixar(inicio, fim):
    """Leituras brutas {dia: [nivel_cm, ...]} entre duas datas, em blocos de 30 dias."""
    por_dia = defaultdict(list)
    d = inicio
    while d <= fim:
        ate = min(d + timedelta(days=29), fim)
        r = requests.get(URL, params={"codEstacao": ESTACAO, "dataInicio": d.strftime("%d/%m/%Y"),
                                      "dataFim": ate.strftime("%d/%m/%Y")}, timeout=120)
        r.raise_for_status()
        for no in ET.fromstring(r.content).iter("DadosHidrometereologicos"):
            quando, nivel = (no.findtext("DataHora") or "").strip(), (no.findtext("Nivel") or "").strip()
            if quando and nivel:
                por_dia[quando[:10]].append(float(nivel))
        print(f"  {d} a {ate}: {sum(len(v) for v in por_dia.values())} leituras acumuladas")
        d = ate + timedelta(days=1)
    return por_dia


def main():
    datas_radar = sorted(CFG["datas"])
    if "--manual" in sys.argv:
        with open(MANUAL, encoding="utf-8") as f:
            serie = [{"data": r["data"], "cota_m": float(r["cota_m"])} for r in csv.DictReader(f) if r["cota_m"]]
        fonte = "Valores informados manualmente em data/cota_manual.csv"
    else:
        inicio = date.fromisoformat(datas_radar[0]) - timedelta(days=17)
        fim = min(date.fromisoformat(datas_radar[-1]) + timedelta(days=30), date.today())
        por_dia = baixar(inicio, fim)
        if not por_dia:
            sys.exit("A ANA nao devolveu leituras. Preencha data/cota_manual.csv e rode com --manual.")
        serie = [{"data": d, "cota_m": round(sum(v) / len(v) / 100, 2), "leituras": len(v)}
                 for d, v in sorted(por_dia.items())]
        fonte = f"ANA - telemetria, estacao {ESTACAO} (Manaus), media diaria do nivel"
        MANUAL.parent.mkdir(exist_ok=True)
        with open(MANUAL, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["data", "cota_m"])
            w.writerows([s["data"], s["cota_m"]] for s in serie)

    por_data = {s["data"]: s["cota_m"] for s in serie}
    nas_cenas = [{"data": d, "cota_m": por_data.get(d)} for d in datas_radar]
    SAIDA.mkdir(parents=True, exist_ok=True)

    # Correlacao entre a cota e a area de floresta alagada nas datas do radar (se o pipeline ja rodou).
    correlacao = None
    stats = SAIDA / "stats.json"
    if stats.exists():
        area = {d["data"]: d["km2"]["floresta_alagada"] for d in json.loads(stats.read_text(encoding="utf-8"))["datas"]}
        pares = [(c["cota_m"], area[c["data"]]) for c in nas_cenas if c["cota_m"] is not None and c["data"] in area]
        if len(pares) >= 3:
            xs, ys = zip(*pares)
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            cov = sum((x - mx) * (y - my) for x, y in pares)
            r = cov / (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
            correlacao = {"r_pearson": round(r, 3), "n": len(pares),
                          "nota": "Uma unica vazante: as duas series caem juntas, entao r alto e esperado."}
            print(f"Correlacao cota x area alagada: r = {r:.3f} (n = {len(pares)})")

    (SAIDA / "cota.json").write_text(json.dumps({
        "fonte": fonte, "url": URL, "estacao": ESTACAO, "unidade": "m", "correlacao": correlacao,
        "nota": "Dado telemetrico bruto, sem consistencia. Manaus fica a jusante do arquipelago.",
        "nas_datas_do_radar": nas_cenas, "serie": serie,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(serie)} dias, de {serie[0]['data']} a {serie[-1]['data']}")
    for c in nas_cenas:
        print(f"  {c['data']}: {c['cota_m']} m")


if __name__ == "__main__":
    main()
