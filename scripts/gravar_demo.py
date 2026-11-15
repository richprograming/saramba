"""
SARamba - grava o material visual da submissao a partir do app rodando localmente.

Antes:  cd app && npm run build && npx vite preview --port 4173
Uso:    python scripts/gravar_demo.py
Saida em docs/submission/:
  SARamba-demo-30s.webm   video de 28 s com legendas em ingles (limite do Space Apps: 30 s)
  app-demo.gif            versao curta, sem legenda, para o README e a pagina (< 10 MB)
  before-after.png, classes.png, duration.png, change.png, probe.png, logo.png

Precisa de: pip install playwright && python -m playwright install chromium
O video e montado quadro a quadro com o ffmpeg que acompanha o Playwright (VP9/WebM).
"""

import io
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from scipy.ndimage import uniform_filter

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "docs" / "submission"
URL = "http://localhost:4173/"
LARGURA, ALTURA, FPS = 1280, 720, 12

LEGENDAS = [
    "The Amazon, 18 June 2026. Optical satellites see clouds and a green roof.",
    "NISAR’s L-band radar sees through both, on the same day.",
    "Black is open water. Bright is consistent with flooded forest.",
    "June to October: the river fell 12 m. Flooded forest: 379 → 30 km².",
    "11 passes, one map of how long the forest stays flooded. SARamba: open data, open source.",
]


def ffmpeg():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "ms-playwright"
    achados = sorted(base.glob("ffmpeg*/ffmpeg*"))
    if not achados:
        raise SystemExit("ffmpeg do Playwright nao encontrado. Rode: python -m playwright install chromium")
    return str(achados[-1])


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    quadros = []      # JPEGs do video, um por quadro
    gif = []          # (imagem, duracao em ms)

    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = nav.new_page(viewport={"width": LARGURA, "height": ALTURA})
        pg.goto(URL)
        pg.wait_for_selector(".cmp-handle")
        pg.wait_for_timeout(5000)
        # Legenda sobre o mapa, so para a gravacao.
        pg.evaluate("""() => {
            const d = document.createElement('div'); d.id = 'legenda';
            d.style.cssText = 'position:absolute;left:50%;bottom:64px;transform:translateX(-50%);z-index:9;' +
              'max-width:80%;padding:10px 18px;border-radius:10px;background:rgba(7,22,43,.92);color:#fff;' +
              'font:600 21px/1.35 Inter,sans-serif;text-align:center;box-shadow:0 4px 18px rgba(0,0,0,.5)';
            document.querySelector('.stage').appendChild(d);
        }""")
        legenda = lambda i: pg.evaluate(
            "t => { const d = document.getElementById('legenda'); d.textContent = t; d.style.display = t ? '' : 'none' }",
            LEGENDAS[i] if i is not None else "")
        foto = lambda: pg.screenshot(type="jpeg", quality=88)

        def segura(segundos, ms_gif=None):
            f = foto()
            quadros.extend([f] * round(segundos * FPS))
            if ms_gif:
                gif.append((Image.open(io.BytesIO(f)).convert("RGB"), ms_gif))

        caixa = pg.locator(".cmp").bounding_box()
        y = caixa["y"] + caixa["height"] / 2
        x_de = lambda f: caixa["x"] + caixa["width"] * f

        # 1. Optico: nuvens (4,5 s).
        pg.mouse.move(x_de(0.5), y)
        pg.mouse.down()
        pg.mouse.move(x_de(0.92), y, steps=4)
        pg.wait_for_timeout(500)
        legenda(0)
        segura(4.5, 1400)

        # 2. Slider do optico para o radar (5,5 s).
        legenda(1)
        n = round(5.5 * FPS)
        for i in range(n):
            f = 0.92 - (0.92 - 0.08) * (i + 1) / n
            pg.mouse.move(x_de(f), y)
            pg.wait_for_timeout(30)
            q = foto()
            quadros.append(q)
            if i % 9 == 8:
                gif.append((Image.open(io.BytesIO(q)).convert("RGB"), 140))

        # 3. Radar parado (4 s).
        legenda(2)
        segura(4, 1500)
        pg.mouse.move(x_de(0.5), y, steps=3)
        pg.mouse.up()
        legenda(None)
        pg.wait_for_timeout(300)
        pg.screenshot(path=SAIDA / "before-after.png")

        # 4. Classes ao longo de todas as datas (8 s).
        pg.get_by_role("checkbox").uncheck()
        pg.get_by_role("button", name="Classes").click()
        legenda(3)
        datas = pg.locator(".date")
        total = datas.count()
        for i in range(total):
            datas.nth(i).click()
            pg.wait_for_timeout(900)
            segura(8 / total, 550)
            if i == 0:
                legenda(None)
                pg.screenshot(path=SAIDA / "classes.png")
                legenda(3)

        # 5. Mapa de duracao (6 s).
        pg.get_by_role("button", name="Duration").click()
        pg.wait_for_timeout(1800)
        legenda(4)
        segura(6, 2600)
        legenda(None)
        pg.screenshot(path=SAIDA / "duration.png")

        # Imagens extras: mudanca e serie do ponto clicado.
        pg.get_by_role("button", name="Change").click()
        pg.wait_for_timeout(1500)
        mudanca = pg.screenshot(path=SAIDA / "change.png")
        # Ponto para o exemplo de serie: o centro da maior mancha laranja (alagada -> nao alagada).
        rgb = np.asarray(Image.open(io.BytesIO(mudanca)).convert("RGB")).astype(int)
        laranja = (rgb[..., 0] > 225) & (rgb[..., 1] > 150) & (rgb[..., 1] < 195) & (rgb[..., 2] < 80)
        laranja[:, int(caixa["x"] + caixa["width"]):] = False
        densidade = uniform_filter(laranja.astype(float), 25)
        py, px = np.unravel_index(densidade.argmax(), densidade.shape)
        pg.get_by_role("button", name="HH", exact=True).click()
        pg.mouse.click(int(px), int(py))
        pg.wait_for_timeout(800)
        pg.locator(".panel footer").scroll_into_view_if_needed()
        pg.wait_for_timeout(600)
        pg.screenshot(path=SAIDA / "probe.png")
        nav.close()

    # Video: os quadros entram pelo stdin do ffmpeg.
    video = SAIDA / "SARamba-demo-30s.webm"
    duracao = len(quadros) / FPS
    assert duracao <= 30, f"video com {duracao:.1f} s: o limite do Space Apps e 30 s"
    proc = subprocess.Popen(
        [ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(FPS), "-i", "pipe:0",
         "-c:v", "libvpx-vp9", "-b:v", "2500k", "-pix_fmt", "yuv420p", "-r", str(FPS), str(video)],
        stdin=subprocess.PIPE)
    for q in quadros:
        proc.stdin.write(q)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg falhou ao montar o video")

    # GIF em 960 px de largura. A paleta sai de uma colagem de TODOS os quadros, para ter
    # os azuis, verdes e laranjas e nao piscar.
    tam = (960, round(960 * ALTURA / LARGURA))
    pequenos = [q.resize(tam, Image.LANCZOS) for q, _ in gif]
    colagem = Image.new("RGB", (tam[0] // 4 * len(pequenos), tam[1] // 4))
    for i, q in enumerate(pequenos):
        colagem.paste(q.resize((tam[0] // 4, tam[1] // 4)), (i * (tam[0] // 4), 0))
    paleta = colagem.quantize(colors=255, method=Image.MEDIANCUT)
    gq = [q.quantize(palette=paleta, dither=Image.NONE) for q in pequenos]
    gq[0].save(SAIDA / "app-demo.gif", save_all=True, append_images=gq[1:],
               duration=[ms for _, ms in gif], loop=0, optimize=True)

    shutil.copy(RAIZ / "brand" / "saramba-logo-dark.png", SAIDA / "logo.png")
    for f in sorted(SAIDA.glob("*.*")):
        if f.suffix in (".png", ".gif", ".webm", ".pdf"):
            print(f"{f.name}: {f.stat().st_size / 1e6:.2f} MB")
    print(f"Video: {duracao:.1f} s ({len(quadros)} quadros a {FPS} fps) | GIF: {sum(ms for _, ms in gif) / 1000:.1f} s")


if __name__ == "__main__":
    main()
