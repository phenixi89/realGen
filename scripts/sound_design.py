"""
Plan des effets sonores d'un reel : qui joue quoi, et quand, a partir du
scenario (cartes, styles, effets) et de la timeline (debut de chaque scene).
Le mixage (volumes, regles anti-abus) est fait par audio_gen.render_sfx_track.

Les instants reproduisent ceux des gabarits d'animation -- a garder
synchronises avec assets/anim/carte.html (TYPE_START, SUSPENSE_REVEAL,
typeInterval) et cta.html :

    accroche (1re image)     -> impact
    changement de scene      -> effet "transition" d'audio.json (tick par defaut)
    carte : surtitre         -> pop
    carte "frappe"           -> un clic par caractere tape
    carte "suspense"         -> riser pendant la jauge, impact a la revelation
    carte "realite"/"apres"  -> ding quand le titre est pose
    carte "mythe"            -> buzz quand le titre se barre
    carte "avant"            -> buzz discret
    scene CTA animee         -> sparkle a l'apparition du bouton
    carte chiffre            -> clics pendant le comptage, impact a l'arrivee
    carte comparaison        -> buzz sur l'Avant, ding sur l'Apres
    carte liste              -> pop a chaque point coche
    curseur anime            -> clic de souris (ajoute par run_pipeline.py)
"""
from urllib.parse import parse_qsl

TYPE_START = 0.35
SUSPENSE_REVEAL = 1.2
STANDARD_TITLE_END = 0.7
CTA_BUTTON_AT = 1.45
WHOOSH_LEAD = 0.12
QUOTES = ' «»"“”'


def transition_sound() -> str:
    """Effet des changements de scene (catalog/audio.json "effets.transition")."""
    import audio_gen
    return audio_gen.audio_config()["effets"].get("transition", "")


def type_interval(n_chars: int, dur: float) -> float:
    return min(0.06, max(0.025, (dur * 0.55) / max(n_chars, 1)))


def display_title(card: dict) -> str:
    """Titre tel qu'affiche par carte.html (guillemets ajoutes pour avant/apres)."""
    title = card.get("titre", "")
    if card.get("style") in ("avant", "apres"):
        title = "« " + title.strip(QUOTES) + " »"
    return title


def title_end(card: dict, dur: float) -> float:
    effet = card.get("effet", "standard")
    if effet == "frappe":
        title = display_title(card)
        return TYPE_START + len(title) * type_interval(len(title), dur)
    if effet == "suspense":
        return SUSPENSE_REVEAL + 0.4
    return STANDARD_TITLE_END


def card_cues(card: dict, start: float, dur: float) -> list[dict]:
    cues = [{"t": start + 0.08, "name": "pop"}]
    effet = card.get("effet", "standard")
    if effet == "frappe":
        title = display_title(card)
        dt = type_interval(len(title), dur)
        cues += [{"t": start + TYPE_START + i * dt, "name": "click"}
                 for i, ch in enumerate(title) if not ch.isspace()]
    elif effet == "suspense":
        cues += [{"t": start + 0.1, "name": "riser", "duration": SUSPENSE_REVEAL - 0.1},
                 {"t": start + SUSPENSE_REVEAL, "name": "impact"}]
    end = start + title_end(card, dur)
    style = card.get("style", "normal")
    if style in ("realite", "apres"):
        cues.append({"t": end + 0.05, "name": "ding"})
    elif style == "mythe":
        # carte.html : texte (fin du titre + 0.3, 0.45 s) puis barre +0.25 s.
        cues.append({"t": end + 1.0, "name": "buzz"})
    elif style == "avant":
        cues.append({"t": end + 0.05, "name": "buzz", "gain": 0.6})
    return cues


def plan_cues(timeline: dict, scene_anims: dict[int, str], hook: bool) -> list[dict]:
    """
    scene_anims : {index de scene: "gabarit?params"} (cf. run_pipeline.plan_montage),
    tel que rendu au montage -- les parametres des cartes y sont deja.
    """
    scenes = timeline["scenes"]
    cues = [{"t": 0.02, "name": "impact", "gain": 0.5}] if hook else []
    for i, scene in enumerate(scenes):
        start, dur = scene["start"], scene["end"] - scene["start"]
        if i > 0 and transition_sound():
            cues.append({"t": max(start - WHOOSH_LEAD, 0), "name": transition_sound(), "transition": True})
        spec = scene_anims.get(i)
        if not spec:
            continue
        name, _, query = spec.partition("?")
        params = dict(parse_qsl(query))
        if name == "carte":
            cues += card_cues(params, start, float(params.get("dur", dur)))
        elif name == "chiffre":
            # chiffre.html : comptage COUNT_START -> +COUNT_DUR, puis onde + legende.
            cues += [{"t": start + 0.08, "name": "pop"}]
            cues += [{"t": start + 0.3 + k * 0.1, "name": "click", "gain": 0.7} for k in range(10)]
            cues.append({"t": start + 1.4, "name": "impact", "gain": 0.6})
        elif name == "comparaison":
            # comparaison.html : Avant a AVANT_AT, rideau de l'Apres a APRES_AT.
            cues += [{"t": start + 0.3, "name": "buzz", "gain": 0.6}, {"t": start + 1.45, "name": "ding"}]
        elif name == "liste":
            # liste.html : un point toutes les itemGap(n) s a partir de FIRST_AT, coche +0.2 s.
            n = max(len([p for p in params.get("points", "").split("|") if p]), 1)
            d = float(params.get("dur", dur))
            gap = min(0.7, max(0.3, (d - 0.6 - 0.8) / n))
            cues += [{"t": start + 0.6 + k * gap + 0.2, "name": "pop"} for k in range(n)]
        elif name == "cta":
            cues.append({"t": start + CTA_BUTTON_AT, "name": "sparkle"})
    return cues
