// Animaux du dessin anime : chat (roux, touche de couleur legere), de profil,
// regard vers la droite. Actions : marcher / traverser, miauler, dormir.
(() => {
  const { g, el } = Dessin;

  function marcherChat(tl, it, a, ctx) {
    const dist = Math.abs(a.vers - ctx.x(it)), duree = a.duree || Math.max(0.6, dist / 300);
    ctx.deplacer(it, a.vers, a.t, duree);
    const pas = 0.18, n = Math.max(1, Math.round(duree / pas));
    tl.fromTo(it.pattes[0], { rotation: -18 }, { rotation: 18, duration: pas, yoyo: true, repeat: n - 1, immediateRender: false }, a.t)
      .fromTo(it.pattes[1], { rotation: 18 }, { rotation: -18, duration: pas, yoyo: true, repeat: n - 1, immediateRender: false }, a.t)
      .to(it.pattes, { rotation: 0, duration: 0.12 }, a.t + n * pas);
    return duree;
  }

  Dessin.enregistrer("chat", {
    categorie: "animal", hauteur: 230, nom: "Le chat", hautTete: 240,
    dessiner(parent, P) {
      const corps = g(parent);
      // Pattes (deux groupes : avant et arriere, pour la marche).
      const pattes = [];
      for (const [x0, x1] of [[-52, -36], [44, 60]]) {
        const pg = g(corps);
        P.trace(pg, [[x0, -70], [x0 - 2, -6]], { w: 3.2 });
        P.trace(pg, [[x1, -70], [x1 + 2, -6]], { w: 3.2 });
        P.rond(pg, x0, -4, 10, 5, { w: 2.4, passes: 1 }); P.rond(pg, x1 + 2, -4, 10, 5, { w: 2.4, passes: 1 });
        gsap.set(pg, { svgOrigin: `${(x0 + x1) / 2} -70` });
        pattes.push(pg);
      }
      // Queue (pivot a la base).
      const queue = g(corps);
      P.trace(queue, [[-78, -110], [-120, -130], [-140, -180], [-118, -228], [-96, -232]], { w: 3.6 });
      gsap.set(queue, { svgOrigin: "-78 -110" });
      // Corps et tete.
      P.lavisRond(corps, 0, -100, 80, 42, "#ffae57", 0.4);
      P.rond(corps, 0, -100, 84, 46, { w: 3.8 });
      const tete = g(corps);
      el("circle", { cx: 90, cy: -152, r: 44, fill: "#000000" }, tete);
      P.lavisRond(tete, 90, -152, 40, 38, "#ffae57", 0.4);
      P.rond(tete, 90, -152, 44, 41, { w: 3.6 });
      P.trace(tete, [[62, -180], [66, -218], [88, -190]], { w: 3.2 });
      P.trace(tete, [[98, -192], [120, -214], [122, -178]], { w: 3.2 });
      for (const i of [0, 1, 2]) P.trace(tete, [[60 + i * 8, -196 + i * 2], [62 + i * 8, -182]], { w: 1.4, passes: 1, jit: 0.6 });   // rayures
      const oeil = g(tete), ferme = g(tete, { opacity: 0 });
      el("ellipse", { cx: 108, cy: -158, rx: 9, ry: 10, fill: "#ffffff", class: "plein" }, oeil);
      el("ellipse", { cx: 111, cy: -158, rx: 3, ry: 8, fill: "#000000" }, oeil);
      P.trace(ferme, [[99, -156], [108, -152], [117, -156]], { w: 2.8, passes: 1 });
      gsap.set(oeil, { svgOrigin: "108 -158" });
      P.trace(tete, [[128, -142], [133, -138], [128, -134]], { w: 2.6, passes: 1 });                  // nez
      P.trace(tete, [[124, -126], [118, -122], [112, -126]], { w: 2.2, passes: 1 });                  // bouche
      for (const dy of [-6, 2]) P.trace(tete, [[118, -136 + dy], [158, -142 + dy * 1.6]], { w: 1.4, passes: 1 });   // moustaches
      gsap.set(tete, { svgOrigin: "60 -140" });
      const bulle = g(parent, { opacity: 0 }), zz = g(parent, { opacity: 0 });
      P.texte(bulle, 150, -230, "miaou !", { taille: 38 });
      P.texte(zz, 130, -220, "z", { taille: 30 }); P.texte(zz, 152, -258, "z", { taille: 38 }); P.texte(zz, 180, -300, "z", { taille: 46 });
      return { corps, pattes, queue, tete, oeil, ferme, bulle, zz, nom: "Le chat", hautTete: 240 };
    },
    vie(tl, it, t0, t1, dec) {
      tl.fromTo(it.queue, { rotation: -8 }, { rotation: 10, duration: 0.9, yoyo: true, repeat: Math.ceil((t1 - t0) / 0.9), ease: "sine.inOut", immediateRender: false }, t0);
      for (let t = t0 + 1.6 + dec; t < t1; t += 3.3) tl.to(it.oeil, { scaleY: 0.1, duration: 0.06, yoyo: true, repeat: 1 }, t);
    },
    actions: {
      marcher: marcherChat,
      traverser: marcherChat,
      miauler(tl, it, a) {
        // Le texte ne doit pas etre retourne avec le chat quand il regarde a gauche.
        tl.set(it.bulle, { scaleX: it._regard || 1, svgOrigin: "150 -240" }, a.t)
          .fromTo(it.bulle, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.2, immediateRender: false }, a.t)
          .to(it.bulle, { opacity: 0, duration: 0.2 }, a.t + 1.2)
          .fromTo(it.tete, { rotation: 0 }, { rotation: -10, duration: 0.15, yoyo: true, repeat: 1, immediateRender: false }, a.t);
        return 1.4;
      },
      dormir(tl, it, a) {
        const d = a.duree || 2;
        tl.set(it.zz, { scaleX: it._regard || 1, svgOrigin: "155 -260" }, a.t)
          .set(it.oeil, { opacity: 0 }, a.t).set(it.ferme, { opacity: 1 }, a.t)
          .fromTo(it.zz, { opacity: 0, y: 10 }, { opacity: 1, y: -10, duration: d, ease: "none", immediateRender: false }, a.t)
          .set(it.zz, { opacity: 0 }, a.t + d).set(it.oeil, { opacity: 1 }, a.t + d).set(it.ferme, { opacity: 0 }, a.t + d);
        return d;
      },
    },
  });
})();
