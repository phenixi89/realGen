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
  `_doc` du fichier et dans le README.
- Icônes dessinables : `assets/anim/icones.js` (JSON strict après `window.ICONES = `, lu aussi par
  `catalog.py`). Nouveau gabarit dessiné : s'appuyer sur `assets/anim/sketch.js`. Tout instant
  d'animation repris par `scripts/sound_design.py` doit rester identique des deux côtés.
- Dessin animé (`assets/anim/scene.html`) : un type (personnage, animal, objet, décor, fond) = un
  `Dessin.enregistrer` dans `assets/anim/dessin/*.js` **et** une entrée dans `catalog/dessins.json`
  (`catalog.py` vérifie la correspondance). Penser par objet, pas par scène ; touches de couleur légères
  (lavis) plutôt qu'aplats.
- Polices : uniquement sous licence libre (OFL), licence copiée dans `assets/fonts/`.
- Après un run du workflow `generate-reels.yml`, l'analyse se fait sur l'artefact `output`
  (images extraites des reels, loudness mesurée avec `ffmpeg -af ebur128`, cible -14 LUFS).

## Points ouverts (décisions utilisateur en attente)

- Format `temoignage_produit` : ajouter la mention « histoire illustrative » ou le retirer.

## Décisions prises

- Domaines : `opuscv.tech` (`PRODUCT_CONTEXT`, bio) et `opuscv.fr` (watermark) sont conservés tous les deux, volontairement.
