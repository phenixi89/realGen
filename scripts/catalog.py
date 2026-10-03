"""
Catalogue editorial et visuel des reels (dossier catalog/ a la racine) :

    formats.json  structure des videos (liste d'erreurs, mythe/realite, demo...)
    sujets.json   de quoi parle la video (conseil ou produit)
    hooks.json    styles d'accroche des 2 premieres secondes
    themes.json   couleurs, polices, style des sous-titres, ambiance musicale
    audio.json    ambiances musicales et effets sonores (scripts/audio_gen.py)
    voix.json     voix TTS en rotation et ton de lecture par defaut
    config.json   mix conseil/produit, registres serieux/humour, anti-redondance,
                  textes propres a Instagram

Tout s'enrichit en editant ces JSON, sans toucher au code : ce module les
charge, les valide (python catalog.py) et fait les choix "intelligents" --
tirage pondere qui evite ce qui a ete publie recemment (historique persiste
dans output/content_history.json) et respecte le mix conseil/produit cible.
"""
import difflib
import json
import random
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"
FONTS_DIR = ROOT / "assets" / "fonts"
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# Police manuscrite des dessins (cartes schema, annotations) -- OFL, assets/fonts/.
HAND_FONT = "Kalam-Bold.ttf"
# Dessin anime : le titre occupe seul l'ecran cette duree (s), puis la voix et la scene commencent
# (2_generate_voice.py ajoute ce silence en tete, run_pipeline.py affiche le titre pendant ce temps).
TITRE_DESSIN_S = 1.0
DESSIN_SUPPORTS = ("papier", "craie", "neon")
CARD_MODES = ("aucune", "autorisees", "majoritaires")
CARD_STYLES = ("normal", "mythe", "realite", "avant", "apres")
CARD_EFFECTS = ("standard", "frappe", "suspense")
# Type de carte -> gabarit assets/anim/<gabarit>.html
DOC_JS = ROOT / "assets" / "anim" / "documentaire"
CARD_TYPES = {"texte": "carte", "chiffre": "chiffre", "comparaison": "comparaison", "liste": "liste",
              "schema": "schema", "conversation": "conversation", "scan": "scan", "impact": "impact",
              "meme": "meme", "documentaire": "documentaire"}
# Marque dessinee sur la derniere etape d'une carte schema (assets/anim/schema.html).
SCHEMA_MARKS = ("entoure", "barre", "coche")
ICONS_JS = ROOT / "assets" / "anim" / "icones.js"
# Dessin anime "trait blanc" : types dessinables (fonds, personnages, objets) declares
# dans catalog/dessins.json et ecrits dans assets/anim/dessin/*.js.
MURAL_Y = 700          # hauteur par defaut d'un objet mural du dessin anime (px)
DESSIN_JS = ROOT / "assets" / "anim" / "dessin"

# Fenetre sur laquelle on mesure le mix conseil/produit deja publie.
MIX_WINDOW = 10
# Registres d'ecriture : "registres" des formats, accroches et themes ; part
# cible de chacun dans config.json "registres".
REGISTRES = ("serieux", "humour")


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((CATALOG_DIR / f"{name}.json").read_text(encoding="utf-8"))


def config() -> dict:
    return _load("config")


def formats() -> list[dict]:
    return _load("formats")["formats"]


def sujets() -> list[dict]:
    return _load("sujets")["sujets"]


def hooks() -> list[dict]:
    return _load("hooks")["hooks"]


def themes() -> list[dict]:
    return _load("themes")["themes"]


@lru_cache(maxsize=None)
def icons() -> dict[str, dict]:
    """Icones dessinables des cartes schema : assets/anim/icones.js (JSON apres "window.ICONES = ")."""
    text = ICONS_JS.read_text(encoding="utf-8")
    start = re.search(r"^window\.ICONES = ", text, re.M).end()  # en debut de ligne (pas celui du commentaire)
    body = text[start:].strip().removesuffix(";")
    return json.loads(body)


def dessins() -> dict:
    return _load("dessins")


def _types_dessin_js() -> dict[str, set[str]]:
    """Types enregistres dans le code : fonds (fonds.js), personnages (MODELES), objets / animaux."""
    fonds_js = (DESSIN_JS / "fonds.js").read_text(encoding="utf-8")
    perso_js = (DESSIN_JS / "personnages.js").read_text(encoding="utf-8")
    autres = "".join((DESSIN_JS / f).read_text(encoding="utf-8") for f in ("objets.js", "animaux.js"))
    modeles = perso_js[perso_js.index("const MODELES"):perso_js.index("};", perso_js.index("const MODELES"))]
    return {"fonds": set(re.findall(r'\breg\("([a-z_]+)"', fonds_js)),
            "objets": set(re.findall(r'^\s+([a-z_]+): \{ nom:', modeles, re.M))
            | set(re.findall(r'(?:\breg|Dessin\.enregistrer)\("([a-z_]+)"', autres))}


def documentaire() -> dict:
    """Documentaire animalier (catalog/documentaire.json) : habitats, moments, especes, cadres, mouvements."""
    return _load("documentaire")


def _types_documentaire_js() -> dict[str, set[str]]:
    """Ids enregistres dans le code du documentaire : habitats (fonds.js), moments (MOMENTS), especes (especes.js)."""
    fonds_js = (DOC_JS / "fonds.js").read_text(encoding="utf-8")
    esp_js = (DOC_JS / "especes.js").read_text(encoding="utf-8")
    moments = fonds_js[fonds_js.index("Doc.MOMENTS = {"):fonds_js.index("};", fonds_js.index("Doc.MOMENTS = {"))]
    habitats = fonds_js[fonds_js.index("const HAB = {"):fonds_js.index("// Monte le decor")]
    return {"habitats": set(re.findall(r'^    ([a-z_]+)\(L, M, rand\) \{', habitats, re.M)),
            "moments": set(re.findall(r'^    ([a-z_]+): *\{ ciel:', moments, re.M)),
            "especes": set(re.findall(r'\breg\("([a-z_]+)"', esp_js))}


def sans_capture_seul(fmt: dict) -> bool:
    """Format dont tous les plans sont dessines (dessin anime, documentaire) : --capture-mode aucune seulement."""
    return bool(fmt.get("dessin") or fmt.get("documentaire"))


def personnages() -> dict[str, dict]:
    """Personnages du dessin anime (catalog/dessins.json, categorie personnage) : id -> {nom, voix...}."""
    return {o["id"]: o for o in dessins()["objets"] if o.get("categorie") == "personnage"}


def clean_scene_dessin(sc: dict, n: int = 1) -> tuple[dict, list[str]]:
    """
    Une scene du dessin anime -> (scene jouable, problemes). Les objets et actions
    invalides (type, ancre, siege, action, cible inconnus) sont retires, une
    expression ou un geste inconnu est oublie : le moteur ne plante jamais sur
    ce qu'une IA a pu ecrire ; les problemes servent a lui faire corriger.
    """
    cat = dessins()
    fonds_ = {f["id"] for f in cat["fonds"]}
    objets_ = {o["id"]: o for o in cat["objets"]}
    perso = cat["personnage"]
    errors, clean = [], {k: v for k, v in sc.items() if k not in ("objets", "actions")}
    if clean.get("ellipse") is not None:
        mots = str(clean["ellipse"]).split()
        if len(mots) > ELLIPSE_MAX_MOTS:
            errors.append(f"scene {n} : ellipse trop longue ({len(mots)} mots, {ELLIPSE_MAX_MOTS} max)")
        clean["ellipse"] = " ".join(mots[:ELLIPSE_MAX_MOTS])
        if not clean["ellipse"]:
            del clean["ellipse"]
    if sc.get("fond", "vide") not in fonds_:
        errors.append(f"scene {n} : fond inconnu '{sc.get('fond')}' (choix : {sorted(fonds_)})")
        clean["fond"] = "vide"
    ids, objets = {}, []
    for o in _ordre_supports([o for o in sc.get("objets") or [] if isinstance(o, dict)]):
        if not isinstance(o, dict):
            continue
        t = objets_.get(o.get("type"))
        if not t or not o.get("id") or o["id"] in ids:
            errors.append(f"scene {n} : objet '{o.get('id')}' : type inconnu '{o.get('type')}' ou id absent / en double")
            continue
        if o.get("assis") and (o["assis"] not in ids or "assise" not in (ids[o["assis"]].get("ancres") or [])
                               or t["categorie"] != "personnage"):
            errors.append(f"scene {n} : '{o['id']}' assis sur '{o['assis']}' : il faut un personnage et une chaise "
                          "(ou un canape) declares avant lui")
            o = {k: v for k, v in o.items() if k != "assis"}
        if o.get("sur"):
            cible, _, anc = str(o["sur"]).partition(".")
            if cible not in ids or anc not in (ids[cible].get("ancres") or []):
                errors.append(f"scene {n} : '{o['id']}' sur '{o['sur']}' : objet ou ancre inconnus (declarer le support avant)")
                continue
        o = dict(o)
        if t["categorie"] == "objet" and not o.get("sur") and o.get("y") is None:
            # Objet a main (tasse, ordinateur...) pose par terre : sur une table de la scene, sinon retire.
            table = next((i for i, ti in ids.items() if "dessus" in (ti.get("ancres") or [])), None)
            errors.append(f"scene {n} : '{o['id']}' pose par terre : mets-le sur une table (\"sur\": \"table.dessus\") "
                          f"ou dans une main (\"sur\": \"lea.main_avant\")")
            if not table:
                continue
            o = {k: v for k, v in o.items() if k not in ("x", "regard")} | {"sur": f"{table}.dessus"}
        if t.get("mural") and o.get("y") is None and not o.get("sur"):
            o["y"] = MURAL_Y  # sinon pose au sol
        if o.get("x") is not None and not o.get("regard") and not o.get("sur") \
                and (t["categorie"] in ("personnage", "animal") or t["id"] == "chaise"):
            o["regard"] = "droite" if float(o["x"]) < 540 else "gauche"  # tourne vers le centre de la scene
        ids[o["id"]] = t
        objets.append(o)
    for qui in dict.fromkeys(a.get("qui") for a in sc.get("actions") or [] if isinstance(a, dict)):
        t = objets_.get(qui)
        if qui not in ids and t and t["categorie"] == "personnage":
            # Personnage qui joue sans avoir ete declare (oubli frequent de l'IA) : place a l'endroit libre.
            occupes = [float(o["x"]) for o in objets if o.get("x") is not None and not o.get("sur")]
            x = max((250, 820, 540), key=lambda c: min((abs(c - v) for v in occupes), default=1e9))
            o = {"id": qui, "type": qui, "x": x, "regard": "droite" if x < 540 else "gauche"}
            ids[qui] = t
            objets.append(o)
    actions, tenus = [], {}   # tenus : personnage -> objet en main
    for o in objets:
        if o.get("sur") and str(o["sur"]).endswith(".main_avant"):
            tenus[o["sur"].split(".")[0]] = o["id"]
    for a in sc.get("actions") or []:
        if not isinstance(a, dict):
            continue
        if a.get("action") == "pause":
            actions.append(a)
            continue
        if a.get("action") == "camera":
            cadres = cat.get("camera", {}).get("cadres", {"large": ""})
            a = {k: v for k, v in a.items() if k != "qui"}
            if a.get("cadre") not in cadres:
                errors.append(f"scene {n} : cadre de camera inconnu '{a.get('cadre')}' (choix : {list(cadres)})")
                continue
            if a["cadre"] != "large" and a.get("sur") not in ids:
                errors.append(f"scene {n} : camera {a['cadre']} sur '{a.get('sur')}' : objet ou personnage absent de la scene")
                continue
            if a["cadre"] == "objet" and ids[a["sur"]]["categorie"] == "personnage":
                a["cadre"] = "buste"
            elif a["cadre"] in ("buste", "visage", "dessous", "epaule") and ids[a["sur"]]["categorie"] != "personnage":
                a["cadre"] = "objet"
            if a.get("depuis") and (a["cadre"] != "epaule" or a["depuis"] not in ids or a["depuis"] == a["sur"]):
                del a["depuis"]
            actions.append(a)
            continue
        t = ids.get(a.get("qui"))
        if not t:
            errors.append(f"scene {n} : action sur un objet absent '{a.get('qui')}'")
            continue
        a = _corrige_expr_geste(a, perso) if t["categorie"] == "personnage" else a
        if t["categorie"] == "personnage" and a.get("action") not in perso["actions"]:
            # Action d'objet donnee a un personnage (Lea "taper") : rendue a l'objet de la scene qui la sait.
            porteurs = [i for i, ti in ids.items() if a.get("action") in (ti.get("actions") or [])]
            if len(porteurs) == 1:
                a = {**a, "qui": porteurs[0]}
                t = ids[porteurs[0]]
        possibles = list(perso["actions"]) if t["categorie"] == "personnage" else (t.get("actions") or [])
        if a.get("action") not in possibles:
            errors.append(f"scene {n} : action '{a.get('action')}' impossible pour {a.get('qui')} (choix : {possibles})")
            continue
        cibles = [a[k] for k in ("objet", "sur", "dans") if a.get(k) and a.get("action") in ("tenir", "poser", "s_asseoir", "jeter")]
        if any(str(c).split(".")[0] not in ids for c in cibles):
            errors.append(f"scene {n} : {a['action']} de {a['qui']} vise un objet absent ({', '.join(map(str, cibles))})")
            continue
        a = dict(a)
        if a["action"] == "jeter" and not a.get("dans"):
            errors.append(f"scene {n} : jeter de {a['qui']} : champ dans (id d'une corbeille de la scene) obligatoire")
            continue
        if a["action"] == "jeter" and not a.get("objet") and not tenus.get(a["qui"]):
            errors.append(f"scene {n} : {a['qui']} jette sans rien tenir (champ objet)")
            continue
        if a["action"] == "jeter" and a.get("objet") and tenus.get(a["qui"]) != a["objet"]:
            actions.append({"qui": a["qui"], "action": "tenir", "objet": a["objet"],
                            **({"avec": True} if a.get("avec") else {})})
            tenus[a["qui"]] = a["objet"]
            a.pop("avec", None)
        if a["action"] == "jeter":
            tenus.pop(a["qui"], None)
        problemes_texte = _textes_action(a)
        if problemes_texte:
            errors += [f"scene {n} : {a['action']} de {a['qui']} : {p}" for p in problemes_texte]
            if any(p.startswith("champ") for p in problemes_texte):
                continue
        if a["action"] in ("boire", "telephoner") and a.get("objet"):
            # Boire / telephoner = avec l'objet en main : on le prend d'abord s'il ne l'est pas.
            if tenus.get(a["qui"]) != a["objet"]:
                if str(a["objet"]).split(".")[0] in ids:
                    actions.append({"qui": a["qui"], "action": "tenir", "objet": a["objet"],
                                    **({"avec": True} if a.get("avec") else {})})
                    tenus[a["qui"]] = a["objet"]
                    a.pop("avec", None)
            a.pop("objet")
        if a["action"] == "tenir":
            tenus[a["qui"]] = a.get("objet")
        elif a["action"] == "poser":
            tenus.pop(a["qui"], None)
        suite = None
        if a.get("geste") in GESTES_MAIN_AU_VISAGE and tenus.get(a.get("qui")):
            del a["geste"]  # la main qui tient l'objet monte devant le visage (telephone sur l'oeil en gros plan)
        if a.get("geste") and a["geste"] not in perso["gestes"] and a["geste"] in perso["actions"] \
                and t["categorie"] == "personnage":
            # "geste": "sauter" -> action a part, jouee en meme temps.
            suite = {"qui": a["qui"], "action": a.pop("geste"), "avec": True}
        for champ, liste in (("expr", perso["expressions"]), ("geste", perso["gestes"])):
            if a.get(champ) and a[champ] not in liste:
                errors.append(f"scene {n} : {champ} inconnu '{a[champ]}' (choix : {liste})")
                del a[champ]
        actions.append(a)
        if suite:
            actions.append(suite)
    clean["objets"], clean["actions"] = objets, actions
    return clean, errors


# Textes des actions a texte (inserts, nuage de pensee) : champ -> (obligatoire, mots max).
TEXTES_ACTIONS = {
    "corriger": {"avant": (True, 14), "apres": (True, 16)},
    "tamponner": {"texte": (False, 3)},
    "afficher": {"titre": (False, 6), "texte": (True, 25)},
    "notifier": {"titre": (False, 4), "texte": (True, 14)},
    "imaginer": {"texte": (False, 4)},
    "comparer": {"titre_gauche": (False, 3), "texte_gauche": (True, 12), "titre_droite": (False, 3), "texte_droite": (True, 12)},
}
ELLIPSE_MAX_MOTS = 6
GESTES_MAIN_AU_VISAGE = ("idee", "tete_mains", "penser")   # gestes qui levent la main avant : pas avec un objet en main


def _textes_action(a: dict) -> list[str]:
    """Champs de texte d'une action (inserts, imaginer) : presence, longueur (coupee), icone connue."""
    problemes = []
    for champ, (requis, mx) in TEXTES_ACTIONS.get(a.get("action"), {}).items():
        mots = " ".join(str(a.get(champ) or "").split()).split()
        if not mots:
            if requis:
                problemes.append(f"champ {champ} obligatoire")
            a.pop(champ, None)
            continue
        if len(mots) > mx:
            problemes.append(f"{champ} trop long ({len(mots)} mots, {mx} max)")
        a[champ] = " ".join(mots[:mx])
    if a.get("action") == "imaginer" and a.get("image") not in icons():
        problemes.append(f"image inconnue '{a.get('image')}' (icônes : {', '.join(icons())})")
        a["image"] = "question"
    return problemes


def _ordre_supports(objets: list[dict]) -> list[dict]:
    """Un support (table, chaise, personnage qui tient) passe avant ce qui s'y pose / s'y assoit."""
    ids = {o.get("id") for o in objets}
    def dep(o):
        cible = str(o.get("sur") or "").split(".")[0] or o.get("assis")
        return cible if cible in ids and cible != o.get("id") else None
    restants, rangés, vus = list(objets), [], set()
    while restants:
        prets = [o for o in restants if dep(o) is None or dep(o) in vus]
        if not prets:  # cycle : ordre d'origine, le controle signalera
            rangés += restants
            break
        for o in prets:
            rangés.append(o)
            vus.add(o.get("id"))
            restants.remove(o)
    return rangés


def _corrige_expr_geste(a: dict, perso: dict) -> dict:
    """
    Confusions frequentes de l'IA, corrigees sans la relancer : un geste ecrit en "expr"
    passe en "geste" (s'il est libre), une expression ecrite en "geste" passe en "expr" ;
    action "expr" -> "expression", action portant le nom d'une expression -> "expression".
    """
    a = dict(a)
    if a.get("action") == "expr":
        a["action"] = "expression"
    if a.get("action") in perso["expressions"]:
        a["expr"], a["action"] = a["action"], "expression"
    if a.get("action") in perso["gestes"] and a["action"] not in perso["actions"]:
        a["geste"], a["action"] = a["action"], "geste"
    if a.get("expr") in perso["gestes"] and a.get("geste") in perso["expressions"]:
        a["expr"], a["geste"] = a["geste"], a["expr"]  # inverses
    if a.get("expr") in perso["gestes"] and a["expr"] not in perso["expressions"]:
        if not a.get("geste"):
            a["geste"] = a["expr"]
        del a["expr"]
    if a.get("geste") in perso["expressions"] and a["geste"] not in perso["gestes"]:
        a.setdefault("expr", a["geste"])
        del a["geste"]
    return a


def validate_scene_dessin(scene: dict) -> list[str]:
    """Verifie une scene (ou {"scenes": [...]}) du dessin anime contre catalog/dessins.json."""
    return [e for n, sc in enumerate(scene.get("scenes") or [scene], 1) for e in clean_scene_dessin(sc, n)[1]]


def _by_id(items: list[dict], item_id: str, kind: str) -> dict:
    for item in items:
        if item["id"] == item_id:
            return item
    raise KeyError(f"{kind} inconnu '{item_id}' (disponibles : {', '.join(i['id'] for i in items)})")


def voices() -> list[dict]:
    return _load("voix")["voix"]


def default_tone() -> str:
    return _load("voix")["ton_par_defaut"]


def pick_voice(history: list[dict], rng: random.Random, fmt: dict | None = None) -> dict:
    """Voix tiree en rotation ; un format a "voix" (documentaire : voix posee) n'utilise que celles-la."""
    pool = [v for v in voices() if not (fmt and fmt.get("voix")) or v["id"] in fmt["voix"]] or voices()
    return weighted_pick(pool, _recent(history, "voix", config().get("historique_voix", 2)), rng)


def get_voice(vid: str) -> dict:
    return _by_id(voices(), vid, "voix")


def ambiances() -> list[dict]:
    return _load("audio")["ambiances"]


def get_format(fid: str) -> dict:
    return _by_id(formats(), fid, "format")


def get_sujet(sid: str) -> dict:
    return _by_id(sujets(), sid, "sujet")


def get_hook(hid: str) -> dict:
    return _by_id(hooks(), hid, "style d'accroche")


def get_theme(tid: str | None) -> dict:
    """Theme par id ; None -> premier theme (couleurs OpusCV)."""
    return _by_id(themes(), tid, "theme") if tid else themes()[0]


def registres_of(item: dict, default: tuple[str, ...] = ("serieux",)) -> list[str]:
    """Registres d'un format ou d'une accroche (defaut : serieux) ou d'un theme (defaut : tous)."""
    return list(item.get("registres") or default)


def tone_for(fmt: dict, registre: str | None) -> str:
    """Ton de lecture (TTS) : celui du format, sa variante humour si le reel est en registre humour."""
    if registre == "humour" and "serieux" in registres_of(fmt):
        return fmt.get("ton_humour") or config().get("ton_humour") or fmt.get("ton") or default_tone()
    return fmt.get("ton") or default_tone()


def compatible_sujets(fmt: dict) -> list[dict]:
    tags = set(fmt["sujets"])
    return [s for s in sujets() if s["categorie"] == fmt["categorie"] and tags & set(s["tags"])]


# ---------------------------------------------------------------------------
# Polices / couleurs
# ---------------------------------------------------------------------------

def font_path(theme: dict | None, role: str = "texte") -> str:
    """role : 'titre' ou 'texte'. Police absente -> DejaVu (toujours installee)."""
    name = (theme or {}).get(f"police_{role}")
    if name and (FONTS_DIR / name).exists():
        return str(FONTS_DIR / name)
    return DEFAULT_FONT


def hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def anim_params(theme: dict | None) -> dict[str, str]:
    """Parametres d'URL communs a tous les gabarits d'animation (cf. assets/anim/common.js)."""
    theme = theme or get_theme(None)
    c = theme["couleurs"]
    return {
        "c1": c["primaire"], "c2": c["secondaire"], "cbg": c["fond"], "cfg": c["texte"], "chl": c["surligne"],
        "ftitle": Path(font_path(theme, "titre")).as_uri(), "ftext": Path(font_path(theme, "texte")).as_uri(),
        # Dessin a la main (assets/anim/sketch.js) : support et police manuscrite.
        "dessin": theme.get("dessin", "papier"), "fhand": (FONTS_DIR / HAND_FONT).as_uri(),
    }


# ---------------------------------------------------------------------------
# Historique et anti-redondance
# ---------------------------------------------------------------------------

def load_history(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(path: Path, history: list[dict], keep: int = 300):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history[-keep:], ensure_ascii=False, indent=2), encoding="utf-8")


def _recent(history: list[dict], key: str, n: int) -> list[str]:
    return [h[key] for h in history[-n:] if h.get(key)] if n > 0 else []


def weighted_pick(items: list[dict], avoid: list[str], rng: random.Random) -> dict:
    """Tirage pondere ("poids", 1 par defaut) parmi les items hors avoid ; tous exclus -> tous."""
    pool = [i for i in items if i["id"] not in avoid] or items
    return rng.choices(pool, weights=[max(float(i.get("poids", 1)), 0.01) for i in pool])[0]


def _most_behind(targets: dict[str, float], recent: list[str], rng: random.Random) -> str:
    """Valeur la plus en retard sur sa part cible, mesuree sur les elements recents."""
    total = len(recent) + 1
    deficit = {k: share - recent.count(k) / total for k, share in targets.items()}
    return max(deficit, key=lambda k: (deficit[k], rng.random()))


def pick_registre(history: list[dict], rng: random.Random, allowed: list[str] | None = None) -> str:
    """
    Registre le plus en retard sur config.json "registres" (serieux / humour),
    parmi `allowed` (ex : registres d'un format impose).
    """
    targets = {k: v for k, v in (config().get("registres") or {"serieux": 1.0}).items()
               if k in REGISTRES and (allowed is None or k in allowed)}
    if not targets:
        return (allowed or ["serieux"])[0]
    return _most_behind(targets, _recent(history, "registre", config().get("historique_registres", MIX_WINDOW)), rng)


def pick_format(history: list[dict], rng: random.Random, registre: str | None = None,
                sans_captures: bool = False) -> dict:
    """
    Categorie la plus en retard sur le mix cible (config.json "mix"), mesure
    sur les derniers reels, parmi celles qui ont un format du registre
    demande ; puis format pondere de cette categorie et de ce registre, en
    evitant les formats utilises tout recemment.
    sans_captures (--capture-mode aucune) : formats compatibles seulement
    (sans_captures_ok), une demo du produit sans image du produit ne dit rien.
    """
    pool = [f for f in formats() if registre is None or registre in registres_of(f)] or formats()
    if sans_captures:
        pool = [f for f in pool if sans_captures_ok(f)] or [f for f in formats() if sans_captures_ok(f)]
    else:  # dessin anime : plans dessines, aucune capture -> --capture-mode aucune seulement
        pool = [f for f in pool if not sans_capture_seul(f)] or [f for f in formats() if not sans_capture_seul(f)]
    available = {f["categorie"] for f in pool}
    targets = {cat: share for cat, share in config()["mix"].items() if cat in available} or {pool[0]["categorie"]: 1.0}
    # Mix mesure au sein du registre : sinon les reels humour absorberaient le retard de toute une categorie.
    same = [h for h in history if registre is None or h.get("registre", "serieux") == registre]
    category = _most_behind(targets, _recent(same, "categorie", MIX_WINDOW), rng)
    candidates = [f for f in pool if f["categorie"] == category]
    if registre == "humour":
        # Les capsules ecrites pour faire rire l'emportent sur celles des deux registres
        # (poids double) : un format serieux "joue en humour" fait nettement moins sourire.
        candidates = [{**f, "poids": float(f.get("poids", 1)) * (2 if registres_of(f) == ["humour"] else 1)}
                      for f in candidates]
    return get_format(weighted_pick(candidates, _recent(history, "format", config()["historique_formats"]), rng)["id"])


def sans_captures_ok(fmt: dict) -> bool:
    """Format jouable sans aucune capture de l'app : contenu conseil, avec des cartes."""
    return fmt.get("categorie") == "conseil" and fmt.get("cartes") != "aucune"


def hook_ok_dessin(h: dict) -> bool:
    """Accroche jouable par un personnage du dessin anime (hooks.json "dessin": false sinon, ex : POV)."""
    return h.get("dessin", True) is not False


def pick_hook(history: list[dict], rng: random.Random, registre: str | None = None, dessin: bool = False,
              tags: list[str] | None = None) -> dict:
    """Accroche tiree (registre, dessin anime, tags du sujet : une accroche a "tags" exige un tag commun avec le sujet)."""
    def ok_tags(h):
        return tags is None or not h.get("tags") or bool(set(h["tags"]) & set(tags))
    pool = [h for h in hooks() if (registre is None or registre in registres_of(h)) and (not dessin or hook_ok_dessin(h)) and ok_tags(h)] \
        or [h for h in hooks() if (not dessin or hook_ok_dessin(h)) and ok_tags(h)]
    return weighted_pick(pool, _recent(history, "hook", config()["historique_hooks"]), rng)


def pick_theme(history: list[dict], rng: random.Random, registre: str | None = None, fmt: dict | None = None) -> dict:
    """Theme tire (registre, format) : un theme a "formats" est reserve a ces formats, et un format a "themes" n'utilise que ceux-la."""
    ok = [t for t in themes() if (not t.get("formats") or (fmt and fmt["id"] in t["formats"]))
          and (not (fmt and fmt.get("themes")) or t["id"] in fmt["themes"])] or themes()
    pool = [t for t in ok if registre is None or registre in registres_of(t, REGISTRES)] or ok
    return weighted_pick(pool, _recent(history, "theme", config()["historique_themes"]), rng)


def pick_cta(categorie: str, rng: random.Random) -> tuple[str, dict]:
    """(phrase de CTA dite en fin de reel, textes du CTA anime) -- variantes de config.json."""
    cfg = config()
    phrases = cfg.get(f"ctas_{categorie}") or cfg.get("ctas_produit") or ["Lien en bio."]
    anims = cfg.get("cta_anim") or [{}]
    return rng.choice(phrases), dict(rng.choice(anims))


NO_MUSIC = "aucune"  # ambiance reservee : sans musique de fond (audio_gen.NO_MUSIC)
PLAN_KEYS = ("format", "sujet", "hook", "theme", "voix", "registre", "ambiance", "angle", "trame")


def validate_plan(plan: list, sans_captures: bool = False) -> list[str]:
    """Plan par reel (--plan, console) : liste d'objets aux cles PLAN_KEYS, vides = automatique."""
    if not isinstance(plan, list) or not plan:
        return ["le plan doit etre une liste non vide d'objets (un par reel)"]
    getters = {"format": get_format, "sujet": get_sujet, "hook": get_hook, "theme": get_theme,
               "voix": get_voice, "ambiance": lambda a: a == NO_MUSIC or _by_id(ambiances(), a, "ambiance")}
    errors = []
    for i, item in enumerate(plan, 1):
        if not isinstance(item, dict):
            errors.append(f"reel {i} : objet attendu")
            continue
        errors += [f"reel {i} : cle inconnue '{k}' (autorisees : {', '.join(PLAN_KEYS)})" for k in item if k not in PLAN_KEYS]
        for k, get in getters.items():
            if item.get(k):
                try:
                    get(item[k])
                except KeyError as e:
                    errors.append(f"reel {i} : {e.args[0].split(' (disponibles')[0]}")
        if item.get("trame") and item["trame"] not in {t["id"] for t in trames()}:
            errors.append(f"reel {i} : trame inconnue '{item['trame']}' (choix : {', '.join(t['id'] for t in trames())})")
        if item.get("registre") and item["registre"] not in REGISTRES:
            errors.append(f"reel {i} : registre inconnu '{item['registre']}'")
        if item.get("sujet") and item.get("angle"):
            errors.append(f"reel {i} : sujet du catalogue OU angle libre, pas les deux")
        if item.get("format") and item["format"] in {f["id"] for f in formats()}:
            if sans_captures and not sans_captures_ok(get_format(item["format"])):
                errors.append(f"reel {i} : format '{item['format']}' impossible sans captures")
            if not sans_captures and sans_capture_seul(get_format(item["format"])):
                errors.append(f"reel {i} : format dessine '{item['format']}' (dessin anime, documentaire) : capture 'aucune' uniquement")
            if get_format(item["format"]).get("dessin") and item.get("hook") in {x["id"] for x in hooks()} \
                    and not hook_ok_dessin(get_hook(item["hook"])):
                errors.append(f"reel {i} : accroche '{item['hook']}' impossible en dessin anime (dite par un personnage)")
    return errors


def pick_ambiance(theme: dict, history: list[dict], rng: random.Random, fmt: dict | None = None) -> str | None:
    """Ambiance musicale parmi celles du theme ("ambiances"), en evitant les 2 plus recentes.
    Format a "ambiances" (dessin anime : musiques douces sous un dialogue) : celles du theme qui y figurent,
    sinon celles du format."""
    options = theme.get("ambiances") or ([theme["ambiance"]] if theme.get("ambiance") else [])
    if fmt and fmt.get("ambiances"):
        options = [a for a in options if a in fmt["ambiances"]] or list(fmt["ambiances"])
    if not options:
        return None
    recent = _recent(history, "ambiance", 2)
    return rng.choice([a for a in options if a not in recent] or options)


def pick_lieu(history: list[dict], rng: random.Random) -> dict | None:
    """Decor (dessins.json "fonds", hors « vide ») le moins recemment utilise par un dessin anime
    (history "fonds"), au hasard entre les jamais utilises : propose a l'IA comme lieu de l'episode."""
    pool = [f for f in dessins()["fonds"] if f["id"] != "vide"]
    if not pool:
        return None
    vus = [f for h in history for f in (h.get("fonds") or [])]
    def age(f):
        return len(vus) - 1 - max(i for i, v in enumerate(vus) if v == f["id"]) if f["id"] in vus else 10 ** 6
    plus_vieux = max(age(f) for f in pool)
    return rng.choice([f for f in pool if age(f) == plus_vieux])


def famille_rotation(sujets_: list[dict], history: list[dict]) -> list[dict]:
    """
    Sujets de la famille la moins recemment traitee (sujets.json "famille"),
    parmi ceux fournis : une famille jamais vue passe avant toutes, puis celle
    vue il y a le plus longtemps. Les familles des config.json
    historique_familles derniers reels sont ecartees tant qu'il en reste
    d'autres -- sans ca, les themes les plus "viraux" (ATS, chiffres)
    revenaient reel apres reel.
    """
    seen = [h.get("famille") for h in history if h.get("famille")]
    last_seen = {f: i for i, f in enumerate(seen)}
    blocked = set(seen[-config().get("historique_familles", 5):]) if seen else set()
    familles = {s.get("famille", s["id"]) for s in sujets_}
    pool = [f for f in familles if f not in blocked] or list(familles)
    best = min(pool, key=lambda f: (last_seen.get(f, -1), f))
    return [s for s in sujets_ if s.get("famille", s["id"]) == best]


def recent_sujets(history: list[dict], n: int = 15) -> list[str]:
    return _recent(history, "sujet", n)


def recent_accroches(history: list[dict]) -> list[str]:
    return _recent(history, "accroche", config()["historique_accroches"])


def series_episode(history: list[dict], format_id: str) -> int:
    return sum(1 for h in history if h.get("format") == format_id) + 1


def series_resumes(history: list[dict], format_id: str, n: int = 5) -> list[tuple[int, str]]:
    """Resumes des n derniers episodes d'une serie (historique, champ "resume") : [(episode, resume)]."""
    episodes = [h for h in history if h.get("format") == format_id]
    return [(i, h["resume"]) for i, h in enumerate(episodes, 1) if h.get("resume")][-n:]


def trames() -> list[dict]:
    return dessins().get("trames") or []


def pick_trame(history: list[dict], rng: random.Random) -> dict | None:
    """Trame d'histoire du dessin anime : la moins recemment utilisee (au hasard entre les jamais vues)."""
    pool = trames()
    if not pool:
        return None
    recentes = [h.get("trame") for h in history if h.get("trame")]
    def age(t):
        return len(recentes) - 1 - max(i for i, r in enumerate(recentes) if r == t["id"]) if t["id"] in recentes else 10 ** 6
    plus_vieux = max(age(t) for t in pool)
    return rng.choice([t for t in pool if age(t) == plus_vieux])


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


def too_similar(text: str, previous: list[str]) -> str | None:
    """-> l'ancienne accroche trop proche (config similarite_max), sinon None."""
    limit = config()["similarite_max"]
    for old in previous:
        if difflib.SequenceMatcher(None, _norm(text), _norm(old)).ratio() >= limit:
            return old
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_catalog() -> list[str]:
    errors = []
    for name, items in (("formats", formats()), ("sujets", sujets()), ("hooks", hooks()), ("themes", themes())):
        ids = [i.get("id") for i in items]
        if len(ids) != len(set(ids)) or None in ids:
            errors.append(f"{name}.json : ids manquants ou en double")
    for s in sujets():
        if not s.get("famille"):
            errors.append(f"sujet {s['id']} : famille manquante")
    for f in formats():
        for key in ("nom", "categorie", "structure", "sujets", "cartes"):
            if key not in f:
                errors.append(f"format {f['id']} : champ '{key}' manquant")
        if f.get("cartes") not in CARD_MODES:
            errors.append(f"format {f['id']} : cartes doit valoir {CARD_MODES}")
        if not compatible_sujets(f):
            errors.append(f"format {f['id']} : aucun sujet compatible (categorie + tags)")
    for t in themes():
        for key in ("primaire", "secondaire", "fond", "texte", "surligne", "contour", "pastille"):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", t.get("couleurs", {}).get(key, "")):
                errors.append(f"theme {t['id']} : couleur '{key}' absente ou pas au format #rrggbb")
        ambiances = {a["id"] for a in _load("audio")["ambiances"]}
        for amb in [t.get("ambiance")] + list(t.get("ambiances") or []):
            if amb and amb not in ambiances:
                errors.append(f"theme {t['id']} : ambiance '{amb}' absente de audio.json")
        if t.get("sous_titres", {}).get("style", "karaoke") not in ("karaoke", "encadre", "boite", "mot"):
            errors.append(f"theme {t['id']} : sous_titres.style inconnu")
        if t.get("dessin", "papier") not in DESSIN_SUPPORTS:
            errors.append(f"theme {t['id']} : dessin doit valoir {DESSIN_SUPPORTS}")
        for role in ("titre", "texte"):
            name = t.get(f"police_{role}")
            if name and not (FONTS_DIR / name).exists():
                errors.append(f"theme {t['id']} : police {name} absente de assets/fonts/")
    for kind, items in (("format", formats()), ("accroche", hooks()), ("theme", themes())):
        for item in items:
            bad = [r for r in item.get("registres") or [] if r not in REGISTRES]
            if bad or ("registres" in item and not item["registres"]):
                errors.append(f"{kind} {item['id']} : registres doit etre une liste non vide parmi {REGISTRES}")
    for reg in config().get("registres") or {}:
        if reg not in REGISTRES:
            errors.append(f"config.json : registre inconnu '{reg}' (choix : {REGISTRES})")
        elif not any(reg in registres_of(f) for f in formats()):
            errors.append(f"config.json : registre '{reg}' sans aucun format")
        elif not any(reg in registres_of(h) for h in hooks()):
            errors.append(f"config.json : registre '{reg}' sans aucune accroche")
    insta = config().get("instagram") or {}
    if insta and not all(isinstance(s, dict) and s.get("titre") for s in insta.get("carrousel_fin") or [{"titre": "x"}]):
        errors.append("config.json : instagram.carrousel_fin doit lister des {titre, texte}")
    for t in themes():
        tr = t.get("transitions", [])
        if not isinstance(tr, list) or not all(isinstance(x, str) and x for x in tr):
            errors.append(f"theme {t['id']} : transitions doit etre une liste de noms xfade")
    if not voices():
        errors.append("voix.json : aucune voix")
    try:
        bad = [k for k, v in icons().items() if not v.get("nom") or not v.get("d")]
        if bad:
            errors.append(f"icones.js : nom ou traits manquants pour {bad}")
    except (ValueError, OSError) as e:
        errors.append(f"icones.js illisible (JSON strict attendu apres 'window.ICONES = ') : {e}")
    try:
        cat, js = dessins(), _types_dessin_js()
        declares = {"fonds": {f["id"] for f in cat["fonds"]}, "objets": {o["id"] for o in cat["objets"]}}
        for kind in ("fonds", "objets"):
            for missing in sorted(declares[kind] - js[kind]):
                errors.append(f"dessins.json : {kind} '{missing}' absent du code assets/anim/dessin/")
            for extra in sorted(js[kind] - declares[kind]):
                errors.append(f"dessins.json : {kind} '{extra}' existe dans le code mais n'est pas declare")
        for o in cat["objets"]:
            if o.get("categorie") not in ("personnage", "animal", "objet", "decor"):
                errors.append(f"dessins.json : objet {o['id']} : categorie inconnue")
            if o.get("categorie") == "personnage" and not (o.get("nom") and o.get("voix")):
                errors.append(f"dessins.json : personnage {o['id']} : nom et voix (Gemini TTS) obligatoires")
        perso = cat["personnage"]
        if set(perso.get("voix_expressions") or {}) != set(perso["expressions"]):
            errors.append("dessins.json : personnage.voix_expressions doit donner un ton pour chaque expression")
        for t in cat.get("trames") or []:
            if not (t.get("id") and t.get("nom") and t.get("consigne")):
                errors.append(f"dessins.json : trame {t} : id, nom et consigne obligatoires")
        principaux = [p for p in personnages().values() if p.get("role", "principal") == "principal"]
        if any(f.get("dessin") for f in formats()) and len(principaux) < 2:
            errors.append("dessins.json : le format dessin anime demande au moins 2 personnages")
    except (ValueError, OSError, KeyError) as e:
        errors.append(f"dessins.json ou assets/anim/dessin/ illisible : {e}")
    try:
        doc, js = documentaire(), _types_documentaire_js()
        for kind, cle in (("habitats", "habitats"), ("moments", "moments"), ("especes", "especes")):
            declares = {x["id"] for x in doc[cle]}
            for missing in sorted(declares - js[kind]):
                errors.append(f"documentaire.json : {kind} '{missing}' absent du code assets/anim/documentaire/")
            for extra in sorted(js[kind] - declares):
                errors.append(f"documentaire.json : {kind} '{extra}' existe dans le code mais n'est pas declare")
        for h in doc["habitats"]:
            if not set(h.get("moments") or []) <= {m["id"] for m in doc["moments"]}:
                errors.append(f"documentaire.json : habitat {h['id']} : moment inconnu")
        for e in doc["especes"]:
            if not (e.get("nom") and e.get("sens")):
                errors.append(f"documentaire.json : espece {e['id']} : nom et sens obligatoires")
        for f in formats():
            if f.get("documentaire") and (f.get("dessin") or f.get("cartes") == "aucune"):
                errors.append(f"format {f['id']} : documentaire incompatible avec dessin et cartes 'aucune'")
            for vid in f.get("voix") or []:
                if vid not in {v["id"] for v in voices()}:
                    errors.append(f"format {f['id']} : voix '{vid}' absente de voix.json")
            for tid in f.get("themes") or []:
                if tid not in {t["id"] for t in themes()}:
                    errors.append(f"format {f['id']} : theme '{tid}' absent de themes.json")
        for t in themes():
            for fid in t.get("formats") or []:
                if fid not in {f["id"] for f in formats()}:
                    errors.append(f"theme {t['id']} : format '{fid}' absent de formats.json")
    except (ValueError, OSError, KeyError) as e:
        errors.append(f"documentaire.json ou assets/anim/documentaire/ illisible : {e}")
    if not (FONTS_DIR / HAND_FONT).exists():
        errors.append(f"police manuscrite {HAND_FONT} absente de assets/fonts/")
    if set(config()["mix"]) - {f["categorie"] for f in formats()}:
        errors.append("config.json : mix cite une categorie sans aucun format")
    return errors


def apercus_manquants() -> list[str]:
    """Apercus de la console (docs/apercus/, scripts/apercus.py) absents pour un element du catalogue."""
    base = ROOT / "docs" / "apercus"
    attendus = ([f"themes/{t['id']}.jpg" for t in themes()] + [f"cartes/{k}.jpg" for k in CARD_TYPES]
                + [f"decors/{f['id']}.jpg" for f in dessins()["fonds"]] + [f"personnages/{p}.jpg" for p in personnages()]
                + [f"habitats/{h['id']}.jpg" for h in documentaire()["habitats"]]
                + [f"animaux/{e['id']}.jpg" for e in documentaire()["especes"]]
                + [f"voix/{v}.mp3" for v in dict.fromkeys([v["id"] for v in voices()] + [p["voix"] for p in personnages().values()])]
                + [f"ambiances/{a['id']}.mp3" for a in ambiances()])
    return [a for a in attendus if not (base / a).exists()]


if __name__ == "__main__":
    problems = validate_catalog()
    for p in problems:
        print(f"ERREUR: {p}", file=sys.stderr)
    manquants = apercus_manquants()
    if manquants:  # pas bloquant : la console affiche alors une vignette neutre
        print(f"ATTENTION: {len(manquants)} apercu(s) de la console manquant(s) ({', '.join(manquants[:6])}"
              f"{'...' if len(manquants) > 6 else ''}) : python scripts/apercus.py", file=sys.stderr)
    print(f"{len(formats())} formats, {len(sujets())} sujets, {len(hooks())} accroches, {len(themes())} themes, "
          f"{len(icons())} icones, {len(dessins()['fonds'])} fonds et {len(dessins()['objets'])} objets dessines")
    for f in formats():
        print(f"  {f['id']:22} [{f['categorie']}/{'+'.join(registres_of(f))}] {len(compatible_sujets(f))} sujets compatibles")
    sys.exit(1 if problems else 0)
