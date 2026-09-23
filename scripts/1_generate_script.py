"""
Genere les SCENARIOS des reels via l'API Gemini, a partir du catalogue
editorial (catalog/, cf. catalog.py) :

  format  -> structure de la video (liste d'erreurs, mythe/realite, demo...)
  sujet   -> de quoi elle parle (conseil utile ou produit)
  accroche-> style des 2 premieres secondes (question choc, chiffre, POV...)
  theme   -> couleurs/polices/musique du montage

Chaque choix evite ce qui a ete publie recemment (output/content_history.json)
et respecte le mix conseil/produit de catalog/config.json : c'est ce qui
empeche les reels de tous se ressembler.

Un scenario est une suite de scenes ; chaque scene = une fonctionnalite reelle
d'OpusCV (id du catalogue features.py, montree a l'ecran) OU une carte texte
animee (conseil, mythe/realite, avant/apres...), + la phrase dite par la voix :

    {
      "format": "liste_erreurs", "categorie": "conseil", "sujet": "titre_cv",
      "hook": "erreur", "theme": "corail_energie",
      "titre": "...", "accroche_ecran": "Ton CV fait cette erreur",
      "legende": "...", "hashtags": ["#cv", ...], "duree_cible_s": 30,
      "scenes": [
        {"feature": "dashboard", "texte": "Tu fais sûrement cette erreur sur ton CV."},
        {"feature": "checklist", "texte": "...", "carte": {"surtitre": "Erreur n°1", "titre": "...", "texte": "...", "style": "normal"}},
        ...
      ],
      "features": ["dashboard", "checklist", ...]   # derive : ce qu'il faut capturer
    }

C'est ce decoupage qui permet la synchro : 4_generate_subtitles.py retrouve
dans l'audio quand commence chaque scene, et le montage (3b/3c) affiche la
bonne fonctionnalite (ou la carte) exactement pendant que la voix en parle.

Parametrable :
  --duration 15|30|45|60...  duree cible (nombre de scenes et de mots en decoulent)
  --format / --theme / --hook   impose un element du catalogue (sinon choix automatique)
  --angle "..."              sujet libre (sinon choisi dans catalog/sujets.json)
  --scenario fichier.json    scenario ecrit a la main (objet ou liste d'objets).
                             Scenes avec "texte" -> gardees telles quelles (aucun
                             appel IA si toutes en ont un) ; scenes sans "texte"
                             -> l'IA ecrit la narration pour la sequence imposee.

Usage:
    python 1_generate_script.py --n 3 --duration 30 --out output/scripts.json
    python 1_generate_script.py --n 1 --format mythe_realite --theme vert_confiance
    python 1_generate_script.py --scenario scenarios/exemple.json --out output/scripts.json

Necessite GEMINI_API_KEY (sauf scenario fourni entierement redige).
"""
import argparse
import json
import math
import os
import random
import re
import sys
from pathlib import Path

import catalog
from features import available_features, normalize_feature_id

PRODUCT_CONTEXT = """Produit : OpusCV (SaaS opuscv.tech), une application qui analyse un CV existant
(PDF ou Word) via l'IA, détecte ce qui bloque le passage des filtres ATS des recruteurs,
propose des corrections concrètes, puis régénère un PDF stylisé (33 thèmes).
L'utilisateur peut aussi adapter son CV à une offre précise, générer une lettre de motivation,
relire l'orthographe, et partager son CV par un lien public.
Plan gratuit : 3 CV sauvegardés. Plan Pro : illimité.
Ton de marque : direct, concret, orienté résultat (décrocher des entretiens), jamais « corporate »."""

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# Debit de la voix TTS (style "rythme rapide pour reseaux sociaux") mesure sur
# les voix Gemini FR : ~2.6 mots/s. Sert a traduire la duree cible en volume
# de texte -- c'est le texte qui fixe la duree reelle du reel, pas l'inverse.
WORDS_PER_SECOND = 2.6
MAX_ATTEMPTS = 3
ACCROCHE_MAX_WORDS = 8
ANIM_KEYS = ("anim", "overlay")
# Sans aucun de ces caracteres sur tout un script, le texte a ete ecrit sans
# accents : les sous-titres (texte exact du script) seraient faux.
ACCENT_RE = re.compile(r"[éèêëàâùûüîïôçœÉÈÊÀÂÙÛÎÔÇ]")
MIN_WORDS_ACCENT_CHECK = 12


def word_budget(duration: int) -> tuple[int, int, int]:
    target = round(duration * WORDS_PER_SECOND)
    return target, round(target * 0.85), round(target * 1.12)


def scene_bounds(duration: int) -> tuple[int, int]:
    # ~3 a ~6 s par scene : en dessous, l'image n'a pas le temps d'etre lue ;
    # au-dessus, le plan s'eternise sur un reel.
    lo = max(3, math.floor(duration / 6))
    hi = max(lo + 1, math.ceil(duration / 3))
    return lo, hi


def _gemini_json(client, prompt: str, temperature: float) -> dict:
    from google.genai import types

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
    )
    text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Plan editorial : format, sujet, accroche, theme
# ---------------------------------------------------------------------------

def choose_sujet(client, fmt: dict, avoid: list[str], rng: random.Random) -> dict:
    """
    Reflexion strategique : Gemini choisit, parmi les sujets compatibles avec
    le format, le plus prometteur maintenant (en evitant les recents).
    Echec -> tirage aleatoire parmi les sujets non recents.
    """
    candidates = catalog.compatible_sujets(fmt)
    fresh = [s for s in candidates if s["id"] not in avoid] or candidates
    listing = "\n".join(f'- {s["id"]} : {s["texte"]}' for s in fresh)
    prompt = f"""Tu es stratège de contenu TikTok/Instagram pour OpusCV (optimisation de CV par IA).

{PRODUCT_CONTEXT}

Le prochain reel suit le format « {fmt['nom']} » : {fmt['structure']}

Sujets possibles (non utilisés récemment) :
{listing}

Choisis le sujet qui a le plus de chances d'arrêter le scroll d'un chercheur d'emploi et de
bien fonctionner avec ce format. Réponds UNIQUEMENT en JSON : {{"id": "...", "raison": "..."}}"""
    try:
        data = _gemini_json(client, prompt, 0.9)
        chosen = next((s for s in fresh if s["id"] == data.get("id")), None)
        if chosen:
            print(f"    sujet : {chosen['id']} -> {data.get('raison', '')}")
            return chosen
    except Exception as e:  # choix strategique optionnel : jamais bloquant
        print(f"ATTENTION: choix de sujet par l'IA indisponible ({e}), tirage aleatoire", file=sys.stderr)
    return rng.choice(fresh)


def plan_reels(client, n: int, history: list[dict], rng: random.Random, format_id: str | None,
               theme_id: str | None, hook_id: str | None, angle: str | None) -> list[dict]:
    """Un plan par reel ; chaque choix tient compte des precedents (historique + ce lot)."""
    plans = []
    working = list(history)
    for _ in range(n):
        fmt = catalog.get_format(format_id) if format_id else (
            catalog.get_format("demo_produit") if angle else catalog.pick_format(working, rng))
        if angle:
            sujet = {"id": "", "texte": angle}
        else:
            sujet = choose_sujet(client, fmt, catalog.recent_sujets(working), rng)
        hook = catalog.get_hook(hook_id) if hook_id else catalog.pick_hook(working, rng)
        theme = catalog.get_theme(theme_id) if theme_id else catalog.pick_theme(working, rng)
        plan = {"format": fmt, "sujet": sujet, "hook": hook, "theme": theme,
                "episode": catalog.series_episode(working, fmt["id"]) if fmt.get("serie") else None}
        plans.append(plan)
        working.append({"format": fmt["id"], "categorie": fmt["categorie"], "sujet": sujet["id"],
                        "hook": hook["id"], "theme": theme["id"]})
    return plans


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

def build_prompt(plan: dict, duration: int, forced: list[dict] | None, feedback: str | None,
                 recent_hooks: list[str]) -> str:
    fmt, hook = plan["format"], plan["hook"]
    catalog_features = "\n".join(f'- "{fid}" : {f.description}' for fid, f in available_features().items())
    target, lo_w, hi_w = word_budget(duration)
    lo_s, hi_s = scene_bounds(duration)
    cfg = catalog.config()
    cta = cfg["cta_conseil"] if fmt["categorie"] == "conseil" else cfg["cta_produit"]
    structure = fmt["structure"].replace("{episode}", str(plan["episode"] or 1))

    # Un sujet "killer feature : ..." vise UNE fonctionnalite en profondeur
    # (plusieurs scenes peuvent la montrer sous differents etats/ecrans) --
    # a l'oppose d'un tour d'horizon, ou changer de fonctionnalite a chaque
    # scene evite justement de s'attarder sur un seul aspect du produit.
    if plan["sujet"]["texte"].startswith("killer feature"):
        variety_rule = ("concentre-toi sur UNE SEULE fonctionnalité (celle du sujet) : plusieurs "
                        "scènes peuvent la montrer sous des états différents ;")
    else:
        variety_rule = "varie les fonctionnalités montrées, jamais la même dans deux scènes consécutives ;"

    if fmt["cartes"] == "aucune":
        cards_rule = "Aucune scène n'a de carte : chaque scène montre uniquement la fonctionnalité."
    else:
        need = "la MAJORITÉ des scènes" if fmt["cartes"] == "majoritaires" else "les scènes où c'est utile"
        cards_rule = f"""Pour {need}, ajoute une "carte" : un écran texte animé affiché à la place de la
capture, qui résume visuellement ce que dit la voix :
  "carte": {{"surtitre": "2 à 4 mots", "titre": "2 à 8 mots, l'idée clé", "texte": "une phrase courte, optionnelle",
             "style": "normal" | "mythe" | "realite" | "avant" | "apres"}}
Jamais de carte sur la scène 1 (l'accroche s'affiche déjà en grand par-dessus) ni sur la dernière (CTA).
Le texte de la carte ne recopie PAS la voix : il la résume. Une scène avec carte garde un champ "feature"
(la fonctionnalité la plus proche du sujet, montrée si la carte ne peut pas être affichée)."""

    intent = ("contenu utile : le spectateur doit apprendre quelque chose, le produit n'est qu'un outil"
              if fmt["categorie"] == "conseil" else "démonstration du produit")
    avoid_hooks = "\n".join(f"- {h}" for h in recent_hooks[-12:]) or "(aucune)"
    prompt = f"""Tu es copywriter spécialisé en contenu court viral (TikTok/Instagram Reels) pour chercheurs d'emploi.
Base-toi UNIQUEMENT sur ces informations produit réelles, n'invente aucune fonctionnalité :

{PRODUCT_CONTEXT}

Tu écris le SCÉNARIO d'un reel vertical de {duration} secondes, en français.

FORMAT : {fmt['nom']} ({intent}).
Structure attendue : {structure}

SUJET : {plan['sujet']['texte']}

ACCROCHE (scène 1, décisive pour la rétention) : style « {hook['id']} » — {hook['consigne']}
Exemple de ton (ne pas recopier) : « {hook['exemple']} »
Ne réutilise pas ces accroches déjà publiées, ni leur formulation :
{avoid_hooks}

Le reel est une suite de SCÈNES. Pendant chaque scène, l'écran montre une fonctionnalité réelle
d'OpusCV (capturée automatiquement dans l'application) et la voix off dit le texte de la scène.
Fonctionnalités filmables (utilise UNIQUEMENT ces ids, champ "feature") :
{catalog_features}

{cards_rule}

Contraintes :
- entre {lo_s} et {hi_s} scènes ;
- texte total entre {lo_w} et {hi_w} mots (environ {target}) : c'est ce qui fait durer le reel {duration} s ;
- scène 1 = l'accroche (12 mots max) ; dernière scène = CTA court, dans l'esprit : « {cta} » ;
- 1 à 2 phrases par scène, ton oral et naturel, tutoiement, pas publicitaire ;
- {variety_rule}
- français impeccable AVEC TOUS LES ACCENTS (é, è, à, ç, ê...) et la ponctuation : le texte est
  affiché tel quel en sous-titres ;
- pas d'emoji, pas de hashtag, pas d'indication de mise en scène dans les textes.

Fournis aussi :
- "accroche_ecran" : le texte affiché en GRAND à l'écran dès la première image ({ACCROCHE_MAX_WORDS} mots max),
  complémentaire de la voix (pas forcément identique), qui donne envie de rester ;
- "legende" : la description de la publication (1 à 2 phrases + une question pour faire commenter) ;
- "hashtags" : 4 à 6 hashtags pertinents (ex : #cv, #emploi, #recherchedemploi) ;
- "offre_emploi" : une offre d'emploi fictive courte (2 à 4 phrases : intitulé, missions, exigences clés)
  plausible pour ce sujet — utilisée dans les démos « adapter le CV » et « lettre de motivation ».
  Varie le métier/secteur d'un scénario à l'autre ;
- "theme_style" : 2 à 4 mots décrivant le style visuel de CV le plus adapté (ex : « sobre et corporate »).
"""
    if plan.get("episode"):
        prompt += f"\nC'est l'épisode {plan['episode']} de la série : ne répète pas les conseils d'un épisode précédent.\n"
    if forced:
        sequence = "\n".join(
            f'{i}. feature "{s["feature"]}"' + (f' -- texte imposé : "{s["texte"]}"' if s.get("texte") else "")
            for i, s in enumerate(forced, 1))
        prompt += f"""
SÉQUENCE IMPOSÉE : garde exactement ces scènes, dans cet ordre, avec ces features.
Recopie à l'identique les textes imposés ; écris uniquement les textes manquants :
{sequence}
"""
    if feedback:
        prompt += f"\nCORRECTION DEMANDÉE sur ta proposition précédente : {feedback}\n"

    prompt += """
Réponds UNIQUEMENT en JSON valide :
{"titre": "...", "accroche_ecran": "...", "legende": "...", "hashtags": ["#..."], "offre_emploi": "...",
 "theme_style": "...", "scenes": [{"feature": "<id>", "texte": "...", "carte": {...} (optionnel)}]}
"""
    return prompt


def clean_card(raw) -> dict | None:
    if not isinstance(raw, dict) or not str(raw.get("titre") or "").strip():
        return None
    style = str(raw.get("style") or "normal").strip().lower()
    return {
        "surtitre": str(raw.get("surtitre") or "").strip(),
        "titre": str(raw["titre"]).strip(),
        "texte": str(raw.get("texte") or "").strip(),
        "style": style if style in catalog.CARD_STYLES else "normal",
    }


def validate(data: dict, duration: int, forced: list[dict] | None, card_mode: str = "aucune",
             recent_hooks: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Nettoie le scenario et liste ce qui ne respecte pas les contraintes (pour relancer l'IA)."""
    problems = []
    scenes = []
    for raw in data.get("scenes") or []:
        texte = str(raw.get("texte") or "").strip()
        fid = normalize_feature_id(raw.get("feature"))
        if not texte:
            continue
        if fid is None:
            # Sequence imposee : la feature est ecrasee plus bas, inutile de relancer pour ca.
            if not forced:
                problems.append(f'feature inconnue "{raw.get("feature")}" (remplacée par apercu_cv)')
            fid = "apercu_cv"
        scene = {"feature": fid, "texte": texte}
        # Scene 1 = accroche : jamais de carte, l'accroche_ecran s'y affiche deja en grand.
        card = clean_card(raw.get("carte")) if card_mode != "aucune" and scenes else None
        if card:
            scene["carte"] = card
        # Animations demandees par le scenario (run_pipeline.py --anims) :
        # conservees telles quelles, interpretees au montage.
        scene.update({k: raw[k] for k in ANIM_KEYS if raw.get(k)})
        scenes.append(scene)

    if forced:
        if len(scenes) != len(forced):
            problems.append(f"il faut exactement {len(forced)} scènes (séquence imposée), pas {len(scenes)}")
        else:
            for scene, imposed in zip(scenes, forced):
                scene["feature"] = imposed["feature"]
                if imposed.get("texte"):
                    scene["texte"] = imposed["texte"]
                if imposed.get("carte"):
                    scene["carte"] = imposed["carte"]
                scene.update({k: imposed[k] for k in ANIM_KEYS if imposed.get(k)})

    words = sum(len(s["texte"].split()) for s in scenes)
    _, lo_w, hi_w = word_budget(duration)
    lo_s, hi_s = scene_bounds(duration)
    if not scenes:
        problems.append("aucune scène exploitable")
    elif not forced and not lo_s <= len(scenes) <= hi_s:
        problems.append(f"{len(scenes)} scènes, il en faut entre {lo_s} et {hi_s}")
    if scenes and not lo_w <= words <= hi_w:
        problems.append(f"le texte fait {words} mots, il en faut entre {lo_w} et {hi_w} pour durer {duration} s")

    all_text = " ".join([s["texte"] for s in scenes] + [str(data.get("accroche_ecran") or "")])
    if len(all_text.split()) >= MIN_WORDS_ACCENT_CHECK and not ACCENT_RE.search(all_text):
        problems.append("le texte est écrit sans accents : écris en français correct avec tous les accents")
    if card_mode == "majoritaires" and scenes and sum("carte" in s for s in scenes) < len(scenes) / 2:
        problems.append("ce format demande une carte pour la majorité des scènes")

    accroche = str(data.get("accroche_ecran") or "").strip()
    if not forced:
        if not accroche:
            problems.append('"accroche_ecran" manquante')
        elif len(accroche.split()) > ACCROCHE_MAX_WORDS:
            problems.append(f'"accroche_ecran" trop longue ({len(accroche.split())} mots, {ACCROCHE_MAX_WORDS} max)')
        for candidate in (accroche, scenes[0]["texte"] if scenes else ""):
            old = catalog.too_similar(candidate, recent_hooks or []) if candidate else None
            if old:
                problems.append(f'accroche trop proche d\'une accroche déjà publiée (« {old} ») : trouve un autre angle')
                break
    return scenes, problems


def generate_scenario(client, plan: dict, duration: int, recent_hooks: list[str],
                      forced: list[dict] | None = None) -> dict:
    fmt = plan["format"]
    feedback = None
    best: list[dict] = []
    best_data: dict = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = _gemini_json(client, build_prompt(plan, duration, forced, feedback, recent_hooks), 0.9)
        except json.JSONDecodeError:
            feedback = "ta réponse n'était pas du JSON valide"
            continue
        scenes, problems = validate(data, duration, forced, fmt["cartes"], recent_hooks)
        if scenes:
            best, best_data = scenes, data
        if not problems:
            break
        feedback = " ; ".join(problems)
        print(f"    tentative {attempt} à corriger : {feedback}")

    if not best:
        raise RuntimeError(f"Scénario inexploitable après {MAX_ATTEMPTS} tentatives (sujet : {plan['sujet']['texte']})")
    hashtags = best_data.get("hashtags") or []
    return finalize({
        "angle": plan["sujet"]["texte"], "titre": best_data.get("titre", ""), "duree_cible_s": duration,
        "scenes": best,
        "accroche_ecran": str(best_data.get("accroche_ecran") or "").strip(),
        "legende": str(best_data.get("legende") or "").strip(),
        "hashtags": [str(h).strip() for h in hashtags if str(h).strip()] if isinstance(hashtags, list) else [],
        "offre_emploi": str(best_data.get("offre_emploi") or "").strip(),
        "theme_style": str(best_data.get("theme_style") or "").strip(),
        **plan_fields(plan),
    })


def plan_fields(plan: dict) -> dict:
    return {"format": plan["format"]["id"], "categorie": plan["format"]["categorie"],
            "sujet": plan["sujet"]["id"], "hook": plan["hook"]["id"], "theme": plan["theme"]["id"],
            "episode": plan["episode"]}


def finalize(scenario: dict) -> dict:
    """Ajoute les champs derives : liste des features a capturer, estimation de duree."""
    seen = []
    for scene in scenario["scenes"]:
        if scene["feature"] not in seen:
            seen.append(scene["feature"])
    scenario["features"] = seen
    words = sum(len(s["texte"].split()) for s in scenario["scenes"])
    scenario["duree_estimee_s"] = round(words / WORDS_PER_SECOND, 1)
    # Absents (scenario impose sans appel IA, ou champ vide renvoye) : la
    # demo retombe alors sur les valeurs par defaut cote features.py.
    for key in ("offre_emploi", "theme_style", "accroche_ecran", "legende"):
        scenario.setdefault(key, "")
    scenario.setdefault("hashtags", [])
    return scenario


def load_scenario_file(path: Path, default_duration: int) -> list[dict]:
    """
    Scenarios ecrits a la main : chaque scene doit nommer une feature du
    catalogue ; le texte est optionnel (l'IA completera). Champs optionnels
    repris tels quels : format, theme, hook, accroche_ecran, legende,
    hashtags ; par scene : carte, anim, overlay.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else [raw]
    scenarios = []
    for n, item in enumerate(items, 1):
        scenes = []
        for s in item.get("scenes") or []:
            fid = normalize_feature_id(s.get("feature"))
            if fid is None:
                raise ValueError(f"{path} scenario {n} : feature inconnue ou non autorisee '{s.get('feature')}' "
                                 f"(liste : python scripts/features.py)")
            scene = {"feature": fid, "texte": str(s.get("texte") or "").strip(),
                     **{k: s[k] for k in ANIM_KEYS if s.get(k)}}
            card = clean_card(s.get("carte"))
            if card:
                scene["carte"] = card
            scenes.append(scene)
        if not scenes:
            raise ValueError(f"{path} scenario {n} : aucune scene")
        scenarios.append({
            "angle": item.get("angle", "scenario impose"),
            "titre": item.get("titre", ""),
            "duree_cible_s": int(item.get("duree_cible_s") or default_duration),
            "scenes": scenes,
            **{k: item[k] for k in ("format", "theme", "hook", "accroche_ecran", "legende", "hashtags") if item.get(k)},
        })
    return scenarios


def get_client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement GEMINI_API_KEY manquante", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5, help="Nombre de scenarios a generer (ignore avec --scenario)")
    parser.add_argument("--duration", type=int, default=30, help="Duree cible de chaque reel, en secondes")
    parser.add_argument("--angle", type=str, default=None,
                         help="Sujet libre impose (format demo_produit sauf --format) ; sinon catalog/sujets.json")
    parser.add_argument("--format", type=str, default=None, help="Format impose (catalog/formats.json)")
    parser.add_argument("--theme", type=str, default=None, help="Theme visuel impose (catalog/themes.json)")
    parser.add_argument("--hook", type=str, default=None, help="Style d'accroche impose (catalog/hooks.json)")
    parser.add_argument("--seed", type=int, default=None, help="Graine du tirage (reproductibilite)")
    parser.add_argument("--scenario", type=str, default=None,
                         help="Fichier JSON de scenario(s) ecrit(s) a la main (voir scenarios/exemple.json)")
    parser.add_argument("--out", type=str, default="output/scripts.json")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja avec assez de scenarios")
    args = parser.parse_args()

    errors = catalog.validate_catalog()
    if errors:
        for e in errors:
            print(f"ERREUR catalogue: {e}", file=sys.stderr)
        sys.exit(1)
    for kind, value, getter in (("format", args.format, catalog.get_format), ("theme", args.theme, catalog.get_theme),
                                ("hook", args.hook, catalog.get_hook)):
        if value:
            try:
                getter(value)
            except KeyError as e:
                parser.error(str(e))

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if len(existing) >= args.n and not args.scenario:
            print(f"REPRISE: {out_path} existe deja avec {len(existing)} scenario(s), on saute (--force pour regenerer)")
            return

    history_path = out_path.parent / "content_history.json"
    history = catalog.load_history(history_path)
    rng = random.Random(args.seed)
    recent_hooks = catalog.recent_accroches(history)

    client = None
    scenarios = []
    if args.scenario:
        for i, item in enumerate(load_scenario_file(Path(args.scenario), args.duration), 1):
            plan = plan_reels(None, 1, history, rng, item.get("format") or args.format or "demo_produit",
                              item.get("theme") or args.theme, item.get("hook") or args.hook, item["angle"])[0]
            if all(s["texte"] for s in item["scenes"]):
                print(f"[{i}] scenario impose, entierement redige : aucun appel IA")
                scenarios.append(finalize({**plan_fields(plan), **item}))
            else:
                print(f"[{i}] scenario impose, l'IA redige les textes manquants")
                client = client or get_client()
                done = generate_scenario(client, plan, item["duree_cible_s"], recent_hooks, forced=item["scenes"])
                done["titre"] = item["titre"] or done["titre"]
                scenarios.append(done)
    else:
        client = get_client()
        print(f"Plan editorial de {args.n} reel(s)...")
        for i, plan in enumerate(plan_reels(client, args.n, history, rng, args.format, args.theme,
                                            args.hook, args.angle), 1):
            print(f"[{i}/{args.n}] {args.duration}s | format {plan['format']['id']} | accroche {plan['hook']['id']} "
                  f"| theme {plan['theme']['id']} | sujet : {plan['sujet']['texte']}")
            scenario = generate_scenario(client, plan, args.duration, recent_hooks)
            recent_hooks = recent_hooks + [scenario["accroche_ecran"], scenario["scenes"][0]["texte"]]
            scenarios.append(scenario)

    for i, s in enumerate(scenarios, 1):
        print(f"  reel {i} : [{s.get('format')}/{s.get('theme')}] {len(s['scenes'])} scenes, ~{s['duree_estimee_s']}s "
              f"-> " + " | ".join(("carte:" if "carte" in sc else "") + sc["feature"] for sc in s["scenes"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    # Historique : ce qui a ete genere nourrit l'anti-redondance des prochains runs.
    catalog.save_history(history_path, history + [
        {"format": s.get("format"), "categorie": s.get("categorie"), "sujet": s.get("sujet"),
         "hook": s.get("hook"), "theme": s.get("theme"), "titre": s.get("titre"),
         "accroche": s.get("accroche_ecran") or (s["scenes"][0]["texte"] if s["scenes"] else "")}
        for s in scenarios])
    print(f"OK -> {out_path} ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
