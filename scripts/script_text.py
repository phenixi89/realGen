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
