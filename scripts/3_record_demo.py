"""
Enregistre un parcours utilisateur sur OpusCV via Playwright (headless Chromium) :
connexion, ouverture de la modale d'analyse, mode demo (profil fictif local),
puis apercu PDF fidele du CV genere.

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
    Parcours OpusCV, une fois connecte : ouvre la modale d'analyse, bascule
    en mode demo (profil fictif genere localement, sans appel IA ni upload --
    rapide et deterministe pour un enregistrement automatise), puis affiche
    l'apercu PDF fidele du CV genere.
    """
    # Ouvre la modale "Analyser un CV"
    await page.get_by_role("button", name="Essayer gratuitement", exact=False).first.click()
    await page.wait_for_selector("text=Analyser un CV", timeout=10000)
    await page.wait_for_timeout(600)

    # Bascule en mode demo (profil fictif local, pas d'appel serveur) --
    # ce bouton est un toggle, son libelle change une fois actif, ne pas
    # recliquer dessus sous peine de repasser en mode import.
    await page.click("text=Essayer avec un profil de démonstration")
    await page.wait_for_timeout(500)

    # Declenche le chargement du CV de demo (clic sur la zone de depot)
    await page.locator("div.border-dashed").click()

    # Attend l'ouverture de l'editeur avec le CV genere
    await page.wait_for_selector("button[aria-label='Aperçu fidèle']", timeout=15000)
    await page.wait_for_timeout(1000)

    # Bascule sur l'apercu PDF stylise -- le rendu final vendeur
    await page.click("button[aria-label='Aperçu fidèle']")
    await page.wait_for_timeout(2500)
    await page.mouse.wheel(0, 300)
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
