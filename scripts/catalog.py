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
DESSIN_SUPPORTS = ("papier", "craie", "neon")
CARD_MODES = ("aucune", "autorisees", "majoritaires")
CARD_STYLES = ("normal", "mythe", "realite", "avant", "apres")
CARD_EFFECTS = ("standard", "frappe", "suspense")
# Type de carte -> gabarit assets/anim/<gabarit>.html
CARD_TYPES = {"texte": "carte", "chiffre": "chiffre", "comparaison": "comparaison", "liste": "liste",
              "schema": "schema", "conversation": "conversation", "scan": "scan", "impact": "impact",
              "meme": "meme"}
# Marque dessinee sur la derniere etape d'une carte schema (assets/anim/schema.html).
SCHEMA_MARKS = ("entoure", "barre", "coche")
ICONS_JS = ROOT / "assets" / "anim" / "icones.js"

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


def _by_id(items: list[dict], item_id: str, kind: str) -> dict:
    for item in items:
        if item["id"] == item_id:
            return item
    raise KeyError(f"{kind} inconnu '{item_id}' (disponibles : {', '.join(i['id'] for i in items)})")


def voices() -> list[dict]:
    return _load("voix")["voix"]


def default_tone() -> str:
    return _load("voix")["ton_par_defaut"]


def pick_voice(history: list[dict], rng: random.Random) -> dict:
    return weighted_pick(voices(), _recent(history, "voix", config().get("historique_voix", 2)), rng)


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


def pick_hook(history: list[dict], rng: random.Random, registre: str | None = None) -> dict:
    pool = [h for h in hooks() if registre is None or registre in registres_of(h)] or hooks()
    return weighted_pick(pool, _recent(history, "hook", config()["historique_hooks"]), rng)


def pick_theme(history: list[dict], rng: random.Random, registre: str | None = None) -> dict:
    pool = [t for t in themes() if registre is None or registre in registres_of(t, REGISTRES)] or themes()
    return weighted_pick(pool, _recent(history, "theme", config()["historique_themes"]), rng)


def pick_cta(categorie: str, rng: random.Random) -> tuple[str, dict]:
    """(phrase de CTA dite en fin de reel, textes du CTA anime) -- variantes de config.json."""
    cfg = config()
    phrases = cfg.get(f"ctas_{categorie}") or cfg.get("ctas_produit") or ["Lien en bio."]
    anims = cfg.get("cta_anim") or [{}]
    return rng.choice(phrases), dict(rng.choice(anims))


PLAN_KEYS = ("format", "sujet", "hook", "theme", "voix", "registre", "ambiance", "angle")


def validate_plan(plan: list, sans_captures: bool = False) -> list[str]:
    """Plan par reel (--plan, console) : liste d'objets aux cles PLAN_KEYS, vides = automatique."""
    if not isinstance(plan, list) or not plan:
        return ["le plan doit etre une liste non vide d'objets (un par reel)"]
    getters = {"format": get_format, "sujet": get_sujet, "hook": get_hook, "theme": get_theme,
               "voix": get_voice, "ambiance": lambda a: _by_id(ambiances(), a, "ambiance")}
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
        if item.get("registre") and item["registre"] not in REGISTRES:
            errors.append(f"reel {i} : registre inconnu '{item['registre']}'")
        if item.get("sujet") and item.get("angle"):
            errors.append(f"reel {i} : sujet du catalogue OU angle libre, pas les deux")
        if sans_captures and item.get("format") and item["format"] in {f["id"] for f in formats()} \
                and not sans_captures_ok(get_format(item["format"])):
            errors.append(f"reel {i} : format '{item['format']}' impossible sans captures")
    return errors


def pick_ambiance(theme: dict, history: list[dict], rng: random.Random) -> str | None:
    """Ambiance musicale parmi celles du theme ("ambiances"), en evitant les 2 plus recentes."""
    options = theme.get("ambiances") or ([theme["ambiance"]] if theme.get("ambiance") else [])
    if not options:
        return None
    recent = _recent(history, "ambiance", 2)
    return rng.choice([a for a in options if a not in recent] or options)


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
    if not (FONTS_DIR / HAND_FONT).exists():
        errors.append(f"police manuscrite {HAND_FONT} absente de assets/fonts/")
    if set(config()["mix"]) - {f["categorie"] for f in formats()}:
        errors.append("config.json : mix cite une categorie sans aucun format")
    return errors


if __name__ == "__main__":
    problems = validate_catalog()
    for p in problems:
        print(f"ERREUR: {p}", file=sys.stderr)
    print(f"{len(formats())} formats, {len(sujets())} sujets, {len(hooks())} accroches, {len(themes())} themes, "
          f"{len(icons())} icones")
    for f in formats():
        print(f"  {f['id']:22} [{f['categorie']}/{'+'.join(registres_of(f))}] {len(compatible_sujets(f))} sujets compatibles")
    sys.exit(1 if problems else 0)
