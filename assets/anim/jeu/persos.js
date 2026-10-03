// Personnages et boss du jeu, dessines a la main en rectangles sur une grille de 2 x 2 pixels de jeu par "pixel d'art"
// (donc plus gros que le decor, comme un sprite de RPG). Chaque fonction prend (px, py) = coin haut-gauche de la boite
// du sprite et un etat {regard: 1|-1, bouche, bras, jambes, flash, ...} ; flash = silhouette blanche (coup recu).
(() => {
  const { R } = Jeu;
  // Outil : rectangle en coordonnees d'art, retourne si regard = -1, blanc si flash.
  const pinceau = (px, py, larg, e, K = 3) => (col, ax, ay, w, h) => {
    const bx = e.regard === -1 ? larg - ax - w : ax;
    R(e.flash ? "#ffffff" : col, px + bx * K, py + ay * K, w * K, h * K);
  };

  Jeu.martin = (px, py, e = {}) => {
    const r = pinceau(px, py, 16, e), j = e.jambes || 0, b = e.bras || "bas";
    r("#23233a", 3, 0, 10, 3); r("#23233a", 2, 2, 2, 5); r("#23233a", 12, 2, 2, 4);                    // cheveux
    r("#e8b08a", 4, 3, 8, 8); r("#e8b08a", 7, 11, 2, 1);                                                // visage, cou
    r("#111111", 4, 5, 4, 3); r("#111111", 9, 5, 4, 3); r("#111111", 8, 6, 1, 1);                      // lunettes
    r("#cfe8ff", 5, 6, 2, 1); r("#cfe8ff", 10, 6, 2, 1); r("#23233a", 6, 6, 1, 1); r("#23233a", 11, 6, 1, 1);
    r(e.bouche ? "#7a2e2e" : "#b0524a", 6, 9, 4, e.bouche ? 2 : 1);                                      // bouche
    r("#2a9d8f", 3, 12, 10, 10); r("#ffffff", 7, 12, 2, 7); r("#ff6b35", 7.5, 13, 1, 6);               // veste, chemise, cravate
    r("#2a9d8f", 1, 13, 2, 8); r("#e8b08a", 1, 21, 2, 2);                                               // bras gauche
    if (b === "haut") { r("#2a9d8f", 13, 6, 2, 8); r("#e8b08a", 13, 4, 2, 2); }                       // bras en l'air (victoire)
    else if (b === "avant") { r("#2a9d8f", 13, 14, 5, 2); r("#e8b08a", 18, 14, 2, 2); }              // bras tendu (attaque)
    else { r("#2a9d8f", 13, 13, 2, 8); r("#e8b08a", 13, 21, 2, 2); }                                   // bras droit
    r("#3b5ba5", 4, 22, 8, 7); r("#2a3f78", 8, 22, 1, 7);                                               // jean
    r("#1a1a2e", 3, 29 - (j === 1 ? 1 : 0), 5, 3); r("#1a1a2e", 9, 29 - (j === 2 ? 1 : 0), 5, 3);      // chaussures
    // CV : parchemin tenu (ou brandi comme une epee)
    if (b === "avant") { r("#fff3b0", 20, 10, 3, 12); r("#d9b56a", 20, 10, 3, 1); r("#d9b56a", 20, 21, 3, 1); }
    else if (b === "haut") { r("#fff3b0", 13, 0, 4, 5); r("#d9b56a", 13, 0, 4, 1); }
    else { r("#fff3b0", 15, 15, 3, 7); r("#d9b56a", 15, 15, 3, 1); r("#d9b56a", 15, 21, 3, 1); }
  };

  Jeu.lea = (px, py, e = {}) => {
    const r = pinceau(px, py, 16, e), j = e.jambes || 0, b = e.bras || "bas";
    r("#7a3a1e", 3, 0, 10, 3); r("#7a3a1e", 2, 2, 2, 8); r("#ff6b5a", 12, 2, 3, 3); r("#7a3a1e", 13, 5, 3, 7);   // cheveux, queue
    r("#e8b08a", 4, 3, 8, 8); r("#e8b08a", 7, 11, 2, 1);
    r("#1a1a2e", 5, 6, 1, 2); r("#1a1a2e", 10, 6, 1, 2);                                                    // yeux
    r(e.bouche ? "#7a2e2e" : "#c25a4a", 6, 9, 4, e.bouche ? 2 : 1);
    r("#ff6b5a", 3, 12, 10, 9); r("#ffffff", 6, 12, 4, 2);                                                   // veste
    r("#ff6b5a", 1, 13, 2, 8); r("#e8b08a", 1, 21, 2, 2);
    if (b === "pointe") { r("#ff6b5a", 13, 14, 5, 2); r("#e8b08a", 18, 14, 2, 2); }                        // bras tendu (elle montre)
    else if (b === "haut") { r("#ff6b5a", 13, 6, 2, 8); r("#e8b08a", 13, 4, 2, 2); }
    else { r("#ff6b5a", 13, 13, 2, 8); r("#e8b08a", 13, 21, 2, 2); }
    r("#3a2a5e", 3, 21, 10, 5); r("#e8b08a", 5, 26, 2, 3); r("#e8b08a", 9, 26, 2, 3);                      // jupe, jambes
    r("#1a1a2e", 4, 29 - (j === 1 ? 1 : 0), 3, 3); r("#1a1a2e", 9, 29 - (j === 2 ? 1 : 0), 3, 3);
  };

  // ---------------------------------------------------------------- boss (grille 24 x 24)
  const BOSS = {
    // Le robot qui trie les CV : un tamis sur la tete, un oeil rouge qui balaie, un tampon REFUSE.
    robot_trieur(px, py, e) {
      const r = pinceau(px, py, 24, e, 4), t = e.t || 0, oeil = Math.round(Math.sin(t * 4) * 2);
      r("#8a93a6", 4, 8, 16, 11); r("#a9b2c4", 4, 8, 16, 2); r("#5d6678", 4, 17, 16, 2);                       // tete
      r("#5d6678", 8, 1, 8, 2); r("#7a8497", 6, 3, 12, 2); r("#8a93a6", 4, 5, 16, 3);                          // tamis (entonnoir)
      for (let i = 0; i < 4; i++) r("#3a4152", 7 + i * 3, 4, 1, 1);                                              // trous du tamis
      r("#111827", 6, 11, 12, 5); r("#ff3b3b", 11 + oeil, 12, 3, 3); r("#ffd1d1", 12 + oeil, 12, 1, 1);        // oeil
      r("#5d6678", 11, 0, 2, 2); r("#ff3b3b", 11, 0, 2, 1);                                                    // antenne
      r("#6b7488", 3, 19, 18, 3); r("#3a4152", 2, 22, 20, 2); for (let i = 0; i < 5; i++) r("#8a93a6", 3 + i * 4, 22, 2, 2);   // corps, chenilles
      r("#ffffff", 7, 19, 10, 3); r("#d62f2f", 8, 20, 8, 1);                                                   // tampon REFUSE
      r("#6b7488", 0, 13, 4, 3); r("#6b7488", 20, 13, 4, 3);                                                   // bras
    },
    // Le fantome du "ghosting" : plus de reponse, il flotte et fait "...".
    fantome(px, py, e) {
      const r = pinceau(px, py, 24, e, 4), t = e.t || 0, f = Math.round(Math.sin(t * 3) * 1);
      r("#eef2ff", 5, 3 + f, 14, 3); r("#eef2ff", 3, 6 + f, 18, 13); r("#d5dcf5", 3, 15 + f, 18, 4);
      for (let i = 0; i < 4; i++) r("#eef2ff", 3 + i * 5, 19 + f, 4, 3 + (i % 2));                              // bas ondule
      r("#1b2133", 7, 9 + f, 3, 4); r("#1b2133", 14, 9 + f, 3, 4); r("#1b2133", 10, 15 + f, 4, 3);              // yeux, bouche
      r("#8aa0ff", 0, 12 + f, 3, 2); r("#8aa0ff", 21, 12 + f, 3, 2);
    },
    // Le monstre de paperasse : une pile de feuilles aux dents d'agrafeuses.
    paperasse(px, py, e) {
      const r = pinceau(px, py, 24, e, 4), t = e.t || 0, s = Math.round(Math.sin(t * 5));
      r("#e9e2c8", 3, 14, 18, 8); r("#fffbe8", 2 + s, 9, 19, 7); r("#e9e2c8", 4, 4, 17, 6); r("#fffbe8", 5 + s, 1, 15, 5);   // feuilles
      for (let i = 0; i < 3; i++) { r("#b8b19a", 5, 3 + i * 2, 10, 1); r("#b8b19a", 4, 11 + i * 2, 11, 1); }
      r("#111827", 7, 9, 4, 3); r("#111827", 13, 9, 4, 3); r("#ff3b3b", 8, 10, 2, 1); r("#ff3b3b", 14, 10, 2, 1);    // yeux furieux
      r("#111827", 6, 7, 5, 1); r("#111827", 13, 7, 5, 1);                                                      // sourcils
      r("#7a7a8a", 6, 16, 12, 3); for (let i = 0; i < 6; i++) r("#ffffff", 7 + i * 2, 16, 1, 2);                // dents d'agrafeuse
      r("#2a2a3a", 6, 19, 12, 1);
    },
  };
  Jeu.boss = (id, px, py, e = {}) => (BOSS[id] || BOSS.robot_trieur)(px, py, e);
  Jeu.BOSS_IDS = Object.keys(BOSS);

  // Icones : coeur, etoile, parchemin (24 x 24 grille 1 x 1 de jeu).
  Jeu.coeur = (a, b, plein = true, flash = false) => {
    const c = flash ? "#ffffff" : plein ? "#ff4d6d" : "#3a2a4a";
    R(c, a, b, 4, 3); R(c, a + 6, b, 4, 3); R(c, a - 1, b + 3, 12, 4); R(c, a + 1, b + 7, 8, 2); R(c, a + 3, b + 9, 4, 2);
    if (plein && !flash) R("#ffb3c1", a + 1, b + 1, 2, 2);
  };
  Jeu.parchemin = (a, b) => { R("#fff3b0", a, b, 14, 22); R("#d9b56a", a, b, 14, 2); R("#d9b56a", a, b + 20, 14, 2); R("#b8903a", a + 3, b + 6, 8, 1); R("#b8903a", a + 3, b + 10, 8, 1); R("#b8903a", a + 3, b + 14, 5, 1); };
  Jeu.etoile = (a, b, col = "#ffd84d") => { R(col, a + 3, b, 2, 8); R(col, a, b + 3, 8, 2); R(col, a + 1, b + 1, 6, 6); };
})();
