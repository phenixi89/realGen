"""
Genere la voix off (TTS) via l'API Gemini et convertit le PCM brut en MP3 avec FFmpeg.

Usage:
    python 2_generate_voice.py --scripts output/scripts.json --voice Kore --out output/audio
    python 2_generate_voice.py --precompute-cta        # enregistre les phrases de CTA (assets/voix_cta/)

Phrase de CTA enregistree (derniere scene "cta_enregistre", catalog/config.json) : elle
n'est pas resynthetisee a chaque reel ; son enregistrement pour la voix du reel (ou du
personnage qui la dit) est colle a la fin, au meme volume que le reste. Enregistrements
cherches dans assets/voix_cta/ (versionnes), sinon dans <out>/../voix_cta/ (cache, cree
au premier besoin et garde d'un run a l'autre par le cache de la CI).

Nécessite GEMINI_API_KEY. Nécessite ffmpeg installé sur la machine.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import wave
from pathlib import Path


from gemini_retry import generate_with_retry
import catalog
from script_text import dialogue_lines, script_to_text

CTA_DIR = Path(__file__).resolve().parent.parent / "assets" / "voix_cta"
CTA_PAUSE_S = 0.3   # silence entre le corps du texte et la phrase de CTA enregistree
SR_TTS = 24000

# Voix disponibles cote Gemini TTS (exemples courants a adapter selon la doc a jour)
VOICES = ["Kore", "Puck", "Enceladus", "Aoede", "Zephyr"]

TTS_MODEL_NAME = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")


DEFAULT_TONE = "chaleureux, dynamique, rythme rapide pour réseaux sociaux"
# Mode sans voix : duree de lecture du texte a l'ecran (mots par seconde).
SILENT_WPS = 3.0


def synthesize(client, text: str, voice: str, pcm_path: Path, tone: str = DEFAULT_TONE):
    """Appelle l'API Gemini TTS et ecrit le flux audio en wav (PCM 24kHz 16-bit mono)."""
    from google.genai import types

    response = generate_with_retry(
        client, model=TTS_MODEL_NAME, label="Gemini TTS",
        contents=f"[style: {tone}] {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    with wave.open(str(pcm_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(24000)
        wf.writeframes(audio_data)


def synthesize_dialogue(client, lines: list[tuple[str, str]], voices: dict[str, str], pcm_path: Path,
                        tone: str = DEFAULT_TONE):
    """
    Dessin anime : toutes les repliques en UN seul appel, une voix par personnage
    (Gemini TTS multi-locuteurs, 2 voix au plus ; un seul personnage -> voix simple).
    Les noms de locuteurs (Lea:, Karim:) guident le TTS et ne sont pas lus.
    """
    from google.genai import types

    speakers = list(dict.fromkeys(qui for qui, _ in lines))
    if len(speakers) > 2:
        raise ValueError(f"Gemini TTS : 2 voix au plus par dialogue, recu {speakers}")
    label = {qui: qui.capitalize() for qui in speakers}
    script = "\n".join(f"{label[qui]}: {texte}" for qui, texte in lines)
    if len(speakers) == 1:
        voice_config = types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voices[speakers[0]])))
    else:
        voice_config = types.SpeechConfig(multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[types.SpeakerVoiceConfig(
                speaker=label[qui], voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voices[qui])))
                for qui in speakers]))
    names = " and ".join(label[q] for q in speakers)
    response = generate_with_retry(
        client, model=TTS_MODEL_NAME, label="Gemini TTS (dialogue)",
        # Consigne au format de la doc Gemini : une consigne libre en francais a deja
        # inverse les voix des deux personnages (verifie a l'ecoute).
        contents=f"TTS the following conversation between {names}, in French "
                 f"(style: {tone}; short pause between lines):\n{script}",
        config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=voice_config),
    )
    audio_data = response.candidates[0].content.parts[0].inline_data.data
    with wave.open(str(pcm_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_data)


def synthesize_lines(client, lines: list[tuple[str, str]], voices: dict[str, str], pcm_path: Path,
                     tone: str = DEFAULT_TONE):
    """Repli : une synthese par replique, chacune avec la voix de son personnage, mises bout a bout."""
    import numpy as np
    parts = []
    for n, (qui, texte) in enumerate(lines):
        tmp = pcm_path.with_suffix(f".l{n}.wav")
        synthesize(client, texte, voices[qui], tmp, tone)
        parts += [_pcm(tmp), np.zeros(int(0.25 * SR_TTS))]
        tmp.unlink()
    with wave.open(str(pcm_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR_TTS)
        wf.writeframes(np.clip(np.concatenate(parts[:-1]), -32768, 32767).astype(np.int16).tobytes())


def cta_filename(voice: str, phrase: str) -> str:
    """Un enregistrement par (voix, phrase exacte) : changer la phrase en cree un autre."""
    return f"{voice}_{hashlib.sha1(phrase.encode('utf-8')).hexdigest()[:10]}.ogg"


def cta_clip(client, voice: str, phrase: str, cache_dir: Path) -> Path:
    """Enregistrement de la phrase de CTA pour cette voix : versionne, en cache, sinon synthetise une fois."""
    name = cta_filename(voice, phrase)
    for folder in (CTA_DIR, cache_dir):
        if (folder / name).exists():
            return folder / name
    if client is None:
        raise RuntimeError(f"enregistrement du CTA absent ({name}) et pas de client Gemini")
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav = cache_dir / (name + ".wav")
    print(f"    CTA « {phrase} » ({voice}) : enregistrement unique -> {cache_dir / name}")
    synthesize(client, phrase, voice, wav, catalog.default_tone())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis", "-q:a", "5",
                    str(cache_dir / name)], check=True)
    wav.unlink()
    return cache_dir / name


def _pcm(path: Path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1",
                          "-ar", str(SR_TTS), "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64)


def append_cta(body_wav: Path, clip: Path, out_wav: Path):
    """Corps + courte pause + CTA enregistre, le CTA ramene au volume de la voix du reel (RMS des passages parles)."""
    import numpy as np
    body, cta = _pcm(body_wav), _pcm(clip)

    def level(x):
        frames = x[: len(x) // 480 * 480].reshape(-1, 480)
        rms = np.sqrt((frames ** 2).mean(axis=1))
        voiced = rms[rms > rms.max() * 0.1]
        return float(np.sqrt((voiced ** 2).mean())) if len(voiced) else 1.0

    cta = cta * (level(body) / level(cta))
    out = np.concatenate([body, np.zeros(int(CTA_PAUSE_S * SR_TTS)), cta])
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR_TTS)
        wf.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes())


def precompute_cta(client):
    """Enregistre chaque phrase de CTA du catalogue pour chaque voix (rotation + personnages) dans assets/voix_cta/."""
    cfg = catalog.config()
    phrases = list(dict.fromkeys(p for k in ("ctas_conseil", "ctas_produit") for p in cfg.get(k) or []))
    voices = list(dict.fromkeys([v["id"] for v in catalog.voices()] + [p["voix"] for p in catalog.personnages().values()]))
    for voice in voices:
        for phrase in phrases:
            if (CTA_DIR / cta_filename(voice, phrase)).exists():
                continue
            path = cta_clip(client, voice, phrase, CTA_DIR)
            print(f"OK -> {path}")


def convert_to_mp3(wav_path: Path, mp3_path: Path):
    """Convertit le wav en mp3 pret pour montage FFmpeg / compatible TikTok-Reels."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)],
        check=True, capture_output=True,
    )


def write_silence(text: str, mp3_path: Path):
    """Mode sans voix : piste muette de la duree de lecture du texte (sous-titres seuls)."""
    duration = len(text.split()) / SILENT_WPS + 1.0
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{duration:.2f}",
                    "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", type=str, default="output/scripts.json")
    parser.add_argument("--voice", type=str, default="auto",
                         help="Voix Gemini (ex: Kore, Puck...) ; 'auto' = celle choisie pour chaque reel "
                              "(catalog/voix.json), Kore a defaut")
    parser.add_argument("--silent", action="store_true",
                         help="Sans voix : piste muette de la duree de lecture (texte a l'ecran uniquement)")
    parser.add_argument("--out", type=str, default="output/audio")
    parser.add_argument("--force", action="store_true",
                         help="Regenere meme si le mp3 existe deja pour un reel")
    parser.add_argument("--index", type=int, default=0, help="Seulement ce reel (1 = le premier) ; 0 = tous")
    parser.add_argument("--par-replique", action="store_true",
                        help="Dessin anime : une synthese par replique au lieu d'un seul appel multi-locuteurs "
                             "(repli quand Gemini a confondu les voix, cf. voix_controle.py)")
    parser.add_argument("--precompute-cta", action="store_true",
                         help="Enregistre les phrases de CTA du catalogue pour chaque voix (assets/voix_cta/), puis s'arrete")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.silent:
        print("ERREUR: variable d'environnement GEMINI_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    client = None
    if not args.silent:  # import tardif : le mode sans voix n'a pas besoin du SDK Gemini
        from google import genai
        client = genai.Client(api_key=api_key)

    if args.precompute_cta:
        precompute_cta(client)
        return

    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, script in enumerate(scripts, 1):
        if args.index and i != args.index:
            continue
        text = script_to_text(script)
        if not text:
            print(f"[{i}] script vide, ignore")
            continue
        voice = script.get("voix") or "Kore" if args.voice == "auto" else args.voice
        tone = script.get("ton") or DEFAULT_TONE
        # Dessin anime : une voix par personnage (catalog/dessins.json "voix"), un seul appel.
        lines = dialogue_lines(script)
        voices = script.get("voix_personnages") or {}
        if lines:
            voice = " / ".join(f"{q}={voices.get(q, '?')}" for q in dict.fromkeys(q for q, _ in lines))
            text_key = "\n".join(f"{q}: {t}" for q, t in lines)
        else:
            text_key = text
        # CTA enregistre : derniere scene dite par l'enregistrement de la voix (du personnage) qui la porte.
        last = (script.get("scenes") or [{}])[-1]
        cta_voice = None
        if last.get("cta_enregistre") and len(script.get("scenes", [])) > 1:
            cta_voice = voices.get(lines[-1][0]) if lines else voice
            text_key += f"\n[cta enregistre : {cta_filename(cta_voice, last['texte'].strip())}]"
        # Empreinte = tout ce qui change le son : texte, voix, ton (ou silence).
        fingerprint = f"[silence]\n{text}" if args.silent else f"[{voice} | {tone}]\n{text_key}"

        wav_path = out_dir / f"reel_{i:02d}.wav"
        mp3_path = out_dir / f"reel_{i:02d}.mp3"
        # Sidecar avec le texte exact ayant produit ce mp3 : 1_generate_script.py
        # peut regenerer scripts.json (ex: --n augmente) sans qu'on force ce
        # script-ci -- sans ce fingerprint, un mp3 d'un texte perime serait
        # reutilise tel quel (sous-titres corrects, mais voix qui dit autre
        # chose), un bug de sync bien pire qu'un simple decalage de timing.
        text_path = out_dir / f"reel_{i:02d}.txt"
        up_to_date = mp3_path.exists() and text_path.exists() and text_path.read_text(encoding="utf-8") == fingerprint

        if not args.force and up_to_date:
            print(f"[{i}/{len(scripts)}] REPRISE: {mp3_path} existe deja, on saute")
            continue
        if not args.force and mp3_path.exists() and not up_to_date:
            print(f"[{i}/{len(scripts)}] texte modifie depuis la derniere synthese -> regeneration")

        try:
            if args.silent:
                print(f"[{i}/{len(scripts)}] Mode sans voix : piste muette")
                write_silence(text, mp3_path)
            else:
                print(f"[{i}/{len(scripts)}] Synthese voix ({voice}, ton : {tone})...")
                body_lines = lines[:-1] if cta_voice and lines else lines
                body_text = " ".join(s["texte"].strip() for s in script["scenes"][:-1]) if cta_voice else text
                if lines:
                    if args.par_replique:
                        synthesize_lines(client, body_lines, voices, wav_path, tone)
                    else:
                        synthesize_dialogue(client, body_lines, voices, wav_path, tone)
                else:
                    synthesize(client, body_text, voice, wav_path, tone)
                if cta_voice:
                    clip = cta_clip(client, cta_voice, last["texte"].strip(), out_dir.parent / "voix_cta")
                    print(f"    CTA enregistre reutilise : {clip.name}")
                    append_cta(wav_path, clip, wav_path)
                convert_to_mp3(wav_path, mp3_path)
            text_path.write_text(fingerprint, encoding="utf-8")
            print(f"    -> {mp3_path}")
        except Exception as e:
            print(f"    ERREUR sur le script {i}: {e}", file=sys.stderr)

    print("Termine.")


if __name__ == "__main__":
    main()
