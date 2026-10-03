"""Texte de narration partage entre 2_generate_voice.py (TTS) et
4_generate_subtitles.py (alignement des sous-titres et des scenes sur ce texte exact)."""


def scene_texts(script: dict) -> list[str]:
    """Texte de chaque scene, dans l'ordre (ancien format hook/probleme/demo/cta = 4 scenes sans feature)."""
    if script.get("scenes"):
        return [s["texte"].strip() for s in script["scenes"] if s.get("texte", "").strip()]
    return [script[k] for k in ("hook", "probleme", "demo", "cta") if script.get(k)]


def script_to_text(script: dict) -> str:
    """Texte complet lu par la voix off : les scenes mises bout a bout."""
    return " ".join(scene_texts(script))


def dialogue_lines(script: dict) -> list[tuple[str, str]]:
    """
    Reel en dessin anime (format "dessin") : les repliques dans l'ordre, [(id du
    personnage, texte)] -- lues a plusieurs voix par 2_generate_voice.py ; [] sinon.
    Le texte de chaque scene est la suite de ses repliques (1_generate_script.py).
    """
    if not (script.get("dessin") or script.get("jeu")):
        return []
    return [(a["qui"], a["texte"].strip()) for s in script.get("scenes", []) for a in s.get("repliques", [])
            if a.get("texte", "").strip()]


def dialogue_expressions(script: dict) -> list[str | None]:
    """
    Expression du personnage pour chaque replique de dialogue_lines (meme ordre) : le "expr" de
    l'action "parler" correspondante de la scene dessinee (None pour le CTA, sans dessin) --
    elle donne le ton de la replique au TTS (2_generate_voice.py).
    """
    if not (script.get("dessin") or script.get("jeu")):
        return []
    exprs = []
    for s in script.get("scenes", []):
        if script.get("jeu"):       # jeu video : l'expression est ecrite avec la replique
            exprs += [r.get("expr") for r in s.get("repliques", []) if r.get("texte", "").strip()]
            continue
        parler = [a for a in (s.get("dessin") or {}).get("actions", []) if a.get("action") == "parler"]
        repliques = [a for a in s.get("repliques", []) if a.get("texte", "").strip()]
        exprs += [(parler[k].get("expr") if k < len(parler) else None) for k in range(len(repliques))]
    return exprs
