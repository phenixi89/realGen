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
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# Format vertical pour Reels/TikTok/Shorts
VIEWPORT = {"width": 405, "height": 720}


async def login(page, email: str, password: str):
    """
    Connexion via le formulaire email/mot de passe (modale AuthModal d'OpusCV).
    Les champs n'ont pas de `name`/`data-testid` -- on cible par `type`, plus
    stable ici que le texte (qui passe par i18n).
    """
    await page.get_by_role("button", name="Se connecter", exact=False).first.click()
    await page.wait_for_selector("input[type='email']", timeout=10000)
    await page.fill("input[type='email']", email)
    await page.fill("input[type='password']", password)
    await page.click("button[type='submit']")
    # Attend la fermeture de la modale (redirection post-login)
    await page.wait_for_selector("input[type='password']", state="detached", timeout=15000)
    await page.wait_for_timeout(1000)


async def play_demo_steps(page):
    """
    ICI : la sequence d'actions a rejouer sur ton SaaS, une fois connecte.
    Exemple generique -- remplace les selecteurs par les tiens (upload de CV,
    lancement de l'analyse IA, apercu du PDF optimise, etc.).
    """
    # Exemple : cliquer sur "Analyser un CV" / "Essayer gratuitement"
    # await page.click("text=Analyser mon CV")
    # await page.wait_for_timeout(2000)

    # Exemple : uploader un fichier de demo
    # await page.set_input_files("input[type='file']", "assets/cv_demo.pdf")
    # await page.wait_for_selector(".analysis-result", timeout=30000)

    # Placeholder : juste un scroll pour avoir un enregistrement non vide
    await page.wait_for_timeout(1500)
    await page.mouse.wheel(0, 400)
    await page.wait_for_timeout(1500)


async def record(url: str, out_dir: Path, email: str | None, password: str | None):
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

        if email and password:
            await login(page, email, password)
        else:
            print("ATTENTION: pas de credentials fournis, demo enregistree sans connexion", file=sys.stderr)

        await play_demo_steps(page)

        await context.close()  # necessaire pour flush la video sur disque
        await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="URL de ton SaaS (page de demo/app)")
    parser.add_argument("--out", type=str, default="output/video")
    args = parser.parse_args()

    out_dir = Path(args.out)
    email = os.environ.get("DEMO_EMAIL")
    password = os.environ.get("DEMO_PASSWORD")
    asyncio.run(record(args.url, out_dir, email, password))

    # Playwright nomme le fichier automatiquement (hash) dans out_dir
    videos = list(out_dir.glob("*.webm"))
    if videos:
        print(f"OK -> {videos[0]}")
    else:
        print("ATTENTION: aucune video generee, verifie l'URL et les selecteurs")


if __name__ == "__main__":
    main()
