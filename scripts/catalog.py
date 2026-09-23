"""
Catalogue editorial et visuel des reels (dossier catalog/ a la racine) :

    formats.json  structure des videos (liste d'erreurs, mythe/realite, demo...)
    sujets.json   de quoi parle la video (conseil ou produit)
    hooks.json    styles d'accroche des 2 premieres secondes
    themes.json   couleurs, polices, style des sous-titres, musique
    config.json   mix conseil/produit, anti-redondance

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
CARD_MODES = ("aucune", "autorisees", "majoritaires")
CARD_STYLES = ("normal", "mythe", "realite", "avant", "apres")
# Fenetre sur laquelle on mesure le mix conseil/produit deja publie.
MIX_WINDOW = 10


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


def _by_id(items: list[dict], item_id: str, kind: str) -> dict:
    for item in items:
        if item["id"] == item_id:
            return item
    raise KeyError(f"{kind} inconnu '{item_id}' (disponibles : {', '.join(i['id'] for i in items)})")


def get_format(fid: str) -> dict:
    return _by_id(formats(), fid, "format")


def get_sujet(sid: str) -> dict:
    return _by_id(sujets(), sid, "sujet")


def get_hook(hid: str) -> dict:
    return _by_id(hooks(), hid, "style d'accroche")


def get_theme(tid: str | None) -> dict:
    """Theme par id ; None -> premier theme (couleurs OpusCV)."""
    return _by_id(themes(), tid, "theme") if tid else themes()[0]


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


def pick_format(history: list[dict], rng: random.Random) -> dict:
    """
    Categorie la plus en retard sur le mix cible (config.json "mix"), mesure
    sur les derniers reels ; puis format pondere de cette categorie, en
    evitant les formats utilises tout recemment.
    """
    mix = config()["mix"]
    recent_cats = _recent(history, "categorie", MIX_WINDOW)
    total = len(recent_cats) + 1
    available = {f["categorie"] for f in formats()}
    deficit = {cat: share - recent_cats.count(cat) / total for cat, share in mix.items() if cat in available}
    category = max(deficit, key=lambda cat: (deficit[cat], rng.random()))
    candidates = [f for f in formats() if f["categorie"] == category]
    return weighted_pick(candidates, _recent(history, "format", config()["historique_formats"]), rng)


def pick_hook(history: list[dict], rng: random.Random) -> dict:
    return weighted_pick(hooks(), _recent(history, "hook", config()["historique_hooks"]), rng)


def pick_theme(history: list[dict], rng: random.Random) -> dict:
    return weighted_pick(themes(), _recent(history, "theme", config()["historique_themes"]), rng)


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
        for role in ("titre", "texte"):
            name = t.get(f"police_{role}")
            if name and not (FONTS_DIR / name).exists():
                errors.append(f"theme {t['id']} : police {name} absente de assets/fonts/")
    if set(config()["mix"]) - {f["categorie"] for f in formats()}:
        errors.append("config.json : mix cite une categorie sans aucun format")
    return errors


if __name__ == "__main__":
    problems = validate_catalog()
    for p in problems:
        print(f"ERREUR: {p}", file=sys.stderr)
    print(f"{len(formats())} formats, {len(sujets())} sujets, {len(hooks())} accroches, {len(themes())} themes")
    for f in formats():
        print(f"  {f['id']:18} [{f['categorie']}] {len(compatible_sujets(f))} sujets compatibles")
    sys.exit(1 if problems else 0)
