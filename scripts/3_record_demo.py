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
import re
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

    Le libelle du bouton de connexion differe entre nav desktop ("Se connecter")
    et nav mobile ("Connexion") -- on tourne en format vertical (mobile), donc
    la regex couvre les deux.
    """
    await page.get_by_role("button", name=re.compile("connexion|se connecter", re.I)).locator(":visible").first.click()
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
    # Une fois connecte, l'accueil (Home) laisse place au Dashboard : le CTA
    # n'est plus "Essayer (gratuitement)" mais le bouton "Analyser" de la nav
    # du bas (mobileNav.analyze), qui ouvre la meme AnalyzeModal.
    await page.get_by_role("button", name=re.compile("analyser", re.I)).locator(":visible").first.click()
    # "Analyser un CV" apparait deux fois sur la page (le libelle responsive
    # du Dashboard, cache sur mobile, et le titre de la modale) -- on cible
    # le dialog par role, seul element garanti unique et visible.
    await page.wait_for_selector("div[role='dialog']", timeout=10000)
    await page.wait_for_timeout(600)

    # Bascule en mode demo (profil fictif local, pas d'appel serveur) --
    # ce bouton est un toggle, son libelle change une fois actif, ne pas
    # recliquer dessus sous peine de repasser en mode import.
    await page.get_by_text("Essayer avec un profil de démonstration").locator(":visible").first.click()
    await page.wait_for_timeout(500)

    # Declenche le chargement du CV de demo (clic sur la zone de depot)
    await page.locator("div.border-dashed:visible").first.click()

    # L'editeur (barreSuperieure) rend sa barre d'outils deux fois -- une
    # version desktop ("hidden md:flex") et une mobile ("flex md:hidden") --
    # donc ce bouton existe deux fois dans le DOM. Le viewport etant mobile,
    # seule la copie mobile est visible : :visible ecarte l'autre.
    apercu_pdf = page.locator("button[aria-label='Aperçu fidèle']:visible").first

    # Attend l'ouverture de l'editeur avec le CV genere
    await apercu_pdf.wait_for(state="visible", timeout=15000)
    await page.wait_for_timeout(1000)

    # Bascule sur l'apercu PDF stylise -- le rendu final vendeur
    await apercu_pdf.click()
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
        # Render free tier met le service en veille apres inactivite : le
        # premier chargement peut prendre 30-60s (cold start).
        page.set_default_timeout(60000)
        await page.goto(url, wait_until="networkidle", timeout=60000)

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
    parser.add_argument("--force", action="store_true",
                         help="Re-enregistre meme si une video existe deja dans --out")
    args = parser.parse_args()

    out_dir = Path(args.out)

    if not args.force and out_dir.exists():
        existing = list(out_dir.glob("*.webm"))
        if existing:
            print(f"REPRISE: {existing[0]} existe deja, on saute (--force pour re-enregistrer)")
            return

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
