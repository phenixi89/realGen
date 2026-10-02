# realGen — consignes pour Claude

Pipeline de reels TikTok/Instagram pour OpusCV (acquisition organique). Documentation
utilisateur : `README.md`.

## Règle permanente : documentation à jour

**Chaque modification (code, catalogue `catalog/*.json`, gabarits `assets/anim/`, workflow,
console `docs/`) met à jour `README.md` dans le même commit** : nouvelle option, nouveau
format/thème/ambiance, changement de comportement ou de valeur par défaut, règle de montage.
Si la modification change une consigne de ce fichier, mettre aussi à jour `CLAUDE.md`.
Avant de commiter, relire les passages du README concernés et retirer ce qui est devenu faux.

## Conventions

- Commits directement sur `main` (autorisé), puis pousser aussi sur la branche de travail de la
  session. Messages de commit en français.
- Échanges avec l'utilisateur en français.
- Textes affichés dans les vidéos (prompts, cartes, sous-titres) en français accentué.
- Vérifications avant commit : `python -m py_compile scripts/*.py` et `python scripts/catalog.py`
  (mêmes contrôles que `.github/workflows/test.yml`).
- Enrichir le catalogue = éditer `catalog/*.json` (aucun code) ; documenter les champs dans le
  `_doc` du fichier et dans le README. Un nouveau thème, décor, personnage, voix ou ambiance a un aperçu
  dans la console : relancer `python scripts/apercus.py` et committer `docs/apercus/`.
- Icônes dessinables : `assets/anim/icones.js` (JSON strict après `window.ICONES = `, lu aussi par
  `catalog.py`). Nouveau gabarit dessiné : s'appuyer sur `assets/anim/sketch.js`. Tout instant
  d'animation repris par `scripts/sound_design.py` doit rester identique des deux côtés.
- Dessin animé (`assets/anim/scene.html`) : un type (personnage, animal, objet, décor, fond) = un
  `Dessin.enregistrer` dans `assets/anim/dessin/*.js` **et** une entrée dans `catalog/dessins.json`
  (`catalog.py` vérifie la correspondance). Penser par objet, pas par scène ; touches de couleur légères
  (lavis) plutôt qu'aplats. Une action qui fait du bruit le signale avec `Dessin.son(nom, t)` (nom déclaré dans
  `catalog/audio.json` "bruitages" et produit par `scripts/audio_gen.py`).
- Dessin animé, règles d'écriture et de mise en scène (contrôlées dans `1_generate_script.py`, détail
  dans le README « Format `dessin_anime` ») :
  - deux personnages parlent au plus par reel (voix Gemini multi-locuteurs) ; l'appel à l'action est dit
    par un personnage `principal` (Léa ou Karim) ;
  - une scène = un lieu et un moment : même décor sans `ellipse` = même scène (fusionnée) ; les plans
    varient avec la caméra ;
  - les répliques sont dites à voix haute : pas de « POV » ni de code des réseaux ; une accroche qui ne se
    dit pas porte `"dessin": false` dans `hooks.json` ;
  - aucune fonction ni chiffre de performance inventé sur OpusCV dans la bouche d'un personnage ;
  - rien ne cache la scène : les bulles passent au-dessus des têtes, les gros plans (inserts) sous la
    zone des bulles, le nuage de pensée du côté libre ; aucun son au changement de scène.
- Sons enregistrés (`assets/sfx/`) : licence CC0 uniquement, source notée dans `assets/sfx/LICENCES.md`.
- Polices : uniquement sous licence libre (OFL), licence copiée dans `assets/fonts/`.
- Après un run du workflow `generate-reels.yml`, l'analyse se fait sur l'artefact `output`
  (images extraites des reels, loudness mesurée avec `ffmpeg -af ebur128`, cible -14 LUFS).

## Points ouverts (décisions utilisateur en attente)

- Format `temoignage_produit` : ajouter la mention « histoire illustrative » ou le retirer.
- Publication automatique après validation, reportée par l'utilisateur : workflow « TikTok : autoriser »
  (échange du code OAuth, `TIKTOK_REFRESH_TOKEN` écrit via `SECRETS_PAT`) et workflow « Publier un reel »
  (Instagram API with Instagram Login, brouillon TikTok `video.upload`, mention contenu IA, rafraîchissement
  des jetons, bouton dans la console). Les jetons ne passent jamais par le chat : secrets GitHub seulement.

## Décisions prises

- Domaines : `opuscv.tech` (`PRODUCT_CONTEXT`, bio) et `opuscv.fr` (watermark) sont conservés tous les deux, volontairement.
- Voix : `gemini-3.8-flash-tts` avec un ton par réplique (choisi à l'écoute), secours
  `gemini-3.1-flash-tts-preview` (également apprécié).
- Dessin animé = série « Karim cherche un job » (épisodes numérotés, résumés gardés dans l'historique),
  une trame d'histoire par épisode, chute obligatoire avant l'appel à l'action.
