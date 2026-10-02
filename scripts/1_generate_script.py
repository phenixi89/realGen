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
MAX_ATTEMPTS = 3
ACCROCHE_MAX_WORDS = 8
ANIM_KEYS = ("anim", "overlay")
# Annotations au feutre sur les captures (assets/anim/annotation.html).
ANNOTATION_MAX_WORDS = 6
MAX_ANNOTATIONS = 2
# Carrousel Instagram : diapositives ecrites par l'IA (hors diapositive finale, ajoutee au rendu).
CARROUSEL_MIN, CARROUSEL_MAX = 4, 8
# Sans aucun de ces caracteres sur tout un script, le texte a ete ecrit sans
# accents : les sous-titres (texte exact du script) seraient faux.
ACCENT_RE = re.compile(r"[éèêëàâùûüîïôçœÉÈÊÀÂÙÛÎÔÇ]")
MIN_WORDS_ACCENT_CHECK = 12


def words_per_second(tone: str = "") -> float:
    """Un ton "rapide" fait parler le TTS nettement plus vite (mesure : ~3.3 mots/s)."""
    return FAST_WORDS_PER_SECOND if re.search(r"rapide|haletant", tone or "", re.I) else WORDS_PER_SECOND


def word_budget(duration: int, tone: str = "") -> tuple[int, int, int]:
    target = round(duration * words_per_second(tone))
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
                  and (not sans_captures or catalog.sans_captures_ok(f))]
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
        hook = catalog.get_hook(hid) if hid else catalog.pick_hook(working, rng, registre)
        theme = catalog.get_theme(tid) if tid else catalog.pick_theme(working, rng, registre)
        voice = catalog.get_voice(ov["voix"]) if ov.get("voix") else catalog.pick_voice(working, rng)
        cta, cta_anim = catalog.pick_cta(fmt["categorie"], rng)
        ambiance = ov.get("ambiance") or catalog.pick_ambiance(theme, working, rng)
        plan = {"format": fmt, "sujet": sujet, "hook": hook, "theme": theme, "voix": voice, "registre": registre,
                "cta": cta, "cta_anim": cta_anim, "ambiance": ambiance,
                "episode": catalog.series_episode(working, fmt["id"]) if fmt.get("serie") else None,
                "sans_captures": sans_captures}
        plans.append(plan)
        working.append({"format": fmt["id"], "categorie": fmt["categorie"], "sujet": sujet["id"],
                        "famille": sujet.get("famille"),
                        "hook": hook["id"], "theme": theme["id"], "voix": voice["id"], "ambiance": ambiance,
                        "registre": registre})
    return plans


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

def build_prompt(plan: dict, duration: int, forced: list[dict] | None, feedback: str | None,
                 recent_hooks: list[str]) -> str:
    fmt, hook = plan["format"], plan["hook"]
    humour = plan.get("registre") == "humour"
    catalog_features = "\n".join(f'- "{fid}" : {f.description}' for fid, f in available_features().items())
    target, lo_w, hi_w = word_budget(duration, catalog.tone_for(fmt, plan.get("registre")))
    lo_s, hi_s = scene_bounds(duration)
    cta = plan.get("cta") or catalog.pick_cta(fmt["categorie"], random.Random())[0]
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
    if sans_captures:
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
""" if wants_save_nudge(fmt, humour) else "")
    prompt = f"""Tu es un expert en création de contenu viral (TikTok, Instagram Reels, YouTube Shorts), spécialisé dans
l'emploi, le recrutement et la recherche de CV. Tes vidéos promeuvent OpusCV avec un ton direct, captivant et
axé sur les frustrations réelles des candidats : l'idée est d'avoir une accroche très forte.
Base-toi UNIQUEMENT sur ces informations produit réelles, n'invente aucune fonctionnalité :

{PRODUCT_CONTEXT}

Tu écris le SCÉNARIO d'un reel vertical de {duration} secondes, en français.

FORMAT : {fmt['nom']} ({intent}).
Structure attendue : {structure}
{registre_rule}
SUJET : {plan['sujet']['texte']}

ACCROCHE (scène 1, décisive pour la rétention) : style « {hook['id']} » — {hook['consigne']}
Exemple de ton (ne pas recopier) : « {hook['exemple']} »
Règles strictes de l'accroche (0-3 s) : 2e personne du singulier (« tu », « ton », « tes ») ; elle déclenche
une émotion forte (peur de l'échec, curiosité, gain de temps, injustice du recrutement) ; elle intègre un
chiffre précis quand c'est possible, mais UNIQUEMENT un chiffre concret ou vérifiable (une durée,
un nombre de lignes, de boîtes, d'étapes : 6 secondes, 30 secondes, 3 lignes, 50 boîtes) ; JAMAIS de
statistique ni de pourcentage inventé (« 80 % des candidats », « 4 candidats sur 5 »…).
Corps (3-20 s) : expose vite le problème précis, puis la solution concrète apportée par OpusCV (montrée à
l'écran) ; rythme rapide, phrases courtes, zéro blabla.
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
- scène 1 = l'accroche (12 mots max){scene1_rule} ; dernière scène = CTA court, dans l'esprit : « {cta} » ;
- 1 à 2 phrases par scène, ton oral et naturel, tutoiement, pas publicitaire{"" if not humour else ", drôle"} ;
- {variety_rule}
- français impeccable AVEC TOUS LES ACCENTS (é, è, à, ç, ê...) et la ponctuation : le texte est
  affiché tel quel en sous-titres ;
- pas d'emoji, pas de hashtag, pas d'indication de mise en scène dans les textes ;
- ORIGINALITÉ : aucun conseil générique ou évident (interdit : {banned}) ;
  chaque scène apporte un élément concret : un exemple de formulation, une phrase à dire ou à écrire,
  un cas précis ou une astuce actionnable immédiatement ;
- RESTE SUR LE SUJET : {off_topic}
- RYTHME : phrases courtes et percutantes, une idée par scène, aucune phrase de transition creuse ;
- BOUCLE OUVERTE : dès la scène 2, promets une révélation placée plus tard (« et la 3ᵉ erreur est la pire »,
  « reste jusqu'à la fin pour la phrase à copier ») et tiens-la dans les dernières scènes : c'est ce qui
  retient le spectateur au-delà des 3 premières secondes ;
- BOUCLE : la dernière phrase répond ou fait écho à l'accroche, pour que la vidéo s'enchaîne
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

    scene_json = ('{"illustration": "<id d\'icône>", "texte": "..."}, {"texte": "...", "carte": {...}}, ..., {"texte": "..."}]'
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
             tone: str = "", sans_captures: bool = False) -> tuple[list[dict], list[str]]:
    """
    Nettoie le scenario et liste ce qui ne respecte pas les contraintes (pour relancer l'IA).
    sans_captures : pas de feature (""), une carte sur chaque scene sauf la 1re (icone
    "illustration") et la derniere (CTA anime), ni preuve ni annotation.
    """
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
    banned = banned_phrases(" ".join(s["texte"] for s in scenes))
    if banned:
        problems.append("formulations trop génériques à remplacer par du concret : " + ", ".join(banned))

    words = sum(len(s["texte"].split()) for s in scenes)
    _, lo_w, hi_w = word_budget(duration, tone)
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
    if card_mode == "majoritaires" and not sans_captures and scenes and sum("carte" in s for s in scenes) < len(scenes) / 2:
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
        sans_captures = bool(plan.get("sans_captures"))
        scenes, problems = validate(data, duration, forced, fmt["cartes"], recent_hooks,
                                    wants_proof(fmt) and not sans_captures,
                                    catalog.tone_for(fmt, plan.get("registre")), sans_captures)
        if scenes:
            best, best_data = scenes, data
        if not problems:
            break
        feedback = " ; ".join(problems)
        print(f"    tentative {attempt} à corriger : {feedback}")

    if not best:
        raise RuntimeError(f"Scénario inexploitable après {MAX_ATTEMPTS} tentatives (sujet : {plan['sujet']['texte']})")
    if plan.get("sans_captures"):
        for scene in best[1:-1]:
            scene.setdefault("carte", fallback_card(scene["texte"]))
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
        **instagram_fields(best_data),
        **plan_fields(plan),
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
            **({"sans_captures": True} if plan.get("sans_captures") else {}),
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
         "registre": s.get("registre"), "titre": s.get("titre"),
         "accroche": s.get("accroche_ecran") or (s["scenes"][0]["texte"] if s["scenes"] else "")}
        for s in scenarios])
    print(f"OK -> {out_path} ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
