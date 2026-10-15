"""
CV de démonstration des captures : un CV propre, créé par l'API de l'app juste avant de filmer, supprimé juste après.

Pourquoi : le compte de démo gardait un vieux CV (coquilles « Growthds », « Globalds » visibles dans le reel du run 79),
et l'app ne propose plus son profil de démonstration à un compte connecté (changement du 06/10) : le script ne pouvait
plus en recréer un. Le CV vient de `assets/cv_demo.json`, copie du profil de démonstration de l'app (Camille Duval,
conseillère de vente) SANS téléphone : l'app signale alors un point bloquant (« téléphone manquant »), ce qui montre
les points à corriger, les repères sur le CV et « Avant d'envoyer » tels que les voit un vrai candidat.

Tout échec (compte plein, réseau, API changée) est signalé et sans conséquence : les captures retombent sur le premier
CV du compte, comme avant.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
TITRE = "Camille Duval - Conseillère de vente"
THEME_PREFERE = "Moutarde Moderne"   # Split à colonne sombre : le nom en haut à droite, les repères dans la marge


@dataclass
class CvDemo:
    base: str
    token: str
    id: str
    titre: str = TITRE

    def supprimer(self) -> None:
        try:
            _appel("DELETE", f"{self.base}/api/cvs/{self.id}", self.token)
            print(f"CV de démonstration supprimé ({self.id})")
        except Exception as exc:  # noqa: BLE001 -- un CV de démo qui reste ne casse rien (retrouvé et supprimé au run suivant)
            print(f"ATTENTION: CV de démonstration non supprimé ({exc})", file=sys.stderr)


def _appel(methode: str, url: str, token: str | None = None, corps: dict | None = None):
    en_tetes = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        en_tetes["Authorization"] = f"Bearer {token}"
    requete = urllib.request.Request(url, data=json.dumps(corps).encode() if corps is not None else None,
                                     headers=en_tetes, method=methode)
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        brut = reponse.read()
    return json.loads(brut) if brut else None


def preparer(url_app: str, email: str, mot_de_passe: str) -> CvDemo | None:
    """Crée le CV de démonstration ; None si ce n'est pas possible (les captures utiliseront le CV existant)."""
    parts = urlsplit(url_app)
    base = f"{parts.scheme}://{parts.netloc}"
    try:
        token = _appel("POST", f"{base}/api/auth/login", corps={"email": email, "password": mot_de_passe})["token"]
        # Restes d'un run interrompu : même titre, supprimés avant d'en créer un neuf (jamais un autre CV du compte).
        for cv in _appel("GET", f"{base}/api/cvs", token) or []:
            if cv.get("title") == TITRE:
                _appel("DELETE", f"{base}/api/cvs/{cv['id']}", token)
        themes = _appel("GET", f"{base}/api/themes") or {}
        theme = THEME_PREFERE if THEME_PREFERE in themes else next(iter(themes), THEME_PREFERE)
        cv_data = json.loads((ROOT / "assets" / "cv_demo.json").read_text(encoding="utf-8"))
        cree = _appel("POST", f"{base}/api/cvs", token, {"title": TITRE, "cv_data": cv_data, "theme_id": theme})
        print(f"CV de démonstration créé : « {TITRE} » ({cree['id']})")
        return CvDemo(base, token, cree["id"])
    except (urllib.error.URLError, KeyError, ValueError, OSError) as exc:
        detail = exc.read().decode("utf-8", "replace")[:200] if isinstance(exc, urllib.error.HTTPError) else ""
        print(f"ATTENTION: CV de démonstration non créé ({exc} {detail}) : captures sur le CV existant du compte", file=sys.stderr)
        return None
