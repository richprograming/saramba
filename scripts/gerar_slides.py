"""
SARamba - gera o PDF dos slides de demonstracao (maximo de 7, regra do Space Apps).

Uso:   python scripts/gerar_slides.py
Fonte: docs/submission/slides.html  ->  docs/submission/SARamba-demo-slides.pdf
Precisa de: pip install playwright && python -m playwright install chromium  (e de app/node_modules para as fontes)
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

PASTA = Path(__file__).resolve().parent.parent / "docs" / "submission"

with sync_playwright() as p:
    nav = p.chromium.launch()
    pg = nav.new_page(viewport={"width": 1280, "height": 720})
    pg.goto((PASTA / "slides.html").as_uri())
    pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready")
    n = pg.locator(".slide").count()
    assert n <= 7, f"{n} slides: o limite do Space Apps e 7"
    pg.pdf(path=PASTA / "SARamba-demo-slides.pdf", width="1280px", height="720px", print_background=True)
    for i in (0, 3, 5, 6):   # previas para conferencia
        pg.locator(".slide").nth(i).screenshot(path=PASTA.parent.parent / "data" / f"_slide{i + 1}.png")
    nav.close()
print(f"{n} slides -> {PASTA / 'SARamba-demo-slides.pdf'} ({(PASTA / 'SARamba-demo-slides.pdf').stat().st_size / 1e6:.1f} MB)")
