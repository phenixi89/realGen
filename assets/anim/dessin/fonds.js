// Fonds du dessin anime (coordonnees ecran 1080x1920, sol a la hauteur `sol`).
// Le decor de fond est trace plus fin et plus transparent que les personnages
// (profondeur), avec quelques touches de couleur legeres (lavis).
//   vide, bureau, cafe, salle_attente.
(() => {
  const { g } = Dessin;
  const reg = (nom, def) => Dessin.enregistrer("fond_" + nom, { categorie: "fond", ...def });
  const FOND = { w: 3, passes: 2, alpha: 0.6 };   // trait du decor

  // Sol commun : ligne a main levee, ombre hachuree sous chaque objet pose au sol.
  function sol(grp, P, y, xs, { cailloux = true } = {}) {
    P.trace(grp, [[-20, y + 6], [240, y + 1], [540, y + 4], [820, y - 1], [1100, y + 3]], { w: 4.4, jit: 2 });
    for (const xc of xs) for (let i = 0; i < 9; i++) {
      const x0 = xc - 70 + i * 16;
      P.trace(grp, [[x0, y + 10], [x0 - 14, y + 26]], { w: 1.6, passes: 1, jit: 1, alpha: 0.6 });
    }
    if (cailloux) for (const [px, r] of [[150, 9], [470, 6], [610, 11], [960, 7]]) P.rond(grp, px, y - r * 0.55, r * 1.6, r, { w: 2.4, passes: 2 });
  }
  const mur = (grp, P, y) => P.trace(grp, [[-20, y], [1100, y + 4]], { ...FOND, w: 3.4 });

  reg("vide", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent);
      sol(grp, P, y, xs);
      P.trace(grp, [[60, y + 26], [380, y + 22], [700, y + 27], [1020, y + 23]], { w: 1.4, passes: 1, jit: 2, alpha: 0.4 });
      for (const px of [80, 545, 1040]) {
        P.trace(grp, [[px, y], [px - 8, y - 22]], { w: 2, passes: 1, jit: 1 });
        P.trace(grp, [[px + 4, y], [px + 6, y - 28]], { w: 2, passes: 1, jit: 1 });
        P.trace(grp, [[px + 8, y], [px + 18, y - 18]], { w: 2, passes: 1, jit: 1 });
      }
      // Une petite fleur : la seule touche de couleur.
      P.trace(grp, [[990, y], [992, y - 60]], { w: 2.2, passes: 1 });
      P.lavisRond(grp, 992, y - 70, 14, 12, "#ff8fb1", 0.6);
      P.rond(grp, 992, y - 70, 12, 10, { w: 2.4, passes: 2 });
      return {};
    },
  });

  reg("bureau", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      for (const x of [-40, 260, 540, 820, 1120]) P.trace(grp, [[540 + (x - 540) * 0.55, m], [x, 1930]], { w: 1.6, passes: 1, alpha: 0.3 });
      // Fenetre (ciel bleute) au milieu du mur.
      P.lavis(grp, [[426, 646], [654, 646], [654, 934], [426, 934]], "#8fd3ff", 0.22);
      P.rect(grp, 420, 640, 240, 300, FOND);
      P.trace(grp, [[540, 640], [540, 940]], { ...FOND, w: 2.4 }); P.trace(grp, [[420, 790], [660, 790]], { ...FOND, w: 2.4 });
      P.trace(grp, [[404, 948], [676, 948]], { ...FOND, w: 3.4 });
      P.trace(grp, [[470, 700], [500, 670]], { w: 1.6, passes: 1, alpha: 0.5 }); P.trace(grp, [[590, 860], [620, 830]], { w: 1.6, passes: 1, alpha: 0.5 });
      // Etagere de livres a gauche (quelques dos colores).
      P.rect(grp, 30, 1060, 170, 420, FOND);
      for (const yy of [1200, 1340]) P.trace(grp, [[30, yy], [200, yy]], FOND);
      const livres = [[44, 1100, 22, "#ff7a6b"], [70, 1090, 18, null], [92, 1110, 26, "#ffc94d"], [124, 1095, 16, null], [146, 1105, 22, "#4f8dff"],
        [46, 1250, 20, null], [70, 1240, 28, "#5cc98a"], [104, 1255, 18, null], [128, 1245, 24, "#ff8fb1"]];
      for (const [x, yy, w, c] of livres) {
        const bas = yy < 1200 ? 1200 : 1340;
        if (c) P.lavis(grp, [[x, yy], [x + w, yy], [x + w, bas], [x, bas]], c, 0.35);
        P.rect(grp, x, yy, w, bas - yy, { w: 1.8, passes: 1, alpha: 0.55 });
      }
      sol(grp, P, y, xs, { cailloux: false });
      return {};
    },
  });

  reg("cafe", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      // Suspensions : lumiere chaude.
      const lampes = [];
      const svg = parent.ownerSVGElement;
      if (svg && !svg.querySelector("#halo-chaud")) {
        const defs = svg.querySelector("defs") || Dessin.el("defs", {}, svg);
        const rg = Dessin.el("radialGradient", { id: "halo-chaud" }, defs);
        Dessin.el("stop", { offset: "0", "stop-color": "#ffd66b", "stop-opacity": "0.55" }, rg);
        Dessin.el("stop", { offset: "0.55", "stop-color": "#ffb84d", "stop-opacity": "0.16" }, rg);
        Dessin.el("stop", { offset: "1", "stop-color": "#ffb84d", "stop-opacity": "0" }, rg);
      }
      const halos = [];
      for (const x of [150, 930]) {
        halos.push(Dessin.el("ellipse", { cx: x, cy: 440, rx: 190, ry: 150, fill: "url(#halo-chaud)", class: "lavis", opacity: 1 }, grp));
        P.trace(grp, [[x, -10], [x, 330]], { w: 2, passes: 1, alpha: 0.6 });
        P.trace(grp, [[x - 28, 330], [x + 28, 330], [x + 52, 400], [x - 52, 400], [x - 28, 330]], { ...FOND, w: 3.4, ferme: true });
        const l = g(grp);
        for (const a of [-0.5, 0, 0.5]) P.trace(l, [[x + Math.sin(a) * 40, 418], [x + Math.sin(a) * 70, 458]], { w: 1.8, passes: 1, alpha: 0.6 });
        lampes.push(l);
      }
      // Ardoise du menu (vert ardoise), ecriture a la craie.
      P.lavis(grp, [[404, 604], [676, 604], [676, 826], [404, 826]], "#3f8f6b", 0.3);
      P.rect(grp, 400, 600, 280, 230, FOND);
      P.texte(grp, 540, 660, "MENU", { taille: 42, alpha: 0.85 });
      P.texte(grp, 540, 718, "Café ... 2 €", { taille: 30, alpha: 0.7 });
      P.texte(grp, 540, 760, "Thé ... 2,50 €", { taille: 30, alpha: 0.7 });
      P.texte(grp, 540, 802, "Croissant ... 1 €", { taille: 30, alpha: 0.7 });
      // Carrelage du sol.
      for (const yy of [y + 60, y + 150]) P.trace(grp, [[-20, yy], [1100, yy]], { w: 1.4, passes: 1, alpha: 0.3 });
      sol(grp, P, y, xs, { cailloux: false });
      return { lampes, halos };
    },
    vie(tl, f, t0, t1) {
      tl.fromTo(f.lampes, { opacity: 0.4 }, { opacity: 1, duration: 0.9, yoyo: true, repeat: Math.ceil((t1 - t0) / 0.9), ease: "sine.inOut", immediateRender: false }, t0)
        .fromTo(f.halos, { scale: 0.94, svgOrigin: "0 0" }, { scale: 1, duration: 1.3, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.3), ease: "sine.inOut", immediateRender: false }, t0);
    },
  });

  reg("salle_attente", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      // Porte des RH a droite, plaque orange.
      P.rect(grp, 850, 1000, 180, m - 1000, FOND);
      P.rect(grp, 872, 1030, 136, 180, { w: 1.8, passes: 1, alpha: 0.45 });
      P.rond(grp, 868, 1250, 7, 7, { w: 2.4, passes: 1 });
      P.lavis(grp, [[888, 940], [992, 940], [992, 984], [888, 984]], "#ffa94d", 0.55);
      P.rect(grp, 886, 938, 108, 48, { w: 2.6, passes: 2 });
      P.texte(grp, 940, 975, "RH", { taille: 34 });
      // Affiche "On recrute !" (jaune pale).
      P.lavis(grp, [[84, 824], [236, 824], [236, 1016], [84, 1016]], "#ffe066", 0.25);
      P.rect(grp, 80, 820, 160, 200, FOND);
      P.texte(grp, 160, 900, "On", { taille: 34, alpha: 0.8 });
      P.texte(grp, 160, 950, "recrute !", { taille: 34, alpha: 0.8 });
      // Rangee de chaises contre le mur (petites, au fond).
      for (const x of [300, 380, 460]) {
        P.trace(grp, [[x - 26, m - 70], [x + 26, m - 70]], { w: 2.2, passes: 1, alpha: 0.45 });
        P.trace(grp, [[x - 26, m - 70], [x - 28, m - 170]], { w: 2.2, passes: 1, alpha: 0.45 });
        P.trace(grp, [[x - 22, m - 70], [x - 24, m]], { w: 2, passes: 1, alpha: 0.45 });
        P.trace(grp, [[x + 22, m - 70], [x + 24, m]], { w: 2, passes: 1, alpha: 0.45 });
      }
      // Horloge murale.
      const h = g(grp);
      P.lavisRond(h, 640, 700, 50, 50, "#ffe08a", 0.25);
      P.rond(h, 640, 700, 52, 52, FOND);
      const minutes = g(h), heures = g(h);
      P.trace(minutes, [[640, 704], [640, 662]], { w: 2.4, passes: 1 });
      P.trace(heures, [[640, 704], [662, 690]], { w: 3, passes: 1 });
      gsap.set([minutes, heures], { svgOrigin: "640 700" });
      sol(grp, P, y, xs, { cailloux: false });
      return { minutes, heures };
    },
    vie(tl, f, t0, t1) {
      tl.fromTo(f.minutes, { rotation: 0 }, { rotation: 360 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0)
        .fromTo(f.heures, { rotation: 0 }, { rotation: 30 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0);
    },
  });
})();
