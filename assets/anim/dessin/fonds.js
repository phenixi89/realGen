// Fonds du dessin anime (coordonnees ecran 1080x1920, sol a la hauteur `sol`).
// Le decor de fond est trace plus fin et plus transparent que les personnages
// (profondeur), avec quelques touches de couleur legeres (lavis).
//   vide, bureau, cafe, salle_attente, salle_entretien, salon, metro, visio,
//   ascenseur, open_space, bureau_manager, salon_emploi.
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
  // Bureau du recruteur : fenetre a stores, tableau blanc avec une courbe, porte-manteau.
  reg("salle_entretien", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      P.lavis(grp, [[86, 606], [394, 606], [394, 974], [86, 974]], "#8fd3ff", 0.18);
      P.rect(grp, 80, 600, 320, 380, FOND);
      for (let yy = 640; yy < 980; yy += 38) P.trace(grp, [[84, yy], [396, yy + 2]], { w: 1.6, passes: 1, alpha: 0.45 });
      P.trace(grp, [[380, 600], [380, 900]], { w: 1.6, passes: 1, alpha: 0.5 });
      // Tableau blanc : une courbe et des post-it.
      P.rect(grp, 600, 640, 360, 250, FOND);
      P.trace(grp, [[630, 850], [700, 820], [760, 830], [830, 760], [920, 700]], { w: 2.6, passes: 1, alpha: 0.7 });
      P.trace(grp, [[900, 690], [922, 698], [912, 720]], { w: 2.4, passes: 1, alpha: 0.7 });
      [[640, 670, "#ffe066"], [700, 668, "#ff8fb1"]].forEach(([x, yy, c]) => { P.lavis(grp, [[x, yy], [x + 44, yy], [x + 44, yy + 44], [x, yy + 44]], c, 0.5); P.rect(grp, x, yy, 44, 44, { w: 1.8, passes: 1, alpha: 0.6 }); });
      P.trace(grp, [[590, 900], [970, 900]], { ...FOND, w: 2.6 });
      // Porte-manteau au fond a droite, une veste accrochee.
      P.trace(grp, [[1010, m], [1012, 980]], { ...FOND, w: 3 });
      for (const s of [-1, 1]) P.trace(grp, [[1011, 990], [1011 + s * 34, 1010]], { ...FOND, w: 2.4 });
      P.lavis(grp, [[984, 1010], [1040, 1010], [1050, 1150], [976, 1150]], "#4f8dff", 0.22);
      P.trace(grp, [[984, 1010], [976, 1150], [1050, 1150], [1040, 1010]], { ...FOND, w: 2.4 });
      sol(grp, P, y, xs, { cailloux: false });
      return {};
    },
  });

  // Salon : fenetre a rideaux, lampadaire, tableau, tapis.
  reg("salon", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      P.lavis(grp, [[646, 626], [934, 626], [934, 954], [646, 954]], "#8fd3ff", 0.2);
      P.rect(grp, 640, 620, 300, 340, FOND);
      P.trace(grp, [[790, 620], [790, 960]], { ...FOND, w: 2.2 });
      for (const [x0, s] of [[620, 1], [960, -1]]) {
        P.lavis(grp, [[x0 - 10, 590], [x0 + s * 70, 590], [x0 + s * 50, 1010], [x0 - 10 * s, 1010]], "#ff7a6b", 0.25);
        P.trace(grp, [[x0, 590], [x0 + s * 18, 800], [x0 - s * 4, 1010]], { ...FOND, w: 2.4 });
        P.trace(grp, [[x0 + s * 60, 590], [x0 + s * 40, 800], [x0 + s * 50, 1010]], { ...FOND, w: 2.4 });
      }
      P.trace(grp, [[590, 586], [990, 586]], { ...FOND, w: 3.4 });
      // Tableau (paysage) a gauche.
      P.rect(grp, 120, 700, 220, 160, FOND);
      P.lavis(grp, [[130, 820], [180, 770], [230, 800], [290, 750], [330, 850], [130, 850]], "#5cc98a", 0.3);
      P.trace(grp, [[130, 820], [180, 770], [230, 800], [290, 750], [330, 820]], { w: 2, passes: 1, alpha: 0.6 });
      P.lavisRond(grp, 300, 735, 14, 14, "#ffc94d", 0.6);
      // Lampadaire.
      P.trace(grp, [[470, m + 10], [470, 900]], { ...FOND, w: 3 });
      P.lavis(grp, [[430, 900], [510, 900], [490, 820], [450, 820]], "#ffe066", 0.35);
      P.trace(grp, [[430, 900], [450, 820], [490, 820], [510, 900], [430, 900]], { ...FOND, w: 3, ferme: true });
      // Tapis.
      P.lavisRond(grp, 540, y + 70, 420, 40, "#ff8fb1", 0.16);
      P.rond(grp, 540, y + 70, 420, 40, { w: 2.2, passes: 1, alpha: 0.5 });
      sol(grp, P, y, xs, { cailloux: false });
      return {};
    },
  });

  // Rame de metro : vitres sur la ville qui defile, barres, poignees qui se balancent, plan de ligne.
  reg("metro", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      // Plan de ligne au-dessus des vitres.
      P.trace(grp, [[80, 560], [1000, 560]], { w: 3, passes: 1, couleur: "#ffc94d", alpha: 0.8 });
      for (let x = 100; x <= 980; x += 110) P.rond(grp, x, 560, 8, 8, { w: 2.4, passes: 1 });
      P.lavisRond(grp, 540, 560, 14, 14, "#ff5a5a", 0.8);
      // Vitres et ville qui defile derriere.
      const svg = parent.ownerSVGElement, defs = svg.querySelector("defs") || Dessin.el("defs", {}, svg);
      const clip = Dessin.el("clipPath", { id: "vitres-metro" }, defs);
      for (const x of [60, 400, 740]) Dessin.el("rect", { x, y: 640, width: 280, height: 300 }, clip);
      const ville = g(grp, { "clip-path": "url(#vitres-metro)" }), defile = g(ville);
      for (let k = 0; k < 3; k++) {
        let x = k * 1100;
        for (const [w, h] of [[90, 160], [60, 230], [120, 120], [70, 200], [100, 260], [80, 140], [130, 190], [60, 110], [110, 220], [90, 170]]) {
          P.trace(defile, [[x, 940], [x, 940 - h], [x + w, 940 - h], [x + w, 940]], { w: 2, passes: 1, alpha: 0.4 });
          for (let fy = 940 - h + 24; fy < 920; fy += 40) P.trace(defile, [[x + 16, fy], [x + 26, fy]], { w: 2, passes: 1, alpha: 0.3 });
          x += w + 20;
        }
      }
      for (const x of [60, 400, 740]) { P.lavis(grp, [[x, 640], [x + 280, 640], [x + 280, 940], [x, 940]], "#8fd3ff", 0.14); P.rect(grp, x, 640, 280, 300, FOND); }
      // Banquettes sous les vitres.
      P.lavis(grp, [[40, m - 120], [1040, m - 120], [1040, m - 60], [40, m - 60]], "#4f8dff", 0.18);
      P.trace(grp, [[40, m - 120], [1040, m - 120]], FOND); P.trace(grp, [[40, m - 60], [1040, m - 60]], FOND);
      // Barres et poignees.
      P.trace(grp, [[0, 610], [1080, 610]], { ...FOND, w: 3 });
      for (const x of [370, 710]) P.trace(grp, [[x, 610], [x + 2, y]], { w: 3.6, passes: 2, alpha: 0.8 });
      const poignees = [];
      for (const x of [140, 260, 480, 600, 820, 940]) {
        const p = g(grp);
        P.trace(p, [[x, 610], [x, 680]], { w: 2.2, passes: 1, alpha: 0.7 });
        P.rond(p, x, 700, 18, 20, { w: 2.6, passes: 1, alpha: 0.8 });
        gsap.set(p, { svgOrigin: `${x} 610` });
        poignees.push(p);
      }
      sol(grp, P, y, xs, { cailloux: false });
      return { defile, poignees };
    },
    vie(tl, f, t0, t1) {
      tl.fromTo(f.defile, { x: 0 }, { x: -1100 * Math.max(1, (t1 - t0) / 4), duration: t1 - t0, ease: "none", immediateRender: false }, t0)
        .fromTo(f.poignees, { rotation: -5 }, { rotation: 5, duration: 0.9, yoyo: true, repeat: Math.ceil((t1 - t0) / 0.9), ease: "sine.inOut", immediateRender: false }, t0);
    },
  });

  // Appel video : l'ecran de l'appel, deux vignettes (une par personnage : gauche et droite),
  // barre du haut (point d'enregistrement), boutons du bas (micro, camera, raccrocher).
  reg("visio", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), haut = 470, bas = y + 40;
      P.rect(grp, 30, haut - 70, 1020, bas - haut + 170, { ...FOND, w: 4, alpha: 0.8 });
      P.trace(grp, [[30, haut], [1050, haut]], FOND);
      const rec = g(grp);
      P.lavisRond(rec, 80, haut - 35, 12, 12, "#ff5a5a", 0.9);
      P.texte(grp, 540, haut - 22, "Entretien en visio", { taille: 40, alpha: 0.75 });
      P.trace(grp, [[540, haut], [540, bas]], { ...FOND, w: 3 });
      P.lavis(grp, [[40, haut + 10], [530, haut + 10], [530, bas - 10], [40, bas - 10]], "#7fc8ff", 0.08);
      P.lavis(grp, [[550, haut + 10], [1040, haut + 10], [1040, bas - 10], [550, bas - 10]], "#ffc94d", 0.08);
      // Decor de chaque vignette : etagere a gauche, plante et cadre a droite.
      P.rect(grp, 60, 620, 140, 220, { w: 2, passes: 1, alpha: 0.45 }); P.trace(grp, [[60, 730], [200, 730]], { w: 2, passes: 1, alpha: 0.45 });
      P.rect(grp, 880, 640, 120, 90, { w: 2, passes: 1, alpha: 0.45 });
      P.trace(grp, [[30, bas], [1050, bas]], FOND);
      [[400, "#ffffff"], [540, "#ffffff"], [680, "#ff5a5a"]].forEach(([x, c]) => {
        if (c !== "#ffffff") P.lavisRond(grp, x, bas + 55, 34, 34, c, 0.7);
        P.rond(grp, x, bas + 55, 36, 36, { w: 3, passes: 1 });
      });
      P.trace(grp, [[390, bas + 40], [390, bas + 64]], { w: 3, passes: 1 }); P.rond(grp, 400, bas + 46, 8, 12, { w: 2.4, passes: 1 });
      P.rect(grp, 520, bas + 42, 30, 24, { w: 2.4, passes: 1 }); P.trace(grp, [[550, bas + 50], [562, bas + 44], [562, bas + 66], [550, bas + 60]], { w: 2.2, passes: 1 });
      P.trace(grp, [[660, bas + 62], [670, bas + 48], [690, bas + 48], [700, bas + 62]], { w: 3, passes: 1 });
      return { rec };
    },
    vie(tl, f, t0, t1) {
      tl.fromTo(f.rec, { opacity: 1 }, { opacity: 0.2, duration: 0.6, yoyo: true, repeat: Math.ceil((t1 - t0) / 0.6), immediateRender: false }, t0);
    },
  });

  // Cabine d'ascenseur : portes coulissantes au fond, afficheur d'etage qui monte, boutons, main courante.
  reg("ascenseur", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      P.rect(grp, 110, 520, 860, m - 520, { ...FOND, w: 4, alpha: 0.8 });
      P.lavis(grp, [[120, 530], [960, 530], [960, 600], [120, 600]], "#ffe08a", 0.16);
      // Afficheur d'etage : un numero qui change.
      P.rect(grp, 440, 580, 200, 96, { ...FOND, w: 3 });
      const etages = [];
      ["4", "5", "6", "7"].forEach((n, i) => { const e = g(grp, { opacity: i ? 0 : 1 }); P.texte(e, 540, 652, n, { taille: 70 }); etages.push(e); });
      P.trace(grp, [[500, 600], [540, 590], [580, 600]], { w: 2.4, passes: 1, alpha: 0.7 });
      // Portes : deux battants, fente au milieu, reflets.
      P.lavis(grp, [[130, 720], [534, 720], [534, m - 20], [130, m - 20]], "#9bb4c8", 0.12);
      P.lavis(grp, [[546, 720], [950, 720], [950, m - 20], [546, m - 20]], "#9bb4c8", 0.12);
      P.rect(grp, 126, 716, 408, m - 20 - 716, { ...FOND, w: 3 }); P.rect(grp, 546, 716, 408, m - 20 - 716, { ...FOND, w: 3 });
      for (const [x0, x1] of [[190, 250], [610, 670]]) P.trace(grp, [[x0, 780], [x1, 740]], { w: 2, passes: 1, alpha: 0.35 });
      // Panneau de boutons a droite.
      P.rect(grp, 1000, 840, 56, 200, { ...FOND, w: 3 });
      [870, 920, 970].forEach((yy, i) => { P.rond(grp, 1028, yy, 12, 12, { w: 2.4, passes: 1 }); if (i === 1) P.lavisRond(grp, 1028, yy, 10, 10, "#ffc94d", 0.8); });
      // Main courante.
      P.trace(grp, [[110, m - 330], [970, m - 330]], { ...FOND, w: 4 });
      for (const x of [150, 930]) P.trace(grp, [[x, m - 330], [x, m - 308]], { ...FOND, w: 3 });
      sol(grp, P, y, xs, { cailloux: false });
      return { etages };
    },
    vie(tl, f, t0, t1) {
      const pas = 2.2;
      f.etages.forEach((e, i) => { if (i) tl.set(e, { opacity: 1 }, t0 + i * pas).set(f.etages[i - 1], { opacity: 0 }, t0 + i * pas); });
    },
  });

  // Plateau open space : bureaux au fond avec ecrans allumes, baie vitree sur la ville, suspensions, plante.
  reg("open_space", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      // Baie vitree et immeubles.
      P.lavis(grp, [[96, 586], [984, 586], [984, 830], [96, 830]], "#8fd3ff", 0.2);
      P.rect(grp, 90, 580, 900, 260, FOND);
      for (const x of [390, 690]) P.trace(grp, [[x, 580], [x, 840]], { ...FOND, w: 2.4 });
      let x = 110;
      for (const [w, h] of [[60, 120], [80, 190], [50, 90], [90, 150], [70, 210], [60, 110], [100, 170], [70, 130], [80, 200], [60, 100]]) {
        P.trace(grp, [[x, 836], [x, 836 - h], [x + w, 836 - h], [x + w, 836]], { w: 2, passes: 1, alpha: 0.4 }); x += w + 12;
      }
      // Suspensions.
      for (const lx of [220, 540, 860]) {
        P.trace(grp, [[lx, 330], [lx, 470]], { w: 2, passes: 1, alpha: 0.5 });
        P.lavis(grp, [[lx - 60, 520], [lx + 60, 520], [lx + 34, 470], [lx - 34, 470]], "#ffe066", 0.35);
        P.trace(grp, [[lx - 60, 520], [lx - 34, 470], [lx + 34, 470], [lx + 60, 520], [lx - 60, 520]], { w: 2.6, passes: 1, alpha: 0.8 });
      }
      // Bureaux du fond : plateau, pieds, ecran allume, cloison.
      const bureaux = [[170, 1], [470, 0], [770, 1]];
      for (const [bx, cloison] of bureaux) {
        P.trace(grp, [[bx - 110, m - 130], [bx + 110, m - 130]], { w: 3, passes: 1, alpha: 0.7 });
        P.trace(grp, [[bx - 100, m - 130], [bx - 100, m]], { w: 2.4, passes: 1, alpha: 0.6 });
        P.trace(grp, [[bx + 100, m - 130], [bx + 100, m]], { w: 2.4, passes: 1, alpha: 0.6 });
        P.lavis(grp, [[bx - 40, m - 230], [bx + 40, m - 230], [bx + 40, m - 160], [bx - 40, m - 160]], "#7fc8ff", 0.4);
        P.rect(grp, bx - 42, m - 232, 84, 72, { w: 2.2, passes: 1, alpha: 0.7 });
        P.trace(grp, [[bx, m - 160], [bx, m - 132]], { w: 2.2, passes: 1, alpha: 0.7 });
        if (cloison) P.trace(grp, [[bx + 130, m - 260], [bx + 130, m - 120]], { w: 2.4, passes: 1, alpha: 0.45 });
      }
      // Plante a droite.
      P.trace(grp, [[1010, m], [1004, m - 90]], { w: 2.4, passes: 1, alpha: 0.7 });
      P.lavisRond(grp, 1004, m - 130, 46, 56, "#5cc98a", 0.35);
      for (const [dx, dy] of [[-26, -90], [0, -130], [26, -96]]) P.trace(grp, [[1004, m - 70], [1004 + dx, m + dy + 0]], { w: 2.2, passes: 1, alpha: 0.7 });
      sol(grp, P, y, xs, { cailloux: false });
      return {};
    },
  });

  // Bureau du manager : baie panoramique, diplomes encadres, bibliotheque, tapis, plaque « Direction ».
  reg("bureau_manager", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      // Grande baie sur la ville au crepuscule.
      P.lavis(grp, [[316, 596], [764, 596], [764, 1010], [316, 1010]], "#ffb067", 0.2);
      P.rect(grp, 310, 590, 460, 430, FOND);
      P.trace(grp, [[540, 590], [540, 1020]], { ...FOND, w: 2.4 }); P.trace(grp, [[310, 800], [770, 800]], { ...FOND, w: 2.4 });
      let x = 322;
      for (const [w, h] of [[50, 120], [40, 200], [60, 90], [44, 170], [56, 230], [40, 130], [60, 160], [36, 110]]) {
        P.trace(grp, [[x, 1016], [x, 1016 - h], [x + w, 1016 - h], [x + w, 1016]], { w: 2, passes: 1, alpha: 0.45 }); x += w + 8;
      }
      P.lavisRond(grp, 660, 700, 34, 34, "#ffe08a", 0.6);
      P.trace(grp, [[290, 1030], [790, 1030]], { ...FOND, w: 3.4 });
      // Diplomes encadres a gauche.
      [[90, 700, 110, 80], [90, 810, 110, 80], [90, 920, 110, 80]].forEach(([fx, fy, w, h], i) => {
        P.rect(grp, fx, fy, w, h, { w: 2.6, passes: 1 });
        P.trace(grp, [[fx + 14, fy + 30], [fx + w - 14, fy + 30]], { w: 1.8, passes: 1, alpha: 0.6 });
        P.trace(grp, [[fx + 14, fy + 50], [fx + w - 30, fy + 50]], { w: 1.8, passes: 1, alpha: 0.6 });
        if (i === 1) P.lavisRond(grp, fx + w - 22, fy + h - 16, 9, 9, "#ffc94d", 0.8);
      });
      // Bibliotheque a droite.
      P.rect(grp, 840, 620, 200, 700, FOND);
      for (const yy of [770, 920, 1070, 1220]) P.trace(grp, [[840, yy], [1040, yy]], FOND);
      const couleurs = ["#ff7a6b", null, "#4f8dff", "#ffc94d", null, "#5cc98a"];
      [[620, 770], [770, 920], [920, 1070], [1070, 1220]].forEach(([haut, bas], r) => {
        let bx = 852;
        couleurs.forEach((c, i) => {
          const w = 20 + ((i + r) % 3) * 6, h = 70 + ((i * 7 + r * 3) % 4) * 12;
          if (c) P.lavis(grp, [[bx, bas - h], [bx + w, bas - h], [bx + w, bas], [bx, bas]], c, 0.35);
          P.rect(grp, bx, bas - h, w, h, { w: 1.8, passes: 1, alpha: 0.55 }); bx += w + 6;
        });
      });
      // Tapis sous le bureau.
      P.lavisRond(grp, 540, y + 60, 360, 34, "#8f7bff", 0.16);
      P.rond(grp, 540, y + 60, 360, 34, { w: 2.2, passes: 1, alpha: 0.5 });
      P.texte(grp, 540, 566, "Direction", { taille: 36, alpha: 0.7 });
      sol(grp, P, y, xs, { cailloux: false });
      return {};
    },
  });

  // Salon de l'emploi : guirlande de fanions, stands avec comptoir et kakemono, ballons, affiche « Salon de l'emploi ».
  reg("salon_emploi", {
    dessiner(parent, P, { sol: y, xs }) {
      const grp = g(parent), m = y - 170;
      mur(grp, P, m);
      // Banderole au centre, entre les deux personnages (les bulles passent plus haut).
      P.lavis(grp, [[376, 686], [704, 686], [704, 770], [376, 770]], "#ffc94d", 0.25);
      P.rect(grp, 370, 680, 340, 96, { ...FOND, w: 3.4 });
      P.texte(grp, 540, 744, "Salon de l'emploi", { taille: 36, alpha: 0.9 });
      for (const x of [390, 690]) P.trace(grp, [[x, 680], [x + (x < 540 ? -10 : 10), 640]], { w: 2, passes: 1, alpha: 0.5 });
      // Guirlande de fanions (oscille doucement).
      const guirlande = g(grp);
      P.trace(guirlande, [[40, 600], [300, 640], [540, 656], [780, 640], [1040, 600]], { w: 2, passes: 1, alpha: 0.7 });
      const coul = ["#ff7a6b", "#ffc94d", "#4f8dff", "#5cc98a", "#ff8fb1"];
      for (let i = 0; i < 11; i++) {
        const t = (i + 0.5) / 11, fx = 40 + t * 1000, fy = 600 + Math.sin(t * Math.PI) * 56 + 4;
        P.lavis(guirlande, [[fx - 22, fy], [fx + 22, fy], [fx, fy + 52]], coul[i % 5], 0.55);
        P.trace(guirlande, [[fx - 22, fy], [fx + 22, fy], [fx, fy + 52], [fx - 22, fy]], { w: 2, passes: 1, alpha: 0.7 });
      }
      gsap.set(guirlande, { svgOrigin: "540 580" });
      // Stands : comptoir, kakemono, logo.
      [[160, "RH", "#4f8dff"], [540, "Tech", "#5cc98a"], [920, "Vente", "#ff7a6b"]].forEach(([sx, nom, c]) => {
        P.lavis(grp, [[sx - 90, m - 150], [sx + 90, m - 150], [sx + 90, m], [sx - 90, m]], c, 0.22);
        P.rect(grp, sx - 90, m - 150, 180, 150, { w: 2.8, passes: 1, alpha: 0.8 });
        P.trace(grp, [[sx - 100, m - 150], [sx + 100, m - 150]], { w: 3.4, passes: 1 });
        P.texte(grp, sx, m - 70, nom, { taille: 46, alpha: 0.9 });
        P.rect(grp, sx - 40, m - 520, 80, 300, { w: 2.4, passes: 1, alpha: 0.6 });
        P.lavis(grp, [[sx - 36, m - 516], [sx + 36, m - 516], [sx + 36, m - 224], [sx - 36, m - 224]], c, 0.3);
        P.rond(grp, sx, m - 440, 16, 16, { w: 2.2, passes: 1, alpha: 0.7 });
      });
      // Ballons au sol a droite.
      P.trace(grp, [[1010, m], [1006, m - 110]], { w: 1.8, passes: 1, alpha: 0.5 });
      P.lavisRond(grp, 1006, m - 140, 26, 32, "#ff8fb1", 0.5); P.rond(grp, 1006, m - 140, 26, 32, { w: 2.2, passes: 1, alpha: 0.7 });
      sol(grp, P, y, xs, { cailloux: false });
      return { guirlande };
    },
    vie(tl, f, t0, t1) {
      tl.fromTo(f.guirlande, { rotation: -0.8 }, { rotation: 0.8, duration: 1.4, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.4), ease: "sine.inOut", immediateRender: false }, t0);
    },
  });
})();
