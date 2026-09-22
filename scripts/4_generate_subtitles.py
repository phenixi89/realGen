"""
Genere les cues de sous-titres avec timing par mot, en alignant le texte
EXACT du script (celui donne au TTS, scripts.json) sur les timestamps
Whisper -- au lieu d'afficher ce que Whisper croit avoir entendu.

Pourquoi : Whisper sert ici a MESURER LE TIMING, pas a transcrire -- le texte
exact est deja connu (c'est celui qu'on a fait lire au TTS). Utiliser la
sortie texte de Whisper telle quelle important ses erreurs de reconnaissance
dans le sous-titre (ex: "lien en bio" entendu/transcrit "lié en bio") alors
qu'on dispose du texte source parfait. align_to_reference() mappe chaque mot
du script sur le timestamp du mot Whisper correspondant (difflib), et
interpole les rares mots que Whisper a rates ou mal decoupes.

Sort un JSON (pas un .srt/.ass) : 5_assemble.py rend chaque cue lui-meme via
caption_render.py (Pillow) plutot que de passer par un filtre ffmpeg/libass.

Usage:
    python 4_generate_subtitles.py --audio output/audio/reel_01.mp3 \
                                    --scripts output/scripts.json --index 1 \
                                    --out output/subs/reel_01.json
"""
import argparse
import difflib
import json
import re
from pathlib import Path

import whisper

from script_text import script_to_text

MAX_WORDS_PER_CUE = 4
DEFAULT_WORD_DURATION = 0.32

_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def _normalize(word: str) -> str:
    return _PUNCT_RE.sub("", word.strip().lower())


def align_to_reference(whisper_words: list[dict], reference_words: list[str]) -> list[dict]:
    """
    Mappe chaque mot du texte de reference (exact, connu a l'avance) sur le
    timing du mot Whisper correspondant. Les blocs "equal" du diff donnent un
    mapping direct et fiable ; les mots que Whisper a rates/mal reconnus
    (blocs replace/insert/delete) recoivent un timing interpole entre les
    ancres connues avant/apres -- imprecis de quelques centiemes au pire,
    mais jamais le mauvais mot affiche.
    """
    whisper_norm = [_normalize(w["word"]) for w in whisper_words]
    ref_norm = [_normalize(w) for w in reference_words]
    matcher = difflib.SequenceMatcher(None, whisper_norm, ref_norm, autojunk=False)

    n = len(reference_words)
    ref_times: list[tuple[float, float] | None] = [None] * n
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for k in range(i2 - i1):
            w = whisper_words[i1 + k]
            ref_times[j1 + k] = (w["start"], w["end"])

    i = 0
    while i < n:
        if ref_times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and ref_times[j] is None:
            j += 1
        prev_end = ref_times[i - 1][1] if i > 0 else 0.0
        next_start = ref_times[j][0] if j < n else prev_end + DEFAULT_WORD_DURATION * (j - i)
        gap_count = j - i
        span = max(next_start - prev_end, 0.05)
        step = span / gap_count
        for k in range(gap_count):
            ref_times[i + k] = (prev_end + step * k, prev_end + step * (k + 1))
        i = j

    return [
        {"text": reference_words[idx], "start": ref_times[idx][0], "end": ref_times[idx][1]}
        for idx in range(n)
    ]


def chunk_words(words: list[dict], max_words: int = MAX_WORDS_PER_CUE) -> list[dict]:
    """
    Regroupe les mots en cues courtes -- une phrase entiere en une seule cue
    forcait soit un texte minuscule pour tenir dans la largeur du cadre, soit
    un debordement hors ecran a taille lisible. 3-4 mots par cue est le
    standard Reels/TikTok.
    """
    cues = []
    for i in range(0, len(words), max_words):
        group = words[i:i + max_words]
        cues.append({"start": group[0]["start"], "end": group[-1]["end"], "words": group})
    return cues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--scripts", type=str, required=True, help="output/scripts.json")
    parser.add_argument("--index", type=int, required=True, help="Index 1-based du reel dans scripts.json")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--model", type=str, default="small",
                         help="tiny/base/small (utilise uniquement pour le timing, pas le texte affiche)")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not args.force and out_path.exists():
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour regenerer)")
        return

    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    reference_text = script_to_text(scripts[args.index - 1])
    reference_words = reference_text.split()

    print(f"Chargement du modele Whisper '{args.model}'...")
    model = whisper.load_model(args.model)

    print(f"Transcription de {args.audio} (mesure du timing uniquement)...")
    result = model.transcribe(args.audio, language="fr", word_timestamps=True)
    whisper_words = [w for seg in result["segments"] for w in seg.get("words", [])]

    aligned = align_to_reference(whisper_words, reference_words)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chunk_words(aligned), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path}")


if __name__ == "__main__":
    main()
