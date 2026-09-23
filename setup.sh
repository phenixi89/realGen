#!/usr/bin/env bash
# Installation et lancement en local du pipeline reel-generation.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d venv ]; then
    python3 -m venv venv
fi

source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ATTENTION: ffmpeg n'est pas installé sur cette machine (brew install ffmpeg / apt install ffmpeg)"
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Fichier .env créé à partir de .env.example — renseigne tes variables avant de relancer."
    exit 1
fi

set -a
source .env
set +a

echo "Environnement prêt. Exemple de lancement :"
echo "  python scripts/run_pipeline.py --n 3 --saas-url \"\${SAAS_URL}\" --voice Kore"
