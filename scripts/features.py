"""
Catalogue des fonctionnalites capturables en mode screenshots (--mode screenshots
de 3_record_demo.py).

Pourquoi un catalogue plutot que le tour cable en dur qu'il remplace : sans
ca, rien ne garantit que le texte du reel (1_generate_script.py) parle d'une
fonctionnalite realement montree a l'ecran. Chaque fonctionnalite est une
petite fonction Playwright autonome -- pas une liste de selecteurs en JSON --
parce que l'enchainement reel a des dependances d'etat (onglet a cliquer
avant de pouvoir deplier une carte, modale a fermer avant de continuer) qui
se pretent mal a du pur declaratif.

Le meme catalogue sert deux fins :
  - 1_generate_script.py y pioche label/script_hint pour ecrire un texte qui
    colle aux fonctionnalites choisies pour ce reel (angle -> feature ids) ;
  - 3_record_demo.py execute, via run_features(), la liste de features
    choisie pour ce reel en mode screenshots.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Awaitable, Callable

from PIL import Image

from scene_compose import compose_scene

# Sections du dock lateral (EditorDock.jsx, SECTIONS + le bouton Design juste
# en dessous) : aria-label = libelle FR exact (common:sections.*), plus fiable
# qu'un index de position si l'app ajoute/retire un onglet.
DESIGN_TAB_LABEL = "Design"  # editor.topBar.designTab


@dataclass
class DemoContext:
    page: object
    form_panel: object
    shoot: Callable[[str, object], Awaitable[Path]]


async def dismiss_onboarding_tooltip(page):
    """
    Popover d'aide au premier affichage de l'editeur (EditorDock.jsx :
    "Comment modifier votre CV" + bouton "Compris !") : plaque en haut du
    dock lateral tant qu'on ne l'a pas ferme -- masque les boutons de
    section juste en dessous sur les toutes premieres captures sinon.
    """
    import re
    got_it = page.locator("button:visible").filter(has_text=re.compile(r"^compris\s*!?$", re.I)).first
    if await got_it.count():
        await got_it.click()
        await page.wait_for_timeout(300)


async def _capture_scene(page, out_dir: Path, index: int, name: str, element) -> Path:
    """
    Capture une "scene" : le viewport entier (fond, pour le flou) + l'element
    precis (carte nette) -- composes en une seule image verticale prete a
    animer par scene_compose.compose_scene().
    """
    bg_bytes = await page.screenshot()
    fg_bytes = await element.screenshot()
    scene = compose_scene(Image.open(BytesIO(bg_bytes)), Image.open(BytesIO(fg_bytes)))
    path = out_dir / f"{index:02d}_{name}.png"
    scene.save(path)
    return path


def _make_simple_section_capture(label: str, name: str):
    """Fabrique une feature "clique cet onglet du dock, capture le panneau"."""

    async def capture(ctx: DemoContext):
        tab = ctx.page.locator(f"aside nav button[aria-label='{label}']").first
        if await tab.count() == 0:
            return
        await tab.click()
        await ctx.page.wait_for_timeout(700)
        await ctx.shoot(name, ctx.form_panel)

    return capture


async def _capture_experiences(ctx: DemoContext):
    """
    Parcours en 3 temps plutot qu'une capture unique isolee : liste repliee
    -> carte ouverte (formulaire poste/entreprise/dates) -> double-clic sur
    les missions dans le LivePreview (data-exp-part="missions"), qui ouvre
    MissionsModal directement -- exactement le geste utilisateur reel.
    """
    tab = ctx.page.locator("aside nav button[aria-label='Expériences']").first
    if await tab.count() == 0:
        return
    await tab.click()
    await ctx.page.wait_for_timeout(700)
    await ctx.shoot("section_experiences_liste", ctx.form_panel)

    first_card = ctx.page.locator("[role='button'][aria-expanded='false']").first
    if await first_card.count() == 0:
        return
    await first_card.click()
    await ctx.page.wait_for_timeout(500)
    await ctx.shoot("section_experiences_ouverte", ctx.form_panel)

    mission_area = ctx.page.locator("[data-exp-part='missions']:visible").first
    if await mission_area.count() == 0:
        return
    await mission_area.dblclick()
    dialog = ctx.page.locator("div[role='dialog']").first
    try:
        await dialog.wait_for(state="visible", timeout=6000)
        await ctx.page.wait_for_timeout(500)
        await ctx.shoot("edition_missions", dialog)
        await ctx.page.keyboard.press("Escape")
        await ctx.page.wait_for_timeout(400)
    except Exception:
        print("ATTENTION: modale missions introuvable, capture ignoree", file=sys.stderr)


async def _capture_design(ctx: DemoContext):
    tab = ctx.page.locator(f"aside nav button[aria-label='{DESIGN_TAB_LABEL}']").first
    if await tab.count() == 0:
        return
    await tab.click()
    await ctx.page.wait_for_timeout(700)
    await ctx.shoot("design", ctx.form_panel)


async def _capture_fonctions_ia(ctx: DemoContext):
    """Bouton "Adapter a une offre" : ouvre une modale dediee (dialog)."""
    adapt_button = ctx.page.locator("button:visible").filter(has=ctx.page.locator("svg.lucide-zap")).first
    if await adapt_button.count() == 0:
        return
    await adapt_button.click()
    dialog = ctx.page.locator("div[role='dialog']").first
    try:
        await dialog.wait_for(state="visible", timeout=8000)
        await ctx.page.wait_for_timeout(600)
        await ctx.shoot("fonctions_ia", dialog)
        await ctx.page.keyboard.press("Escape")
        await ctx.page.wait_for_timeout(400)
    except Exception:
        print("ATTENTION: modale IA introuvable, capture ignoree", file=sys.stderr)


async def _capture_apercu_cv(ctx: DemoContext):
    """
    Mode focus (icone agrandir de la barre superieure) : affiche l'apercu
    stylise en plein ecran. Doit rester la DERNIERE feature executee -- le
    mode focus masque le dock de sections, donc plus aucune autre feature
    n'est accessible une fois ce bouton clique.
    """
    focus_button = ctx.page.locator("button[title]:visible").filter(has=ctx.page.locator("svg.lucide-maximize-2")).first
    if await focus_button.count() == 0:
        return
    await focus_button.click()
    await ctx.page.wait_for_timeout(1200)
    preview = ctx.page.locator("main").first
    await ctx.shoot("apercu_cv", preview)


@dataclass
class Feature:
    id: str
    label: str
    # Phrase courte injectee dans le prompt du script audio (1_generate_script.py)
    # pour que le texte parle de ce qui est reellement montre a l'ecran.
    script_hint: str
    capture: Callable[[DemoContext], Awaitable[None]]
    # Certaines features ferment des portes derriere elles (le mode focus
    # masque le dock) : forcees en derniere position par run_features().
    must_be_last: bool = False


FEATURES: dict[str, Feature] = {
    f.id: f
    for f in [
        Feature("identite", "Identite / profil", "modifier ses infos de contact et son resume en un clic",
                _make_simple_section_capture("Identité", "section_identite")),
        Feature("experiences", "Experiences (edition + missions IA)",
                "deplier une experience et reecrire ses missions directement depuis l'apercu",
                _capture_experiences),
        Feature("formation", "Formation", "renseigner ses diplomes et formations",
                _make_simple_section_capture("Formation", "section_formation")),
        Feature("competences", "Competences", "lister ses competences cles",
                _make_simple_section_capture("Compétences", "section_competences")),
        Feature("langues", "Langues", "indiquer son niveau dans chaque langue",
                _make_simple_section_capture("Langues", "section_langues")),
        Feature("design", "Design / 33 themes", "changer de theme de mise en page en un clic parmi 33",
                _capture_design),
        Feature("fonctions_ia", "Adapter a une offre (IA)",
                "adapter automatiquement son CV a une offre d'emploi precise avec l'IA",
                _capture_fonctions_ia),
        Feature("apercu_cv", "Apercu stylise plein ecran", "voir le rendu final, fidele et stylise, du CV",
                _capture_apercu_cv, must_be_last=True),
    ]
}

# Ordre par defaut (et fallback) si un reel ne precise pas de features.
DEFAULT_FEATURE_ORDER = [
    "identite", "experiences", "formation", "competences", "langues",
    "design", "fonctions_ia", "apercu_cv",
]


def resolve_feature_order(feature_ids: list[str] | None) -> list[str]:
    """
    Valide et ordonne une liste d'ids choisie pour un reel : ids inconnus
    ignores (silencieux -- un id perime dans un vieux scripts.json ne doit
    pas faire echouer tout le pipeline), ordre = DEFAULT_FEATURE_ORDER,
    "apercu_cv" toujours pousse en dernier (must_be_last).
    """
    if not feature_ids:
        return list(DEFAULT_FEATURE_ORDER)
    chosen = [fid for fid in DEFAULT_FEATURE_ORDER if fid in feature_ids and fid in FEATURES]
    last = [fid for fid in chosen if FEATURES[fid].must_be_last]
    rest = [fid for fid in chosen if not FEATURES[fid].must_be_last]
    return rest + last


async def run_features(page, out_dir: Path, shoot, form_panel, feature_ids: list[str] | None = None):
    """Execute, dans l'ordre resolu, les features choisies pour ce reel."""
    ctx = DemoContext(page=page, form_panel=form_panel, shoot=shoot)
    for fid in resolve_feature_order(feature_ids):
        await FEATURES[fid].capture(ctx)
