"""
Enregistre un parcours utilisateur sur ton SaaS via Playwright (headless Chromium).

A ADAPTER : la fonction `play_demo_steps` doit correspondre au vrai parcours
de ton produit (selecteurs CSS/texte reels). Ce fichier fournit un squelette
fonctionnel avec un exemple generique d'upload + generation de CV.

Usage:
    python 3_record_demo.py --url https://tonapp.com --out output/video/demo_raw.webm
"""
import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

# Format vertical pour Reels/TikTok/Shorts
VIEWPORT = {"width": 405, "height": 720}


async def play_demo_steps(page):
    """
    ICI : la sequence d'actions a rejouer sur ton SaaS.
    Exemple generique -- remplace les selecteurs par les tiens.
    """
    # Exemple : remplir un champ nom
    # await page.fill("input[name='full_name']", "Camille Dupont")
    # await page.wait_for_timeout(800)

    # Exemple : cliquer sur "Generer mon CV"
    # await page.click("text=Generer mon CV")
    # await page.wait_for_timeout(2000)

    # Exemple : attendre l'apparition du resultat
    # await page.wait_for_selector(".cv-preview", timeout=15000)
    # await page.wait_for_timeout(3000)

    # Placeholder : juste un scroll pour avoir un enregistrement non vide
    await page.wait_for_timeout(1500)
    await page.mouse.wheel(0, 400)
    await page.wait_for_timeout(1500)


async def record(url: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(out_dir),
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle")

        await play_demo_steps(page)

        await context.close()  # necessaire pour flush la video sur disque
        await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="URL de ton SaaS (page de demo/app)")
    parser.add_argument("--out", type=str, default="output/video")
    args = parser.parse_args()

    out_dir = Path(args.out)
    asyncio.run(record(args.url, out_dir))

    # Playwright nomme le fichier automatiquement (hash) dans out_dir
    videos = list(out_dir.glob("*.webm"))
    if videos:
        print(f"OK -> {videos[0]}")
    else:
        print("ATTENTION: aucune video generee, verifie l'URL et les selecteurs")


if __name__ == "__main__":
    main()
