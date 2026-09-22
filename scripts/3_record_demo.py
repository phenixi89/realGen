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

# Taille CSS de la page (garde le point de rupture mobile de l'app -- c'est
# ce qui determine quelle version de l'UI (responsive) s'affiche).
VIEWPORT = {"width": 405, "height": 720}

# Resolution d'encodage de la video, independante du viewport CSS : Playwright
# redimensionne les frames captures vers cette taille. 1080x1920 est le
# standard recommande pour Reels/TikTok/Shorts -- enregistrer directement a
# la taille du viewport (405x720) produisait une image ~2.7x trop petite.
RECORD_SIZE = {"width": 1080, "height": 1920}

# Viewport large ecran pour le mode "screenshots" (--mode screenshots) : au-dela
# du seuil `md`/`xl` Tailwind de l'app, ca fait apparaitre la barre d'outils
# desktop (EditorDock, AccountMenu) qui n'existe pas sur le viewport mobile
# ci-dessus.
DESKTOP_VIEWPORT = {"width": 1440, "height": 900}


async def dismiss_cookie_banner(page):
    """
    Bandeau RGPD (App.jsx) : fixe en bas d'ecran tant qu'aucun consentement
    n'est enregistre. Sans ca, il reste visible sur toutes les captures/
    l'enregistrement -- gênant surtout en mode screenshots, ou il finit dans
    le cadrage final.
    """
    accept = page.locator("button:visible").filter(has_text=re.compile("j'ai compris|compris", re.I)).first
    try:
        await accept.click(timeout=3000)
    except Exception:
        pass  # deja accepte (execution precedente / --force) ou bandeau absent


async def login(page, email: str, password: str):
    """
    Connexion via le formulaire email/mot de passe (modale AuthModal d'OpusCV).
    Les champs n'ont pas de `name`/`data-testid` -- on cible par `type`, plus
    stable ici que le texte (qui passe par i18n).

    Le libelle du bouton de connexion differe entre nav desktop ("Se connecter")
    et nav mobile ("Connexion") -- on tourne en format vertical (mobile), donc
    la regex couvre les deux.
    """
    await page.locator("button:visible").filter(has_text=re.compile("connexion|se connecter", re.I)).first.click()
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
    await page.locator("button:visible").filter(has_text=re.compile("analyser", re.I)).first.click()
    # "Analyser un CV" apparait deux fois sur la page (le libelle responsive
    # du Dashboard, cache sur mobile, et le titre de la modale) -- on cible
    # le dialog par role, seul element garanti unique et visible.
    await page.wait_for_selector("div[role='dialog']", timeout=10000)
    await page.wait_for_timeout(600)

    # Bascule en mode demo (profil fictif local, pas d'appel serveur) --
    # ce bouton est un toggle, son libelle change une fois actif, ne pas
    # recliquer dessus sous peine de repasser en mode import.
    await page.locator("button:visible").filter(has_text="Essayer avec un profil de démonstration").first.click()
    await page.wait_for_timeout(500)

    # Declenche le chargement du CV de demo (clic sur la zone de depot)
    await page.locator("div.border-dashed:visible").first.click()

    # Sur mobile, l'editeur s'ouvre sur le panneau de formulaire ; le <main>
    # qui contient le LivePreview (rendu stylise en direct du CV) reste
    # `hidden` tant qu'on n'a pas bascule via le bouton "Aperçu" (icone oeil)
    # de l'en-tete mobile -- c'etait la vraie cause du timeout precedent, pas
    # un probleme de doublon DOM. aria-label="Aperçu" est un match EXACT
    # (contrairement a "Aperçu fidèle", plus long), donc pas d'ambiguite.
    show_preview = page.locator("button[aria-label='Aperçu']:visible").first

    # L'editeur est charge en lazy (chunk JS a part) : premier fetch parfois
    # lent sur Render free tier, d'ou une marge large ici.
    await show_preview.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1000)
    await show_preview.click()

    # <main> passe en overlay plein ecran et affiche le LivePreview stylise --
    # c'est deja le plan le plus vendeur, pas besoin d'ouvrir en plus la
    # modale "Aperçu fidèle".
    await page.wait_for_timeout(2500)
    await page.mouse.wheel(0, 300)
    await page.wait_for_timeout(1500)


async def capture_pc_screenshots(page, out_dir: Path) -> list[Path]:
    """
    Mode "PC" : au lieu d'enregistrer une video continue (fragile -- doit
    rester stable pendant toute l'interaction), on prend des captures d'ecran
    nettes a des etapes cles. 5_assemble.py (via build_video_from_screenshots)
    anime chacune avec un zoom in/out (ffmpeg zoompan) pour donner du mouvement
    a l'assemblage final, sans dependre du timing d'un enregistrement live.
    """
    shots: list[Path] = []

    async def shoot(name: str):
        path = out_dir / f"{len(shots) + 1:02d}_{name}.png"
        await page.screenshot(path=str(path))
        shots.append(path)

    # Une fois connecte, App.jsx affiche directement Dashboard.jsx (pas de
    # menu compte a ouvrir ni de modale) : "Mes CVs sauvegardés" y est deja
    # la section principale de la page -- exactement ce que montre la
    # capture. On attend la premiere ligne de CV (le fetch /api/cvs est
    # asynchrone, precede d'un skeleton de chargement).
    first_row = page.locator("li:visible", has=page.locator("button[title]")).first
    await first_row.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(800)
    await shoot("mes_cvs")

    # Survole la premiere ligne pour reveler ses icones d'action (Renommer,
    # Dupliquer, Supprimer -- masquees hors survol) avant de capturer, puis
    # ouvre ce CV dans l'editeur.
    await first_row.hover()
    await page.wait_for_timeout(400)
    await shoot("mes_cvs_actions")

    await first_row.click()
    # Ouvre l'editeur (chunk charge en lazy) : attend son dock lateral
    # desktop plutot qu'une modale, absente de ce parcours.
    await page.wait_for_selector("aside nav", timeout=30000)
    await page.wait_for_timeout(1500)
    await shoot("editeur")

    # Bascule sur quelques onglets du dock lateral (EditorDock, colonne
    # d'icones a gauche) pour montrer differentes sections en cours d'edition.
    dock_tabs = page.locator("aside nav button:visible")
    tab_count = await dock_tabs.count()
    for i in range(min(tab_count, 2)):
        await dock_tabs.nth(i).click()
        await page.wait_for_timeout(900)
        await shoot(f"section_{i + 1}")

    # Mode focus (icone agrandir de la barre superieure) : affiche l'apercu
    # stylise en plein ecran, le plan le plus "vendeur" du produit.
    focus_button = page.locator("button[title]:visible").filter(has=page.locator("svg.lucide-maximize-2")).first
    if await focus_button.count():
        await focus_button.click()
        await page.wait_for_timeout(1200)
        await shoot("apercu_focus")

    return shots


async def record(url: str, out_dir: Path, email: str | None, password: str | None, mode: str = "video"):
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context_kwargs = dict(
            # Rendu a densite de pixels plus elevee (equivalent "Retina") --
            # sans ca, le texte/l'UI captures restent flous une fois agrandis.
            device_scale_factor=2 if mode == "screenshots" else 3,
        )
        if mode == "screenshots":
            context_kwargs["viewport"] = DESKTOP_VIEWPORT
        else:
            context_kwargs.update(
                viewport=VIEWPORT,
                record_video_dir=str(out_dir),
                record_video_size=RECORD_SIZE,
            )
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        # Capture la console/les erreurs JS de la page : en cas d'echec, ca
        # dit si l'app a plante cote client au lieu de deviner a l'aveugle.
        page.on("console", lambda msg: print(f"[console:{msg.type}] {msg.text}", file=sys.stderr))
        page.on("pageerror", lambda exc: print(f"[pageerror] {exc}", file=sys.stderr))
        # Render free tier met le service en veille apres inactivite : le
        # premier chargement peut prendre 30-60s (cold start).
        page.set_default_timeout(60000)
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await dismiss_cookie_banner(page)

        try:
            if email and password:
                await login(page, email, password)
            else:
                print("ATTENTION: pas de credentials fournis, demo enregistree sans connexion", file=sys.stderr)

            if mode == "screenshots":
                # S'appuie sur un CV deja sauvegarde dans le compte demo
                # (contrairement au mode video, qui genere un profil fictif
                # local a la volee) -- la liste "Mes CVs" a capturer suppose
                # qu'il y en a au moins un.
                await capture_pc_screenshots(page, out_dir)
            else:
                await play_demo_steps(page)
        except Exception:
            # Screenshot + HTML dans out_dir pour diagnostiquer sans deviner :
            # ils sont remontes comme artifact GitHub Actions meme en echec.
            debug_dir = out_dir.parent.parent / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(debug_dir / f"{out_dir.name}.png"), full_page=True)
            (debug_dir / f"{out_dir.name}.html").write_text(await page.content(), encoding="utf-8")
            print(f"DEBUG: capture -> {debug_dir}", file=sys.stderr)
            raise
        finally:
            await context.close()  # necessaire pour flush la video sur disque
            await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="URL de ton SaaS (page de demo/app)")
    parser.add_argument("--out", type=str, default="output/video")
    parser.add_argument("--mode", type=str, default="video", choices=["video", "screenshots"],
                         help="video = enregistrement continu (mobile) ; "
                              "screenshots = captures fixes desktop, animees ensuite au montage (zoom in/out)")
    parser.add_argument("--force", action="store_true",
                         help="Re-enregistre meme si une sortie existe deja dans --out")
    args = parser.parse_args()

    out_dir = Path(args.out)
    pattern = "*.png" if args.mode == "screenshots" else "*.webm"

    if out_dir.exists():
        existing = sorted(out_dir.glob(pattern))
        if existing:
            if not args.force:
                print(f"REPRISE: {len(existing)} fichier(s) existent deja dans {out_dir}, on saute (--force pour re-enregistrer)")
                return
            # --force : supprime les anciennes sorties avant de re-enregistrer,
            # sinon un vieux .webm (nomme par un hash Playwright, pas
            # deterministe) traine a cote du nouveau et un glob() ulterieur
            # peut en reprendre un au hasard.
            for f in existing:
                f.unlink()

    email = os.environ.get("DEMO_EMAIL")
    password = os.environ.get("DEMO_PASSWORD")
    asyncio.run(record(args.url, out_dir, email, password, mode=args.mode))

    outputs = sorted(out_dir.glob(pattern))
    if outputs:
        print(f"OK -> {len(outputs)} fichier(s) dans {out_dir}")
    else:
        print("ATTENTION: aucune sortie generee, verifie l'URL et les selecteurs")


if __name__ == "__main__":
    main()
