"""
Catalogue des fonctionnalites d'OpusCV capturables (modes screenshots et
video_desktop de 3_record_demo.py).

Chaque fonctionnalite est une petite fonction Playwright autonome -- pas une
liste de selecteurs en JSON -- parce que l'enchainement reel a des
dependances d'etat (onglet a ouvrir avant de deplier une carte, modale a
refermer avant la suivante) qui se pretent mal a du pur declaratif.

Le meme catalogue sert deux fins :
  - 1_generate_script.py le donne a l'IA (id + description de ce qu'on voit
    a l'ecran) pour qu'elle ecrive un scenario scene par scene, chaque scene
    = une fonctionnalite + la phrase dite pendant qu'elle est a l'ecran ;
  - 3_record_demo.py capture les fonctionnalites du scenario. Chaque capture
    est etiquetee avec son id de fonctionnalite : le montage (3b/3c) les
    replace ensuite dans l'ORDRE DU SCENARIO, cale sur le timing de la voix
    -- l'ordre de capture, lui, reste libre (dicte par les dependances d'etat).

Selecteurs : titres/aria-label FR exacts de l'app (locales/fr/*.json du repo
cv-optimizer-fastapi-react), icone lucide en secours quand le titre peut
changer (ex: le titre devient le message de quota epuise).

    python features.py   # liste le catalogue (utile pour ecrire un scenario a la main)
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Awaitable, Callable

# Offre d'emploi fictive tapee dans les modales "Adapter" / "Lettre" : montre
# le geste reel (coller une offre) sans lancer la generation IA, qui
# consommerait le quota du compte demo a chaque execution du pipeline.
SAMPLE_JOB_OFFER = (
    "Responsable Marketing Digital (CDI, Paris) - Vous pilotez l'acquisition "
    "B2B, le SEO et les campagnes LinkedIn Ads. 5 ans d'experience minimum, "
    "maitrise de HubSpot et de Google Analytics 4."
)


@dataclass
class DemoContext:
    page: object
    form_panel: object
    shoot: Callable[[str, object], Awaitable[None]]
    # Generes par 1_generate_script.py (Gemini) pour ce scenario precis --
    # vide/None si non fournis (scenario impose sans IA, appel direct de
    # features.py) : les fonctions ci-dessous retombent alors sur les
    # valeurs par defaut (SAMPLE_JOB_OFFER, choix d'index actuel).
    job_offer: str = ""
    theme_style: str = ""


# ---------------------------------------------------------------------------
# Helpers d'etat
# ---------------------------------------------------------------------------

async def dismiss_onboarding_tooltip(page):
    """
    Popover d'aide au premier affichage de l'editeur (EditorDock.jsx :
    "Comment modifier votre CV" + bouton "Compris !") : plaque sur le dock
    lateral tant qu'on ne l'a pas ferme -- masque les boutons de section.
    """
    got_it = page.locator("button:visible").filter(has_text=re.compile(r"^compris\s*!?$", re.I)).first
    if await got_it.count():
        await got_it.click()
        await page.wait_for_timeout(300)


def _checklist_button(page):
    # ChecklistButton.jsx : seul <button aria-expanded> de la barre du haut
    # (les cartes d'experience sont des <div role=button>, exclues ici).
    return page.locator("button[aria-expanded]:visible").filter(
        has_text=re.compile(r"corriger|votre cv|point|pr[eê]t", re.I)).first


async def close_checklist_if_open(page):
    """
    La checklist s'ouvre toute seule des que l'aide du dock est fermee
    (autoOpen) et pose un calque plein ecran qui intercepte tous les clics
    suivants -- a refermer avant toute autre interaction.
    """
    button = _checklist_button(page)
    if not (await button.count() and await button.get_attribute("aria-expanded") == "true"):
        return
    # Le calque "clic a l'exterieur" (fixed inset-0) recouvre le bouton lui-meme :
    # on ferme par Echap, sinon par un clic sur ce calque, en dernier recours force.
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    if await button.get_attribute("aria-expanded") == "true":
        backdrop = page.locator("div.fixed.inset-0.z-40").first
        if await backdrop.count():
            await backdrop.click(position={"x": 5, "y": 5}, timeout=3000)
        else:
            await button.click(force=True, timeout=3000)
    await page.wait_for_timeout(400)


async def reset_state(page):
    """Referme toute modale restee ouverte (y compris une confirmation de fermeture)."""
    for _ in range(3):
        dialogs = page.locator("div[role='dialog']:visible")
        if await dialogs.count() == 0:
            break
        confirm = dialogs.last.locator("button").filter(
            has_text=re.compile(r"fermer sans|abandonner|quitter|effacer", re.I)).first
        if await confirm.count():
            await confirm.click()
        else:
            await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
    await close_checklist_if_open(page)


async def _top_button(page, title: str, icon: str):
    """Bouton de la barre du haut, par titre exact, sinon par son icone lucide."""
    by_title = page.locator(f'button[title="{title}"]:visible').first
    if await by_title.count():
        return by_title
    by_icon = page.locator("button:visible").filter(has=page.locator(f"svg.lucide-{icon}")).first
    return by_icon if await by_icon.count() else None


async def _open_dialog(page, button, timeout: int = 8000):
    await button.click()
    dialog = page.locator("div[role='dialog']:visible").last
    await dialog.wait_for(state="visible", timeout=timeout)
    await page.wait_for_timeout(600)
    return await _dialog_panel(dialog)


async def _dialog_panel(dialog):
    """
    Modal.jsx pose role=dialog sur le fond noir plein ecran : la carte
    utile est son premier enfant. La capturer plutot que le fond, sinon la
    fenetre ne fait qu'un petit rectangle illisible au milieu du plan.
    """
    panel = dialog.locator(":scope > div").first
    if await panel.count():
        box, full = await panel.bounding_box(), await dialog.bounding_box()
        if box and full and box["width"] * box["height"] < 0.8 * full["width"] * full["height"]:
            return panel
    return dialog


async def _click_dock(ctx: DemoContext, label: str) -> bool:
    tab = ctx.page.locator(f'aside nav button[aria-label="{label}"]').first
    if await tab.count() == 0:
        print(f"ATTENTION: onglet '{label}' introuvable", file=sys.stderr)
        return False
    await tab.click()
    await ctx.page.wait_for_timeout(700)
    return True


# Bouton "d'action" d'une capture : c'est la que le curseur anime clique et
# que la camera zoome (3b_build_video_from_screenshots.py).
ACTION_RE = re.compile(r"corriger|appliquer|adapter|g[ée]n[ée]rer|analyser|comparer|valider|relancer|"
                       r"t[ée]l[ée]charger|enregistrer|ajouter|reformuler|modifier|essayer", re.I)


async def _focus_point(element, rect: tuple[int, int, int, int]) -> list[int] | None:
    """
    -> [x, y] (px de la scene 1080x1920) du bouton d'action le plus parlant de
    l'element capture, sinon de son dernier bouton visible ; None si aucun.
    """
    try:
        box = await element.bounding_box()
        buttons = element.locator("button:visible")
        count = min(await buttons.count(), 40)
        best = None
        for k in range(count):
            b = buttons.nth(k)
            label = (await b.inner_text(timeout=500)).strip()
            bb = await b.bounding_box()
            if not bb or bb["width"] < 8:
                continue
            if ACTION_RE.search(label):
                best = bb
                break
            best = bb
        if not box or not best:
            return None
        rx = (best["x"] + best["width"] / 2 - box["x"]) / box["width"]
        ry = (best["y"] + best["height"] / 2 - box["y"]) / box["height"]
        if not (0 <= rx <= 1 and 0 <= ry <= 1):
            return None
        x, y, w, h = rect
        return [round(x + rx * w), round(y + ry * h)]
    except Exception:
        return None


async def _capture_scene(page, out_dir: Path, index: int, name: str, element,
                         meta: dict | None = None) -> Path:
    """
    Capture une "scene" : le viewport entier (fond, pour le flou) + l'element
    precis (carte nette) -- composes en une seule image verticale prete a
    animer par scene_compose.compose_scene(). meta (optionnel) recoit
    "card" = [x, y, w, h] de la carte dans l'image, pour le souligne anime.
    """
    from PIL import Image
    from scene_compose import card_rect, compose_scene

    bg_bytes = await page.screenshot()
    fg_bytes = await element.screenshot()
    fg = Image.open(BytesIO(fg_bytes))
    scene = compose_scene(Image.open(BytesIO(bg_bytes)), fg)
    if meta is not None:
        rect = card_rect(fg.size)
        meta["card"] = list(rect)
        focus = await _focus_point(element, rect)
        if focus:
            meta["focus"] = focus
    path = out_dir / f"{index:02d}_{name}.png"
    scene.save(path)
    return path


# ---------------------------------------------------------------------------
# Fonctionnalites
# ---------------------------------------------------------------------------

def _make_section_capture(label: str, name: str):
    async def capture(ctx: DemoContext):
        if await _click_dock(ctx, label):
            await ctx.shoot(name, ctx.form_panel)
    return capture


async def _capture_experiences(ctx: DemoContext):
    """
    Liste repliee -> carte ouverte -> tiroir d'edition des missions, ouvert
    par le bouton "Modifier les missions" de la carte (MissionsModal.jsx, un
    Drawer role=dialog). L'apercu etant desormais le PDF exact (canvas), le
    double-clic dans l'apercu n'a plus de cible DOM a viser.
    """
    if not await _click_dock(ctx, "Expériences"):
        return
    await ctx.shoot("experiences_liste", ctx.form_panel)

    first_card = ctx.page.locator("[role='button'][aria-expanded='false']").first
    if await first_card.count() == 0:
        return
    await first_card.click()
    await ctx.page.wait_for_timeout(500)
    await ctx.shoot("experiences_ouverte", ctx.form_panel)

    edit = ctx.form_panel.locator("button:visible").filter(has_text=re.compile(r"modifier les missions", re.I)).first
    if await edit.count() == 0:
        return
    await edit.click()
    dialog = ctx.page.locator("div[role='dialog']:visible").last
    await dialog.wait_for(state="visible", timeout=6000)
    await ctx.page.wait_for_timeout(600)
    await ctx.shoot("experiences_missions", dialog)
    await reset_state(ctx.page)


async def _preview_page(page):
    """
    Premiere page du CV dans l'apercu : le PDF exact (ApercuExact.jsx, une
    div blanche par page) pour un compte, sinon l'apercu HTML (<main>).
    """
    exact = page.locator(".apercu-exact > div").first
    try:
        # Pendant un nouveau rendu, l'apercu HTML reprend la place du PDF.
        await exact.wait_for(state="visible", timeout=15000)
        return exact
    except Exception:
        return page.locator("main").first


async def _after_preview_refresh(page, action):
    """
    Lance action() et attend le nouveau rendu de l'apercu exact (POST
    /api/apercu, puis dessin pdf.js) ; sans rendu serveur (apercu HTML),
    simple pause.
    """
    try:
        async with page.expect_response(lambda r: "/api/apercu" in r.url, timeout=20000):
            await action()
        # pdf.js ouvre le nouveau document puis redessine chaque page.
        await page.wait_for_timeout(2500)
    except Exception:
        await page.wait_for_timeout(1200)


async def _open_design(ctx: DemoContext) -> bool:
    if not await _click_dock(ctx, "Design"):
        return False
    await ctx.page.wait_for_timeout(300)
    return True


async def _capture_design_themes(ctx: DemoContext):
    """
    Panneau Design (structures en liste, themes en pastilles), puis deux
    themes appliques l'un apres l'autre : l'apercu change en direct -- le
    "avant/apres" le plus visuel du produit. Rien n'est sauvegarde.
    """
    if not await _open_design(ctx):
        return
    await ctx.shoot("design_panneau", ctx.form_panel)

    # Pastilles de theme (DesignPanel.jsx) : seuls boutons aria-pressed a
    # porter un title (le nom du theme) ; les structures n'en ont pas.
    themes = ctx.form_panel.locator("button[aria-pressed][title]")
    count = await themes.count()
    titles = [(await themes.nth(i).get_attribute("title") or "") for i in range(count)]
    pressed = [await themes.nth(i).get_attribute("aria-pressed") == "true" for i in range(count)]
    candidates = [i for i in range(count) if not pressed[i]]

    picks = []
    if ctx.theme_style and candidates:
        # theme_style vient de 1_generate_script.py (Gemini), ex. "sobre et
        # corporate" -- matching texte simple contre les noms REELS des
        # themes affiches (donnee live, jamais inventee).
        style_words = {w for w in re.split(r"\W+", ctx.theme_style.lower()) if len(w) > 2}
        picks = [i for i in candidates if any(w in titles[i].lower() for w in style_words)][:2]
    # A defaut : deux themes repartis dans la palette de la structure active.
    for i in (candidates[len(candidates) // 2:] + candidates[:1]) if candidates else []:
        if len(picks) >= 2:
            break
        if i not in picks:
            picks.append(i)
    for n, idx in enumerate(picks):
        theme = themes.nth(idx)
        await theme.scroll_into_view_if_needed()
        await _after_preview_refresh(ctx.page, theme.click)
        await ctx.shoot(f"design_theme_{n + 1}", await _preview_page(ctx.page))


# Structures montrees par "mises_en_page" (libelles de DesignPanel.jsx,
# editor.designPanel.layouts), dans cet ordre ; la structure d'origine est
# remise a la fin pour ne pas changer l'apparence des captures suivantes.
LAYOUT_PICKS = ("Frise", "Classique", "Minimal")


async def _capture_mises_en_page(ctx: DemoContext):
    """Six structures (Colonne, Classique, Minimal, Bandeau, ATS, Frise) : trois appliquees tour a tour."""
    if not await _open_design(ctx):
        return
    group = ctx.form_panel.locator("div[role='group'][aria-label='Structure']").first
    if await group.count() == 0:
        print("ATTENTION: liste des structures introuvable", file=sys.stderr)
        return
    buttons = group.locator("button")
    initial = None
    for k in range(await buttons.count()):
        if await buttons.nth(k).get_attribute("aria-pressed") == "true":
            initial = buttons.nth(k)
    await ctx.shoot("mises_en_page_liste", group)
    for n, label in enumerate(LAYOUT_PICKS):
        button = buttons.filter(has_text=re.compile(rf"^\s*{label}", re.I)).first
        if await button.count() == 0 or await button.get_attribute("aria-pressed") == "true":
            continue
        await _after_preview_refresh(ctx.page, button.click)
        await ctx.shoot(f"mise_en_page_{n + 1}", await _preview_page(ctx.page))
    if initial is not None:
        await _after_preview_refresh(ctx.page, initial.click)


async def _capture_personnalisation(ctx: DemoContext):
    """Blocs "Details" (forme de la photo, langues en points, icones) et "Reglages fins" du panneau Design."""
    if not await _open_design(ctx):
        return
    opened = []
    for titre in ("Détails", "Réglages fins"):
        toggle = ctx.form_panel.locator("button[aria-expanded]").filter(has_text=re.compile(rf"^\s*{titre}", re.I)).first
        if await toggle.count() and await toggle.get_attribute("aria-expanded") != "true":
            await toggle.click()
            await ctx.page.wait_for_timeout(400)
            opened.append(toggle)
    if opened:
        await opened[0].scroll_into_view_if_needed()
        await ctx.page.wait_for_timeout(300)
    await ctx.shoot("personnalisation", ctx.form_panel)
    # Ferme ce qu'on a ouvert : l'etat des replis est retenu par le navigateur.
    for toggle in opened:
        await toggle.click()
        await ctx.page.wait_for_timeout(200)


async def _capture_sections_perso(ctx: DemoContext):
    """Structure -> "Ajouter une section" -> titre tape (Certifications), sans la creer."""
    if not await _click_dock(ctx, "Structure — ordre des blocs"):
        return
    add = ctx.form_panel.locator("button:visible").filter(has_text=re.compile(r"ajouter une section", re.I)).first
    if await add.count() == 0:
        return
    await add.click()
    await ctx.page.wait_for_timeout(400)
    field = ctx.form_panel.locator("input[aria-label='Titre de la nouvelle section']").first
    if await field.count():
        await field.press_sequentially("Certifications", delay=40)
        await ctx.page.wait_for_timeout(300)
        await field.scroll_into_view_if_needed()
    await ctx.shoot("sections_perso", ctx.form_panel)
    if await field.count():
        await field.fill("")
        await field.press("Escape")


async def _capture_convertir(ctx: DemoContext):
    """Fenetre "Convertir le CV" : langue cible choisie (anglais), sans lancer la traduction (IA)."""
    button = await _top_button(ctx.page, "Convertir le CV", "languages")
    if button is None:
        print("ATTENTION: bouton 'Convertir le CV' introuvable", file=sys.stderr)
        return
    dialog = await _open_dialog(ctx.page, button)
    target = dialog.locator("button:visible, label:visible").filter(has_text=re.compile(r"^\s*english\s*$", re.I)).first
    if await target.count():
        await target.click()
        await ctx.page.wait_for_timeout(400)
    else:
        select = dialog.locator("select").first
        if await select.count():
            try:
                await select.select_option(label="English")
            except Exception:
                pass
    await ctx.shoot("convertir", dialog)
    await reset_state(ctx.page)


async def _capture_checklist(ctx: DemoContext):
    button = _checklist_button(ctx.page)
    if await button.count() == 0:
        return
    if await button.get_attribute("aria-expanded") != "true":
        await button.click()
    panel = ctx.page.locator("div.fixed.shadow-2xl.z-50:visible").first
    await panel.wait_for(state="visible", timeout=6000)
    await ctx.page.wait_for_timeout(500)
    await ctx.shoot("checklist", panel)
    await close_checklist_if_open(ctx.page)


def _make_offer_modal_capture(title: str, icon: str, name: str):
    """Modale IA avec champ "offre d'emploi" : ouverture, puis offre tapee (sans generer)."""

    async def capture(ctx: DemoContext):
        button = await _top_button(ctx.page, title, icon)
        if button is None:
            print(f"ATTENTION: bouton '{title}' introuvable", file=sys.stderr)
            return
        dialog = await _open_dialog(ctx.page, button)
        await ctx.shoot(f"{name}_ouverte", dialog)
        textarea = dialog.locator("textarea").first
        if await textarea.count():
            await textarea.click()
            await textarea.press_sequentially(ctx.job_offer or SAMPLE_JOB_OFFER, delay=12)
            await ctx.page.wait_for_timeout(400)
            await ctx.shoot(f"{name}_offre", dialog)
            await textarea.fill("")  # evite la confirmation "abandonner ?" a la fermeture
        await reset_state(ctx.page)

    return capture


async def _capture_relecture(ctx: DemoContext):
    """
    Fenetre de relecture : les fautes deja relevees (analyse de l'import), une
    corrigee en un clic ; sans faute relevee, l'invitation "Relisez votre CV"
    (la relecture elle-meme est un appel IA, jamais lance ici).
    """
    button = await _top_button(ctx.page, "Relecture orthographique", "spell-check-2")
    if button is None:
        return
    dialog = await _open_dialog(ctx.page, button)
    await ctx.shoot("relecture", dialog)
    fix = dialog.locator("button").filter(has_text=re.compile(r"^\s*corriger\s*$", re.I)).first
    if await fix.count():
        await fix.click()
        await ctx.page.wait_for_timeout(700)
        await ctx.shoot("relecture_corrigee", dialog)
    await reset_state(ctx.page)


async def _capture_partage(ctx: DemoContext):
    button = await _top_button(ctx.page, "Partager", "share-2")
    if button is None:
        return
    dialog = await _open_dialog(ctx.page, button)
    await ctx.page.wait_for_timeout(800)  # GET /shares
    await ctx.shoot("partage", dialog)
    await reset_state(ctx.page)


async def _capture_apercu_pdf(ctx: DemoContext):
    """
    L'apercu de l'editeur EST le PDF (ApercuExact.jsx : rendu serveur dessine
    par pdf.js, badge "PDF exact" dans la barre d'outils) : on capture la
    colonne d'apercu entiere, barre comprise. L'ancienne fenetre "Apercu
    fidele" n'existe plus.
    """
    page_el = ctx.page.locator(".apercu-exact > div").first
    try:
        await page_el.wait_for(state="visible", timeout=30000)
    except Exception:
        print("ATTENTION: apercu exact non affiche, capture de l'apercu HTML", file=sys.stderr)
    await ctx.page.wait_for_timeout(800)
    await ctx.shoot("apercu_pdf", ctx.page.locator("main").first)


async def _capture_mode_sombre(ctx: DemoContext):
    button = await _top_button(ctx.page, "Thème sombre", "moon")
    if button is None:
        return
    await button.click()
    await ctx.page.wait_for_timeout(900)
    await ctx.shoot("mode_sombre", ctx.page.locator("body"))
    back = await _top_button(ctx.page, "Thème clair", "sun")
    if back is not None:
        await back.click()
        await ctx.page.wait_for_timeout(500)


async def _capture_entretien(ctx: DemoContext):
    """Consomme une action IA : la modale genere les questions des son ouverture."""
    button = await _top_button(ctx.page, "Questions d'entretien", "message-square")
    if button is None:
        return
    dialog = await _open_dialog(ctx.page, button)
    # "networkidle" ne suffit pas : la generation IA peut repondre apres. On
    # attend que le loader "Préparation des questions..." ait disparu --
    # sinon la capture montre un spinner sur fond vide. Toujours la apres
    # 60 s : pas de capture (le montage reprend la scene precedente).
    loader = ctx.page.get_by_text(re.compile(r"préparation des questions", re.I))
    try:
        await ctx.page.wait_for_load_state("networkidle", timeout=45000)
        await loader.first.wait_for(state="hidden", timeout=60000)
    except Exception:
        if await loader.count() and await loader.first.is_visible():
            print("ATTENTION: questions d'entretien toujours en preparation, capture ignoree")
            await reset_state(ctx.page)
            return
    await ctx.page.wait_for_timeout(1000)
    await ctx.shoot("entretien", dialog)
    await reset_state(ctx.page)


async def _capture_adapter(ctx: DemoContext):
    # Titre = libelle, ou message de quota epuise -> icone zap en secours.
    await _make_offer_modal_capture("Adapter à une offre", "zap", "adapter")(ctx)


async def _capture_apercu_cv(ctx: DemoContext):
    """
    Mode focus : apercu stylise plein ecran. Toujours execute en DERNIER --
    le mode focus demonte le dock, plus aucune autre fonctionnalite n'est
    accessible ensuite.
    """
    button = await _top_button(ctx.page, "Focus preview", "maximize-2")
    if button is None:
        return
    await button.click()
    await ctx.page.wait_for_timeout(1500)
    await ctx.shoot("apercu_cv", await _preview_page(ctx.page))


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass
class Feature:
    id: str
    label: str
    # Ce que le spectateur VOIT a l'ecran -- donne a l'IA pour qu'elle ecrive
    # une phrase qui colle a l'image affichee pendant qu'elle est dite.
    description: str
    capture: Callable[[DemoContext], Awaitable[None]] | None
    must_be_last: bool = False
    # Declenche un appel IA facture sur le quota du compte demo : exclu par
    # defaut (ALLOW_AI_QUOTA_FEATURES=1 pour l'autoriser).
    consumes_ai: bool = False


# "dashboard" n'a pas de fonction : il est capture pendant la mise en place
# (3_record_demo.py), avant l'ouverture de l'editeur.
FEATURES: dict[str, Feature] = {f.id: f for f in [
    Feature("dashboard", "Mes CVs", "le tableau de bord avec la liste des CV sauvegardes et leurs actions (renommer, dupliquer)", None),
    Feature("checklist", "Points a corriger", "la liste des points a corriger detectes sur le CV (defauts, puis idees), chacun explique en une phrase -- pas de note globale", _capture_checklist),
    Feature("identite", "Identite / profil", "le formulaire identite : photo, poste vise, nom, email, telephone, ville, LinkedIn, site, permis, resume", _make_section_capture("Identité", "identite")),
    Feature("experiences", "Experiences + missions", "la liste des experiences, une experience depliee, puis le panneau d'edition de ses missions", _capture_experiences),
    Feature("formation", "Formation", "la section formation : diplomes, ecoles, dates", _make_section_capture("Formation", "formation")),
    Feature("competences", "Competences", "les competences par groupe, avec les competences proposees a ajouter en un clic", _make_section_capture("Compétences", "competences")),
    Feature("langues", "Langues", "les langues avec leur niveau", _make_section_capture("Langues", "langues")),
    Feature("structure", "Structure", "l'ordre des blocs du CV (glisser-deposer), la langue et le format de page du CV, le pied de page", _make_section_capture("Structure — ordre des blocs", "structure")),
    Feature("sections_perso", "Sections libres", "l'ajout d'une section libre au CV (certifications, projets, benevolat...)", _capture_sections_perso),
    Feature("relecture", "Relecture orthographique", "la fenetre de relecture : l'IA repere fautes d'orthographe, de grammaire et d'accord ; chaque correction se valide en un clic", _capture_relecture),
    Feature("fonctions_ia", "Adapter a une offre (IA)", "la fenetre 'Adapter a une offre' : on colle une offre d'emploi, l'IA suggere les ameliorations et cree une variante du CV pour ce poste", _capture_adapter),
    Feature("lettre_motivation", "Lettre de motivation (IA)", "la fenetre de lettre de motivation : on colle l'offre, l'IA ecrit une lettre calee sur l'offre et le CV, a telecharger en PDF aux couleurs du CV", _make_offer_modal_capture("Lettre de motivation", "mail", "lettre")),
    Feature("convertir", "Convertir (langue, format)", "la fenetre 'Convertir le CV' : une variante en anglais, allemand ou espagnol, ou au format Letter (Etats-Unis, Canada)", _capture_convertir),
    Feature("partage", "Partage par lien", "le partage du CV par un lien public, consultable sans compte ni piece jointe", _capture_partage),
    Feature("apercu_pdf", "Apercu = PDF exact", "l'apercu de l'editeur, qui est le PDF exact tel qu'il sera telecharge, au pixel pres", _capture_apercu_pdf),
    Feature("design", "Themes (41) en direct", "le panneau Design puis le CV qui change de theme en un clic (41 themes)", _capture_design_themes),
    Feature("mises_en_page", "6 mises en page", "les six mises en page (colonne, classique, minimal, bandeau, ATS, frise), puis le meme CV en bandeau, en frise et en minimal", _capture_mises_en_page),
    Feature("personnalisation", "Reglages fins", "les reglages de detail : forme de la photo, langues en points, icones des titres, taille du texte, interligne, marges", _capture_personnalisation),
    Feature("mode_sombre", "Mode sombre", "l'editeur complet en mode sombre", _capture_mode_sombre),
    Feature("entretien", "Simulation d'entretien (IA)", "six questions d'entretien probables generees depuis le CV, avec une piste de reponse", _capture_entretien, consumes_ai=True),
    Feature("apercu_cv", "Apercu plein ecran", "le rendu final du CV, stylise, en plein ecran", _capture_apercu_cv, must_be_last=True),
]}

# Ordre de CAPTURE (dependances d'etat), independant de l'ordre d'affichage
# dans le scenario. La checklist passe tot (elle s'ouvre seule), le design
# et le mode sombre tard (ils changent l'apparence des captures suivantes),
# mises_en_page apres les themes (changer de structure change de theme),
# l'entretien juste avant la fin
# (sa confirmation de fermeture est la plus susceptible de bloquer la suite).
DEFAULT_FEATURE_ORDER = [
    "dashboard", "checklist", "identite", "experiences", "formation", "competences", "langues",
    "structure", "sections_perso", "relecture", "fonctions_ia", "lettre_motivation", "convertir", "partage",
    "apercu_pdf", "personnalisation", "design", "mises_en_page", "mode_sombre", "entretien", "apercu_cv",
]

# Anciens ids (scripts.json generes avant le catalogue actuel).
ALIASES = {"design_themes": "design"}


def ai_quota_allowed() -> bool:
    return os.environ.get("ALLOW_AI_QUOTA_FEATURES", "").lower() in ("1", "true", "yes")


def available_features() -> dict[str, Feature]:
    """Catalogue propose a l'IA / accepte a la capture (sans les features a quota, sauf opt-in)."""
    allow = ai_quota_allowed()
    return {fid: f for fid, f in FEATURES.items() if allow or not f.consumes_ai}


def normalize_feature_id(fid: str | None) -> str | None:
    if not fid:
        return None
    fid = ALIASES.get(fid.strip(), fid.strip())
    return fid if fid in available_features() else None


def resolve_feature_order(feature_ids: list[str] | None) -> list[str]:
    """
    Ids demandes -> ordre de capture valide : ids inconnus ignores (un vieux
    scripts.json ne doit pas faire echouer le pipeline), doublons retires,
    ordre = DEFAULT_FEATURE_ORDER, features must_be_last en dernier.
    """
    available = available_features()
    if not feature_ids:
        chosen = [fid for fid in DEFAULT_FEATURE_ORDER if fid in available]
    else:
        wanted = {normalize_feature_id(f) for f in feature_ids} - {None}
        chosen = [fid for fid in DEFAULT_FEATURE_ORDER if fid in wanted]
    rest = [fid for fid in chosen if not FEATURES[fid].must_be_last]
    last = [fid for fid in chosen if FEATURES[fid].must_be_last]
    return rest + last


async def run_features(page, shoot, form_panel, feature_ids: list[str] | None = None,
                        job_offer: str = "", theme_style: str = ""):
    """
    Execute les fonctionnalites demandees (sauf "dashboard", deja capture a
    la mise en place). `shoot(feature_id, name, element)` recoit l'id de la
    fonctionnalite en cours, pour que le montage puisse retrouver ses
    captures. Une fonctionnalite qui echoue est signalee et sautee, sans
    faire tomber les autres (le montage retombe alors sur une autre capture).
    """
    for fid in resolve_feature_order(feature_ids):
        feature = FEATURES[fid]
        if feature.capture is None:
            continue

        async def feature_shoot(name, element, _fid=fid):
            await shoot(_fid, name, element)

        ctx = DemoContext(page=page, form_panel=form_panel, shoot=feature_shoot,
                           job_offer=job_offer, theme_style=theme_style)
        try:
            await feature.capture(ctx)
        except Exception as exc:
            print(f"ATTENTION: fonctionnalite '{fid}' en echec, sautee ({exc})", file=sys.stderr)
            try:
                await reset_state(page)
            except Exception:
                pass


if __name__ == "__main__":
    for fid, f in FEATURES.items():
        flag = " [consomme du quota IA : ALLOW_AI_QUOTA_FEATURES=1]" if f.consumes_ai else ""
        print(f"{fid:18} {f.label} -- {f.description}{flag}")
