// Icones dessinees a la main (cartes "schema", cf. sketch.js) : chaque icone
// est une liste de traits SVG (attribut "d") dans une boite 100x100, traces
// dans l'ordre. Le contenu entre "window.ICONES = " et le ";" final est du
// JSON strict : scripts/catalog.py le lit pour valider les cartes et lister
// les icones dans le prompt. Ajouter une icone = ajouter une entree ici.
window.ICONES = {
  "cv": {"nom": "un CV / document", "d": ["M22 8 H62 L78 24 V92 H22 Z", "M62 8 V24 H78", "M32 34 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0", "M54 30 H70", "M54 38 H66", "M30 54 H70", "M30 64 H70", "M30 74 H58"]},
  "robot": {"nom": "le logiciel ATS / un robot", "d": ["M24 34 H76 V78 H24 Z", "M50 34 V20", "M45 14 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0", "M33 50 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0", "M57 50 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0", "M36 66 H64", "M24 50 H16 V62 H24", "M76 50 H84 V62 H76"]},
  "poubelle": {"nom": "la poubelle (rejeté)", "d": ["M20 24 H80", "M40 24 V16 H60 V24", "M26 24 L32 90 H68 L74 24", "M42 36 L44 80", "M58 36 L56 80"]},
  "loupe": {"nom": "une loupe (analyse, lecture)", "d": ["M18 42 a24 24 0 1 0 48 0 a24 24 0 1 0 -48 0", "M60 60 L86 86"]},
  "cible": {"nom": "une cible (viser juste, offre ciblée)", "d": ["M14 50 a36 36 0 1 0 72 0 a36 36 0 1 0 -72 0", "M28 50 a22 22 0 1 0 44 0 a22 22 0 1 0 -44 0", "M42 50 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0", "M50 50 L86 14", "M76 14 H86 V24"]},
  "horloge": {"nom": "une horloge (temps, secondes)", "d": ["M12 50 a38 38 0 1 0 76 0 a38 38 0 1 0 -76 0", "M50 50 V26", "M50 50 L66 60"]},
  "ampoule": {"nom": "une ampoule (idée, astuce)", "d": ["M36 64 C20 50 26 16 50 16 C74 16 80 50 64 64 V72 H36 Z", "M38 80 H62", "M42 88 H58", "M50 4 V9", "M14 28 L20 31", "M86 28 L80 31"]},
  "enveloppe": {"nom": "un e-mail / une candidature envoyée", "d": ["M14 28 H86 V76 H14 Z", "M14 28 L50 56 L86 28"]},
  "bulle": {"nom": "une bulle (message, réponse)", "d": ["M16 20 H84 V66 H44 L28 82 V66 H16 Z", "M36 44 h1", "M50 44 h1", "M64 44 h1"]},
  "personne": {"nom": "le candidat / une personne", "d": ["M36 32 a14 14 0 1 0 28 0 a14 14 0 1 0 -28 0", "M20 90 C20 60 80 60 80 90"]},
  "recruteur": {"nom": "le recruteur (personne en cravate)", "d": ["M36 28 a14 14 0 1 0 28 0 a14 14 0 1 0 -28 0", "M18 92 C18 58 82 58 82 92", "M50 60 L44 70 L50 88 L56 70 Z"]},
  "graphique": {"nom": "une courbe qui monte (progression)", "d": ["M14 12 V86 H90", "M22 72 L40 52 L54 62 L80 28", "M68 28 H80 V40"]},
  "etoile": {"nom": "une étoile (point fort, excellence)", "d": ["M50 10 L61 38 L90 38 L66 56 L75 86 L50 68 L25 86 L34 56 L10 38 L39 38 Z"]},
  "fusee": {"nom": "une fusée (décoller, accélérer)", "d": ["M50 8 C68 24 70 50 62 70 H38 C30 50 32 24 50 8 Z", "M43 38 a7 7 0 1 0 14 0 a7 7 0 1 0 -14 0", "M38 56 L24 76 L38 72", "M62 56 L76 76 L62 72", "M44 76 L50 92 L56 76"]},
  "cle": {"nom": "une clé (la clé, le secret)", "d": ["M16 50 a14 14 0 1 0 28 0 a14 14 0 1 0 -28 0", "M44 50 H88", "M74 50 V62", "M84 50 V60"]},
  "valise": {"nom": "une mallette (le poste, le job)", "d": ["M12 32 H88 V84 H12 Z", "M38 32 V22 H62 V32", "M12 52 H88", "M46 52 V60 H54 V52"]},
  "calendrier": {"nom": "un calendrier (délai, jour J)", "d": ["M14 22 H86 V88 H14 Z", "M14 38 H86", "M32 14 V28", "M68 14 V28", "M36 62 L46 72 L66 50"]},
  "coche": {"nom": "une grande coche (validé)", "d": ["M16 52 L40 76 L86 24"]},
  "croix": {"nom": "une grande croix (refusé, erreur)", "d": ["M22 22 L78 78", "M78 22 L22 78"]},
  "oeil": {"nom": "un œil (ce qui est vu, lu)", "d": ["M8 50 C28 18 72 18 92 50 C72 82 28 82 8 50 Z", "M38 50 a12 12 0 1 0 24 0 a12 12 0 1 0 -24 0"]},
  "entonnoir": {"nom": "un entonnoir (le filtre, le tri)", "d": ["M10 16 H90 L60 52 V80 L40 92 V52 Z", "M22 28 H78"]},
  "telephone": {"nom": "un smartphone (appel, message)", "d": ["M30 6 H70 V94 H30 Z", "M44 14 H56", "M47 84 H53"]},
  "trophee": {"nom": "un trophée (réussite, décrocher)", "d": ["M30 12 H70 V34 C70 56 30 56 30 34 Z", "M30 20 H16 C16 36 24 42 32 42", "M70 20 H84 C84 36 76 42 68 42", "M50 54 V70", "M34 84 H66 V70 H34 Z"]},
  "crayon": {"nom": "un crayon (rédiger, réécrire)", "d": ["M18 82 L22 64 L68 18 L82 32 L36 78 Z", "M22 64 L36 78", "M60 26 L74 40"]},
  "sablier": {"nom": "un sablier (attente, temps perdu)", "d": ["M26 8 H74", "M26 92 H74", "M32 8 C32 36 50 40 50 50 C50 60 32 64 32 92", "M68 8 C68 36 50 40 50 50 C50 60 68 64 68 92", "M40 84 H60"]},
  "coeur": {"nom": "un cœur (motivation, envie)", "d": ["M50 86 C18 62 8 42 18 28 C28 14 46 18 50 32 C54 18 72 14 82 28 C92 42 82 62 50 86 Z"]},
  "question": {"nom": "un point d'interrogation (doute)", "d": ["M32 32 C32 10 68 10 68 32 C68 48 50 48 50 64", "M50 80 V82"]},
  "exclamation": {"nom": "un point d'exclamation (attention)", "d": ["M50 12 V62", "M50 80 V82"]},
  "feu": {"nom": "une flamme (tendance, urgent)", "d": ["M50 92 C26 92 18 68 30 50 C32 62 40 66 40 66 C36 44 46 24 58 10 C60 30 82 42 78 64 C76 84 64 92 50 92 Z"]}
};
