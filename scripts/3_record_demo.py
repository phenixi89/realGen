"""
Enregistre un parcours utilisateur sur OpusCV via Playwright (headless Chromium) :
connexion, ouverture de la modale d'analyse, mode demo (profil fictif local),
puis apercu PDF fidele du CV genere.

Usage:
    python 3_record_demo.py --url https://tonapp.com --out output/video/demo_raw.webm
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

import features as features_module

# Taille CSS de la page (garde le point de rupture mobile de l'app -- c'est
# ce qui determine quelle version de l'UI (responsive) s'affiche).
VIEWPORT = {"width": 405, "height": 720}

# Resolution d'encodage de la video, independante du viewport CSS : Playwright
# redimensionne les frames captures vers cette taille. 1080x1920 est le
# standard recommande pour Reels/TikTok/Shorts -- enregistrer directement a
# la taille du viewport (405x720) produisait une image ~2.7x trop petite.
RECORD_SIZE = {"width": 1080, "height": 1920}

# Viewport large ecran pour les modes "screenshots" et "video_desktop" :
# au-dela du seuil `md`/`xl` Tailwind de l'app, ca fait apparaitre la barre
# d'outils desktop (EditorDock, AccountMenu) qui n'existe pas sur le viewport
# mobile ci-dessus.
DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
DESKTOP_SCALE_FACTOR = 2  # equivalent Retina, sans quoi le texte capture reste flou une fois agrandi


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


async def create_demo_cv(page):
    """Ouvre l'editeur sur le profil de demonstration, l'enregistre, revient au tableau de bord."""
    await page.locator("button:visible").filter(has_text=re.compile("analyser", re.I)).first.click()
    await page.wait_for_selector("div[role='dialog']", timeout=10000)
    await page.wait_for_timeout(600)
    await page.locator("button:visible").filter(has_text="Essayer avec un profil de démonstration").first.click()
    await page.wait_for_timeout(500)
    await page.locator("div.border-dashed:visible").first.click()
    await page.locator("#editor-form-panel").wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1500)
    await page.keyboard.press("Control+s")
    await page.wait_for_timeout(2000)
    await page.goto(page.url.split("#")[0])


async def walk_features(page, shoot, feature_ids: list[str] | None = None):
    """
    Parcours desktop commun aux modes screenshots et video_desktop : tableau
    de bord, ouverture de l'editeur, puis les fonctionnalites demandees
    (features.py). `shoot(feature_id, name, element)` decide quoi faire a
    chaque moment cle (photo figee, ou marqueur de segment video).
    """
    wanted = features_module.resolve_feature_order(feature_ids)

    # Une fois connecte, App.jsx affiche directement Dashboard.jsx : on
    # attend la premiere ligne de CV (fetch /api/cvs asynchrone, precede
    # d'un skeleton de chargement).
    first_row = page.locator("li:visible", has=page.locator("button[title]")).first
    empty_state = page.locator("button:visible").filter(has_text=re.compile("créer de zéro", re.I)).first
    await first_row.or_(empty_state).first.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(800)
    if not await first_row.is_visible():
        # Compte sans aucun CV (compte demo neuf ou vide) : on cree le CV de
        # demonstration, puis on revient au tableau de bord qui le liste.
        print("Compte sans CV : creation du CV de demonstration")
        await create_demo_cv(page)
        await first_row.wait_for(state="visible", timeout=30000)
        await page.wait_for_timeout(800)
    if "dashboard" in wanted:
        await shoot("dashboard", "mes_cvs", first_row)
        # Survol : revele les icones d'action (Renommer, Dupliquer, Supprimer).
        await first_row.hover()
        await page.wait_for_timeout(400)
        await shoot("dashboard", "mes_cvs_actions", first_row)

    await first_row.click()
    # Editeur charge en lazy : attend son panneau de contenu (id stable).
    form_panel = page.locator("#editor-form-panel")
    await form_panel.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1000)
    await features_module.dismiss_onboarding_tooltip(page)
    # La checklist s'ouvre seule une fois l'aide fermee, avec un calque qui
    # intercepterait tous les clics suivants.
    await page.wait_for_timeout(800)
    await features_module.close_checklist_if_open(page)

    await features_module.run_features(page, shoot, form_panel, wanted)


async def capture_pc_screenshots(page, out_dir: Path, feature_ids: list[str] | None = None) -> list[dict]:
    """
    Mode screenshots : une image composee (fond floute + carte nette, cf.
    scene_compose.py) par moment cle, etiquetee avec sa fonctionnalite dans
    captures.json -- 3b_build_video_from_screenshots.py les replace dans
    l'ordre du scenario, cale sur le timing de la voix.
    """
    shots: list[dict] = []

    async def shoot(feature_id: str, name: str, element):
        path = await features_module._capture_scene(page, out_dir, len(shots) + 1, name, element)
        shots.append({"feature": feature_id, "name": name, "file": path.name})

    await walk_features(page, shoot, feature_ids)
    (out_dir / "captures.json").write_text(json.dumps(shots, ensure_ascii=False, indent=2), encoding="utf-8")
    return shots


async def capture_pc_video(page, out_dir: Path, feature_ids: list[str] | None = None) -> list[dict]:
    """
    Mode video_desktop : le meme parcours, sur l'enregistrement video continu
    deja actif sur le context (cf. record()). Chaque shoot() marque la fin
    d'un segment (fonctionnalite + position de l'element vise a cet instant),
    recadre ensuite par 3c_build_video_from_recording.py sur cette seule zone.

    Chemin independant du mode screenshots : si celui-ci echoue ou rend mal,
    --mode screenshots reste disponible et inchange.
    """
    segments: list[dict] = []
    t0 = time.monotonic()

    async def shoot(feature_id: str, name: str, element):
        try:
            bbox = await element.bounding_box()
        except Exception:
            bbox = None
        segments.append({"feature": feature_id, "name": name, "end": time.monotonic() - t0, "bbox": bbox})

    await walk_features(page, shoot, feature_ids)

    starts = [0.0] + [s["end"] for s in segments[:-1]]
    for seg, start in zip(segments, starts):
        seg["start"] = start
    return segments


async def record(url: str, out_dir: Path, email: str | None, password: str | None, mode: str = "video",
                  feature_ids: list[str] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context_kwargs = dict(
            # Rendu a densite de pixels plus elevee (equivalent "Retina") --
            # sans ca, le texte/l'UI captures restent flous une fois agrandis.
            device_scale_factor=DESKTOP_SCALE_FACTOR if mode in ("screenshots", "video_desktop") else 3,
        )
        if mode == "screenshots":
            context_kwargs["viewport"] = DESKTOP_VIEWPORT
        elif mode == "video_desktop":
            context_kwargs.update(
                viewport=DESKTOP_VIEWPORT,
                record_video_dir=str(out_dir),
                # Explicitement egal a viewport*scale : sans ca, Playwright
                # etirerait l'enregistrement vers une autre resolution, et
                # les bbox (en pixels CSS) captures par capture_pc_video()
                # ne correspondraient plus aux pixels reels de la video --
                # le recadrage de 3c_build_video_from_recording.py viserait
                # a cote de l'element.
                record_video_size={
                    "width": DESKTOP_VIEWPORT["width"] * DESKTOP_SCALE_FACTOR,
                    "height": DESKTOP_VIEWPORT["height"] * DESKTOP_SCALE_FACTOR,
                },
            )
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

        segments = None
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
                await capture_pc_screenshots(page, out_dir, feature_ids)
            elif mode == "video_desktop":
                segments = await capture_pc_video(page, out_dir, feature_ids)
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

        if mode == "video_desktop" and segments:
            # page.video n'est resolu qu'une fois le context ferme (video
            # flushee sur disque, cf. ci-dessus) -- doit rester avant
            # browser.close(), qui invaliderait la reference.
            raw_path = Path(await page.video.path())
            final_raw_path = out_dir / "raw.webm"
            raw_path.replace(final_raw_path)
            manifest = {
                "device_scale_factor": context_kwargs["device_scale_factor"],
                "video_size": context_kwargs["record_video_size"],
                "segments": segments,
            }
            (out_dir / "segments.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        await browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="URL de ton SaaS (page de demo/app)")
    parser.add_argument("--out", type=str, default="output/video")
    parser.add_argument("--mode", type=str, default="video", choices=["video", "screenshots", "video_desktop"],
                         help="video = enregistrement continu mobile ; "
                              "screenshots = captures fixes desktop, animees ensuite au montage (zoom in/out) ; "
                              "video_desktop = enregistrement continu desktop, recadre ensuite (3c) sur "
                              "chaque fonctionnalite montree plutot que le viewport entier")
    parser.add_argument("--force", action="store_true",
                         help="Re-enregistre meme si une sortie existe deja dans --out")
    parser.add_argument("--features", type=str, default=None,
                         help="Ids de features.FEATURES separes par des virgules (modes screenshots/"
                              "video_desktop uniquement) ; omis = tout le catalogue dans l'ordre par defaut")
    args = parser.parse_args()
    feature_ids = [f.strip() for f in args.features.split(",") if f.strip()] if args.features else None

    out_dir = Path(args.out)
    if args.mode == "screenshots":
        pattern = "*.png"
    elif args.mode == "video_desktop":
        pattern = "segments.json"
    else:
        pattern = "*.webm"

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
            stray = list(out_dir.glob("*.webm")) if args.mode == "video_desktop" else list(out_dir.glob("captures.json"))
            for f in {*existing, *stray}:
                f.unlink()

    email = os.environ.get("DEMO_EMAIL")
    password = os.environ.get("DEMO_PASSWORD")
    asyncio.run(record(args.url, out_dir, email, password, mode=args.mode, feature_ids=feature_ids))

    outputs = sorted(out_dir.glob(pattern))
    if outputs:
        print(f"OK -> {len(outputs)} fichier(s) dans {out_dir}")
    else:
        print("ATTENTION: aucune sortie generee, verifie l'URL et les selecteurs")


if __name__ == "__main__":
    main()
