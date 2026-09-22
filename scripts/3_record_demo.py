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
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

from scene_compose import compose_scene

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


async def dismiss_onboarding_tooltip(page):
    """
    Popover d'aide au premier affichage de l'editeur (EditorDock.jsx :
    "Comment modifier votre CV" + bouton "Compris !") : plaque en haut du
    dock lateral tant qu'on ne l'a pas ferme -- masque les boutons de
    section juste en dessous sur les toutes premieres captures sinon.
    """
    got_it = page.locator("button:visible").filter(has_text=re.compile(r"^compris\s*!?$", re.I)).first
    if await got_it.count():
        await got_it.click()
        await page.wait_for_timeout(300)


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


# Sections du dock lateral (EditorDock.jsx, SECTIONS + le bouton Design juste
# en dessous) : aria-label = libelle FR exact (common:sections.*), plus fiable
# qu'un index de position si l'app ajoute/retire un onglet.
DOCK_SECTIONS = ["Identité", "Expériences", "Formation", "Compétences", "Langues"]
DESIGN_TAB_LABEL = "Design"  # editor.topBar.designTab


async def _capture_scene(page, out_dir: Path, index: int, name: str, element) -> Path:
    """
    Capture une "scene" : le viewport entier (fond, pour le flou) + l'element
    precis (carte nette) -- composes en une seule image verticale prete a
    animer par scene_compose.compose_scene(). Remplace l'ancien plein-ecran
    recadre en paysage->portrait, qui perdait du contenu sur les bords.
    """
    bg_bytes = await page.screenshot()
    fg_bytes = await element.screenshot()
    scene = compose_scene(Image.open(BytesIO(bg_bytes)), Image.open(BytesIO(fg_bytes)))
    path = out_dir / f"{index:02d}_{name}.png"
    scene.save(path)
    return path


async def capture_pc_screenshots(page, out_dir: Path) -> list[Path]:
    """
    Mode "PC" : au lieu d'enregistrer une video continue (fragile -- doit
    rester stable pendant toute l'interaction), on capture chaque section de
    l'app individuellement (liste des CVs, chaque onglet d'edition -- y
    compris Experiences --, Design, fonctions IA, apercu du CV) plutot qu'un
    plein-ecran unique. Chaque scene est composee (fond floute + carte nette,
    voir scene_compose.py) et animee au montage (zoom in/out).
    """
    shots: list[Path] = []
    idx = 0

    async def shoot(name: str, element):
        nonlocal idx
        idx += 1
        shots.append(await _capture_scene(page, out_dir, idx, name, element))

    # Une fois connecte, App.jsx affiche directement Dashboard.jsx (pas de
    # menu compte a ouvrir ni de modale) : "Mes CVs sauvegardés" y est deja
    # la section principale de la page -- exactement ce que montre la
    # capture. On attend la premiere ligne de CV (le fetch /api/cvs est
    # asynchrone, precede d'un skeleton de chargement).
    first_row = page.locator("li:visible", has=page.locator("button[title]")).first
    await first_row.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(800)
    await shoot("mes_cvs", first_row)

    # Survole la premiere ligne pour reveler ses icones d'action (Renommer,
    # Dupliquer, Supprimer -- masquees hors survol) avant de capturer, puis
    # ouvre ce CV dans l'editeur.
    await first_row.hover()
    await page.wait_for_timeout(400)
    await shoot("mes_cvs_actions", first_row)

    await first_row.click()
    # Ouvre l'editeur (chunk charge en lazy) : attend son panneau de contenu
    # (id stable, contrairement aux classes Tailwind qui changent souvent).
    form_panel = page.locator("#editor-form-panel")
    await form_panel.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1000)
    await dismiss_onboarding_tooltip(page)

    # Chaque onglet de contenu (Identite, Experiences -- en mode edition --,
    # Formation, Competences, Langues) : le panneau de gauche est capture a
    # chaque fois, avec le contenu de l'onglet actif.
    for label in DOCK_SECTIONS:
        tab = page.locator(f"aside nav button[aria-label='{label}']").first
        if await tab.count() == 0:
            continue
        await tab.click()
        await page.wait_for_timeout(700)
        await dismiss_onboarding_tooltip(page)  # peut reapparaitre au premier changement d'onglet

        if label == "Expériences":
            # Parcours en 3 temps plutot qu'une capture unique isolee :
            # liste repliee -> carte depliee (formulaire poste/entreprise/
            # dates) -> double-clic sur les missions dans l'apercu en direct
            # (LivePreview.jsx, data-exp-part="missions"), qui ouvre
            # directement MissionsModal -- exactement le geste utilisateur
            # reel, pas un raccourci via le bouton "Modifier les missions".
            await shoot("section_experiences_liste", form_panel)

            first_card = page.locator("[role='button'][aria-expanded='false']").first
            if await first_card.count():
                await first_card.click()
                await page.wait_for_timeout(500)
                await shoot("section_experiences_ouverte", form_panel)

                mission_area = page.locator("[data-exp-part='missions']:visible").first
                if await mission_area.count():
                    await mission_area.dblclick()
                    dialog = page.locator("div[role='dialog']").first
                    try:
                        await dialog.wait_for(state="visible", timeout=6000)
                        await page.wait_for_timeout(500)
                        await shoot("edition_missions", dialog)
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(400)
                    except Exception:
                        print("ATTENTION: modale missions introuvable, capture ignoree", file=sys.stderr)
            continue

        await shoot(f"section_{label.lower()}", form_panel)

    # Onglet Design (theme/personnalisation) : meme panneau, contenu differe.
    design_tab = page.locator(f"aside nav button[aria-label='{DESIGN_TAB_LABEL}']").first
    if await design_tab.count():
        await design_tab.click()
        await page.wait_for_timeout(700)
        await shoot("design", form_panel)

    # Fonctions IA : le bouton "Adapter a une offre" ouvre une modale dediee
    # (dialog) -- une des fonctionnalites phares du produit.
    adapt_button = page.locator("button:visible").filter(has=page.locator("svg.lucide-zap")).first
    if await adapt_button.count():
        await adapt_button.click()
        dialog = page.locator("div[role='dialog']").first
        try:
            await dialog.wait_for(state="visible", timeout=8000)
            await page.wait_for_timeout(600)
            await shoot("fonctions_ia", dialog)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
        except Exception:
            print("ATTENTION: modale IA introuvable, capture ignoree", file=sys.stderr)

    # Mode focus (icone agrandir de la barre superieure) : affiche l'apercu
    # stylise en plein ecran, le plan le plus "vendeur" du produit.
    focus_button = page.locator("button[title]:visible").filter(has=page.locator("svg.lucide-maximize-2")).first
    if await focus_button.count():
        await focus_button.click()
        await page.wait_for_timeout(1200)
        preview = page.locator("main").first
        await shoot("apercu_cv", preview)

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
