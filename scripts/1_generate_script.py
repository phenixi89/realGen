"""
Genere les SCENARIOS des reels via l'API Gemini, a partir du catalogue
editorial (catalog/, cf. catalog.py) :

  format  -> structure de la video (liste d'erreurs, mythe/realite, demo...)
  sujet   -> de quoi elle parle (conseil utile ou produit)
  accroche-> style des 2 premieres secondes (question choc, chiffre, POV...)
  theme   -> couleurs/polices/musique du montage
  registre-> serieux ou humour (config.json "registres") : filtre formats,
             accroches et themes, ajoute les regles d'ecriture humoristique

Chaque choix evite ce qui a ete publie recemment (output/content_history.json)
et respecte le mix conseil/produit et le mix de registres de
catalog/config.json : c'est ce qui empeche les reels de tous se ressembler.

Le scenario porte aussi ses textes Instagram (legende_instagram,
hashtags_instagram, carrousel), exploites par scripts/instagram.py.

Un scenario est une suite de scenes ; chaque scene = une fonctionnalite reelle
d'OpusCV (id du catalogue features.py, montree a l'ecran) OU une carte texte
animee (conseil, mythe/realite, avant/apres...), + la phrase dite par la voix :

    {
      "format": "liste_erreurs", "categorie": "conseil", "sujet": "titre_cv",
      "hook": "erreur", "theme": "corail_energie", "registre": "serieux",
      "titre": "...", "accroche_ecran": "Ton CV fait cette erreur",
      "legende": "...", "hashtags": ["#cv", ...], "duree_cible_s": 30,
      "legende_instagram": "...", "hashtags_instagram": ["#cv", ...],
      "carrousel": [{"titre": "...", "texte": "..."}, ...],
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
  --duration 15|25|30|45|60...  duree cible (nombre de scenes et de mots en decoulent)
  --format / --theme / --hook   impose un element du catalogue (sinon choix automatique)
  --registre serieux|humour  impose le registre (sinon mix de config.json "registres")
  --angle "..."              sujet libre (sinon choisi dans catalog/sujets.json)
  --plan '[{...}, ...]'      combinaison imposee reel par reel (JSON, un objet par reel ;
                             cles format, sujet, hook, theme, voix, registre, ambiance,
                             angle ; absente ou vide = choix automatique ; --n = longueur)
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
import difflib
import json
import math
import os
import random
import re
import sys
from pathlib import Path

import catalog
from features import available_features, normalize_feature_id
from gemini_retry import generate_with_retry

PRODUCT_CONTEXT = """Produit : OpusCV (SaaS opuscv.tech, application app.opuscv.tech), qui aide à sortir un CV prêt à envoyer,
corrigé, mis en page et décliné par offre d'emploi.
- Entrer : importer un CV existant (PDF ou Word) analysé par l'IA, partir d'un CV vierge, ou laisser l'IA
  écrire un premier brouillon à partir de quelques phrases.
- Corriger : une liste de « points à corriger » (profil trop court, mission sans résultat, coordonnée
  manquante...), chacun expliqué en une phrase et relié au champ à réparer. PAS de note ni de score global.
- Écrire : réécriture d'une section, relecture orthographique et grammaticale ; pour chiffrer une mission,
  l'outil POSE DES QUESTIONS au candidat puis écrit la phrase avec SES réponses : il n'invente jamais un chiffre
  ni un fait. Toute modification proposée passe par un avant/après à valider.
- Mettre en page : 41 thèmes sur 6 mises en page (colonne, classique, minimal, bandeau, ATS sobre lisible
  par les robots, frise chronologique), couleurs, polices, densité et réglages fins ; sections libres
  (certifications, projets, bénévolat...) ; l'aperçu de l'éditeur est le PDF exact, au pixel près.
- Sortir : PDF, Word (plan Pro), lien de partage public avec expiration et décompte des consultations.
- Candidater : adapter le CV à une offre (enregistré en variante), lettre de motivation (téléchargeable en PDF
  aux couleurs du CV), six questions d'entretien probables avec pistes de réponse.
- Langues : CV en français, anglais, allemand ou espagnol, au format A4 ou Letter ; « Convertir » traduit un CV
  en variante dans une autre langue ou un autre format.
Plan gratuit pour commencer (quelques CV et actions IA), plan Pro illimité.
Ton de marque : direct, concret, orienté résultat (décrocher des entretiens), jamais « corporate »."""

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# Modele de repli quand le principal reste surcharge (503) apres plusieurs essais (gemini_retry.py).
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

# Debit de la voix TTS (style "rythme rapide pour reseaux sociaux") mesure sur
# les voix Gemini FR : ~2.6 mots/s. Sert a traduire la duree cible en volume
# de texte -- c'est le texte qui fixe la duree reelle du reel, pas l'inverse.
WORDS_PER_SECOND = 2.6
FAST_WORDS_PER_SECOND = 3.4
# Dessin anime (dialogue TTS a deux voix, repliques courtes) : ~2,9 mots/s mesures sur les
# premiers reels ; un peu en dessous pour garder de l'air entre les repliques.
DOC_WORDS_PER_SECOND = 2.1   # voix off de documentaire : posée, avec de longues pauses (mesurée au 1er run, puis output/vitesse_voix.json)
DIALOGUE_WORDS_PER_SECOND = 2.3   # mesure au run 64 : 78 mots = 33,7 s (voix posees, pauses avant les chutes)
MAX_ATTEMPTS = 3
ACCROCHE_MAX_WORDS = 8
ANIM_KEYS = ("anim", "overlay")
# Annotations au feutre sur les captures (assets/anim/annotation.html).
ANNOTATION_MAX_WORDS = 6
MAX_ANNOTATIONS = 2
# Carrousel Instagram : diapositives ecrites par l'IA (hors diapositive finale, ajoutee au rendu).
CARROUSEL_MIN, CARROUSEL_MAX = 4, 8
# Dessin anime (formats "dessin": true) : une replique tient dans une bulle.
REPLIQUE_MAX_WORDS = 12   # phrases courtes et simples (une idée par réplique)
# Actions sans parole qui ne se voient presque pas (ne comptent pas comme "action" d'une scene).
ACTIONS_PAROLE = ("parler", "expression", "geste", "regarder", "pause", "camera")
# Mise en scene "cinema" (gros plans, inserts, nuage de pensee, carton d'ellipse) : au moins une par reel.
ACTIONS_MISE_EN_SCENE = ("camera", "corriger", "tamponner", "afficher", "notifier", "imaginer", "comparer")
# Actions qui font un bruitage (Dessin.son dans assets/anim/dessin/) : au moins 2 par reel.
ACTIONS_BRUITEES = ("marcher", "entrer", "sortir", "sauter", "s_asseoir", "se_lever", "poser", "vibrer",
                    "taper", "miauler", "dormir", "traverser", "idee", "jeter", "tamponner", "corriger",
                    "notifier", "afficher", "defiler", "imaginer", "comparer")
MIN_BRUITAGES = 2
# Sans aucun de ces caracteres sur tout un script, le texte a ete ecrit sans
# accents : les sous-titres (texte exact du script) seraient faux.
ACCENT_RE = re.compile(r"[éèêëàâùûüîïôçœÉÈÊÀÂÙÛÎÔÇ]")
MIN_WORDS_ACCENT_CHECK = 12


def words_per_second(tone: str = "") -> float:
    """Un ton "rapide" fait parler le TTS nettement plus vite (mesure : ~3.3 mots/s)."""
    return FAST_WORDS_PER_SECOND if re.search(r"rapide|haletant", tone or "", re.I) else WORDS_PER_SECOND


VITESSE_DOC: list[float] = []     # idem pour la voix off des documentaires
VITESSE_VOIX: list[float] = []   # mots/s mesures sur les derniers dessins animes (output/vitesse_voix.json, ecrit par 2_generate_voice.py)


def charger_vitesse(chemin: Path) -> None:
    """Vitesse reelle de la voix des derniers dialogues (mots dits / duree de l'audio, CTA compris)."""
    VITESSE_VOIX.clear()
    VITESSE_DOC.clear()
    try:
        mesures = json.loads(chemin.read_text(encoding="utf-8"))
        VITESSE_DOC.extend(float(m["mots"]) / float(m["duree"]) for m in mesures[-6:] if m.get("documentaire") and m.get("duree"))
        VITESSE_VOIX.extend(float(m["mots"]) / float(m["duree"]) for m in mesures[-6:] if m.get("dessin") and m.get("duree"))
    except (OSError, ValueError, KeyError, TypeError):
        pass


def dialogue_wps() -> float:
    """Mots par seconde du dialogue : mediane des mesures recentes (bornee 1,8 a 2,9), sinon la valeur par defaut."""
    if not VITESSE_VOIX:
        return DIALOGUE_WORDS_PER_SECOND
    mesures = sorted(VITESSE_VOIX)
    return min(2.9, max(1.8, mesures[len(mesures) // 2]))


def doc_wps() -> float:
    """Mots par seconde de la voix off du documentaire : mediane des mesures recentes (1,6 a 2,6), sinon la valeur par defaut."""
    if not VITESSE_DOC:
        return DOC_WORDS_PER_SECOND
    mesures = sorted(VITESSE_DOC)
    return min(2.6, max(1.6, mesures[len(mesures) // 2]))


def word_budget(duration: int, tone: str = "", dialogue: bool = False, documentaire: bool = False) -> tuple[int, int, int]:
    target = round(duration * (doc_wps() if documentaire else dialogue_wps() if dialogue else words_per_second(tone)))
    return target, round(target * 0.85), round(target * 1.12)


def scene_bounds(duration: int) -> tuple[int, int]:
    # ~3 a ~6 s par scene : en dessous, l'image n'a pas le temps d'etre lue ;
    # au-dessus, le plan s'eternise sur un reel.
    # Rythme reseaux sociaux : un changement de plan toutes les ~2.5-5 s.
    lo = max(3, math.floor(duration / 5))
    hi = max(lo + 1, math.ceil(duration / 2.5))
    return lo, hi


def _gemini_json(client, prompt: str, temperature: float) -> dict:
    from google.genai import types

    response = generate_with_retry(
        client, model=MODEL_NAME, fallback_model=FALLBACK_MODEL, label="Gemini (scenario)",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
    )
    text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Plan editorial : format, sujet, accroche, theme
# ---------------------------------------------------------------------------

def choose_sujet(client, fmt: dict, history: list[dict], rng: random.Random) -> dict:
    """
    Famille de sujet imposee par la rotation (catalog.famille_rotation : la
    moins recemment traitee), puis Gemini choisit dans cette famille le sujet
    le plus prometteur (en evitant les sujets recents). Laisse libre sur tout
    le catalogue, il reprenait toujours les themes "viraux" (ATS, chiffres).
    Echec -> tirage aleatoire.
    """
    avoid = catalog.recent_sujets(history)
    candidates = catalog.compatible_sujets(fmt)
    fresh = [s for s in candidates if s["id"] not in avoid] or candidates
    fresh = catalog.famille_rotation(fresh, history)
    if client is None or len(fresh) == 1:
        return rng.choice(fresh)
    listing = "\n".join(f'- {s["id"]} : {s["texte"]}' for s in fresh)
    if fmt.get("documentaire"):
        cadre = ("Tu es scénariste de faux documentaires animaliers humoristiques, spécialisé dans les conseils emploi et recrutement.\n"
                 "Le documentaire donne un VRAI conseil de recherche d'emploi en observant le candidat comme un animal ; le produit n'est pas son sujet.")
    elif fmt.get("dessin"):
        cadre = ("Tu es scénariste de séries courtes et expert en marketing de contenu, spécialisé dans les conseils emploi et recrutement.\n"
                 "Le dessin animé donne un VRAI conseil de recherche d'emploi ou de carrière ; le produit n'est pas son sujet.")
    else:
        cadre = f"Tu es stratège de contenu TikTok/Instagram pour OpusCV (optimisation de CV par IA).\n\n{PRODUCT_CONTEXT}"
    prompt = f"""{cadre}

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
               theme_id: str | None, hook_id: str | None, angle: str | None,
               registre_id: str | None = None, sans_captures: bool = False,
               overrides: list[dict] | None = None) -> list[dict]:
    """
    Un plan par reel ; chaque choix tient compte des precedents (historique + ce lot).
    Le registre (serieux/humour) est choisi d'abord : il filtre formats, accroches et themes.
    Format impose sans registre impose : registre tire parmi ceux du format.
    sans_captures : aucune capture de l'app (--capture-mode aucune) -> formats conseil a cartes.
    overrides : combinaison imposee par reel (--plan) ; chaque cle renseignee
    l'emporte sur les options globales, les autres restent automatiques.
    """
    plans = []
    working = list(history)
    for i in range(n):
        ov = (overrides[i] if overrides and i < len(overrides) else None) or {}
        fid, reel_angle = ov.get("format") or format_id, ov.get("angle") or (None if ov.get("sujet") else angle)
        forced_sujet = catalog.get_sujet(ov["sujet"]) if ov.get("sujet") else None
        forced_fmt = catalog.get_format(fid) if fid else (
            catalog.get_format("demo_produit") if reel_angle and not sans_captures else None)
        registre = ov.get("registre") or registre_id or catalog.pick_registre(
            working, rng, catalog.registres_of(forced_fmt) if forced_fmt else None)
        if forced_fmt:
            fmt = forced_fmt
        elif forced_sujet:  # sujet impose : format tire parmi ceux qui l'acceptent
            ok = [f for f in catalog.formats() if forced_sujet in catalog.compatible_sujets(f)
                  and (not sans_captures or catalog.sans_captures_ok(f)) and (sans_captures or not catalog.sans_capture_seul(f))]
            pool = [f for f in ok if registre in catalog.registres_of(f)] or ok
            fmt = catalog.weighted_pick(pool, [], rng) if pool else catalog.pick_format(working, rng, registre, sans_captures)
        else:
            fmt = catalog.pick_format(working, rng, registre, sans_captures)
        if forced_sujet:
            sujet = forced_sujet
        elif reel_angle:
            sujet = {"id": "", "texte": reel_angle}
        else:
            sujet = choose_sujet(client, fmt, working, rng)
        hid, tid = ov.get("hook") or hook_id, ov.get("theme") or theme_id
        hook = catalog.get_hook(hid) if hid else catalog.pick_hook(working, rng, registre, bool(fmt.get("dessin")), sujet.get("tags"))
        theme = catalog.get_theme(tid) if tid else catalog.pick_theme(working, rng, registre, fmt)
        voice = catalog.get_voice(ov["voix"]) if ov.get("voix") else catalog.pick_voice(working, rng, fmt)
        cta, cta_anim = catalog.pick_cta(fmt["categorie"], rng)
        ambiance = ov.get("ambiance") or catalog.pick_ambiance(theme, working, rng, fmt)
        plan = {"format": fmt, "sujet": sujet, "hook": hook, "theme": theme, "voix": voice, "registre": registre,
                "cta": cta, "cta_anim": cta_anim, "ambiance": ambiance,
                "episode": catalog.series_episode(working, fmt["id"]) if fmt.get("serie") else None,
                "sans_captures": sans_captures}
        if fmt.get("dessin"):  # trame d'histoire (rotation) et episodes precedents de la serie
            plan["trame"] = next((t for t in catalog.trames() if t["id"] == ov.get("trame")), None) \
                or catalog.pick_trame(working, rng)
            plan["episodes_precedents"] = catalog.series_resumes(working, fmt["id"]) if fmt.get("serie") else []
            plan["lieu"] = catalog.pick_lieu(working, rng)
        plans.append(plan)
        working.append({"format": fmt["id"], "categorie": fmt["categorie"], "sujet": sujet["id"],
                        "trame": (plan.get("trame") or {}).get("id"),
                        "famille": sujet.get("famille"),
                        "hook": hook["id"], "theme": theme["id"], "voix": voice["id"], "ambiance": ambiance,
                        "registre": registre})
    return plans


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

def cta_enregistre() -> bool:
    """config.json "cta_enregistre" : derniere phrase = phrase du catalogue, voix enregistree une fois pour toutes."""
    return bool(catalog.config().get("cta_enregistre", True))


def fixer_cta(scenes: list[dict], cta: str) -> None:
    """Derniere scene = la phrase de CTA exacte (2_generate_voice.py colle son enregistrement)."""
    if not scenes or len(scenes) < 2:
        return
    last = scenes[-1]
    last["texte"] = cta
    if last.get("repliques"):
        last["repliques"] = [{"qui": last["repliques"][0]["qui"], "texte": cta}]
    last["cta_enregistre"] = True


def dessin_bounds(duration: int) -> tuple[int, int]:
    """Dessin anime : 1 a ~4 lieux / moments (un decor dure plusieurs repliques) + la scene CTA."""
    return 2, max(4, math.ceil(duration / 6))


def documentaire_bounds(duration: int) -> tuple[int, int]:
    """Documentaire : 3 plans au moins (probleme, comportement, conseil) + la scene d'appel a l'action."""
    return 4, max(5, math.ceil(duration / 5))


DRAMATURGIE = """ÉCRITURE : UN PROBLÈME, UNE SOLUTION, EN MOTS SIMPLES (un mini-scénario, pas une fiche pratique lue à deux voix) :
  - LANGAGE : les mots de tous les jours, des phrases courtes (une idée par réplique, 12 mots au plus), qu'un enfant de
    12 ans comprend. Aucun jargon, aucune formule de coach, aucun nom de « règle » ou de « méthode » inventé
    (« la règle du cadre », « la méthode des 3 P » sont interdits) : on dit simplement quoi faire ;
  - CONTEXTE : dans les 2 premières répliques, le spectateur sait QUI a un problème, DANS QUELLE SITUATION (un entretien
    jeudi, un CV envoyé sans réponse, une offre bizarre) et QUEL EST le problème. Jamais de phrase abstraite sans situation ;
  - PROBLÈME (au début) : un problème précis que le spectateur a vécu, montré dans une situation réelle (pas une idée) ;
  - SOLUTION ENSEIGNÉE (au milieu) : le personnage qui sait (Léa, le recruteur) dit à l'autre QUOI faire, avec les mots
    exacts à dire ou à écrire entre « guillemets français » (« Dis plutôt : « … » »), sur un exemple PRÉCIS et réaliste
    (une entreprise, un poste, un détail inventés), jamais une phrase générique (« J'adore votre projet ») ; l'autre
    l'essaie ensuite. Une seule chose à faire, et POURQUOI ça marche en une courte phrase simple ;
  - Jamais de phrase adressée au public dans l'histoire (« reste pour la formule », « attends la suite ») ;
  - OUVERTURE : la 1re réplique fait 8 mots au plus, dit de qui ou de quoi on parle (pas de « lui », « ça », « elle » sans
    qu'on sache), et ne reprend pas les mots du titre ;
  - RÉSULTAT (à la fin) : on VOIT que ça marche (gros plan, mail reçu, tampon), puis une chute courte : une RÉACTION ou
    un retournement de situation drôle, jamais un slogan ni une morale (« Fini les CV qui endorment tout le monde ! ») ;
  - PAS DE SUSPENSE ARTIFICIEL : on ne fait pas patienter (« attends la formule exacte », « tu vas voir ») ; Léa dit la
    phrase tout de suite, c'est la phrase qui compte ;
  - Karim vit le problème et agit ; Léa l'aide en 1 ou 2 répliques à la fois, comme une amie, jamais en donnant un cours :
    jamais plus de 2 répliques de suite par le même personnage ;
  - MONTRE, NE FAIS PAS LA LEÇON : le conseil passe par un essai raté puis réussi, pas par un discours ;
  - PERSONNAGES : Karim est maladroit et de bonne foi, Léa est pince-sans-rire, le recruteur pressé mais honnête ; les gags
    viennent d'eux, pas de blagues plaquées ;
  - PROMESSE TENUE : ce qu'un personnage annonce (« je te donne la phrase ») est dit mot pour mot plus loin, avant la chute ;
  - COMPRÉHENSION (le point le plus important) : relis ton histoire comme un spectateur qui n'a QUE le titre et les
    répliques, sans connaître l'histoire. Il doit pouvoir la raconter en deux phrases : qui est qui (le recruteur, le
    candidat), ce qui ne va pas, ce qu'on essaie, ce qui se passe, pourquoi c'est drôle. Chaque réplique répond à la
    précédente (pas de sujet nouveau qui sort de nulle part, pas de « suite » promise) ; un personnage garde le même
    rôle d'un bout à l'autre, sauf si l'inversion est dite clairement (« Attends, c'est toi le recruteur ? ») ;
    la chute découle de ce qu'on vient de voir, en une idée, sans qu'il faille la deviner ;
  - CE QU'ON DIT = CE QU'ON VOIT : un nombre ou un objet cité dans une réplique correspond exactement à ce qui est dessiné
    (si le CV montré liste 10 technos, on dit « dix » et pas « vingt » ; si un texte barré est montré, on le dit) ;
  - ORIGINALITÉ : évite l'histoire attendue (« Karim rate son entretien, Léa lui explique ») : choisis une situation précise
    et surprenante (inversion des rôles, point de vue du recruteur, décompte...), mais toujours compréhensible tout de suite.
"""


def dessin_rules(plan: dict | None = None) -> str:
    """Consignes du format dessin anime : catalogue des decors, objets, personnages et actions,
    trame d'histoire du reel, serie (episodes precedents)."""
    cat = catalog.dessins()
    perso = cat["personnage"]
    principaux = [o["id"] for o in cat["objets"] if o["categorie"] == "personnage" and o.get("role", "principal") == "principal"]
    actions_objets = "\n".join(f"  - {k} ({v.split(' : ', 1)[0]}) : {v.split(' : ', 1)[-1]}"
                                for k, v in (cat.get("actions_objets") or {}).items())
    cadres = " ; ".join(f'{k} = {v}' for k, v in (cat.get("camera") or {}).get("cadres", {}).items())
    icones = ", ".join(catalog.icons())
    plan = plan or {}
    trame = plan.get("trame")
    trame_rule = (f"""TRAME DE CET ÉPISODE : « {trame['nom']} » -- {trame['consigne']}
""" if trame else "")
    lieu = plan.get("lieu")
    lieu_rule = (f"""LIEU POSSIBLE : « {lieu['id']} » ({lieu['description'].split('.')[0]}). À utiliser SEULEMENT s'il colle à l'histoire ;
sinon choisis le lieu logique pour la situation (un entretien se passe dans la salle d'entretien, un appel chez soi...).
""" if lieu else "")
    serie = cat.get("serie") or {}
    serie_rule = ""
    if serie and plan.get("episode"):
        anciens = "\n".join(f"  - épisode {n} : {r}" for n, r in plan.get("episodes_precedents") or []) or "  (aucun résumé encore)"
        serie_rule = f"""SÉRIE « {serie['titre']} », ÉPISODE {plan['episode']}. {serie.get('consigne', '')}
Épisodes précédents (les plus récents) :
{anciens}
Ne refais pas l'histoire d'un épisode précédent ; un clin d'œil à un épisode passé est bienvenu.
"""
    fonds = "\n".join(f'  - "{f["id"]}" : {f["description"]}' for f in cat["fonds"])
    persos = "\n".join(f'  - "{o["id"]}" : {o["description"]}' for o in cat["objets"] if o["categorie"] == "personnage")
    objets = "\n".join(
        f'  - "{o["id"]}" ({o["categorie"]}{", mural" if o.get("mural") else ""}) : {o["description"]}'
        + (f' ; ancres : {", ".join(o["ancres"])}' if o.get("ancres") else "")
        + (f' ; actions : {", ".join(o["actions"])}' if o.get("actions") else "")
        for o in cat["objets"] if o["categorie"] != "personnage")
    actions = "\n".join(f'  - {k} : {v}' for k, v in perso["actions"].items())
    return f"""DESSIN ANIMÉ : le reel est un mini dessin animé au trait blanc sur fond noir (touches de couleur légères).
Personnages (id = type) :
{persos}
TOUT le texte est DIT PAR LES PERSONNAGES, il n'y a pas de voix off : chaque réplique s'affiche dans une bulle
et est lue avec la voix du personnage. DEUX personnages parlent au plus dans tout le reel (limite des voix) :
Léa et Karim, ou Karim et le recruteur ; un troisième peut être présent sans parler. Le chat ne parle pas (il miaule).
L'appel à l'action final est dit par {" ou ".join(principaux)}.

Chaque scène dessinée = un décor + des objets placés + des actions jouées dans l'ordre :
{{"fond": "cafe", "titre": "Le lendemain",
  "objets": [{{"id": "c1", "type": "chaise", "x": 300, "regard": "droite"}}, {{"id": "karim", "type": "karim", "assis": "c1"}},
             {{"id": "table", "type": "table_ronde", "x": 540}}, {{"id": "tasse", "type": "tasse", "sur": "table.dessus_gauche"}},
             {{"id": "lea", "type": "lea", "x": 820, "regard": "gauche"}}],
  "actions": [{{"qui": "karim", "action": "parler", "texte": "Pourquoi personne ne me rappelle ?", "expr": "triste", "geste": "tete_mains"}},
              {{"qui": "lea", "action": "parler", "texte": "Tu envoies le même CV partout ?", "expr": "doute"}},
              {{"qui": "karim", "action": "tenir", "objet": "tasse"}}, {{"qui": "karim", "action": "boire"}}]}}
Décors ("fond") :
{fonds}
Objets, animaux et décor ("type") :
{objets}
Personnages : expressions {", ".join(perso["expressions"])} ; gestes {", ".join(perso["gestes"])} ; actions :
{actions}
Actions des objets ("qui" = id de l'objet ; GROS PLAN = insert plein écran pendant que le dialogue continue) :
{actions_objets}
Icônes de "imaginer" (champ "image") : {icones}
CAMÉRA (action SANS "qui", jouée en même temps que l'action suivante) : {{"action": "camera", "cadre": "visage", "sur": "karim"}}
  cadres : {cadres} ; "rapide": true = coupe sèche (pour une réaction, une chute) ; "lent": true = travelling
  avant progressif (3 s : une tension qui monte) ; "dessous" : le personnage domine (le recruteur qui juge,
  une prise de confiance) ; "epaule" + "depuis": id = on regarde "sur" par-dessus l'épaule de l'autre
  (un face-à-face tendu) ; revenir en "large" ensuite. Varie les plans : jamais deux fois le même cadre de suite.
  AU MOINS UN plan original par reel : cadre "dessous", cadre "epaule", "lent": true ou un split-screen
  (objet "diptyque" + action "comparer") ; un personnage qui TIENT un objet (téléphone, tasse) ne fait pas de
  geste « idee », « tete_mains » ou « penser » (la main monterait devant son visage) : il le pose avant.
Mise en scène :
  - "x" = position au sol, de 0 à 1080 : les personnages vers 250 et 820, face à face ("regard" droite / gauche),
    meubles au centre (table vers x 540) ; objet mural : "x" et "y" (600 à 850) ; objet posé : "sur": "table.dessus"
    (ou dessus_gauche / dessus_droite) ; objet déjà en main : "sur": "lea.main_avant" ; personnage assis dès le
    début : "assis": "<id d'une chaise ou d'un canapé déclaré AVANT lui>" (la chaise porte "x" et "regard" ;
    sur un canapé, deux personnages s'assoient côte à côte) ;
  - "id" unique dans la scène (deux chaises : "c1", "c2") ; un support est déclaré avant ce qui est posé dessus ;
  - 3 à 7 objets par scène : les personnages présents + au moins un objet ou meuble qui situe l'action ;
  - "parler" porte UNE réplique ("texte" : 3 à {REPLIQUE_MAX_WORDS} mots, une phrase orale), avec "expr" et "geste"
    accordés au texte (geste optionnel ; "expr" donne aussi le ton de la voix) ; 2 à 5 répliques par scène ;
  - des répliques PARLÉES, comme entre deux amis : mots de tous les jours, phrases courtes, relances et
    réactions (« Attends… », « Ah bon ? », « Franchement, », « Bah oui ! »), un personnage peut couper l'autre ;
    jamais de langage écrit ou de jargon (pas « valorise ton périmètre d'action », mais « dis ce que TU as géré ») ;
  - CHAQUE scène a 1 à 3 actions sans parole qui se voient, utiles à l'histoire (entrer, s'asseoir, tenir puis
    boire, poser, téléphone qui vibre, ordinateur qui tape, chat qui miaule ou dort, sauter de joie, idée...),
    à la suite ou en même temps que la réplique précédente ("avec": true) ; au moins {MIN_BRUITAGES} dans le reel
    qui s'entendent : {", ".join(ACTIONS_BRUITEES)} ; un personnage peut entrer pendant que l'autre parle ;
    le chat (une scène au plus) apporte une petite touche d'humour ;
  - "titre" (optionnel, 2 à 4 mots : lieu ou moment, ex : « Lundi, 9 h ») : jamais sur la scène 1 ;
  - UNE SCÈNE = UN LIEU ET UN MOMENT. On ne change de scène QUE si le lieu change (chez le recruteur,
    dans le métro…) ou si des heures passent (le soir, le lendemain : "ellipse") : sinon, reste dans la
    même scène (jusqu'à 6 répliques) et varie les plans avec la caméra (gros plan sur un visage, sur le
    CV, retour au plan large). « Deux minutes après » n'est pas un changement de scène : deux scènes de
    suite dans le même décor sans "ellipse" sont fusionnées en une seule ;
  - un saut dans le temps s'annonce par "ellipse" (au lieu de "titre") : « Une semaine plus tard… » (2 à 6 mots),
    et peut se voir (calendrier qui "defiler") ;
  - MONTRE au lieu de dire, au moins une fois par reel : gros plan caméra sur une réaction, le CV corrigé à l'écran
    ("corriger" : la phrase faible barrée puis la bonne), l'e-mail ou la notification reçus, le tampon du recruteur,
    ou ce qu'imagine un personnage ("imaginer") ; le CV à l'écran dès que le conseil porte sur une formulation ;
  - un objet déclaré APRÈS un personnage passe devant lui (recruteur derrière son bureau : le recruteur, puis la table) ;
  - pas de "imaginer" ni d'"ellipse" dans la scène 1 (l'accroche occupe le haut de l'écran) ;
  - les répliques sont DITES à voix haute : pas de « POV », d'abréviation ni de code des réseaux qui ne se
    disent pas dans une vraie conversation ;
  - le dialogue ne parle PAS du produit : jamais « OpusCV » ni « l'appli » dans une réplique, sauf l'appel à
    l'action final ; l'histoire donne un conseil emploi/recrutement valable avec ou sans outil, et aucun
    personnage n'invente de chiffre de performance (« 50 refus évités ») ni de fonction.
{DRAMATURGIE}
{lieu_rule}{trame_rule}{serie_rule}CHUTE : juste avant l'appel à l'action, une chute : un retournement ou une réplique drôle (un sourire en
registre sérieux), souvent soulignée par un gros plan "rapide" sur le visage qui réagit.
Scène 1 : l'accroche est la 1re réplique (12 mots max, sans pourcentage ni statistique), dite tout de suite,
avant toute autre action ; la scène 1 a ensuite, elle aussi, au moins une action visible.
Une révélation annoncée (« je te donne LA phrase », « attends la suite ») arrive EXPLICITEMENT plus loin dans le
dialogue, avant le CTA : jamais de promesse sans suite.
Une phrase de CV donnée en exemple ne dicte jamais de chiffres au spectateur (« écris : 30 comptes, 95 % de
satisfaction ») : elle dit d'où ils viennent (« avec TES vrais chiffres : combien de comptes ? ») -- OpusCV
n'écrit jamais un chiffre que le candidat ne lui a pas donné. Citations entre « guillemets français ».
Dernière scène = l'appel à l'action, SANS décor : {{"cta": true, "qui": "lea", "texte": "..."}} -- un personnage
le dit pendant que l'écran d'appel à l'action s'affiche.
Dans ce format, "accroche_ecran" est le TITRE de la vidéo, de préférence une question au « tu » qui s'adresse au
spectateur, 6 mots au plus (il s'affiche seul, plein écran, une seconde avant la scène) ; la 1re réplique est une vraie phrase de la scène (à la 1re personne : « Pourquoi personne ne me
rappelle ? », ou une question à l'autre personnage), jamais le titre recopié ni un slogan.
"""


DOC_ECRITURE = """ÉCRITURE : VOIX OFF DE DOCUMENTAIRE ANIMALIER SUR UN VRAI CONSEIL D'EMPLOI :
  - TON : voix off solennelle et posée, humour pince-sans-rire par le décalage (on parle d'un CV comme d'un rituel de la
    savane). Présent de narration, phrases courtes (18 mots au plus), mots de tous les jours, aucun jargon ni « règle du … »
    inventé. Jamais de blague annoncée, jamais de suspense artificiel (« attends la suite », « tu vas voir ») ;
  - CONTEXTE : le plan 1 dit de QUI on parle (le candidat, le recruteur, le CV, le robot qui trie les candidatures) et OÙ
    (« Ici, dans la savane des offres d'emploi… ») ; en deux phrases, le spectateur sait quel est le problème, dans une
    situation qu'il a vraiment vécue (candidature sans réponse, entretien raté, CV ignoré…) ;
  - PROBLÈME → CONSEIL → RÉSULTAT : (plan 1) l'espèce et son problème précis ; (plan 2) le comportement qui coince et ce qu'il
    coûte ; (plan 3) le tournant : UNE chose à faire, avec la phrase exacte à dire ou à écrire entre « guillemets français »
    sur un exemple précis et réaliste, et POURQUOI ça marche en une phrase simple ; puis le résultat et une chute-réaction
    (jamais un slogan ni une morale) ;
  - LES ANIMAUX JOUENT LA PHRASE : chaque plan montre ce que dit la voix. Elle parle d'ignorer le problème ? l'autruche enfouit
    sa tête. D'un CV trop chargé ? le paon déploie sa queue. Du recruteur qui tarde ? le lion dort. De la concurrence ? des gnous
    traversent l'horizon. De candidatures envoyées en masse ? des oiseaux s'envolent. Choisis l'animal d'après ce qu'il
    représente (champ « sens » de la liste) ;
  - FAUX NOM LATIN : la légende du plan 1 donne un nom latin inventé et drôle (« Candidatus ignoratus », « Curriculum floridus »),
    lisible, 3 mots au plus ; les autres plans n'ont une légende que si un nouvel animal apparaît ;
  - CE QU'ON DIT = CE QU'ON VOIT : un nombre ou un animal cité correspond à ce qui est montré ;
  - VARIE LES PLANS : deux plans de suite ne se ressemblent pas (autre habitat, autre moment de la journée ou autre cadre) ;
  - UN SEUL CONSEIL, bien compris. Aucun chiffre ni statistique inventé ; OpusCV n'est jamais cité avant l'appel à l'action final.
"""


def documentaire_rules() -> str:
    """Consignes du format documentaire : catalogue des habitats, moments, animaux et prises de vue + exemple de plan."""
    doc = catalog.documentaire()
    habitats = "\n".join(f'  - "{h["id"]}" : {h["description"]}' for h in doc["habitats"])
    moments = "\n".join(f'  - "{m["id"]}" : {m["description"]}' for m in doc["moments"])
    especes = "\n".join(f'  - "{e["id"]}" ({e["nom"]}) : {e["sens"]}. {e["description"]}'
                        + (f' Actions : {", ".join(e["actions"])}.' if e["actions"] else "") for e in doc["especes"])
    cadres = "\n".join(f'  - "{k}" : {v}' for k, v in doc["cadres"].items())
    mouvements = "\n".join(f'  - "{k}" : {v}' for k, v in doc["mouvements"].items())
    return f"""{doc["consigne"]}

Chaque scène (sauf la dernière) est un PLAN de documentaire, dans le champ "carte" :
{{"type": "documentaire", "habitat": "savane", "moment": "crepuscule", "cadre": "moyen", "mouvement": "avant",
 "sujets": [{{"espece": "autruche", "x": "centre", "regard": "droite", "action": "enfouir"}},
            {{"espece": "gnou", "x": "gauche", "nombre": 4, "action": "marcher", "vers": "droite"}}],
 "legende": {{"titre": "Le chercheur d'emploi", "latin": "Candidatus ignoratus", "detail": "Habitat : sa boîte mail"}}}}
Habitats ("habitat") :
{habitats}
Moments de la lumière ("moment") :
{moments}
Animaux ("espece" ; 1 à 3 par plan, "x" = gauche | centre | droite, "regard" = gauche | droite, "echelle" 0.5 à 1.6,
"profondeur" 0 (devant) à 1 (au loin), "action" = une de ses actions ou "marcher" avec "vers" ; "nombre" pour les
oiseaux et pour un troupeau de gnous) :
{especes}
Cadre ("cadre") :
{cadres}
Mouvement de caméra ("mouvement") :
{mouvements}
"legende" : "titre" (le nom de l'espèce observée, 5 mots au plus), "latin" (faux nom latin drôle), "detail" (une
observation, 9 mots au plus : « Habitat : sa boîte mail. Régime : les offres d'emploi »).
Le texte de la carte ne recopie pas la voix : la voix raconte, l'image montre."""


def build_prompt_documentaire(plan: dict, duration: int, feedback: str | None, recent_hooks: list[str]) -> str:
    """Prompt du faux documentaire animalier (format documentaire_nature)."""
    fmt, hook = plan["format"], plan["hook"]
    humour = plan.get("registre") == "humour"
    target, lo_w, hi_w = word_budget(duration, catalog.tone_for(fmt, plan.get("registre")), documentaire=True)
    lo_s, hi_s = documentaire_bounds(duration)
    cta = plan.get("cta") or catalog.pick_cta(fmt["categorie"], random.Random())[0]
    cta_rule = (f"dernière scène = EXACTEMENT cette phrase, recopiée mot pour mot (elle est déjà enregistrée), sans plan : « {cta} »"
                if cta_enregistre() else f"dernière scène = CTA court, sans plan, dans l'esprit : « {cta} »")
    avoid_hooks = "\n".join(f"- {h}" for h in recent_hooks[-12:]) or "(aucune)"
    banned = " ; ".join(f"« {b} »" for b in catalog.config().get("phrases_bannies", []))
    insta_max = (catalog.config().get("instagram") or {}).get("hashtags_max", 5)
    registre = (f"\nREGISTRE : HUMOUR. {catalog.config().get('consigne_humour', '')}\n" if humour else "")
    prompt = f"""Tu es scénariste de documentaires animaliers humoristiques ET expert en contenu TikTok / Instagram Reels sur l'emploi, le
recrutement et la carrière. Tu écris le SCÉNARIO d'un faux documentaire vertical de {duration} secondes, en français : une voix off
calme observe le candidat comme un animal dans son habitat et donne un VRAI conseil de recruteur. Le spectateur repart avec une
phrase ou un réflexe à utiliser dès demain. Le produit (OpusCV) n'est pas le sujet : il n'apparaît que dans l'appel à l'action final.

FORMAT : {fmt['nom']}.
Structure attendue : {fmt['structure']}
{registre}SUJET : {plan['sujet']['texte']}

TITRE À L'ÉCRAN ("accroche_ecran") : il s'affiche SEUL, plein écran, UNE seconde avant le documentaire. 6 mots au plus,
accrocheur, lisible d'un coup d'œil, qui donne envie de rester (une question que le spectateur se pose vraiment, ou une
affirmation qui intrigue). Inspiration de style, sans la recopier : « {hook['id']} » — {hook['consigne']} ; ex. « {hook['exemple']} ».
La voix off ne répète pas le titre. Pas de nombre annoncé (« 3 conseils »). Ne réutilise pas ces accroches déjà publiées :
{avoid_hooks}

{DOC_ECRITURE}
{documentaire_rules()}

Contraintes :
- entre {lo_s} et {hi_s} scènes (plans + la scène finale d'appel à l'action) ;
- texte total entre {lo_w} et {hi_w} mots (environ {target}) : c'est ce qui fait durer le reel {duration} s (voix lente) ;
- {cta_rule} ;
- public : des CANDIDATS qui cherchent un emploi ; le CTA parle de leur recherche (décrocher un entretien) ;
- français impeccable AVEC TOUS LES ACCENTS et la ponctuation : le texte est affiché tel quel en sous-titres ;
- pas d'emoji, pas de hashtag, pas d'indication de mise en scène dans les textes ;
- aucun conseil générique ou évident (interdit : {banned}) ;
- RESTE SUR LE SUJET : traite CE sujet, avec ses exemples propres.

Fournis aussi :
- "mots_cles" : 3 à 6 mots-clés du texte dit (mots isolés, tels qu'écrits dans les scènes), mis en couleur dans les sous-titres ;
- "legende" : la description TikTok (1 à 2 phrases + une question pour faire commenter) ;
- "hashtags" : 4 à 6 hashtags pertinents pour TikTok ;
- "legende_instagram" : la description Instagram (1re ligne accrocheuse, 2 à 4 phrases courtes, une question, une invitation à
  enregistrer ; sauts de ligne autorisés, pas d'emoji) ;
- "hashtags_instagram" : {insta_max} hashtags au plus, précis et en français ;
- "carrousel" : {CARROUSEL_MIN} à {CARROUSEL_MAX} diapositives [{{"titre": "4 à 9 mots", "texte": "1 à 2 phrases, 30 mots max"}}] (la 1re
  = la couverture ; une idée concrète par diapositive ; pas de diapositive d'appel à l'action) ;
- "offre_emploi" : une offre d'emploi fictive courte (2 à 4 phrases) plausible pour ce sujet ;
- "theme_style" : 2 à 4 mots décrivant le style visuel de CV le plus adapté.
"""
    if feedback:
        prompt += f"\nCORRECTION DEMANDÉE sur ta proposition précédente : {feedback}\n"
    prompt += """
Réponds UNIQUEMENT en JSON valide :
{"titre": "...", "accroche_ecran": "...", "mots_cles": ["..."], "legende": "...", "hashtags": ["#..."],
 "legende_instagram": "...", "hashtags_instagram": ["#..."], "carrousel": [{"titre": "...", "texte": "..."}], "offre_emploi": "...",
 "theme_style": "...", "scenes": [{"texte": "voix off du plan 1", "carte": {"type": "documentaire", ...}}, ..., {"texte": "..."}]}
"""
    return prompt


def build_prompt(plan: dict, duration: int, forced: list[dict] | None, feedback: str | None,
                 recent_hooks: list[str]) -> str:
    if plan["format"].get("documentaire"):
        return build_prompt_documentaire(plan, duration, feedback, recent_hooks)
    fmt, hook = plan["format"], plan["hook"]
    humour = plan.get("registre") == "humour"
    catalog_features = "\n".join(f'- "{fid}" : {f.description}' for fid, f in available_features().items())
    target, lo_w, hi_w = word_budget(duration, catalog.tone_for(fmt, plan.get("registre")), bool(fmt.get("dessin")))
    lo_s, hi_s = scene_bounds(duration)
    cta = plan.get("cta") or catalog.pick_cta(fmt["categorie"], random.Random())[0]
    # CTA enregistre (config.json cta_enregistre) : phrase recopiee telle quelle, sa voix est deja enregistree.
    cta_fixe = cta_enregistre()
    cta_rule = (f"dernière scène = EXACTEMENT cette phrase, recopiée mot pour mot (elle est déjà enregistrée) : « {cta} »"
                if cta_fixe else f"dernière scène = CTA court, dans l'esprit : « {cta} »")
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

    icons = " ; ".join(f"{k} = {v['nom']}" for k, v in catalog.icons().items())
    meme_card = """
  - carte mème (format mème pour faire rire : en haut une situation vécue, une icône dessinée au milieu,
    en bas la chute en grosses lettres ; 1 à 3 par reel) :
    "carte": {"type": "meme", "haut": "la situation, 12 mots max (ex : Quand l'offre demande 5 ans d'expérience pour un stage)",
              "icone": "<id d'icône>", "bas": "la chute, 7 mots max (ex : Moi, né l'an dernier)"}""" if humour else ""
    sans_captures = bool(plan.get("sans_captures"))
    if fmt["cartes"] == "aucune" and not sans_captures:
        cards_rule = "Aucune scène n'a de carte : chaque scène montre uniquement la fonctionnalité."
    else:
        need = ("CHAQUE scène sauf la première et la dernière" if sans_captures
                else "la MAJORITÉ des scènes" if fmt["cartes"] == "majoritaires" else "les scènes où c'est utile")
        cards_rule = f"""Pour {need}, ajoute une "carte" : un écran texte animé affiché à la place de la
capture, qui résume visuellement ce que dit la voix :
  - carte texte (par défaut) :
    "carte": {{"type": "texte", "surtitre": "2 à 4 mots", "titre": "2 à 8 mots, l'idée clé",
               "texte": "une phrase courte, optionnelle",
               "style": "normal" | "mythe" | "realite" | "avant" | "apres",
               "effet": "standard" | "frappe" | "suspense"}}
  - carte chiffre (un grand nombre qui compte, pour une donnée marquante et PLAUSIBLE, jamais
    une statistique inventée sur OpusCV) :
    "carte": {{"type": "chiffre", "surtitre": "...", "valeur": "75", "unite": "%", "titre": "légende courte"}}
  - carte comparaison (avant/après côte à côte, idéale pour une ligne de CV réécrite) :
    "carte": {{"type": "comparaison", "surtitre": "...", "avant": "formulation faible", "apres": "formulation forte"}}
  - carte liste (2 à 5 points qui se cochent un par un, pour une checklist ou un récapitulatif) :
    "carte": {{"type": "liste", "surtitre": "...", "titre": "...", "points": ["...", "..."]}}
  - carte schéma (explication DESSINÉE À LA MAIN, comme au tableau : 1 à 3 étapes-icônes reliées par des
    flèches, idéale pour expliquer un mécanisme : le tri par l'ATS, le trajet d'une candidature, ce que
    regarde un recruteur) :
    "carte": {{"type": "schema", "surtitre": "...", "titre": "2 à 6 mots",
               "etapes": [{{"icone": "<id>", "label": "2 à 5 mots"}}, ...],
               "marque": "barre" (dernière étape = l'échec) | "coche" (= la réussite) | "entoure" (pour insister) | ""}}
    icônes disponibles (champ "icone") : {icons}
  - carte conversation (échange de messages FICTIF et réaliste, 2 à 4 messages de 12 mots max, entre le candidat
    "moi" et un interlocuteur, ex : la réponse d'un recruteur) :
    "carte": {{"type": "conversation", "contact": "Recruteur", "messages": [{{"de": "recruteur", "texte": "..."}},
               {{"de": "moi", "texte": "..."}}]}}
  - carte scan (le CV passé au scanner ATS face à l'offre : mots-clés de l'offre trouvés / manquants, 3 à 6 au
    total, repris de "offre_emploi") :
    "carte": {{"type": "scan", "surtitre": "...", "titre": "...", "trouves": ["..."], "manquants": ["..."]}}
  - carte impact (LA phrase à retenir, qui claque mot par mot en très grand ; UNE SEULE par reel, pour le
    message clé) : "carte": {{"type": "impact", "texte": "4 à 9 mots", "mot": "le mot fort de la phrase"}}{meme_card}
Varie les types de cartes dans un même reel quand le contenu s'y prête.
Effets d'apparition du titre (cartes texte) : "frappe" (tapé au clavier, idéal pour une citation, une formulation
de CV ou une phrase d'offre), "suspense" (titre caché puis révélé avec un impact : UNE SEULE fois
par reel, pour la révélation la plus forte, jamais sur deux cartes), sinon "standard". Varie-les.
Jamais de carte sur la scène 1 (l'accroche s'affiche déjà en grand par-dessus) ni sur la dernière (CTA).
Le texte de la carte ne recopie PAS la voix : il la résume.""" + ("" if sans_captures else """ Une scène avec carte garde un champ "feature"
(la fonctionnalité la plus proche du sujet, montrée si la carte ne peut pas être affichée).""")

    annotation_rule = """
ANNOTATION AU FEUTRE : sur la scène preuve (s'il y en a une) et au plus une autre scène SANS carte qui montre
OpusCV, ajoute "annotation": 2 à 5 mots manuscrits sur un post-it qui pointe l'élément clé de l'écran
(ex : « tes mots-clés manquants », « le bouton magique »), en tutoyant. Jamais sur la scène 1 ni la dernière.
"""
    proof_rule = ""
    if sans_captures:
        annotation_rule = ""
    elif wants_proof(fmt):
        proof_rule = """
SCÈNE PREUVE (obligatoire, une seule) : l'avant-dernière ou l'antépénultième scène montre le conseil
APPLIQUÉ EN DIRECT dans OpusCV : marque-la "preuve": true, SANS carte, avec la fonctionnalité qui
applique ce conseil (ex : "checklist" pour les erreurs détectées, "adapter" pour les mots-clés d'une offre,
"relecture" pour l'orthographe). La voix dit concrètement ce que l'outil fait à ce moment
(« là, l'outil repère... »), naturellement, sans ton publicitaire ni superlatif.
"""
    intent = ("contenu utile : le spectateur doit apprendre quelque chose, le produit n'est qu'un outil"
              if fmt["categorie"] == "conseil" else "démonstration du produit")
    registre_rule = ""
    if humour:
        registre_rule = f"""
REGISTRE : HUMOUR. {catalog.config().get("consigne_humour", "")}
Ton de lecture de la voix : {catalog.tone_for(fmt, "humour")}.
"""
    avoid_hooks = "\n".join(f"- {h}" for h in recent_hooks[-12:]) or "(aucune)"
    banned = " ; ".join(f"« {b} »" for b in catalog.config().get("phrases_bannies", []))
    insta_max = (catalog.config().get("instagram") or {}).get("hashtags_max", 5)
    # Themes deja tres traites sur le compte : n'y revenir que s'ils SONT le sujet.
    off_topic = ("ce sujet porte justement sur ce thème, traite-le à fond."
                 if plan["sujet"].get("famille") in ("ats_mots_cles", "redaction_cv", "produit_analyse")
                 else "ne dérive pas vers les logiciels ATS, les mots-clés ni le fait de chiffrer ses résultats "
                      "(thèmes déjà très traités sur le compte) ; traite CE sujet, avec ses exemples propres.")
    dessin = bool(fmt.get("dessin"))
    if dessin:
        lo_s, hi_s = dessin_bounds(duration)
        cards_rule = proof_rule = annotation_rule = ""
        # Volume de texte rendu concret : le dialogue deborde sinon (93 mots pour 73 au plus, run 57).
        cards_rule = (f"LONGUEUR : {lo_w} à {hi_w} mots EN TOUT, CTA compris (environ {target}) : par exemple "
                      f"{max(6, round(target / 7))} à {max(7, round(target / 6))} répliques de 6 à 8 mots. "
                      "Compte tes mots avant de répondre : un texte trop long fait dépasser la durée du reel.")
    if dessin:
        screen_rule = dessin_rules(plan) + """OpusCV n'est cité que dans l'appel à l'action final (phrase imposée), jamais dans l'histoire.
"""
        scene1_rule = ""
        variety_rule = "chaque scène fait avancer l'histoire (pas deux scènes qui disent la même chose) ;"
    elif sans_captures:
        screen_rule = f"""Le reel est une suite de SCÈNES, SANS AUCUNE IMAGE DE L'APPLICATION : l'écran de chaque scène est
une carte animée (ci-dessous) pendant que la voix off dit le texte de la scène. Pas de champ "feature".
Scène 1 : pas de carte, mais un champ "illustration" = l'id d'une icône dessinée à la main sous l'accroche,
en rapport avec le sujet (icônes disponibles : {", ".join(catalog.icons())}).
Dernière scène : pas de carte (l'appel à l'action animé s'affiche automatiquement).
Tu peux citer OpusCV à la fin comme l'outil qui aide, sans décrire d'écran que le spectateur ne voit pas.
"""
        scene1_rule = ""
        variety_rule = "varie les types de cartes, jamais le même type dans deux scènes consécutives ;"
    else:
        screen_rule = f"""Le reel est une suite de SCÈNES. Pendant chaque scène, l'écran montre une fonctionnalité réelle
d'OpusCV (capturée automatiquement dans l'application) et la voix off dit le texte de la scène.
Fonctionnalités filmables (utilise UNIQUEMENT ces ids, champ "feature") :
{catalog_features}
"""
        scene1_rule = (', sur une fonctionnalité visuellement riche (pas "dashboard",\n'
                       '  dont la capture est une simple ligne)')
    save_rule = ("""Relance juste après l'accroche : la 1re phrase de la scène 2 (juste après l'accroche)
invite en 5 à 7 mots à enregistrer la vidéo pour ne pas la perdre, puis enchaîne aussitôt sur le
contenu. Varie la formulation (ex : « Enregistre-la, tu vas en avoir besoin. », « Garde-la avant de
postuler. ») ; ne demande PAS l'abonnement ici, il est réservé au CTA final.
""" if wants_save_nudge(fmt, humour) and not dessin else "")
    intro = ("""Tu es scénariste de séries courtes (sitcom, comédie de situation) ET expert en marketing de contenu TikTok /
Instagram Reels, spécialisé dans l'emploi, le recrutement et la carrière. Tu écris un mini-scénario original qui donne un
VRAI conseil de recruteur à des candidats : le reel est de la valeur pour le spectateur (il repart avec une phrase,
une règle ou un réflexe à utiliser dès demain), pas une publicité. Le produit (OpusCV) n'est pas le sujet : il
n'apparaît que dans l'appel à l'action final.
""" if dessin else f"""Tu es un expert en création de contenu viral (TikTok, Instagram Reels, YouTube Shorts), spécialisé dans
l'emploi, le recrutement et la recherche de CV. Tes vidéos promeuvent OpusCV avec un ton direct, captivant et
axé sur les frustrations réelles des candidats : l'idée est d'avoir une accroche très forte.
Base-toi UNIQUEMENT sur ces informations produit réelles, n'invente aucune fonctionnalité :

{PRODUCT_CONTEXT}
""")
    hook_rule = (f"""ACCROCHE (décisive pour la rétention) : une QUESTION simple, que le spectateur se pose vraiment, sur un problème
précis qu'il a vécu (inspiration de style, sans la recopier : « {hook['id']} » — {hook['consigne']} ; ex. « {hook['exemple']} »).
Deux façons, au choix, et JAMAIS un slogan ni un titre dit par un personnage :
  - le TITRE à l'écran ("accroche_ecran") est la question (« Pourquoi personne ne te rappelle ? »,
    2e personne), et la 1re réplique est une vraie phrase de la scène ; ce TITRE s'affiche SEUL, plein écran, UNE seconde
    avant la scène : 6 mots au plus, accrocheur, lisible d'un coup d'œil ;
  - ou la 1re réplique est la question, posée par un personnage dans la situation (« Pourquoi personne ne me rappelle ? »),
    et le titre à l'écran la reprend autrement.
Le titre et la bulle ne se répètent pas. Pas de nombre annoncé (« 3 conseils », « 2 questions ») : dis ce qu'on va
apprendre, c'est tout. Un chiffre ne s'écrit que s'il est concret et vrai (7 jours, 30 secondes) ; JAMAIS de
statistique inventée (« 80 % des candidats »).""" if dessin else f"""ACCROCHE (scène 1, décisive pour la rétention) : style « {hook['id']} » — {hook['consigne']}
Exemple de ton (ne pas recopier) : « {hook['exemple']} »
Règles strictes de l'accroche (0-3 s) : 2e personne du singulier (« tu », « ton », « tes ») ; elle déclenche
une émotion forte (peur de l'échec, curiosité, gain de temps, injustice du recrutement) ; elle intègre un
chiffre précis quand c'est possible, mais UNIQUEMENT un chiffre concret ou vérifiable (une durée,
un nombre de lignes, de boîtes, d'étapes : 6 secondes, 30 secondes, 3 lignes, 50 boîtes) ; JAMAIS de
statistique ni de pourcentage inventé (« 80 % des candidats », « 4 candidats sur 5 »…).""")
    corps = ("Corps : l'histoire (voir DESSIN ANIMÉ ci-dessous) pose vite le problème précis, puis le conseil concret de "
             "recruteur, appliqué et visible ; rythme rapide, phrases courtes, zéro blabla." if dessin else
             "Corps (3-20 s) : expose vite le problème précis, puis la solution concrète apportée par OpusCV (montrée à\n"
             "l'écran) ; rythme rapide, phrases courtes, zéro blabla.")
    prompt = f"""{intro}
Tu écris le SCÉNARIO d'un reel vertical de {duration} secondes, en français.

FORMAT : {fmt['nom']} ({intent}).
Structure attendue : {structure}
{registre_rule}
SUJET : {plan['sujet']['texte']}

{hook_rule}
{corps}
Public : des CANDIDATS qui cherchent un emploi (jamais des recruteurs) ; le CTA parle de leur recherche
(décrocher un entretien, un job), pas de « recrutements ».
Appel à l'action (fin) : incite à tester gratuitement l'outil (ex : « Lien en bio pour tester gratuitement »).
{save_rule}Ne réutilise pas ces accroches déjà publiées, ni leur formulation :
{avoid_hooks}

{screen_rule}
{cards_rule}
{proof_rule}{annotation_rule}
Contraintes :
- entre {lo_s} et {hi_s} scènes ;
- texte total entre {lo_w} et {hi_w} mots (environ {target}) : c'est ce qui fait durer le reel {duration} s ;
- scène 1 = l'accroche (12 mots max){scene1_rule} ; {cta_rule} ;
- {"des répliques courtes et vivantes, comme un vrai dialogue" if dessin else "1 à 2 phrases par scène"}, ton oral et naturel, tutoiement, pas publicitaire{"" if not humour else ", drôle"} ;
- {variety_rule}
- français impeccable AVEC TOUS LES ACCENTS (é, è, à, ç, ê...) et la ponctuation : le texte est
  affiché tel quel en sous-titres ;
- pas d'emoji, pas de hashtag, pas d'indication de mise en scène dans les textes ;
- les exemples de phrases de CV ou de lettre n'inventent AUCUN chiffre précis (pas « 200 k€ de ventes ») :
  formule sans chiffre, ou « [ton chiffre] » quand il en faut un ;
- ORIGINALITÉ : aucun conseil générique ou évident (interdit : {banned}) ;
  chaque scène apporte un élément concret : un exemple de formulation, une phrase à dire ou à écrire,
  un cas précis ou une astuce actionnable immédiatement ;
- RESTE SUR LE SUJET : {off_topic}
- RYTHME : phrases courtes et percutantes, une idée par scène, aucune phrase de transition creuse ;
- BOUCLE OUVERTE : dès la scène 2, promets une révélation placée plus tard (« et la 3ᵉ erreur est la pire »,
  « reste jusqu'à la fin pour la phrase à copier ») et tiens-la dans les dernières scènes : c'est ce qui
  retient le spectateur au-delà des 3 premières secondes ;
- BOUCLE : {"l'avant-dernière scène" if cta_fixe else "la dernière phrase"} répond ou fait écho à l'accroche, pour que la vidéo s'enchaîne
  naturellement si elle recommence.

Fournis aussi :
- "accroche_ecran" : le texte de la couverture / hook visuel, affiché en GRAND dès la première image
  ({ACCROCHE_MAX_WORDS} mots max), complémentaire de la voix (pas forcément identique), avec un chiffre si
  possible, qui donne envie de rester ;
- "mots_cles" : 3 à 6 mots-clés du texte dit (mots isolés, tels qu'écrits dans les textes des scènes),
  mis en couleur dans les sous-titres — les mots qui portent le message (ex : "relance", "pitch", "recruteur") ;
- "legende" : la description de la publication TikTok (1 à 2 phrases + une question pour faire commenter) ;
- "hashtags" : 4 à 6 hashtags pertinents pour TikTok (ex : #cv, #emploi, #recherchedemploi) ;
- "legende_instagram" : la description Instagram, plus riche : une 1re ligne accrocheuse (visible avant « plus »),
  puis 2 à 4 phrases courtes qui résument les conseils du reel, une question pour faire commenter, et une
  invitation à enregistrer le post (sauts de ligne autorisés, pas d'emoji) ;
- "hashtags_instagram" : {insta_max} hashtags au plus, précis et en français (Instagram en limite le nombre) ;
- "carrousel" : la déclinaison du reel en carrousel Instagram, {CARROUSEL_MIN} à {CARROUSEL_MAX} diapositives
  [{{"titre": "4 à 9 mots", "texte": "1 à 2 phrases, 30 mots max"}}] : la 1re = la couverture (promesse forte,
  "texte" = sous-titre court), puis une idée concrète par diapositive (lisible sans le son ni la vidéo) ;
  pas de diapositive d'appel à l'action (ajoutée automatiquement) ;
- "offre_emploi" : une offre d'emploi fictive courte (2 à 4 phrases : intitulé, missions, exigences clés)
  plausible pour ce sujet — utilisée dans les démos « adapter le CV » et « lettre de motivation ».
  Varie le métier/secteur d'un scénario à l'autre ;
- "theme_style" : 2 à 4 mots décrivant le style visuel de CV le plus adapté (ex : « sobre et corporate »).
"""
    if plan.get("episode"):
        prompt += f"\nC'est l'épisode {plan['episode']} de la série : ne répète pas les conseils d'un épisode précédent.\n"
    if dessin and plan.get("episode"):
        prompt += ('Fournis aussi "resume_episode" : UNE phrase (25 mots max) qui résume ce qui arrive à Karim dans cet '
                   "épisode et où il en est à la fin (elle sera rappelée à l'épisode suivant).\n")
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

    scene_json = ('{"fond": "...", "titre": "...", "objets": [...], "actions": [...]}, ..., {"cta": true, "qui": "...", "texte": "..."}]'
                  if dessin else
                  '{"illustration": "<id d\'icône>", "texte": "..."}, {"texte": "...", "carte": {...}}, ..., {"texte": "..."}]'
                  if sans_captures else
                  '{"feature": "<id>", "texte": "...", "carte": {...} (optionnel), "preuve": true (optionnel),\n'
                  ' "annotation": "..." (optionnel)}]')
    prompt += """
Réponds UNIQUEMENT en JSON valide :
{"titre": "...", "accroche_ecran": "...", "mots_cles": ["..."], "legende": "...", "hashtags": ["#..."],
 "legende_instagram": "...", "hashtags_instagram": ["#..."], "carrousel": [{"titre": "...", "texte": "..."}], "offre_emploi": "...",
 "theme_style": "...", "scenes": [""" + scene_json + "}\n"
    return prompt


def clean_card(raw) -> dict | None:
    """
    Carte normalisee selon son type (catalog.CARD_TYPES) :
      texte       : surtitre, titre, texte, style, effet   (assets/anim/carte.html)
      chiffre     : surtitre, valeur, unite, titre         (chiffre.html)
      comparaison : surtitre, avant, apres                 (comparaison.html)
      liste       : surtitre, titre, points[2-5]           (liste.html)
      schema      : surtitre, titre, etapes[1-3] {icone, label}, marque   (schema.html)
      conversation: surtitre, contact, messages[2-4] {de: recruteur|moi, texte}   (conversation.html)
      scan        : surtitre, titre, trouves, manquants (6 mots-cles max)  (scan.html)
      impact      : texte, mot                              (impact.html)
      meme        : haut, bas, icone                        (meme.html)
    Champs obligatoires absents -> None (scene sans carte).
    """
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("type") or "texte").strip().lower()
    txt = lambda k: str(raw.get(k) or "").strip()
    if kind == "chiffre":
        valeur = re.sub(r"[^0-9,.]", "", txt("valeur"))
        if not valeur or not txt("titre"):
            return None
        return {"type": "chiffre", "surtitre": txt("surtitre"), "valeur": valeur,
                "unite": txt("unite")[:6], "titre": txt("titre")}
    if kind == "comparaison":
        if not txt("avant") or not txt("apres"):
            return None
        return {"type": "comparaison", "surtitre": txt("surtitre"), "avant": txt("avant"), "apres": txt("apres")}
    if kind == "liste":
        points = [str(p).strip() for p in raw.get("points") or [] if str(p).strip()][:5]
        if len(points) < 2:
            return None
        return {"type": "liste", "surtitre": txt("surtitre"), "titre": txt("titre"), "points": points}
    if kind == "schema":
        steps = []
        for step in raw.get("etapes") or []:
            if not isinstance(step, dict) or not str(step.get("label") or "").strip():
                continue
            icon = str(step.get("icone") or "").strip().lower()
            steps.append({"icone": icon if icon in catalog.icons() else closest_icon(icon),
                          "label": str(step["label"]).strip()})
        if not steps or not txt("titre"):
            return None
        marque = txt("marque").lower()
        return {"type": "schema", "surtitre": txt("surtitre"), "titre": txt("titre"), "etapes": steps[:3],
                "marque": marque if marque in catalog.SCHEMA_MARKS else ""}
    if kind == "conversation":
        msgs = [{"de": "moi" if str(m.get("de") or "").strip().lower() in ("moi", "candidat", "m") else "recruteur",
                 "texte": str(m.get("texte") or "").strip()}
                for m in raw.get("messages") or [] if isinstance(m, dict) and str(m.get("texte") or "").strip()]
        if len(msgs) < 2:
            return None
        return {"type": "conversation", "surtitre": txt("surtitre"), "contact": txt("contact") or "Recruteur",
                "messages": msgs[:4]}
    if kind == "scan":
        words = lambda k: [str(w).strip() for w in raw.get(k) or [] if str(w).strip()]
        found, missing = words("trouves"), words("manquants")
        if not found and not missing:
            return None
        return {"type": "scan", "surtitre": txt("surtitre"), "titre": txt("titre"),
                "trouves": found[:4], "manquants": missing[:4]}
    if kind == "impact":
        if not txt("texte"):
            return None
        return {"type": "impact", "texte": txt("texte"), "mot": txt("mot")}
    if kind == "documentaire":
        return clean_card_documentaire(raw)
    if kind == "meme":
        if not txt("haut") or not txt("bas"):
            return None
        icon = txt("icone").lower()
        return {"type": "meme", "haut": txt("haut"), "bas": txt("bas"),
                "icone": icon if icon in catalog.icons() else closest_icon(icon)}
    if not txt("titre"):
        return None
    style, effet = txt("style").lower() or "normal", txt("effet").lower() or "standard"
    return {
        "type": "texte",
        "effet": effet if effet in catalog.CARD_EFFECTS else "standard",
        "surtitre": txt("surtitre"),
        "titre": txt("titre"),
        "texte": txt("texte"),
        "style": style if style in catalog.CARD_STYLES else "normal",
    }


def _choix(valeur, valides, defaut: str, cutoff: float = 0.7) -> str:
    """Valeur ecrite par l'IA -> la plus proche des valeurs valides (accents et casse ignores), sinon le defaut."""
    import difflib
    v = catalog._norm(str(valeur or ""))
    ids = {catalog._norm(x): x for x in valides}
    if v in ids:
        return ids[v]
    proche = difflib.get_close_matches(v, list(ids), n=1, cutoff=cutoff)
    return ids[proche[0]] if proche else defaut


def clean_card_documentaire(raw: dict) -> dict | None:
    """
    Plan de documentaire normalise (assets/anim/documentaire.html, catalog/documentaire.json) :
      habitat, moment, cadre, mouvement, sujets[1-4] {espece, x ("gauche|centre|droite" ou pixels), regard,
      echelle, profondeur, nombre, action, vers}, legende {titre, latin, detail}.
    Une espece, un habitat ou un moment inconnu est remplace par le plus proche ; sans aucun animal valide -> None.
    Le resultat est directement le plan joue par le gabarit ("sujets" avec ids, "actions" chronologiques).
    """
    doc = catalog.documentaire()
    especes = {e["id"]: e for e in doc["especes"]}
    positions = doc["positions"]
    txt = lambda d, k: " ".join(str(d.get(k) or "").split())
    habitat = _choix(raw.get("habitat"), [h["id"] for h in doc["habitats"]], "savane")
    moment = _choix(raw.get("moment"), [m["id"] for m in doc["moments"]], "jour")
    cadre = _choix(raw.get("cadre"), doc["cadres"], "moyen")
    mouvement = _choix(raw.get("mouvement"), doc["mouvements"], "fixe")
    sujets, actions = [], []
    brut = [x for x in raw.get("sujets") or [] if isinstance(x, dict)]
    for k, x in enumerate(brut[:4]):
        eid = _choix(x.get("espece"), list(especes), "", cutoff=0.85)
        if not eid:
            continue
        esp = especes[eid]
        if sum(1 for q in sujets if q["espece"] == eid) >= esp.get("max", 2):
            continue
        pos = x.get("x")
        if isinstance(pos, (int, float)):
            px = int(min(max(pos, 100), 980))
        else:
            px = positions[_choix(pos, positions, ["centre", "gauche", "droite", "centre"][k % 4] if len(brut) > 1 else "centre")]
        sid = f"s{len(sujets) + 1}"
        sujet = {"id": sid, "espece": eid, "x": px}
        regard = _choix(x.get("regard"), doc["regards"], "droite")
        if regard == "gauche":
            sujet["regard"] = "gauche"
        for cle, lo, hi in (("echelle", 0.5, 1.6), ("profondeur", 0, 1)):
            try:
                sujet[cle] = round(min(max(float(x.get(cle)), lo), hi), 2)
            except (TypeError, ValueError):
                pass
        if esp.get("ciel"):
            try:
                sujet["nombre"] = int(min(max(int(x.get("nombre") or 7), 3), 10))
            except (TypeError, ValueError):
                sujet["nombre"] = 7
        action = _choix(x.get("action"), esp.get("actions", []) + ["marcher"], "")
        if action:
            act = {"qui": sid, "action": action, "t": round(0.9 + 0.5 * len(actions), 2)}
            if action == "marcher":
                vers = x.get("vers")
                act["vers"] = int(min(max(vers, 100), 980)) if isinstance(vers, (int, float)) else \
                    positions[_choix(vers, positions, "droite" if px < 540 else "gauche")]
            actions.append(act)
        sujets.append(sujet)
        if eid == "gnou" and isinstance(x.get("nombre"), (int, float)) and int(x["nombre"]) > 1:
            # Troupeau : le meme gnou repete le long de l'horizon, tous en marche.
            for j in range(1, min(int(x["nombre"]), esp.get("max", 8))):
                gid = f"s{len(sujets) + 1}"
                gx = int(min(max(px + 90 * j, 100), 980))
                sujets.append({"id": gid, "espece": "gnou", "x": gx, "profondeur": round(min(0.3 + 0.1 * (j % 4), 0.7), 2),
                               **({"regard": "gauche"} if regard == "gauche" else {})})
                actions.append({"qui": gid, "action": "marcher", "t": round(0.6 + 0.05 * j, 2),
                                "vers": int(min(max(gx + (-260 if regard == "gauche" else 260), 100), 980))})
    if not sujets:
        return None
    # Les ids doivent rester uniques et dans l'ordre ou ils sont poses.
    leg = raw.get("legende") if isinstance(raw.get("legende"), dict) else {}
    legende = {k: txt(leg, k)[:n] for k, n in (("titre", 42), ("latin", 40), ("detail", 80))}
    plan = {"type": "documentaire", "habitat": habitat, "moment": moment, "cadre": cadre, "mouvement": mouvement,
            "sujets": sujets, "actions": actions}
    if legende["titre"]:
        plan["legende"] = {k: v for k, v in legende.items() if v}
    return plan


def closest_icon(name: str) -> str:
    """Icone inventee par l'IA -> la plus proche du catalogue (par le nom), sinon "question"."""
    import difflib
    ids = list(catalog.icons())
    match = difflib.get_close_matches(catalog._norm(name), ids, n=1, cutoff=0.6)
    return match[0] if match else "question"


def wants_proof(fmt: dict) -> bool:
    """Reels conseil : une scene "preuve" montre le conseil applique dans OpusCV (config preuve_produit)."""
    return fmt.get("categorie") == "conseil" and bool(catalog.config().get("preuve_produit", True))


def wants_save_nudge(fmt: dict, humour: bool) -> bool:
    """Reels conseil serieux : relance "enregistre" juste apres l'accroche (config relance_enregistrer)."""
    return (fmt.get("categorie") == "conseil" and not humour
            and bool(catalog.config().get("relance_enregistrer", True)))


def banned_phrases(text: str) -> list[str]:
    low = catalog._norm(text)
    return [b for b in catalog.config().get("phrases_bannies", []) if catalog._norm(b) in low]


def validate(data: dict, duration: int, forced: list[dict] | None, card_mode: str = "aucune",
             recent_hooks: list[str] | None = None, proof: bool = False,
             tone: str = "", sans_captures: bool = False, dessin: bool = False,
             documentaire: bool = False) -> tuple[list[dict], list[str]]:
    """
    Nettoie le scenario et liste ce qui ne respecte pas les contraintes (pour relancer l'IA).
    sans_captures : pas de feature (""), une carte sur chaque scene sauf la 1re (icone
    "illustration") et la derniere (CTA anime), ni preuve ni annotation.
    dessin : scenes dessinees (dessin_scenes), le texte = les repliques des personnages.
    """
    if documentaire:
        scenes, problems = documentaire_scenes(data)
        problems = problems + documentaire_texte_problems(scenes, data)
        return scenes, problems + common_problems(scenes, data, duration, tone, recent_hooks, None,
                                                  documentaire_bounds(duration), documentaire=True)
    if dessin:
        scenes, problems = dessin_scenes(data)
        problems = problems + dessin_texte_problems(scenes, data)
        return scenes, problems + common_problems(scenes, data, duration, tone, recent_hooks, None,
                                                  dessin_bounds(duration), dialogue=True)
    problems = []
    scenes = []
    for raw in data.get("scenes") or []:
        texte = str(raw.get("texte") or "").strip()
        fid = normalize_feature_id(raw.get("feature"))
        if not texte:
            continue
        if fid is None and sans_captures:
            fid = ""
        elif fid is None:
            # Sequence imposee : la feature est ecrasee plus bas, inutile de relancer pour ca.
            if not forced:
                problems.append(f'feature inconnue "{raw.get("feature")}" (remplacée par apercu_cv)')
            fid = "apercu_cv"
        scene = {"feature": fid, "texte": texte}
        # Scene 1 = accroche : jamais de carte, l'accroche_ecran s'y affiche deja en grand.
        card = clean_card(raw.get("carte")) if (card_mode != "aucune" or sans_captures) and scenes else None
        if card:
            scene["carte"] = card
        # Animations demandees par le scenario (run_pipeline.py --anims) :
        # conservees telles quelles, interpretees au montage.
        scene.update({k: raw[k] for k in ANIM_KEYS if raw.get(k)})
        if sans_captures:
            if not scenes:
                icone = str(raw.get("illustration") or "").strip().lower()
                scene["illustration"] = icone if icone in catalog.icons() else "cv"
            scenes.append(scene)
            continue
        if raw.get("preuve") is True and proof:
            scene["preuve"] = True
        annotation = " ".join(str(raw.get("annotation") or "").split())
        if annotation and "carte" not in scene:
            scene["annotation"] = " ".join(annotation.split()[:ANNOTATION_MAX_WORDS])
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
                    scene.pop("annotation", None)
                scene.update({k: imposed[k] for k in ANIM_KEYS + ("annotation", "preuve") if imposed.get(k)})

    if sans_captures and scenes:
        scenes[-1].pop("carte", None)  # CTA anime
        bare = [i for i in range(1, len(scenes) - 1) if "carte" not in scenes[i]]
        if bare:
            problems.append(f"sans capture de l'application, chaque scène sauf la 1re et la dernière a une carte "
                            f"(manquante aux scènes {', '.join(str(i + 1) for i in bare)})")
    # Carte impact = LA phrase a retenir : une seule par reel (les suivantes -> cartes texte).
    impacts = [s for s in scenes if s.get("carte", {}).get("type") == "impact"]
    for extra in impacts[1:]:
        extra["carte"] = {"type": "texte", "effet": "standard", "surtitre": "", "titre": extra["carte"]["texte"],
                          "texte": "", "style": "normal"}
    # Annotations au feutre : ni accroche ni CTA, 2 par reel au plus (la preuve d'abord).
    for i in (0, len(scenes) - 1):
        if scenes and "annotation" in scenes[i]:
            del scenes[i]["annotation"]
    annotated = sorted((i for i, s in enumerate(scenes) if s.get("annotation")), key=lambda i: not scenes[i].get("preuve"))
    for i in annotated[MAX_ANNOTATIONS:]:
        del scenes[i]["annotation"]
    # Suspense = effet de revelation : un seul par reel, sinon il s'use.
    suspense = [s for s in scenes if s.get("carte", {}).get("effet") == "suspense"]  # noqa: E501
    for extra in suspense[1:]:
        extra["carte"]["effet"] = "standard"

    if proof and not forced and scenes:
        # Preuve : une seule, sans carte, ni accroche ni CTA.
        proofs = [i for i, s in enumerate(scenes) if s.get("preuve")]
        for i in proofs:
            if i in (0, len(scenes) - 1):
                del scenes[i]["preuve"]
        proofs = [i for i in proofs if 0 < i < len(scenes) - 1]
        for i in proofs[1:]:
            del scenes[i]["preuve"]
        if proofs:
            scenes[proofs[0]].pop("carte", None)
        else:
            problems.append('il manque la scène "preuve": true (conseil appliqué en direct dans OpusCV)')
    problems += common_problems(scenes, data, duration, tone, recent_hooks, forced)
    if card_mode == "majoritaires" and not sans_captures and scenes and sum("carte" in s for s in scenes) < len(scenes) / 2:
        problems.append("ce format demande une carte pour la majorité des scènes")
    return scenes, problems


def common_problems(scenes: list[dict], data: dict, duration: int, tone: str, recent_hooks: list[str] | None,
                    forced: list[dict] | None, bounds: tuple[int, int] | None = None,
                    dialogue: bool = False, documentaire: bool = False) -> list[str]:
    """Controles communs a tous les formats : phrases bannies, volume de texte, accents, accroche."""
    problems = []
    banned = banned_phrases(" ".join(s["texte"] for s in scenes))
    if banned:
        problems.append("formulations trop génériques à remplacer par du concret : " + ", ".join(banned))

    words = sum(len(s["texte"].split()) for s in scenes)
    _, lo_w, hi_w = word_budget(duration, tone, dialogue, documentaire)
    lo_s, hi_s = bounds or scene_bounds(duration)
    if not scenes:
        problems.append("aucune scène exploitable")
    elif not forced and not lo_s <= len(scenes) <= hi_s:
        problems.append(f"{len(scenes)} scènes, il en faut entre {lo_s} et {hi_s}")
    if scenes and not lo_w <= words <= hi_w:
        problems.append(f"le texte fait {words} mots, il en faut entre {lo_w} et {hi_w} pour durer {duration} s")

    all_text = " ".join([s["texte"] for s in scenes] + [str(data.get("accroche_ecran") or "")])
    if len(all_text.split()) >= MIN_WORDS_ACCENT_CHECK and not ACCENT_RE.search(all_text):
        problems.append("le texte est écrit sans accents : écris en français correct avec tous les accents")

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
    return problems


def completer_mise_en_scene(scenes: list[dict]) -> None:
    """
    Dernier recours (apres les tentatives) : une scene dessinee restee sans action visible
    recoit une posture pour celui qui ecoute la 1re replique (il reflechit si c'est une
    question, sinon il croise les bras) -- jamais un plan fige ou seules les bouches bougent.
    """
    for s in scenes:
        d = s.get("dessin")
        if not d or any(a.get("action") not in ACTIONS_PAROLE for a in d["actions"]):
            continue
        parler = [i for i, a in enumerate(d["actions"]) if a.get("action") == "parler"]
        presents = [o["id"] for o in d["objets"] if o["id"] in catalog.personnages() or o["type"] in catalog.personnages()]
        if not parler or not presents:
            continue
        orateur = d["actions"][parler[0]]["qui"]
        ecoute = next((p for p in presents if p != orateur), orateur)
        posture = "penser" if d["actions"][parler[0]]["texte"].rstrip().endswith("?") else "bras_croises"
        d["actions"].insert(parler[0] + 1, {"qui": ecoute, "action": posture, "avec": True})


MOTS_VIDES = {"comment", "pourquoi", "quand", "avec", "sans", "pour", "dans", "votre", "vous", "tout", "cette", "faire",
              "plus", "mais", "donc", "alors", "sont", "fait", "quel", "quelle", "quoi", "est-ce"}


def _mots_cles(texte: str) -> set[str]:
    """Mots porteurs de sens d'une phrase (5 lettres et plus, hors mots vides), sans accents ni majuscules."""
    return {m for m in catalog._norm(texte).split() if len(m) >= 5 and m not in MOTS_VIDES}


NOMBRE_ANNONCE = re.compile(r"\b\d+\s*(questions?|conseils?|erreurs?|astuces?|phrases?|raisons?|r[èe]gles?|[ée]tapes?|signes?|secrets?)\b", re.I)


def nb_mots(texte: str) -> int:
    """Mots d'un texte : la ponctuation isolee (« ? », « ! », « : » apres un espace) n'en est pas un (run 69 : un titre
    de 6 mots comptait 7 avec son « ? » et epuisait les 3 tentatives)."""
    return len(re.findall(r"[\w'’-]+", texte))


TEASER_RE = re.compile(r"\battends[, ]+(la|le|les|l')\s*(formule|phrase|suite|secret|astuce|r[eè]gle|m[eé]thode|solution|r[eé]ponse)"
                       r"|\b(la )?formule (exacte|magique)|\b[ée]coute (bien )?(la suite|ça)|\btu vas voir\b", re.I)


def dessin_texte_problems(scenes: list[dict], data: dict) -> list[str]:
    """Texte du dessin animé : accroche-question, bulle distincte du titre, langage simple, pas de monologue."""
    problems = []
    accroche = str(data.get("accroche_ecran") or "").strip()
    reps = [(r["qui"], r["texte"]) for s_ in scenes if "dessin" in s_ for r in s_["repliques"]]
    if not reps:
        return problems
    premiere = reps[0][1]
    if nb_mots(premiere) > 8:
        problems.append(f"la 1re réplique fait {nb_mots(premiere)} mots : 8 au plus, l'ouverture doit être immédiate")
    if re.search(r"\b(lui|leur|leurs|elle|elles|ils|ça|cela|celui|celle)\b|\bil (?!y a|faut)", premiere.lower()):
        problems.append("la 1re réplique parle de « lui / elle / ça » sans qu'on sache de qui ou de quoi : nomme la personne "
                        "ou la chose (le recruteur, mon CV, cette offre)")
    if nb_mots(accroche) > 6:
        problems.append(f"le titre fait {nb_mots(accroche)} mots : il s'affiche seul une seconde, 6 mots au plus, accrocheur")
    commun = _mots_cles(premiere) & _mots_cles(accroche)
    if len(commun) >= 2:
        problems.append(f"la 1re réplique et le titre à l'écran disent la même chose (mots communs : {', '.join(sorted(commun))}) : "
                        "la bulle fait avancer la scène, le titre pose la question")
    if any(re.search(r"reste pour|rester jusqu|attends la suite|[ée]coute (bien )?la suite|jusqu'à la fin|dans cette vid[ée]o|abonne|like|commente", t, re.I) for _, t in reps):
        problems.append("une réplique s'adresse au public (« reste pour… », « attends la suite », « abonne-toi ») : "
                        "les personnages parlent entre eux, l'appel à l'action est réservé à la dernière scène")
    if any(TEASER_RE.search(t) for _, t in reps):
        problems.append("une réplique ANNONCE ce qu'elle va dire (« attends la formule exacte », « tu vas voir ») au lieu de le dire : "
                        "le personnage qui sait donne la phrase exacte tout de suite")
    if not any("«" in t and "»" in t for _, t in reps):
        problems.append("aucune phrase exacte entre « guillemets français » : un personnage dit à l'autre quoi dire ou écrire, mot pour mot")
    if not (accroche.endswith("?") or "?" in premiere):
        problems.append("l'accroche doit être une QUESTION : soit le titre à l'écran (accroche_ecran), soit la 1re réplique "
                        "posée par un personnage dans la situation")
    if difflib.SequenceMatcher(None, catalog._norm(premiere), catalog._norm(accroche)).ratio() >= 0.6:
        problems.append("la 1re réplique répète le titre à l'écran : la bulle est une vraie phrase de la scène, "
                        "le titre est affiché à part")
    if NOMBRE_ANNONCE.search(accroche):
        problems.append(f"nombre annoncé dans le titre (« {accroche} ») : dis ce qu'on va apprendre, sans compter "
                        "(« 2 questions », « 3 conseils »…)")
    if any(re.search(r"\br[èe]gle (du|des|de la|de l')\b", t, re.I) for _, t in reps):
        problems.append("une « règle du … » inventée n'est pas comprise : dis simplement quoi faire, avec la phrase exacte")
    suite = 1
    for (q0, _), (q1, _) in zip(reps, reps[1:]):
        suite = suite + 1 if q0 == q1 else 1
        if suite >= 3:
            problems.append(f"{q1} parle 3 fois de suite : alterne les personnages (pas de cours, une conversation)")
            break
    return problems


def dessin_scenes(data: dict) -> tuple[list[dict], list[str]]:
    """
    Format dessin anime -> scenes du scenario :
      {"feature": "", "texte": repliques mises bout a bout, "repliques": [{"qui", "texte"}],
       "dessin": scene jouable par assets/anim/dessin/moteur.js (catalog.clean_scene_dessin)}
    et en dernier la scene CTA, sans "dessin" ({"cta": true, "qui", "texte"} cote IA).
    Le minutage des repliques (bulles, bouches) est pose au montage, sur la voix.
    """
    personnages = catalog.personnages()
    scenes, problems = [], []
    for n, raw in enumerate(data.get("scenes") or [], 1):
        if not isinstance(raw, dict):
            continue
        if raw.get("cta"):
            texte = " ".join(str(raw.get("texte") or "").split())
            # CTA dit par un personnage principal (Lea, Karim) : de preference un qui parle deja (2 voix au plus).
            principaux = [q for q, p in personnages.items() if p.get("role", "principal") == "principal"]
            parlent = [r["qui"] for sc_ in scenes for r in sc_["repliques"] if r["qui"] in principaux]
            qui = raw.get("qui") if raw.get("qui") in principaux else (parlent or principaux)[0]
            if texte:
                scenes.append({"feature": "", "texte": texte, "repliques": [{"qui": qui, "texte": texte}]})
            continue
        sc = {k: raw[k] for k in ("fond", "titre", "ellipse", "objets", "actions") if raw.get(k) is not None}
        if not scenes:
            sc.pop("titre", None)  # scene 1 : l'accroche s'affiche deja en haut
            sc.pop("ellipse", None)
        clean, errors = catalog.clean_scene_dessin(sc, n)
        problems += errors
        actions, repliques = [], []
        for a in clean["actions"]:
            a = {k: v for k, v in a.items() if k not in ("t", "duree") or a.get("action") != "parler"}
            if a.get("action") == "parler":
                a["texte"] = " ".join(str(a.get("texte") or "").split())
                if not a["texte"]:
                    continue
                if a["qui"] not in personnages:
                    problems.append(f"scène {n} : « {a['qui']} » ne parle pas (seuls {', '.join(personnages)} parlent)")
                    continue
                if len(a["texte"].split()) > REPLIQUE_MAX_WORDS:
                    problems.append(f"scène {n} : réplique trop longue pour une bulle ({len(a['texte'].split())} mots, "
                                    f"{REPLIQUE_MAX_WORDS} max) : « {a['texte'][:40]}… »")
                repliques.append({"qui": a["qui"], "texte": a["texte"]})
            actions.append(a)
        clean["actions"] = actions
        if not repliques:
            problems.append(f"scène {n} : aucune réplique (action parler avec un texte)")
            continue
        scenes.append({"feature": "", "texte": " ".join(r["texte"] for r in repliques),
                       "repliques": repliques, "dessin": clean})
    scenes = fusionner_meme_lieu(scenes)
    if scenes and "dessin" in scenes[0]:
        for a in scenes[0]["dessin"]["actions"]:
            if a.get("action") == "imaginer":
                problems.append("scène 1 : pas de « imaginer » (le nuage cacherait l'accroche)")
                break
    if any(re.search(r"opus\s?cv", r["texte"], re.I) for s_ in scenes if "dessin" in s_ for r in s_["repliques"]):
        problems.append("« OpusCV » dans une réplique de l'histoire : le dessin animé donne un conseil emploi, "
                        "le produit n'est cité que dans l'appel à l'action final")
    for s_ in scenes:
        if any(re.search(r"\bPOV\b", r["texte"]) for r in s_["repliques"]):
            problems.append("« POV » dans une réplique : ça ne se dit pas dans un dialogue, reformule (« Imagine… », « Toi, tu… »)")
            break
    originaux = sum(1 for s_ in scenes if "dessin" in s_ for a in s_["dessin"]["actions"]
                    if a.get("action") == "comparer" or (a.get("action") == "camera" and (a.get("lent") or a.get("cadre") in ("dessous", "epaule"))))
    if any("dessin" in s_ for s_ in scenes) and not originaux:
        problems.append('aucun plan original : ajoute un cadre caméra "dessous" ou "epaule", un travelling "lent": true, '
                        'ou un split-screen (objet "diptyque" + action "comparer")')
    mises_en_scene = sum(1 for s_ in scenes if "dessin" in s_ for a in s_["dessin"]["actions"]
                         if a.get("action") in ACTIONS_MISE_EN_SCENE)
    if any("dessin" in s_ for s_ in scenes) and not mises_en_scene:
        problems.append("aucun plan qui MONTRE : ajoute au moins un gros plan caméra, un CV corrigé à l'écran (corriger), "
                        "un e-mail / une notification (afficher, notifier), un tampon ou un nuage de pensée (imaginer)")
    if scenes and "dessin" in scenes[-1]:
        problems.append('la dernière scène doit être l\'appel à l\'action : {"cta": true, "qui": "...", "texte": "..."}')
    if scenes and "dessin" not in scenes[0]:
        problems.append("la scène 1 doit être une scène dessinée (l'accroche dite par un personnage)")
    parleurs = list(dict.fromkeys(r["qui"] for s in scenes for r in s["repliques"]))
    if len(parleurs) > 2:
        problems.append(f"{len(parleurs)} personnages parlent ({', '.join(parleurs)}) : 2 au plus")
    if scenes and len(scenes[0]["repliques"][0]["texte"].split()) > 12:
        problems.append("l'accroche (1re réplique) dépasse 12 mots")
    if scenes and "%" in scenes[0]["repliques"][0]["texte"]:
        problems.append("l'accroche (1re réplique) contient un pourcentage : pas de statistique inventée")
    dessinees = [s for s in scenes if "dessin" in s]
    muettes = [i + 1 for i, s in enumerate(scenes) if "dessin" in s
               and not any(a.get("action") not in ACTIONS_PAROLE for a in s["dessin"]["actions"])]
    if muettes:
        problems.append(f"scène(s) {', '.join(map(str, muettes))} sans action visible (que des paroles) : "
                        "ajoute une action (entrer, s'asseoir, poser, vibrer, taper, miauler...)")
    bruits = sum(1 for s in dessinees for a in s["dessin"]["actions"]
                 if a.get("action") in ACTIONS_BRUITEES or a.get("geste") == "idee")
    if dessinees and bruits < MIN_BRUITAGES:
        problems.append(f"{bruits} action(s) qui s'entendent, il en faut au moins {MIN_BRUITAGES} "
                        f"({', '.join(ACTIONS_BRUITEES)})")
    return scenes, problems


def relecture_dessin(client, data: dict, scenes: list[dict]) -> list[str]:
    """
    Relecture du dessin anime par un second appel : un lecteur qui ne connait QUE le titre et les repliques (et ce qui
    est dessine) raconte l'histoire puis dit ce qui ne se comprend pas. Run 67 : roles qui s'inversent sans
    explication, chute illisible, « vingt technos » dit devant un CV qui en liste dix. Echec de l'appel : aucun probleme
    (la relecture ne bloque jamais la generation).
    """
    reps, dessin = [], []
    for sc in scenes:
        reps += [f"{r['qui']} : {r['texte']}" for r in sc.get("repliques", [])]
        d = sc.get("dessin")
        if d:
            dessin.append(f"décor {d.get('fond', 'vide')} ; objets : {', '.join(o['type'] for o in d.get('objets', []))}")
            dessin += [f"texte barré / corrigé à l'écran : « {a.get('avant', '')} » devient « {a.get('apres', '')} »"
                       for a in d.get("actions", []) if a.get("action") == "corriger"]
    prompt = f"""Tu relis le scénario d'un mini dessin animé de 25 secondes (conseil emploi / recrutement, deux personnages,
Karim et Léa) AVANT tournage. Tu es un spectateur qui ne connaît QUE ce qui suit, rien d'autre.

TITRE affiché seul une seconde : « {data.get('accroche_ecran', '')} »
RÉPLIQUES, dans l'ordre :
{chr(10).join(reps)}
CE QUI EST DESSINÉ : {' | '.join(dessin) or 'rien de précis'}

Travail :
1. Raconte l'histoire en deux phrases, comme si tu la découvrais (qui est qui, ce qui se passe, la chute).
2. Cherche tout ce qui ne se comprend pas du premier coup : un personnage dont on ne sait pas s'il est le recruteur ou le
   candidat, un changement de rôle sans explication, une réplique qui ne répond pas à la précédente, une chute qu'il faut
   deviner ou qui n'est pas drôle, un nombre dit qui ne correspond pas à ce qui est dessiné, un conseil flou ou faux.
3. Verdict sévère : "comprehensible" est false si l'un de ces défauts gêne la compréhension d'un spectateur pressé.

Réponds en JSON : {{"histoire": "...", "comprehensible": true|false, "problemes": ["défaut précis et comment le corriger", ...]}}"""
    try:
        verdict = _gemini_json(client, prompt, 0.2)
    except Exception as e:  # noqa: BLE001 -- facultatif : jamais bloquant
        print(f"    relecture ignorée ({e})")
        return []
    problemes = [str(x).strip() for x in verdict.get("problemes") or [] if str(x).strip()]
    if verdict.get("comprehensible") is False or problemes:
        print(f"    relecture : {verdict.get('histoire', '')}")
        return ["relecture : " + " ; ".join(problemes or ["histoire pas comprise du premier coup"])
                + " -- réécris l'histoire pour qu'elle se comprenne seule"]
    return []


def documentaire_scenes(data: dict) -> tuple[list[dict], list[str]]:
    """Scenes du documentaire : chacune (sauf la derniere, CTA) porte un plan "carte" de type documentaire."""
    problems, scenes = [], []
    brut = [r for r in data.get("scenes") or [] if isinstance(r, dict) and str(r.get("texte") or "").strip()]
    for i, raw in enumerate(brut):
        scene = {"feature": "", "texte": " ".join(str(raw["texte"]).split())}
        if i < len(brut) - 1:
            card = clean_card_documentaire(raw["carte"]) if isinstance(raw.get("carte"), dict) else None
            if card:
                scene["carte"] = card
            else:
                problems.append(f"scène {i + 1} : plan de documentaire manquant ou sans animal valide (carte de type documentaire)")
        scenes.append(scene)
    return scenes, problems


def documentaire_texte_problems(scenes: list[dict], data: dict) -> list[str]:
    """Texte et plans du documentaire : titre court, conseil avec phrase exacte, voix off sobre, plans varies."""
    problems = []
    if not scenes:
        return problems
    accroche = str(data.get("accroche_ecran") or "").strip()
    if nb_mots(accroche) > 6:
        problems.append(f"le titre fait {nb_mots(accroche)} mots : il s'affiche seul une seconde, 6 mots au plus, accrocheur")
    if NOMBRE_ANNONCE.search(accroche):
        problems.append(f"nombre annoncé dans le titre (« {accroche} ») : dis ce qu'on va apprendre, sans compter")
    corps = scenes[:-1]
    texte = " ".join(sc["texte"] for sc in corps)
    if not any("«" in sc["texte"] and "»" in sc["texte"] for sc in corps):
        problems.append("aucune phrase exacte entre « guillemets français » : la voix off donne mot pour mot ce qu'il faut dire ou écrire")
    if TEASER_RE.search(texte):
        problems.append("la voix off ANNONCE ce qu'elle va dire (« attends la suite », « tu vas voir ») au lieu de le dire : donne le conseil tout de suite")
    if re.search(r"abonne|\blike\b|commente|dans cette vid[ée]o|lien en bio", texte, re.I):
        problems.append("le texte s'adresse au public (« abonne-toi », « lien en bio ») : réservé à la scène finale")
    if re.search(r"opus\s?cv", texte, re.I):
        problems.append("OpusCV est cité avant l'appel à l'action : le documentaire donne un conseil, le produit n'apparaît qu'à la fin")
    if re.search(r"\br[èe]gle (du|des|de la|de l')\b", texte, re.I):
        problems.append("une « règle du … » inventée n'est pas comprise : dis simplement quoi faire, avec la phrase exacte")
    long = [ph for ph in re.split(r"(?<=[.!?…])\s+", texte) if nb_mots(ph) > 24]
    if long:
        problems.append(f"phrase de voix off trop longue ({nb_mots(long[0])} mots) : 18 mots au plus, une idée par phrase")
    plans = [sc["carte"] for sc in corps if sc.get("carte")]
    if plans and not plans[0].get("legende"):
        problems.append("le plan 1 n'a pas de légende (titre + faux nom latin + détail) : elle présente l'espèce observée")
    for a, b in zip(plans, plans[1:]):
        if (a["habitat"], a["moment"], a["cadre"]) == (b["habitat"], b["moment"], b["cadre"]):
            problems.append("deux plans de suite identiques (même habitat, même moment, même cadre) : varie au moins un des trois")
            break
    if len({p_["habitat"] for p_ in plans}) < 2 and len(plans) >= 3:
        problems.append("tous les plans ont le même habitat : change de lieu au moins une fois")
    if len({s_["espece"] for p_ in plans for s_ in p_["sujets"]}) < 2 and len(plans) >= 3:
        problems.append("un seul animal dans tout le reel : en montrer au moins deux (le candidat et ce qui l'entoure)")
    return problems


def relecture_documentaire(client, data: dict, scenes: list[dict]) -> list[str]:
    """
    Relecture du documentaire par un second appel : un spectateur qui ne connait QUE le titre, la voix off et
    ce qui est montre raconte l'histoire puis dit ce qui ne se comprend pas. Echec de l'appel : aucun probleme.
    """
    lignes = []
    for i, sc in enumerate(scenes, 1):
        plan = sc.get("carte")
        if plan:
            vus = ", ".join(f"{x['espece']}" + (f" x{x['nombre']}" if x.get("nombre") else "") for x in plan["sujets"])
            leg = plan.get("legende") or {}
            lignes.append(f"PLAN {i} ({plan['habitat']}, {plan['moment']}) montre : {vus}"
                          + (f" ; légende : {leg.get('titre', '')} / {leg.get('latin', '')} / {leg.get('detail', '')}" if leg else ""))
        lignes.append(f"VOIX OFF {i} : {sc['texte']}")
    prompt = f"""Tu relis le scénario d'un faux documentaire animalier de 25 secondes (conseil emploi / recrutement) AVANT tournage. Tu es
un spectateur qui ne connaît QUE ce qui suit, rien d'autre.

TITRE affiché seul une seconde : « {data.get('accroche_ecran', '')} »
{chr(10).join(lignes)}

Travail :
1. Raconte le documentaire en deux phrases, comme si tu le découvrais (qui est observé, quel est le problème, quel est le conseil).
2. Cherche tout ce qui ne se comprend pas du premier coup : on ne sait pas de qui ou de quoi on parle, la métaphore animale est
   arbitraire (l'animal montré n'a aucun rapport avec la phrase), un plan qui ne correspond pas à la voix off, un conseil flou ou faux,
   une phrase exacte absente ou inutilisable, une chute qui est un slogan, un enchaînement qui saute une étape.
3. Verdict sévère : "comprehensible" est false si l'un de ces défauts gêne un spectateur pressé.

Réponds en JSON : {{"histoire": "...", "comprehensible": true|false, "problemes": ["défaut précis et comment le corriger", ...]}}"""
    try:
        verdict = _gemini_json(client, prompt, 0.2)
    except Exception as e:  # noqa: BLE001 -- facultatif : jamais bloquant
        print(f"    relecture ignorée ({e})")
        return []
    problemes = [str(x).strip() for x in verdict.get("problemes") or [] if str(x).strip()]
    if verdict.get("comprehensible") is False or problemes:
        print(f"    relecture : {verdict.get('histoire', '')}")
        return ["relecture : " + " ; ".join(problemes or ["documentaire pas compris du premier coup"])
                + " -- réécris pour qu'il se comprenne seul"]
    return []


def fusionner_meme_lieu(scenes: list[dict]) -> list[dict]:
    """
    Deux scenes dessinees de suite dans le meme decor, sans ellipse (meme lieu, meme moment) : une seule
    scene, le titre de la seconde oublie (run 61 : « Deux minutes apres » dans le meme salon). Changer de scene sans changer de lieu ni de moment coupait l'action pour rien
    (nouveau trace du decor, fondu). Les objets de la seconde absents de la premiere s'y ajoutent.
    """
    out = []
    for sc in scenes:
        prev = out[-1] if out else None
        d, dp = sc.get("dessin"), prev.get("dessin") if prev else None
        if d and dp and d.get("fond", "vide") == dp.get("fond", "vide") and not d.get("ellipse"):
            ids = {o["id"] for o in dp["objets"]}
            dp["objets"] += [o for o in d["objets"] if o["id"] not in ids]
            dp["actions"] += d["actions"]
            prev["repliques"] += sc["repliques"]
            prev["texte"] = " ".join(r["texte"] for r in prev["repliques"])
            continue
        out.append(sc)
    return out


def generate_scenario(client, plan: dict, duration: int, recent_hooks: list[str],
                      forced: list[dict] | None = None) -> dict:
    fmt = plan["format"]
    if not plan.get("cta"):  # meme phrase pour le prompt et pour fixer_cta
        plan["cta"] = catalog.pick_cta(fmt["categorie"], random.Random())[0]
    feedback = None
    best: list[dict] = []
    best_data: dict = {}
    best_problems: list[str] | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = _gemini_json(client, build_prompt(plan, duration, forced, feedback, recent_hooks), 0.9)
        except json.JSONDecodeError:
            feedback = "ta réponse n'était pas du JSON valide"
            continue
        sans_captures = bool(plan.get("sans_captures"))
        scenes, problems = validate(data, duration, forced, fmt["cartes"], recent_hooks,
                                    wants_proof(fmt) and not sans_captures and not fmt.get("dessin"),
                                    catalog.tone_for(fmt, plan.get("registre")), sans_captures, bool(fmt.get("dessin")),
                                    bool(fmt.get("documentaire")))
        if scenes and not problems and fmt.get("dessin"):
            problems = relecture_dessin(client, data, scenes)
        elif scenes and not problems and fmt.get("documentaire"):
            problems = relecture_documentaire(client, data, scenes)
        if scenes:
            # Garde la tentative la plus propre (pas forcement la derniere) si aucune n'est parfaite.
            if best_problems is None or len(problems) <= len(best_problems):
                best, best_data, best_problems = scenes, data, problems
        if not problems:
            break
        feedback = " ; ".join(problems)
        print(f"    tentative {attempt} à corriger : {feedback}")

    if not best:
        raise RuntimeError(f"Scénario inexploitable après {MAX_ATTEMPTS} tentatives (sujet : {plan['sujet']['texte']})")
    if plan.get("sans_captures") and not catalog.sans_capture_seul(fmt):
        for scene in best[1:-1]:
            scene.setdefault("carte", fallback_card(scene["texte"]))
    if cta_enregistre() and not forced:
        fixer_cta(best, plan["cta"])
    dessin_fields = {}
    if fmt.get("dessin"):
        completer_mise_en_scene(best)
        # Une voix par personnage qui parle (2_generate_voice.py, un seul appel multi-locuteurs).
        parleurs = dict.fromkeys(r["qui"] for s in best for r in s.get("repliques", []))
        dessin_fields = {"dessin": True,
                         "voix_personnages": {q: catalog.personnages()[q]["voix"] for q in list(parleurs)[:2]}}
    hashtags = best_data.get("hashtags") or []
    return finalize({
        "angle": plan["sujet"]["texte"], "titre": best_data.get("titre", ""), "duree_cible_s": duration,
        "scenes": best,
        "accroche_ecran": str(best_data.get("accroche_ecran") or "").strip(),
        "legende": str(best_data.get("legende") or "").strip(),
        "hashtags": [str(h).strip() for h in hashtags if str(h).strip()] if isinstance(hashtags, list) else [],
        "mots_cles": [str(k).strip() for k in best_data.get("mots_cles") or [] if str(k).strip()][:6]
        if isinstance(best_data.get("mots_cles"), list) else [],
        "offre_emploi": str(best_data.get("offre_emploi") or "").strip(),
        "theme_style": str(best_data.get("theme_style") or "").strip(),
        **({"resume_episode": " ".join(str(best_data.get("resume_episode") or "").split()[:30])}
           if fmt.get("dessin") and best_data.get("resume_episode") else {}),
        **instagram_fields(best_data),
        **plan_fields(plan),
        **dessin_fields,
    })


def fallback_card(texte: str) -> dict:
    """Carte texte de secours (sans capture, l'IA n'en a pas donne) : la 1re phrase, 9 mots au plus."""
    phrase = re.split(r"(?<=[.!?…])\s+", texte.strip())[0]
    words = phrase.split()
    titre = " ".join(words[:9]) + ("…" if len(words) > 9 else "")
    return {"type": "texte", "surtitre": "", "titre": titre.rstrip(".") if len(words) <= 9 else titre,
            "texte": "", "style": "normal", "effet": "standard"}


def _hashtags(raw, limit: int | None = None) -> list[str]:
    tags = []
    for h in raw if isinstance(raw, list) else []:
        tag = "#" + str(h).strip().lstrip("#").replace(" ", "")
        if len(tag) > 1 and tag.lower() not in [t.lower() for t in tags]:
            tags.append(tag)
    return tags[:limit] if limit else tags


def clean_carrousel(raw) -> list[dict]:
    """Diapositives du carrousel Instagram {titre, texte} ; moins de CARROUSEL_MIN -> [] (derive au rendu)."""
    slides = [{"titre": str(d.get("titre") or "").strip(), "texte": str(d.get("texte") or "").strip()}
              for d in raw or [] if isinstance(d, dict) and str(d.get("titre") or "").strip()]
    return slides[:CARROUSEL_MAX] if len(slides) >= CARROUSEL_MIN else []


def instagram_fields(data: dict) -> dict:
    """Textes Instagram du scenario (legende, hashtags limites par config.json, carrousel)."""
    limit = (catalog.config().get("instagram") or {}).get("hashtags_max", 5)
    return {"legende_instagram": str(data.get("legende_instagram") or "").strip(),
            "hashtags_instagram": _hashtags(data.get("hashtags_instagram"), limit),
            "carrousel": clean_carrousel(data.get("carrousel"))}


def plan_fields(plan: dict) -> dict:
    return {"format": plan["format"]["id"], "categorie": plan["format"]["categorie"],
            "sujet": plan["sujet"]["id"], "famille": plan["sujet"].get("famille"),
            "hook": plan["hook"]["id"], "theme": plan["theme"]["id"],
            "episode": plan["episode"], "voix": plan["voix"]["id"],
            "registre": plan.get("registre") or "serieux",
            "ton": catalog.tone_for(plan["format"], plan.get("registre")),
            "cta_anim": plan.get("cta_anim") or {},
            "ambiance": plan.get("ambiance"),
            **({"trame": plan["trame"]["id"]} if plan.get("trame") else {}),
            **({"serie_titre": (catalog.dessins().get("serie") or {}).get("titre")}
               if plan["format"].get("dessin") and plan.get("episode") else {}),
            **({"sans_captures": True} if plan.get("sans_captures") else {}),
            **({"documentaire": True} if plan["format"].get("documentaire") else {}),
            **({"titre_seul": True} if catalog.sans_capture_seul(plan["format"]) else {}),
            **({"habillage": plan["format"]["habillage"], "habillage_params": plan["format"].get("habillage_params", {})}
               if plan["format"].get("habillage") else {})}


def finalize(scenario: dict) -> dict:
    """Ajoute les champs derives : liste des features a capturer, estimation de duree."""
    seen = []
    for scene in scenario["scenes"]:
        if scene["feature"] and scene["feature"] not in seen:
            seen.append(scene["feature"])
    scenario["features"] = seen
    words = sum(len(s["texte"].split()) for s in scenario["scenes"])
    scenario["duree_estimee_s"] = round(words / WORDS_PER_SECOND, 1)
    # Absents (scenario impose sans appel IA, ou champ vide renvoye) : la
    # demo retombe alors sur les valeurs par defaut cote features.py.
    for key in ("offre_emploi", "theme_style", "accroche_ecran", "legende", "legende_instagram"):
        scenario.setdefault(key, "")
    scenario.setdefault("hashtags", [])
    scenario.setdefault("hashtags_instagram", [])
    scenario.setdefault("carrousel", [])
    scenario.setdefault("mots_cles", [])
    return scenario


def load_scenario_file(path: Path, default_duration: int, sans_captures: bool = False) -> list[dict]:
    """
    Scenarios ecrits a la main : chaque scene doit nommer une feature du
    catalogue ; le texte est optionnel (l'IA completera). Champs optionnels
    repris tels quels : format, theme, hook, registre, accroche_ecran, legende,
    hashtags, legende_instagram, hashtags_instagram, carrousel ; par scene : carte, anim, overlay, annotation (post-it au feutre),
    preuve.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else [raw]
    scenarios = []
    for n, item in enumerate(items, 1):
        scenes = []
        for s in item.get("scenes") or []:
            fid = normalize_feature_id(s.get("feature"))
            if fid is None and sans_captures:
                fid = ""  # sans capture : la scene sans carte devient un plan illustre
            elif fid is None:
                raise ValueError(f"{path} scenario {n} : feature inconnue ou non autorisee '{s.get('feature')}' "
                                 f"(liste : python scripts/features.py)")
            scene = {"feature": fid, "texte": str(s.get("texte") or "").strip(),
                     **{k: s[k] for k in ANIM_KEYS if s.get(k)}}
            card = clean_card(s.get("carte"))
            if card:
                scene["carte"] = card
            if str(s.get("annotation") or "").strip() and not card:
                scene["annotation"] = " ".join(str(s["annotation"]).split()[:ANNOTATION_MAX_WORDS])
            if s.get("preuve") is True and not card:
                scene["preuve"] = True
            if str(s.get("illustration") or "") in catalog.icons():
                scene["illustration"] = s["illustration"]
            scenes.append(scene)
        if not scenes:
            raise ValueError(f"{path} scenario {n} : aucune scene")
        scenarios.append({
            "angle": item.get("angle", "scenario impose"),
            "titre": item.get("titre", ""),
            "duree_cible_s": int(item.get("duree_cible_s") or default_duration),
            "scenes": scenes,
            **{k: item[k] for k in ("format", "theme", "hook", "registre", "accroche_ecran", "legende", "hashtags",
                                    "mots_cles", "legende_instagram", "hashtags_instagram")
               if item.get(k)},
            **({"carrousel": clean_carrousel(item["carrousel"])} if item.get("carrousel") else {}),
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
    parser.add_argument("--duration", type=int, default=25, help="Duree cible de chaque reel, en secondes")
    parser.add_argument("--angle", type=str, default=None,
                         help="Sujet libre impose (format demo_produit sauf --format) ; sinon catalog/sujets.json")
    parser.add_argument("--format", type=str, default=None, help="Format impose (catalog/formats.json)")
    parser.add_argument("--theme", type=str, default=None, help="Theme visuel impose (catalog/themes.json)")
    parser.add_argument("--hook", type=str, default=None, help="Style d'accroche impose (catalog/hooks.json)")
    parser.add_argument("--registre", type=str, default=None, choices=catalog.REGISTRES,
                         help="Registre impose (serieux / humour) ; sinon mix de catalog/config.json 'registres'")
    parser.add_argument("--sans-captures", action="store_true",
                         help="Aucune capture de l'app (run_pipeline --capture-mode aucune) : formats conseil, "
                              "toutes les scenes en cartes animees")
    parser.add_argument("--plan", type=str, default=None,
                        help="Combinaison imposee reel par reel : JSON (liste d'objets format/sujet/hook/theme/"
                             "voix/registre/ambiance/angle, vide = automatique) ; remplace --n")
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
    if args.sans_captures and args.format and not catalog.sans_captures_ok(catalog.get_format(args.format)):
        parser.error(f"format '{args.format}' impossible sans captures (formats conseil avec cartes uniquement)")
    overrides = None
    if args.plan:
        try:
            overrides = json.loads(args.plan)
        except json.JSONDecodeError as e:
            parser.error(f"--plan : JSON invalide ({e})")
        errors = catalog.validate_plan(overrides, args.sans_captures)
        if errors:
            parser.error("--plan : " + " ; ".join(errors))
        args.n = len(overrides)

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if len(existing) >= args.n and not args.scenario and not args.plan:
            print(f"REPRISE: {out_path} existe deja avec {len(existing)} scenario(s), on saute (--force pour regenerer)")
            return

    charger_vitesse(out_path.parent / "vitesse_voix.json")
    history_path = out_path.parent / "content_history.json"
    history = catalog.load_history(history_path)
    rng = random.Random(args.seed)
    recent_hooks = catalog.recent_accroches(history)

    client = None
    scenarios = []
    if args.scenario:
        for i, item in enumerate(load_scenario_file(Path(args.scenario), args.duration, args.sans_captures), 1):
            plan = plan_reels(None, 1, history, rng,
                              item.get("format") or args.format or ("liste_erreurs" if args.sans_captures else "demo_produit"),
                              item.get("theme") or args.theme, item.get("hook") or args.hook, item["angle"],
                              item.get("registre") or args.registre, args.sans_captures)[0]
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
                                            args.hook, args.angle, args.registre, args.sans_captures,
                                            overrides), 1):
            print(f"[{i}/{args.n}] {args.duration}s | {plan['registre']} | format {plan['format']['id']} "
                  f"| accroche {plan['hook']['id']} "
                  f"| theme {plan['theme']['id']} | sujet : {plan['sujet']['texte']}")
            scenario = generate_scenario(client, plan, args.duration, recent_hooks)
            recent_hooks = recent_hooks + [scenario["accroche_ecran"], scenario["scenes"][0]["texte"]]
            scenarios.append(scenario)

    for i, s in enumerate(scenarios, 1):
        print(f"  reel {i} : [{s.get('format')}/{s.get('theme')}] {len(s['scenes'])} scenes, ~{s['duree_estimee_s']}s "
              f"-> " + " | ".join(("carte:" + sc["carte"].get("type", "texte") if "carte" in sc
                                   else sc["feature"] or "illustration:" + sc.get("illustration", "cv"))
                                  for sc in s["scenes"]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    # Historique : ce qui a ete genere nourrit l'anti-redondance des prochains runs.
    catalog.save_history(history_path, history + [
        {"format": s.get("format"), "categorie": s.get("categorie"), "sujet": s.get("sujet"), "famille": s.get("famille"),
         "hook": s.get("hook"), "theme": s.get("theme"), "voix": s.get("voix"), "ambiance": s.get("ambiance"),
         "registre": s.get("registre"), "titre": s.get("titre"), "trame": s.get("trame"),
         "resume": s.get("resume_episode"),
         "fonds": [sc["dessin"].get("fond") for sc in s.get("scenes", []) if sc.get("dessin")],
         "accroche": s.get("accroche_ecran") or (s["scenes"][0]["texte"] if s["scenes"] else "")}
        for s in scenarios])
    print(f"OK -> {out_path} ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
