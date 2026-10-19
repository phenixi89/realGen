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
import subprocess
import sys
from pathlib import Path

from script_text import scene_texts, script_to_text

# Temps de reflexion (config de la chaine « pause_reflexion_s », Objectif Civique) : apres une scene qui pose une
# question (carte de ces types, ou scene suivie d'un verdict VRAI / FAUX), un silence est insere dans la voix ; la carte
# y fait son compte a rebours et ne revele la reponse qu'a la fin (run 93 : la reponse s'allumait avant meme que la
# voix ait lu les choix, le spectateur n'avait pas le temps de chercher).
CARTES_QUESTION = ("quiz", "qcm", "duel", "intrus", "indices", "relier")

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
    end_total = max(audio_duration, aligned[-1]["end"] if aligned else 0.0)
    for k, (a, _) in enumerate(ranges):
        start = 0.0 if k == 0 else max(starts[-1] + 0.3, aligned[a]["start"] - SCENE_LEAD_S)
        starts.append(start)
    items = []
    for k, scene in enumerate(scenes):
        end = starts[k + 1] if k + 1 < len(scenes) else end_total
        item = {"feature": scene.get("feature"), "start": round(starts[k], 3),
                "end": round(end, 3), "texte": scene["texte"]}
        if scene.get("repliques"):
            item["repliques"] = replique_times(aligned, ranges[k][0], scene["repliques"])
        items.append(item)
    return {"duration": round(end_total, 3), "scenes": items}


def replique_times(aligned: list[dict], first: int, repliques: list[dict]) -> list[dict]:
    """
    Dessin anime : quand chaque replique est dite (premier mot -> dernier mot) ; le texte
    de la scene est la suite exacte de ses repliques (1_generate_script.py).
    """
    out, pos = [], first
    for r in repliques:
        n = len(r["texte"].split())
        words = aligned[pos:pos + n]
        if words:
            out.append({"qui": r["qui"], "start": round(words[0]["start"], 3), "end": round(words[-1]["end"], 3)})
        pos += n
    return out


def scenes_a_reflexion(scenes: list[dict]) -> list[int]:
    """Rangs des scenes suivies d'un temps de reflexion : carte question, ou scene suivante qui tranche (verdict)."""
    return [k for k in range(len(scenes) - 1)
            if (scenes[k].get("carte") or {}).get("type") in CARTES_QUESTION or (scenes[k + 1].get("carte") or {}).get("verdict")]


def lire_pcm(audio: Path):
    """-> (echantillons int16 [n, canaux], frequence) de l'audio."""
    import numpy as np
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                      "stream=sample_rate,channels", "-of", "json", str(audio)],
                                     capture_output=True, text=True, check=True).stdout)["streams"][0]
    sr, ch = int(info["sample_rate"]), int(info["channels"])
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", str(ch), "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.int16).reshape(-1, ch), sr


def instant_le_plus_calme(x, sr: int, a: float, b: float, marge: float = 0.12) -> float:
    """
    Garde-fou de la coupure : l'instant le plus silencieux (fenetres de 20 ms) entre la fin du dernier mot (a) et le
    debut du suivant (b), elargi de « marge » de chaque cote (Whisper se trompe de quelques centiemes) : on ne coupe
    jamais dans un mot.
    """
    import numpy as np
    pas = int(0.02 * sr)
    i0, i1 = max(int((min(a, b) - marge) * sr), 0), min(int((max(a, b) + marge) * sr), len(x))
    if i1 - i0 < 2 * pas:
        return (a + b) / 2
    m = x[i0:i1].astype(np.float32).mean(axis=1)
    n = (len(m) - pas) // (pas // 2) + 1
    energie = [float(np.sqrt(np.mean(m[k * (pas // 2):k * (pas // 2) + pas] ** 2))) for k in range(n)]
    k = int(np.argmin(energie))
    return (i0 + k * (pas // 2) + pas / 2) / sr


def inserer_silences(audio: Path, points: list[tuple[float, float]], pcm=None):
    """Insere dans l'audio (mp3 mono ou stereo) un silence de duree d a chaque instant t ((t, d) croissants), sur place."""
    import numpy as np
    x, sr = pcm or lire_pcm(audio)
    ch = x.shape[1]
    morceaux, prec = [], 0
    for t, d in points:
        i = min(max(int(t * sr), prec), len(x))
        morceaux += [x[prec:i], np.zeros((int(d * sr), ch), dtype=np.int16)]
        prec = i
    morceaux.append(x[prec:])
    tmp = audio.with_name(audio.stem + ".pause" + audio.suffix)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ac", str(ch), "-ar", str(sr), "-i", "-",
                    "-codec:a", "libmp3lame", "-qscale:a", "2", str(tmp)], input=np.concatenate(morceaux).tobytes(), check=True)
    tmp.replace(audio)


def reflexion_deja_faite(audio: Path) -> dict[int, float] | None:
    """Silences deja inseres dans CET audio (trace reel_XX.reflexion.json a la date de l'audio), sinon None."""
    trace = audio.with_name(audio.stem + ".reflexion.json")
    if not trace.exists():
        return None
    deja = json.loads(trace.read_text(encoding="utf-8"))
    return {int(k): v for k, v in deja["pauses"].items()} if abs(deja.get("mtime", 0) - audio.stat().st_mtime) < 1e-3 else None


def appliquer_reflexion(audio: Path, aligned: list[dict], scenes: list[dict], pause_s: float,
                        dans_audio: bool = False) -> dict[int, float]:
    """
    Temps de reflexion : silence insere apres le dernier mot de chaque scene a question (entre lui et le mot suivant),
    timings des mots suivants decales d'autant. Fait une seule fois par synthese : la trace (reel_XX.reflexion.json, a
    cote de l'audio, avec la date de l'audio) evite de rallonger deux fois le meme audio quand l'etape est refaite.
    dans_audio : silences deja dans l'audio, seuls les timings sont decales (timing calcule, mode sans voix).
    -> {rang de scene: duree du silence}.
    """
    rangs = scenes_a_reflexion(scenes)
    trace = audio.with_name(audio.stem + ".reflexion.json")
    if not rangs or pause_s <= 0:
        return {}
    ranges = scene_ranges([len(sc["texte"].split()) for sc in scenes])
    pcm = None if dans_audio else lire_pcm(audio)
    points = []
    for k in rangs:
        fin = ranges[k][1]
        if not 0 < fin < len(aligned):
            continue
        a, b = aligned[fin - 1]["end"], aligned[fin]["start"]   # entre le dernier mot de la scene et le suivant
        t = (a + b) / 2 if pcm is None else instant_le_plus_calme(*pcm, a, b)
        points.append((t, pause_s))
    for t, d in points:   # decale les mots qui suivent chaque silence
        for w in aligned:
            if w["start"] >= t:
                w["start"] += d
                w["end"] += d
    if not points:
        return {}
    if dans_audio:
        return {k: pause_s for k in rangs[:len(points)]}
    inserer_silences(audio, points, pcm)
    pauses = {k: pause_s for k in rangs[:len(points)]}
    trace.write_text(json.dumps({"mtime": audio.stat().st_mtime, "pauses": pauses}), encoding="utf-8")
    print(f"Temps de reflexion : {len(points)} silence(s) de {pause_s} s apres les scenes {[k + 1 for k in pauses]}")
    return pauses


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
    scenes = [{"feature": s.get("feature"), "texte": s["texte"], "carte": s.get("carte"),
               **({"repliques": s["repliques"]} if s.get("repliques") else {})} for s in script.get("scenes", [])
              if s.get("texte", "").strip()] or [{"feature": None, "texte": t} for t in scene_texts(script)]
    reference_words = script_to_text(script).split()

    deja = reflexion_deja_faite(Path(args.audio))   # silences de reflexion deja inseres dans cet audio
    if args.synthetic:
        from moviepy import AudioFileClip
        clip = AudioFileClip(args.audio)
        audio_duration = clip.duration
        clip.close()
        # Audio deja rallonge : le timing calcule l'est sur la voix seule, les silences sont decales ensuite.
        aligned = synthetic_timing(reference_words, audio_duration - sum((deja or {}).values()))
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

    # Temps de reflexion apres les questions (chaine a « pause_reflexion_s ») : l'audio est rallonge, la timeline le sait.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import catalog
    if script.get("chaine") in catalog.chaines():
        catalog.set_chaine(script["chaine"])
    pause_s = float(catalog.config().get("pause_reflexion_s") or 0)
    if deja is not None and not args.synthetic:
        pauses = deja   # Whisper a mesure l'audio rallonge : les silences sont deja dans ses timings
    elif pause_s or deja:
        pauses = appliquer_reflexion(Path(args.audio), aligned, scenes, pause_s or max(deja.values()), dans_audio=deja is not None)
        if deja is None:
            audio_duration += sum(pauses.values())
    else:
        pauses = {}

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
        for k, d in pauses.items():   # la carte de cette scene fait son compte a rebours pendant le silence
            timeline["scenes"][k]["reflexion"] = d
        timeline_path.parent.mkdir(parents=True, exist_ok=True)
        timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK -> {timeline_path} ({len(timeline['scenes'])} scenes, {timeline['duration']}s)")
        for s in timeline["scenes"]:
            print(f"   {s['start']:6.2f}-{s['end']:6.2f}s  {s['feature'] or '-':18} {s['texte'][:50]}")


if __name__ == "__main__":
    main()
