# Image du pipeline "Generate Reels" : bundle une bonne fois pour toutes ce
# qui est long a (re)installer a chaque run CI (deps pip dont torch/whisper,
# navigateur Playwright + ses libs systeme, modele Whisper "small" -- ~500Mo
# telecharge au premier usage sinon). Le workflow generate-reels.yml pull
# cette image au lieu de tout reinstaller : seul le code (scripts/) change
# a chaque run, jamais l'image, sauf quand requirements.txt change.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# git : necessaire a actions/checkout, qui s'execute dans ce conteneur.
# curl : etape de warm-up du service de demo dans le workflow.
# ffmpeg + fonts-dejavu-core : assemblage final (5_assemble.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + ses dependances systeme (libs graphiques, etc.), installees une
# seule fois dans l'image plutot qu'a chaque run.
RUN playwright install --with-deps chromium

# Precharge le modele Whisper "small" dans l'image : sinon 4_generate_subtitles.py
# le telecharge (~500 Mo) au premier appel de chaque run.
RUN python -c "import whisper; whisper.load_model('small')"

CMD ["bash"]
