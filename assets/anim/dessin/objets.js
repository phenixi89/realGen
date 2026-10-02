// Objets et decor du dessin anime (unites dessin, origine au sol sous l'objet,
// sauf objets muraux places avec "y" : origine au centre). Chaque objet peut
// porter une touche de couleur legere (lavis) et avoir des ancres (ou poser un
// autre objet) et des actions.
//   tasse (vapeur), telephone (vibrer), cv, ordinateur (taper), table (bureau),
//   table_ronde (cafe), chaise, plante, horloge (murale), cadre (mural).
// "prise" = point saisi par une main (tenir).
(() => {
  const { g, el } = Dessin;
  const reg = Dessin.enregistrer;

  reg("tasse", {
    categorie: "objet", hauteur: 70, prise: [30, -30],
    dessiner(parent, P) {
      const corps = g(parent);
      P.lavis(corps, [[-21, -50], [-17, -5], [17, -5], [21, -50]], "#ff8a5c", 0.55);
      P.trace(corps, [[-22, -52], [-18, -4], [18, -4], [22, -52]], { w: 3.4 });
      P.rond(corps, 0, -52, 22, 5, { w: 2.6, passes: 2 });
      P.trace(corps, [[20, -44], [34, -42], [36, -26], [19, -18]], { w: 3 });
      const vapeur = g(parent);
      for (const dx of [-10, 4, 16]) P.trace(vapeur, [[dx, -66], [dx - 6, -82], [dx + 4, -98], [dx - 3, -116]], { w: 2, passes: 1, jit: 1.2, alpha: 0.7 });
      return { corps, vapeur };
    },
    vie(tl, it, t0, t1) {
      tl.fromTo(it.vapeur, { y: 6, opacity: 0.3 }, { y: -10, opacity: 0.9, duration: 1.2, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.2), ease: "sine.inOut", immediateRender: false }, t0);
    },
    actions: {},
  });

  reg("telephone", {
    categorie: "objet", hauteur: 80, prise: [0, -30],
    dessiner(parent, P) {
      const corps = g(parent);
      P.lavis(corps, [[-13, -70], [13, -70], [13, -12], [-13, -12]], "#7fc8ff", 0.4);
      P.rect(corps, -18, -76, 36, 76, { w: 3.2, passes: 2 });
      P.rond(corps, 0, -6, 3, 3, { w: 2, passes: 1 });
      const ondes = g(parent, { opacity: 0 });
      for (const s of [-1, 1]) {
        P.trace(ondes, [[s * 28, -60], [s * 36, -40], [s * 28, -20]], { w: 2.4, passes: 1 });
        P.trace(ondes, [[s * 40, -66], [s * 50, -40], [s * 40, -14]], { w: 2, passes: 1 });
      }
      gsap.set(corps, { svgOrigin: "0 -38" });
      return { corps, ondes };
    },
    actions: {
      vibrer(tl, it, a) {
        const d = a.duree || 1.2, n = Math.round(d / 0.06);
        tl.set(it.ondes, { opacity: 1 }, a.t).set(it.ondes, { opacity: 0 }, a.t + d)
          .fromTo(it.corps, { rotation: -9 }, { rotation: 9, duration: 0.06, yoyo: true, repeat: n - 1, immediateRender: false }, a.t)
          .to(it.corps, { rotation: 0, duration: 0.05 }, a.t + d);
        return d;
      },
    },
  });

  reg("cv", {
    categorie: "objet", hauteur: 130, prise: [0, -40],
    dessiner(parent, P) {
      const f = g(parent);
      P.lavis(f, [[-44, -118], [44, -118], [44, -2], [-44, -2]], "#fff1c9", 0.2);
      P.rect(f, -45, -120, 90, 120, { w: 3, passes: 2 });
      P.rect(f, -34, -108, 24, 28, { w: 2, passes: 1 });
      P.trace(f, [[0, -102], [32, -102]], { w: 2.4, passes: 1 });
      P.trace(f, [[0, -90], [24, -90]], { w: 1.8, passes: 1 });
      for (let i = 0; i < 4; i++) P.trace(f, [[-34, -66 + i * 14], [30 - (i % 2) * 14, -66 + i * 14]], { w: 1.8, passes: 1 });
      P.texte(f, 22, -84, "CV", { taille: 18 });
      return { f };
    },
    actions: {},
  });

  reg("ordinateur", {
    categorie: "objet", hauteur: 140,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-74, -126], [74, -126], [74, -36], [-74, -36]], "#7fc8ff", 0.25);
      P.rect(g0, -80, -132, 160, 102, { w: 3.4, passes: 2 });
      P.trace(g0, [[-96, -24], [96, -24], [104, 0], [-104, 0], [-96, -24]], { w: 3.2, passes: 2 });
      P.trace(g0, [[-20, -12], [20, -12]], { w: 2, passes: 1 });
      const lignes = [];
      for (let i = 0; i < 4; i++) { const l = g(g0, { opacity: 0 }); P.trace(l, [[-62, -114 + i * 18], [40 - (i % 2) * 30, -114 + i * 18]], { w: 2.2, passes: 1 }); lignes.push(l); }
      return { lignes };
    },
    actions: {
      taper(tl, it, a) {
        const d = a.duree || 1.6;
        it.lignes.forEach((l, i) => tl.set(l, { opacity: 1 }, a.t + (i + 1) * (d / (it.lignes.length + 1))));
        return d;
      },
    },
  });

  reg("table", {
    categorie: "decor", hauteur: 450,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-258, -444], [258, -444], [258, -428], [-258, -428]], "#d9a066", 0.45);
      P.rect(g0, -260, -446, 520, 18, { w: 3.6 });
      for (const x of [-232, 232]) P.trace(g0, [[x, -428], [x + Math.sign(x) * 4, 0]], { w: 3.6 });
      P.rect(g0, 90, -428, 130, 64, { w: 2.6, passes: 2 });
      P.trace(g0, [[140, -396], [170, -396]], { w: 3, passes: 1 });
      return { ancres: { dessus: { groupe: g0, x: 0, y: -446 }, dessus_gauche: { groupe: g0, x: -150, y: -446 }, dessus_droite: { groupe: g0, x: 150, y: -446 } } };
    },
  });

  reg("table_ronde", {
    categorie: "decor", hauteur: 440,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavisRond(g0, 0, -424, 148, 14, "#d9a066", 0.45);
      P.rond(g0, 0, -424, 150, 16, { w: 3.6 });
      P.trace(g0, [[0, -408], [0, -18]], { w: 4 });
      P.rond(g0, 0, -10, 70, 10, { w: 3.2 });
      return { ancres: { dessus: { groupe: g0, x: 0, y: -430 }, dessus_gauche: { groupe: g0, x: -80, y: -430 }, dessus_droite: { groupe: g0, x: 80, y: -430 } } };
    },
  });

  reg("chaise", {
    categorie: "decor", hauteur: 600,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-60, -282], [70, -282], [70, -270], [-60, -270]], "#d9a066", 0.45);
      P.rect(g0, -62, -286, 134, 16, { w: 3.4 });
      P.trace(g0, [[-58, -286], [-66, -600]], { w: 3.6 });
      P.trace(g0, [[-66, -600], [-40, -604]], { w: 3.4 });
      P.trace(g0, [[-62, -470], [-38, -470]], { w: 2.6, passes: 2 });
      P.trace(g0, [[62, -270], [66, 0]], { w: 3.4 });
      P.trace(g0, [[-54, -270], [-58, 0]], { w: 3.4 });
      return { ancres: { assise: { groupe: g0, x: 0, y: -286 } } };
    },
  });

  reg("plante", {
    categorie: "decor", hauteur: 440,
    dessiner(parent, P) {
      const pot = g(parent), feuilles = g(parent);
      P.lavis(pot, [[-52, -128], [52, -128], [40, -4], [-40, -4]], "#e07a4f", 0.5);
      P.trace(pot, [[-56, -130], [56, -130], [42, 0], [-42, 0], [-56, -130]], { w: 3.6 });
      P.trace(pot, [[-60, -130], [60, -130]], { w: 4 });
      const feuille = (bx, by, tx, ty, l) => {
        const mx = (bx + tx) / 2, my = (by + ty) / 2, nx = -(ty - by), ny = tx - bx, n = Math.hypot(nx, ny) || 1;
        const pts = [[bx, by], [mx + (nx / n) * l, my + (ny / n) * l], [tx, ty], [mx - (nx / n) * l, my - (ny / n) * l], [bx, by]];
        P.lavis(feuilles, pts.slice(0, 4), "#5cc98a", 0.45);
        P.trace(feuilles, pts, { w: 2.8, passes: 2, ferme: true });
        P.trace(feuilles, [[bx, by], [tx, ty]], { w: 1.6, passes: 1 });
      };
      feuille(0, -130, -120, -330, 34); feuille(0, -130, 10, -420, 30); feuille(0, -130, 120, -320, 34);
      feuille(0, -130, -70, -250, 22); feuille(0, -130, 80, -240, 22);
      gsap.set(feuilles, { svgOrigin: "0 -130" });
      return { feuilles };
    },
    vie(tl, it, t0, t1) {
      tl.fromTo(it.feuilles, { rotation: -1.5 }, { rotation: 1.5, duration: 1.6, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.6), ease: "sine.inOut", immediateRender: false }, t0);
    },
  });

  // Horloge murale (placee avec "y" : origine au centre) ; les aiguilles tournent.
  reg("horloge", {
    categorie: "decor", hauteur: 130,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavisRond(g0, 0, 0, 58, 58, "#ffe08a", 0.3);
      P.rond(g0, 0, 0, 60, 60, { w: 3.6 });
      for (let i = 0; i < 12; i += 3) { const a = (i / 12) * Math.PI * 2; P.trace(g0, [[Math.sin(a) * 46, -Math.cos(a) * 46], [Math.sin(a) * 54, -Math.cos(a) * 54]], { w: 2.6, passes: 1 }); }
      const minutes = g(g0), heures = g(g0);
      P.trace(minutes, [[0, 4], [0, -44]], { w: 2.8, passes: 1 });
      P.trace(heures, [[0, 4], [24, -12]], { w: 3.4, passes: 1 });
      el("circle", { cx: 0, cy: 0, r: 4, fill: "#ffffff" }, g0);
      gsap.set([minutes, heures], { svgOrigin: "0 0" });
      return { minutes, heures };
    },
    vie(tl, it, t0, t1) {
      tl.fromTo(it.minutes, { rotation: 0 }, { rotation: 360 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0)
        .fromTo(it.heures, { rotation: 0 }, { rotation: 30 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0);
    },
  });

  // Cadre mural (diplome) : origine au centre.
  reg("cadre", {
    categorie: "decor", hauteur: 110,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.rect(g0, -70, -50, 140, 100, { w: 3.2, passes: 2 });
      P.rect(g0, -58, -38, 116, 76, { w: 1.8, passes: 1 });
      for (let i = 0; i < 3; i++) P.trace(g0, [[-40, -20 + i * 14], [30 - i * 10, -20 + i * 14]], { w: 1.8, passes: 1 });
      P.lavisRond(g0, 36, 22, 12, 12, "#ffc94d", 0.7);
      P.rond(g0, 36, 22, 11, 11, { w: 2.2, passes: 1 });
      return {};
    },
  });
})();
