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

from script_text import scene_texts, script_to_text

MAX_WORDS_PER_CUE = 4
DEFAULT_WORD_DURATION = 0.32
SCENE_LEAD_S = 0.15

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


OPENING_PUNCT = {"«", "“", "(", "—", "–"}


def glue_punctuation(words: list[dict]) -> list[dict]:
    """
    Ponctuation isolee par une espace (typographie francaise : « mot », « : »,
    « ? ») -> collee au mot voisin par une espace insecable. Sinon le decoupage
    en cues de quelques mots laisse un « ou un » seul a l'ecran.
    """
    out: list[dict] = []
    pending: dict | None = None  # ponctuation ouvrante en attente du mot suivant
    for w in words:
        text = w["text"]
        is_punct = not any(ch.isalnum() for ch in text)
        if is_punct and text in OPENING_PUNCT:
            pending = {**w, "text": (pending["text"] + "\u00a0" if pending else "") + text}
            continue
        if is_punct and out and not pending:
            out[-1] = {**out[-1], "text": out[-1]["text"] + "\u00a0" + text, "end": w["end"]}
            continue
        if pending:
            w = {**w, "text": pending["text"] + "\u00a0" + text, "start": pending["start"]}
            pending = None
        out.append(w)
    if pending:
        out.append(pending)
    return out


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


def synthetic_timing(reference_words: list[str], audio_duration: float) -> list[dict]:
    """
    Mode sans voix : pas de Whisper, chaque mot recoit une duree de lecture
    proportionnelle a sa longueur (+ pause apres la ponctuation), etalee sur
    toute la piste -- meme format que align_to_reference().
    """
    weights = [0.6 + len(w) * 0.07 + (0.35 if w[-1:] in ".!?:;," else 0) for w in reference_words]
    usable = max(audio_duration - 0.8, 0.5)
    scale = usable / sum(weights)
    words, t = [], 0.3
    for w, weight in zip(reference_words, weights):
        d = weight * scale
        words.append({"text": w, "start": round(t, 3), "end": round(t + d * 0.92, 3)})
        t += d
    return words


def scene_ranges(scene_word_counts: list[int]) -> list[tuple[int, int]]:
    ranges, pos = [], 0
    for count in scene_word_counts:
        ranges.append((pos, pos + count))
        pos += count
    return ranges


def build_timeline(aligned: list[dict], scenes: list[dict], audio_duration: float) -> dict:
    """
    Quand chaque scene est-elle dite dans l'audio : debut = premier mot de
    la scene (un leger temps d'avance pour que l'image arrive avec la voix,
    pas apres), fin = debut de la scene suivante. La premiere scene part de
    0, la derniere va jusqu'au bout de l'audio -- la video couvre donc
    exactement la duree de la voix, sans boucle ni coupure.
    """
    ranges = scene_ranges([len(s["texte"].split()) for s in scenes])
    starts = []
    for k, (a, _) in enumerate(ranges):
        start = 0.0 if k == 0 else max(starts[-1] + 0.3, aligned[a]["start"] - SCENE_LEAD_S)
        starts.append(start)
    end_total = max(audio_duration, aligned[-1]["end"] if aligned else 0.0)
    items = []
    for k, scene in enumerate(scenes):
        end = starts[k + 1] if k + 1 < len(scenes) else end_total
        items.append({"feature": scene.get("feature"), "start": round(starts[k], 3),
                      "end": round(end, 3), "texte": scene["texte"]})
    return {"duration": round(end_total, 3), "scenes": items}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=str, required=True)
    parser.add_argument("--scripts", type=str, required=True, help="output/scripts.json")
    parser.add_argument("--index", type=int, required=True, help="Index 1-based du reel dans scripts.json")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--model", type=str, default="small",
                         help="tiny/base/small (utilise uniquement pour le timing, pas le texte affiche)")
    parser.add_argument("--timeline-out", type=str, default=None,
                         help="Ecrit aussi la timeline des scenes (debut/fin de chaque scene dans l'audio), "
                              "utilisee par le montage pour caler l'image sur la voix")
    parser.add_argument("--synthetic", action="store_true",
                         help="Mode sans voix : timing calcule (lecture a l'ecran), sans Whisper")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si --out existe deja")
    args = parser.parse_args()

    out_path = Path(args.out)
    timeline_path = Path(args.timeline_out) if args.timeline_out else None
    if not args.force and out_path.exists() and (timeline_path is None or timeline_path.exists()):
        print(f"REPRISE: {out_path} existe deja, on saute (--force pour regenerer)")
        return

    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    script = scripts[args.index - 1]
    scenes = [{"feature": s.get("feature"), "texte": s["texte"]} for s in script.get("scenes", [])
              if s.get("texte", "").strip()] or [{"feature": None, "texte": t} for t in scene_texts(script)]
    reference_words = script_to_text(script).split()

    if args.synthetic:
        from moviepy import AudioFileClip
        clip = AudioFileClip(args.audio)
        audio_duration = clip.duration
        clip.close()
        aligned = synthetic_timing(reference_words, audio_duration)
    else:
        import whisper

        print(f"Chargement du modele Whisper '{args.model}'...")
        model = whisper.load_model(args.model)

        print(f"Transcription de {args.audio} (mesure du timing uniquement)...")
        audio = whisper.load_audio(args.audio)
        audio_duration = len(audio) / whisper.audio.SAMPLE_RATE
        result = model.transcribe(audio, language="fr", word_timestamps=True)
        whisper_words = [w for seg in result["segments"] for w in seg.get("words", [])]

        aligned = align_to_reference(whisper_words, reference_words)

    # Cues decoupees scene par scene : un sous-titre ne chevauche jamais une
    # coupe d'image, il change en meme temps que la fonctionnalite montree.
    cues = []
    for a, b in scene_ranges([len(s["texte"].split()) for s in scenes]):
        cues.extend(chunk_words(glue_punctuation(aligned[a:b])))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {out_path}")

    if timeline_path:
        timeline = build_timeline(aligned, scenes, audio_duration)
        timeline_path.parent.mkdir(parents=True, exist_ok=True)
        timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK -> {timeline_path} ({len(timeline['scenes'])} scenes, {timeline['duration']}s)")
        for s in timeline["scenes"]:
            print(f"   {s['start']:6.2f}-{s['end']:6.2f}s  {s['feature'] or '-':18} {s['texte'][:50]}")


if __name__ == "__main__":
    main()
