"""
Genere la voix off (TTS) via l'API Gemini et convertit le PCM brut en MP3 avec FFmpeg.

Usage:
    python 2_generate_voice.py --scripts output/scripts.json --voice Kore --out output/audio

Nécessite GEMINI_API_KEY. Nécessite ffmpeg installé sur la machine.
"""
import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import google.generativeai as genai

# Voix disponibles cote Gemini TTS (exemples courants a adapter selon la doc a jour)
VOICES = ["Kore", "Puck", "Enceladus", "Aoede", "Zephyr"]


def script_to_text(script: dict) -> str:
    """Assemble hook/probleme/demo/cta en un seul texte a lire."""
    parts = [script.get("hook", ""), script.get("probleme", ""),
              script.get("demo", ""), script.get("cta", "")]
    return " ".join(p for p in parts if p)


def synthesize(model, text: str, voice: str, pcm_path: Path):
    """Appelle l'API Gemini TTS et ecrit le flux audio en wav (PCM 24kHz 16-bit mono)."""
    response = model.generate_content(
        f"[style: chaleureux, dynamique, rythme rapide pour reseaux sociaux] {text}",
        generation_config={"response_modalities": ["AUDIO"],
                            "speech_config": {"voice_config": {
                                "prebuilt_voice_config": {"voice_name": voice}}}},
    )
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    with wave.open(str(pcm_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(24000)
        wf.writeframes(audio_data)


def convert_to_mp3(wav_path: Path, mp3_path: Path):
    """Convertit le wav en mp3 pret pour montage FFmpeg / compatible TikTok-Reels."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)],
        check=True, capture_output=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripts", type=str, default="output/scripts.json")
    parser.add_argument("--voice", type=str, default="Kore", choices=VOICES)
    parser.add_argument("--out", type=str, default="output/audio")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERREUR: variable d'environnement GEMINI_API_KEY manquante", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")  # a adapter vers le modele TTS dispo sur ton compte

    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, script in enumerate(scripts, 1):
        text = script_to_text(script)
        if not text:
            print(f"[{i}] script vide, ignore")
            continue

        wav_path = out_dir / f"reel_{i:02d}.wav"
        mp3_path = out_dir / f"reel_{i:02d}.mp3"

        print(f"[{i}/{len(scripts)}] Synthese voix ({args.voice})...")
        try:
            synthesize(model, text, args.voice, wav_path)
            convert_to_mp3(wav_path, mp3_path)
            print(f"    -> {mp3_path}")
        except Exception as e:
            print(f"    ERREUR sur le script {i}: {e}", file=sys.stderr)

    print("Termine.")


if __name__ == "__main__":
    main()
