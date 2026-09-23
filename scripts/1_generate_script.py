"""
Genere les SCENARIOS des reels via l'API Gemini.

Un scenario est une suite de scenes ; chaque scene = une fonctionnalite reelle
d'OpusCV montree a l'ecran (id du catalogue features.py) + la phrase dite
par la voix off pendant qu'elle est affichee :

    {
      "angle": "...", "titre": "...", "duree_cible_s": 30,
      "scenes": [
        {"feature": "dashboard",   "texte": "Ton CV passe-t-il vraiment les filtres ATS ?"},
        {"feature": "checklist",   "texte": "OpusCV liste tout ce qui bloque, par priorite."},
        ...
        {"feature": "apercu_cv",   "texte": "Essaie gratuitement, lien en bio."}
      ],
      "features": ["dashboard", "checklist", ...]   # derive : ce qu'il faut capturer
    }

C'est ce decoupage qui permet la synchro : 4_generate_subtitles.py retrouve
dans l'audio quand commence chaque scene, et le montage (3b/3c) affiche la
bonne fonctionnalite exactement pendant que la voix en parle.

Parametrable :
  --duration 15|30|45|60...  duree cible (nombre de scenes et de mots en decoulent)
  --angle "..."              angle marketing libre (sinon rotation sur ANGLES)
  --scenario fichier.json    scenario ecrit a la main (objet ou liste d'objets).
                             Scenes avec "texte" -> gardees telles quelles (aucun
                             appel IA si toutes en ont un) ; scenes sans "texte"
                             -> l'IA ecrit la narration pour la sequence imposee.

Usage:
    python 1_generate_script.py --n 3 --duration 30 --out output/scripts.json
    python 1_generate_script.py --scenario scenarios/exemple.json --out output/scripts.json

Necessite GEMINI_API_KEY (sauf scenario fourni entierement redige).
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

from features import available_features, normalize_feature_id

ANGLES = [
    "avant/apres : CV mal fait vs CV optimise par l'outil (points a corriger, relecture, apercu final)",
    "3 erreurs de CV que les recruteurs detestent, + comment l'outil les corrige",
    "un CV par offre : adapter son CV et sa lettre de motivation a chaque candidature en quelques secondes",
    "temoignage type : 'mon CV etait invisible pour les ATS, maintenant je decroche des entretiens'",
    "comparatif : reecrire son CV a la main (long, stressant) vs l'optimiser avec l'IA (rapide)",
    "33 themes de mise en page : un CV qui sort du lot sans sacrifier la lisibilite ATS",
    "de l'edition a l'envoi : relecture, apercu PDF fidele, partage par lien",
    # Angles "un seul killer feature, a fond" : message unique plutot qu'un
    # tour d'horizon, pour tester chaque fonctionnalite forte independamment
    # (retention/conversion se comparent alors reel a reel, feature a feature).
    "killer feature : la lettre de motivation generee par l'IA, calee sur l'offre et le CV, en quelques secondes",
    "killer feature : la simulation d'entretien IA, qui anticipe les questions du recruteur avant le grand jour",
    "killer feature : partager son CV par un simple lien, sans piece jointe ni compte cote recruteur",
    "killer feature : reorganiser tout son CV par glisser-deposer, sans mise en page a refaire a la main",
    "killer feature : l'apercu PDF fidele en un clic, zero surprise a l'impression ou a l'envoi",
]

PRODUCT_CONTEXT = """Produit : OpusCV (SaaS opuscv.tech), une application qui analyse un CV existant
(PDF ou Word) via l'IA, detecte ce qui bloque le passage des filtres ATS des recruteurs,
propose des corrections concretes, puis regenere un PDF stylise (33 themes).
L'utilisateur peut aussi adapter son CV a une offre precise, generer une lettre de motivation,
relire l'orthographe, et partager son CV par un lien public.
Plan gratuit : 3 CV sauvegardes. Plan Pro : illimite.
Ton de marque : direct, concret, oriente resultat (decrocher des entretiens), jamais "corporate"."""

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# Debit de la voix TTS (style "rythme rapide pour reseaux sociaux") mesure sur
# les voix Gemini FR : ~2.6 mots/s. Sert a traduire la duree cible en volume
# de texte -- c'est le texte qui fixe la duree reelle du reel, pas l'inverse.
WORDS_PER_SECOND = 2.6
MAX_ATTEMPTS = 3


def word_budget(duration: int) -> tuple[int, int, int]:
    target = round(duration * WORDS_PER_SECOND)
    return target, round(target * 0.85), round(target * 1.12)


def scene_bounds(duration: int) -> tuple[int, int]:
    # ~3 a ~6 s par scene : en dessous, l'image n'a pas le temps d'etre lue ;
    # au-dessus, le plan s'eternise sur un reel.
    lo = max(3, math.floor(duration / 6))
    hi = max(lo + 1, math.ceil(duration / 3))
    return lo, hi


def choose_angles(client, n: int, history_path: Path) -> list[str]:
    """
    Reflexion strategique en amont du texte : au lieu de toujours reprendre
    les n premiers angles de ANGLES dans le meme ordre (aucune variete d'un
    run a l'autre), demande a Gemini lesquels tester maintenant, en evitant
    ceux recemment utilises (historique persiste entre les runs).
    """
    from google.genai import types

    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            history = []
    recent = history[-20:]

    catalog = "\n".join(f'{i}. {a}' for i, a in enumerate(ANGLES, 1))
    recent_block = ("\n".join(f"- {a}" for a in recent) if recent else "(aucun -- premiere execution)")
    prompt = f"""Tu es strategiste marketing pour OpusCV (SaaS opuscv.tech, optimisation de CV par IA).

{PRODUCT_CONTEXT}

Voici le catalogue d'angles marketing disponibles pour les reels TikTok/Instagram :
{catalog}

Angles utilises lors des dernieres executions (a EVITER si possible, pour varier le contenu) :
{recent_block}

Choisis les {n} angles les plus prometteurs a tester maintenant, dans l'ordre de priorite.
Varie les registres (temoignage, comparatif, killer feature isolee, tour d'horizon) plutot que
de choisir {n} angles trop proches les uns des autres. Recopie le texte EXACT de l'angle choisi
(ne le reformule pas), pris dans le catalogue ci-dessus uniquement.

Reponds UNIQUEMENT en JSON valide : {{"angles": ["...", ...], "raisons": ["...", ...]}}
(un "raisons" bref par angle choisi, une phrase)."""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8),
        )
        text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        chosen = [a for a in data.get("angles") or [] if a in ANGLES]
        for angle, raison in zip(chosen, data.get("raisons") or []):
            print(f"  angle retenu : {angle}\n    -> {raison}")
    except Exception as e:
        print(f"ATTENTION: choix d'angle strategique indisponible ({e}), rotation simple utilisee", file=sys.stderr)
        chosen = []

    # Complete si Gemini en propose moins que n (ou a echoue) : rotation simple
    # sur les angles non repris, en excluant l'historique recent en priorite.
    if len(chosen) < n:
        pool = [a for a in ANGLES if a not in chosen and a not in recent] or \
               [a for a in ANGLES if a not in chosen]
        chosen += (pool * (n // max(len(pool), 1) + 1))[: n - len(chosen)]
    chosen = chosen[:n]

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps((history + chosen)[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    return chosen


def build_prompt(angle: str, duration: int, forced: list[dict] | None, feedback: str | None) -> str:
    catalog = "\n".join(f'- "{fid}" : {f.description}' for fid, f in available_features().items())
    target, lo_w, hi_w = word_budget(duration)
    lo_s, hi_s = scene_bounds(duration)

    # Un angle "killer feature : ..." vise UNE fonctionnalite en profondeur
    # (plusieurs scenes peuvent la montrer sous differents etats/ecrans) --
    # a l'oppose d'un tour d'horizon, ou changer de fonctionnalite a chaque
    # scene evite justement de s'attarder sur un seul aspect du produit.
    if angle.startswith("killer feature"):
        variety_rule = ("concentre-toi sur UNE SEULE fonctionnalite (celle de l'angle) : plusieurs "
                         "scenes peuvent la montrer sous des etats/angles differents, la feature peut "
                         "donc se repeter d'une scene a l'autre ;")
    else:
        variety_rule = "varie les fonctionnalites, jamais la meme dans deux scenes consecutives ;"

    prompt = f"""Tu es copywriter specialise en contenu court viral (TikTok/Instagram Reels).
Base-toi UNIQUEMENT sur ces informations produit reelles, n'invente aucune fonctionnalite :

{PRODUCT_CONTEXT}

Tu ecris le SCENARIO d'un reel vertical de {duration} secondes, en francais.
Le reel est une suite de SCENES. Pendant chaque scene, l'ecran montre UNE fonctionnalite
reelle d'OpusCV (capturee automatiquement dans l'application) et la voix off dit le texte
de la scene. Le texte d'une scene doit parler de ce que le spectateur VOIT a ce moment-la.

Fonctionnalites filmables (utilise UNIQUEMENT ces ids, champ "feature") :
{catalog}

Contraintes :
- entre {lo_s} et {hi_s} scenes ;
- texte total entre {lo_w} et {hi_w} mots (environ {target}) : c'est ce qui fait durer le reel {duration} s ;
- scene 1 = HOOK qui arrete le scroll (12 mots max) ; derniere scene = CTA court
  (ex : "Essaie gratuitement, lien en bio.") ;
- 1 a 2 phrases par scene, ton oral et naturel, pas publicitaire ;
- {variety_rule}
- pas d'emoji, pas de hashtag, pas d'indication de mise en scene dans les textes.

Angle du reel : {angle}

En plus du scenario, fournis deux elements utilises pour rendre la demo capturee
coherente avec cet angle (memes contraintes : n'invente rien qui contredise le produit) :
- "offre_emploi" : une offre d'emploi fictive courte (2 a 4 phrases : intitule du poste,
  responsabilites/exigences cles) plausible pour le persona de cet angle -- utilisee dans
  les demos "adapter le CV a une offre" et "lettre de motivation". Varie le metier/secteur
  d'un scenario a l'autre plutot que de toujours reprendre le meme exemple.
- "theme_style" : 2 a 4 mots decrivant le style visuel de CV le plus adapte a cet angle/
  persona (ex : "sobre et corporate", "moderne et colore", "minimaliste noir et blanc") --
  utilise pour choisir un theme parmi ceux proposes par l'application lors de la demo design.
"""
    if forced:
        sequence = "\n".join(
            f'{i}. feature "{s["feature"]}"' + (f' -- texte impose : "{s["texte"]}"' if s.get("texte") else "")
            for i, s in enumerate(forced, 1))
        prompt += f"""
SEQUENCE IMPOSEE : garde exactement ces scenes, dans cet ordre, avec ces features.
Recopie a l'identique les textes imposes ; ecris uniquement les textes manquants :
{sequence}
"""
    if feedback:
        prompt += f"\nCORRECTION DEMANDEE sur ta proposition precedente : {feedback}\n"

    prompt += """
Reponds UNIQUEMENT en JSON valide :
{"titre": "...", "offre_emploi": "...", "theme_style": "...",
 "scenes": [{"feature": "<id>", "texte": "..."}]}
"""
    return prompt


ANIM_KEYS = ("anim", "overlay")


def validate(data: dict, duration: int, forced: list[dict] | None) -> tuple[list[dict], list[str]]:
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
                problems.append(f'feature inconnue "{raw.get("feature")}" (remplacee par apercu_cv)')
            fid = "apercu_cv"
        scene = {"feature": fid, "texte": texte}
        # Animations demandees par le scenario (run_pipeline.py --anims) :
        # conservees telles quelles, interpretees au montage.
        scene.update({k: raw[k] for k in ANIM_KEYS if raw.get(k)})
        scenes.append(scene)

    if forced:
        if len(scenes) != len(forced):
            problems.append(f"il faut exactement {len(forced)} scenes (sequence imposee), pas {len(scenes)}")
        else:
            for scene, imposed in zip(scenes, forced):
                scene["feature"] = imposed["feature"]
                if imposed.get("texte"):
                    scene["texte"] = imposed["texte"]
                scene.update({k: imposed[k] for k in ANIM_KEYS if imposed.get(k)})

    words = sum(len(s["texte"].split()) for s in scenes)
    _, lo_w, hi_w = word_budget(duration)
    lo_s, hi_s = scene_bounds(duration)
    if not scenes:
        problems.append("aucune scene exploitable")
    elif not forced and not lo_s <= len(scenes) <= hi_s:
        problems.append(f"{len(scenes)} scenes, il en faut entre {lo_s} et {hi_s}")
    if scenes and not lo_w <= words <= hi_w:
        problems.append(f"le texte fait {words} mots, il en faut entre {lo_w} et {hi_w} pour durer {duration} s")
    return scenes, problems


def generate_scenario(client, angle: str, duration: int, forced: list[dict] | None = None) -> dict:
    from google.genai import types

    feedback = None
    best: list[dict] = []
    titre = ""
    offre_emploi = ""
    theme_style = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_prompt(angle, duration, forced, feedback),
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9),
        )
        text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            feedback = "ta reponse n'etait pas du JSON valide"
            continue
        scenes, problems = validate(data, duration, forced)
        if scenes:
            best = scenes
            titre = data.get("titre", "")
            offre_emploi = str(data.get("offre_emploi") or "").strip()
            theme_style = str(data.get("theme_style") or "").strip()
        if not problems:
            break
        feedback = " ; ".join(problems)
        print(f"    tentative {attempt} a corriger : {feedback}")

    if not best:
        raise RuntimeError(f"Scenario inexploitable apres {MAX_ATTEMPTS} tentatives (angle : {angle})")
    return finalize({"angle": angle, "titre": titre, "duree_cible_s": duration, "scenes": best,
                      "offre_emploi": offre_emploi, "theme_style": theme_style})


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
    scenario.setdefault("offre_emploi", "")
    scenario.setdefault("theme_style", "")
    return scenario


def load_scenario_file(path: Path, default_duration: int) -> list[dict]:
    """
    Scenarios ecrits a la main : chaque scene doit nommer une feature du
    catalogue ; le texte est optionnel (l'IA completera).
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
            scenes.append({"feature": fid, "texte": str(s.get("texte") or "").strip(),
                           **{k: s[k] for k in ANIM_KEYS if s.get(k)}})
        if not scenes:
            raise ValueError(f"{path} scenario {n} : aucune scene")
        scenarios.append({
            "angle": item.get("angle", "scenario impose"),
            "titre": item.get("titre", ""),
            "duree_cible_s": int(item.get("duree_cible_s") or default_duration),
            "scenes": scenes,
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
    parser.add_argument("--angle", type=str, default=None, help="Angle marketing impose (sinon rotation sur ANGLES)")
    parser.add_argument("--scenario", type=str, default=None,
                         help="Fichier JSON de scenario(s) ecrit(s) a la main (voir scenarios/exemple.json)")
    parser.add_argument("--out", type=str, default="output/scripts.json")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja avec assez de scenarios")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if len(existing) >= args.n and not args.scenario:
            print(f"REPRISE: {out_path} existe deja avec {len(existing)} scenario(s), on saute (--force pour regenerer)")
            return

    client = None
    scenarios = []
    if args.scenario:
        for i, item in enumerate(load_scenario_file(Path(args.scenario), args.duration), 1):
            if all(s["texte"] for s in item["scenes"]):
                print(f"[{i}] scenario impose, entierement redige : aucun appel IA")
                scenarios.append(finalize(item))
            else:
                print(f"[{i}] scenario impose, l'IA redige les textes manquants")
                client = client or get_client()
                done = generate_scenario(client, item["angle"], item["duree_cible_s"], forced=item["scenes"])
                done["titre"] = item["titre"] or done["titre"]
                scenarios.append(done)
    else:
        client = get_client()
        if args.angle:
            angles = [args.angle] * args.n
        else:
            print(f"Choix strategique de {args.n} angle(s) parmi {len(ANGLES)}...")
            angles = choose_angles(client, args.n, out_path.parent / "angle_history.json")
        for i, angle in enumerate(angles, 1):
            print(f"[{i}/{len(angles)}] Scenario {args.duration}s, angle : {angle}")
            scenarios.append(generate_scenario(client, angle, args.duration))

    for i, s in enumerate(scenarios, 1):
        print(f"  reel {i} : {len(s['scenes'])} scenes, ~{s['duree_estimee_s']}s -> " +
              " | ".join(sc["feature"] for sc in s["scenes"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path} ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
