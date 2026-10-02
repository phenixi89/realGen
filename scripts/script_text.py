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
    if not script.get("dessin"):
        return []
    return [(a["qui"], a["texte"].strip()) for s in script.get("scenes", []) for a in s.get("repliques", [])
            if a.get("texte", "").strip()]
