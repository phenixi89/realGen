// Briques du jeu video retro (assets/anim/jeu.html) : un ecran de 270 x 480 "pixels de jeu" dessine sur un canvas,
// agrandi x4 sans lissage (1080 x 1920). Tout est calcule a partir du temps t seulement : le rendu image par image est
// identique d'un lancement a l'autre. Texte : Press Start 2P (OFL, assets/fonts/).
window.Jeu = window.Jeu || {};
(() => {
  const W = 270, H = 480;
  const cv = document.getElementById("ecran"), x = cv.getContext("2d");
  x.imageSmoothingEnabled = false;
  let cible = x;   // contexte dessine (l'ecran, ou un calque hors ecran pendant le trace d'un decor)
  const vers = (ctx) => { cible = ctx; };
  const R = (col, a, b, w, h) => { cible.fillStyle = col; cible.fillRect(Math.round(a), Math.round(b), w, h); };
  const texte = (str, a, b, col = "#fff", taille = 8) => { cible.fillStyle = col; cible.font = `${taille}px PS`; cible.textBaseline = "alphabetic"; cible.fillText(str, Math.round(a), Math.round(b)); };
  // Boite style RPG : cadre blanc, liseres bleus, fond sombre.
  const boite = (a, b, w, h, fond = "#16123a", lisere = "#5b6bff") => {
    R("#ffffff", a, b, w, h); R("#16123a", a + 1, b + 1, w - 2, h - 2); R(fond, a + 2, b + 2, w - 4, h - 4);
    R(lisere, a + 2, b + 2, w - 4, 1); R(lisere, a + 2, b + h - 3, w - 4, 1);
  };
  // Retour a la ligne (police a chasse fixe : 8 px par caractere pour une taille de 8).
  const coupe = (str, largeur, taille = 8) => {
    const max = Math.max(1, Math.floor(largeur / taille)), lignes = []; let cur = "";
    for (const mot of str.split(" ")) {
      if ((cur + " " + mot).trim().length > max) { if (cur) lignes.push(cur); cur = mot; } else cur = (cur + " " + mot).trim();
    }
    if (cur) lignes.push(cur);
    return lignes;
  };
  const hasard = (graine) => () => { graine = (graine * 16807) % 2147483647; return graine / 2147483647; };
  const lerp = (a, b, t) => a + (b - a) * Math.min(Math.max(t, 0), 1);
  const facile = (t) => 1 - Math.pow(1 - Math.min(Math.max(t, 0), 1), 3);
  // Calque hors ecran (decor fixe dessine une seule fois).
  const calque = () => { const c = document.createElement("canvas"); c.width = W; c.height = H; const k = c.getContext("2d"); k.imageSmoothingEnabled = false; return [c, k]; };
  Object.assign(Jeu, { W, H, cv, x, vers, R, texte, boite, coupe, hasard, lerp, facile, calque });
})();
