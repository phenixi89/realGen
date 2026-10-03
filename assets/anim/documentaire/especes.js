// Animaux du documentaire : silhouettes de profil (regard vers la droite, pieds en y = 0, haut = y negatif),
// remplies de la couleur du moment (currentColor). Chaque espece declare :
//   hauteur      hauteur de reference (px) -- sert a poser la legende et le gros plan
//   dessiner     trace l'animal -> les pieces a animer (pattes, cou, queue...)
//   vie(tl,it,t0,t1)   mouvement permanent (respiration, queue, regard)
//   actions      actions jouables par le scenario ("marcher" et "attendre" existent pour toutes)
(() => {
  const { g, ell, membre, forme, lisse, el } = Doc;
  Doc.especes = {};
  const reg = (id, def) => (Doc.especes[id] = { id, ...def });
  const balance = (tl, cible, de, vers, duree, t0, t1, extra = {}) => {
    const n = Math.max(1, Math.ceil((t1 - t0) / duree));
    tl.fromTo(cible, { rotation: de }, { rotation: vers, duration: duree, yoyo: true, repeat: n, ease: "sine.inOut", immediateRender: false, ...extra }, t0);
  };
  // Pas : chaque patte oscille autour de la hanche, deux a deux en opposition.
  const pas = (tl, it, a, duree, ampl = 22, cadence = 0.32) => {
    const n = Math.max(1, Math.round(duree / cadence));
    it.pattes.forEach((p, i) => {
      const s = i % 2 ? -1 : 1;
      tl.fromTo(p, { rotation: -ampl * s }, { rotation: ampl * s, duration: cadence, yoyo: true, repeat: n, ease: "sine.inOut", immediateRender: false }, a.t)
        .to(p, { rotation: 0, duration: 0.2 }, a.t + (n + 1) * cadence);
    });
    tl.fromTo(it.corps, { y: 0 }, { y: -5, duration: cadence / 2, yoyo: true, repeat: n * 2 + 1, ease: "sine.inOut", immediateRender: false }, a.t)
      .to(it.corps, { y: 0, duration: 0.2 }, a.t + (n + 1) * cadence);
  };
  const pivot = (n, x, y) => gsap.set(n, { svgOrigin: `${x} ${y}` });
  // Une piece a la fois animee en permanence (vie) et par les actions : deux groupes emboites, memes pivots --
  // sinon le mouvement permanent efface la fin de l'action. -> [groupe des actions, groupe du mouvement permanent]
  const duo = (parent, x, y) => { const ext = g(parent), int = g(ext); pivot(ext, x, y); pivot(int, x, y); return [ext, int]; };

  // ---------------------------------------------------------------- suricate
  reg("suricate", {
    echelle: 1.7, nom: "Le suricate", hauteur: 170, vitesse: 90,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      membre(corps, [[-14, -22], [-46, -12], [-70, -2]], 7);                                // queue
      for (const x of [-9, 11]) { const pg = g(corps); membre(pg, [[x, -42], [x + 1, -6]], 15); ell(pg, x + 6, -3, 15, 6); pivot(pg, x, -42); pattes.push(pg); }
      ell(corps, 0, -88, 26, 50, 4);                                                         // torse dresse
      const bras = g(corps); membre(bras, [[14, -108], [30, -92], [22, -76]], 9); pivot(bras, 14, -108);
      const tete = g(corps);
      ell(tete, 8, -150, 18, 17); ell(tete, 25, -144, 14, 9, 14);                            // crane, museau
      ell(tete, -4, -166, 6, 8, -20);                                                         // oreille
      pivot(tete, 4, -138);
      return { corps, pattes, tete, bras };
    },
    vie(tl, it, t0, t1) { balance(tl, it.bras, -3, 5, 1.1, t0, t1); },
    actions: {
      // Guet : la tete balaie l'horizon (regard a droite, puis a gauche).
      guetter(tl, it, a) {
        const d = a.duree || 4;
        for (let k = 0, t = a.t; t < a.t + d; k++, t += 0.9) {
          tl.to(it.tete, { scaleX: k % 2 ? -1 : 1, rotation: k % 2 ? 8 : -12, duration: 0.18, ease: "power2.out" }, t);
        }
        tl.fromTo(it.corps, { y: 0 }, { y: -8, duration: 0.14, yoyo: true, repeat: 3, immediateRender: false }, a.t + 0.1)
          .to(it.tete, { scaleX: 1, rotation: 0, duration: 0.25 }, a.t + d);
        return d;
      },
    },
  });

  // ------------------------------------------------------------------- lion
  reg("lion", {
    echelle: 1.25, nom: "Le lion", hauteur: 240, vitesse: 70,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      // Pattes de derriere (loin : meme couleur, decalees), puis du devant.
      for (const [x, ang] of [[-112, 0], [-84, 0], [86, 0], [114, 0]]) {
        const pg = g(corps);
        membre(pg, x < 0 ? [[x, -120], [x - 8, -62], [x - 2, -6]] : [[x, -120], [x + 2, -60], [x + 4, -6]], x < 0 ? 38 : 32);
        ell(pg, x + 10, -5, 24, 8); pivot(pg, x, -120); pattes.push(pg);
      }
      ell(corps, 0, -156, 150, 66, -3);                                                       // corps
      const queue = g(corps);
      membre(queue, [[-140, -178], [-186, -170], [-206, -120], [-204, -70]], 9); ell(queue, -204, -56, 13, 26);
      pivot(queue, -140, -178);
      const [tete, teteVie] = duo(corps, 130, -190);
      el("circle", { cx: 162, cy: -206, r: 74, fill: "currentColor" }, teteVie);                // crinière
      for (let a = 0; a < 360; a += 30) el("circle", { cx: 162 + 74 * Math.cos(a * Math.PI / 180), cy: -206 + 74 * Math.sin(a * Math.PI / 180), r: 20, fill: "currentColor" }, teteVie);
      ell(teteVie, 214, -196, 40, 30, 8); ell(teteVie, 246, -188, 18, 14);                   // face, museau
      ell(teteVie, 150, -282, 11, 12); ell(teteVie, 196, -270, 11, 12);                       // oreilles
      return { corps, pattes, queue, tete, teteVie };
    },
    vie(tl, it, t0, t1) { balance(tl, it.queue, -7, 9, 1.3, t0, t1); balance(tl, it.teteVie, -2, 2, 2.2, t0, t1); },
    actions: {
      // Sieste : la tete s'abaisse, le corps s'affaisse un peu.
      dormir(tl, it, a) {
        const d = a.duree || 4;
        tl.to(it.tete, { rotation: 18, y: 38, x: -6, duration: 0.8, ease: "power2.inOut" }, a.t)
          .to(it.corps, { y: 24, scaleY: 0.82, svgOrigin: "0 0", duration: 0.8, ease: "power2.inOut" }, a.t)
          .to(it.tete, { rotation: 0, y: 0, x: 0, duration: 0.5 }, a.t + d)
          .to(it.corps, { y: 0, scaleY: 1, duration: 0.5 }, a.t + d);
        if (it.zz) tl.fromTo(it.zz, { opacity: 0, y: 0 }, { opacity: 1, y: -50, duration: d, ease: "none", immediateRender: false }, a.t + 0.6)
          .set(it.zz, { opacity: 0 }, a.t + d);
        return d;
      },
    },
  });

  // ----------------------------------------------------------------- girafe
  reg("girafe", {
    nom: "La girafe", hauteur: 640, vitesse: 60,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      for (const [x, dx] of [[-98, -6], [-66, -2], [72, 4], [102, 8]]) {
        const pg = g(corps); membre(pg, [[x, -300], [x + dx / 2, -150], [x + dx, -8]], 26); ell(pg, x + dx + 8, -5, 21, 8); pivot(pg, x, -300); pattes.push(pg);
      }
      forme(corps, lisse([[-130, -320], [-110, -396], [-20, -420], [70, -428], [120, -390], [116, -310], [40, -262], [-40, -258], [-120, -276]], true));   // corps
      const queue = g(corps); membre(queue, [[-116, -340], [-150, -300], [-152, -230]], 7); ell(queue, -152, -218, 8, 18); pivot(queue, -116, -340);
      const [cou, couVie] = duo(corps, 82, -352);
      forme(couVie, "M30 -380 L124 -392 L196 -586 L136 -608 Z");                                // cou
      const [tete, teteVie] = duo(couVie, 165, -596);
      ell(teteVie, 188, -612, 52, 26, -22); ell(teteVie, 232, -594, 22, 16, -22);               // tete, museau
      membre(teteVie, [[176, -634], [170, -672]], 6); membre(teteVie, [[196, -632], [200, -670]], 6);
      ell(teteVie, 170, -676, 6, 6); ell(teteVie, 201, -674, 6, 6); ell(teteVie, 150, -622, 14, 8, 30);
      return { corps, pattes, queue, cou, couVie, tete, teteVie };
    },
    vie(tl, it, t0, t1) { balance(tl, it.couVie, -2, 4, 2.4, t0, t1); balance(tl, it.teteVie, -5, 4, 1.7, t0, t1); balance(tl, it.queue, -6, 8, 1.4, t0, t1); },
    actions: {
      // Regarde ailleurs : le cou s'incline, la tete se tourne.
      regarder(tl, it, a) {
        const d = a.duree || 3;
        tl.to(it.cou, { rotation: 14, duration: 0.9, ease: "power2.inOut" }, a.t).to(it.tete, { rotation: 14, duration: 0.9 }, a.t)
          .to(it.cou, { rotation: 0, duration: 0.9 }, a.t + d).to(it.tete, { rotation: 0, duration: 0.9 }, a.t + d);
        return d;
      },
    },
  });

  // --------------------------------------------------------------- elephant
  reg("elephant", {
    nom: "L'éléphant", hauteur: 360, vitesse: 45,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      for (const [x, w] of [[-120, 58], [-62, 58], [62, 60], [122, 62]]) {
        const pg = g(corps); membre(pg, [[x, -180], [x, -90], [x + 2, -14]], w); ell(pg, x + 4, -8, w * 0.58, 12); pivot(pg, x, -180); pattes.push(pg);
      }
      ell(corps, 0, -236, 188, 124, -2);                                                      // corps
      membre(corps, [[-184, -270], [-208, -210], [-200, -150]], 8);                           // queue
      const tete = g(corps);
      ell(tete, 196, -270, 88, 92);                                                           // tete
      const [oreille, oreilleVie] = duo(tete, 160, -300);
      forme(oreilleVie, lisse([[150, -330], [96, -350], [56, -290], [70, -190], [130, -190], [172, -240]], true));
      const [trompe, trompeVie] = duo(tete, 236, -290);
      forme(trompeVie, "M232 -300 C282 -290 306 -190 292 -90 C288 -50 276 -22 262 -24 C250 -26 262 -62 264 -90 C270 -170 244 -210 214 -226 Z");
      pivot(tete, 160, -250);
      return { corps, pattes, tete, oreille, oreilleVie, trompe, trompeVie };
    },
    vie(tl, it, t0, t1) { balance(tl, it.oreilleVie, -5, 9, 1.6, t0, t1); balance(tl, it.trompeVie, -5, 6, 2.1, t0, t1); },
    actions: {
      barrir(tl, it, a) {
        tl.to(it.trompe, { rotation: -42, duration: 0.5, ease: "back.out(2)" }, a.t).to(it.trompe, { rotation: 0, duration: 0.7 }, a.t + 1.4)
          .to(it.oreille, { rotation: 18, duration: 0.3, yoyo: true, repeat: 3 }, a.t);
        return 2;
      },
    },
  });

  // ----------------------------------------------------------------- tortue
  reg("tortue", {
    echelle: 1.5, nom: "La tortue", hauteur: 120, vitesse: 14,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      for (const x of [-62, 52]) { const pg = g(corps); ell(pg, x, -14, 24, 17); pivot(pg, x, -30); pattes.push(pg); }
      const tete = g(corps);
      membre(tete, [[92, -52], [122, -62]], 22); ell(tete, 140, -66, 24, 18); pivot(tete, 90, -52);
      forme(corps, "M-112 -22 C-112 -138 112 -138 112 -22 Z");                                // carapace
      membre(corps, [[-110, -30], [-134, -22]], 8);                                           // queue
      return { corps, pattes, tete };
    },
    vie(tl, it, t0, t1) { balance(tl, it.tete, -4, 6, 2.4, t0, t1); },
    actions: {
      rentrer(tl, it, a) {
        const d = a.duree || 2.5;
        tl.to(it.tete, { x: -64, scaleX: 0.5, duration: 0.5, ease: "power2.in" }, a.t).to(it.tete, { x: 0, scaleX: 1, duration: 0.6 }, a.t + d);
        return d;
      },
    },
  });

  // --------------------------------------------------------------- autruche
  reg("autruche", {
    nom: "L'autruche", hauteur: 330, vitesse: 120,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      for (const x of [-12, 14]) { const pg = g(corps); membre(pg, [[x, -150], [x + 4, -76], [x - 2, -8]], 15); membre(pg, [[x - 2, -8], [x + 24, -4]], 10); pivot(pg, x, -150); pattes.push(pg); }
      ell(corps, -64, -214, 50, 36, 22); ell(corps, 0, -190, 66, 54, -6);                    // plumes, corps
      const [cou, couVie] = duo(corps, 42, -214);
      membre(couVie, [[42, -220], [64, -300], [70, -346]], 15);
      const tete = g(couVie); ell(tete, 82, -356, 20, 12, -8); forme(tete, "M98 -358 L122 -352 L98 -348 Z");
      const sable = g(parent); ell(sable, 120, -4, 62, 18);                                    // monticule (au premier plan)
      sable.setAttribute("opacity", 0);
      return { corps, pattes, cou, couVie, tete, sable };
    },
    vie(tl, it, t0, t1) { balance(tl, it.couVie, -4, 4, 1.9, t0, t1); },
    actions: {
      // Tete dans le sable (le gag de l'autruche) : le cou plonge, un monticule cache la tete.
      enfouir(tl, it, a) {
        const d = a.duree || 3;
        tl.set(it.sable, { opacity: 1 }, a.t + 0.45).to(it.cou, { rotation: 128, duration: 0.7, ease: "power2.in" }, a.t)
          .to(it.cou, { rotation: 0, duration: 0.6, ease: "power2.out" }, a.t + d).set(it.sable, { opacity: 0 }, a.t + d + 0.5);
        return d;
      },
    },
  });

  // ------------------------------------------------------------------- paon
  reg("paon", {
    echelle: 1.3, nom: "Le paon", hauteur: 300, vitesse: 70,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      const eventail = g(corps);
      forme(eventail, "M-26 -150 L" + [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((k) => { const a = (-162 + k * 12) * Math.PI / 180; return `${-26 + 150 * Math.cos(a)} ${-150 + 150 * Math.sin(a)}`; }).join(" L") + " Z");
      for (let i = 0; i < 27; i++) {
        const a = -164 + i * 6.1;
        const plume = g(eventail, { transform: `rotate(${a} -26 -150)` });
        ell(plume, -26 + 190, -150, 96, 8); el("circle", { cx: -26 + 282, cy: -150, r: 14, fill: "currentColor" }, plume);
      }
      pivot(eventail, -26, -150); gsap.set(eventail, { scale: 0, opacity: 0 });
      const traine = g(corps);
      forme(traine, "M-16 -138 C-90 -112 -200 -52 -330 -2 C-250 -52 -150 -86 -50 -86 Z");     // longue traine
      for (const x of [-4, 14]) { const pg = g(corps); membre(pg, [[x, -76], [x + 2, -38], [x, -4]], 8); membre(pg, [[x, -4], [x + 16, -2]], 6); pivot(pg, x, -76); pattes.push(pg); }
      ell(corps, 0, -112, 36, 52, 18);
      const cou = g(corps);
      membre(cou, [[16, -140], [34, -196], [48, -226]], 14);
      const tete = g(cou); ell(tete, 54, -238, 12, 10); forme(tete, "M62 -238 L80 -233 L62 -230 Z");
      membre(tete, [[50, -246], [46, -268]], 3); membre(tete, [[54, -247], [56, -270]], 3); membre(tete, [[58, -246], [64, -266]], 3);
      pivot(cou, 16, -140);
      return { corps, pattes, cou, tete, eventail };
    },
    vie(tl, it, t0, t1) { balance(tl, it.cou, -3, 5, 1.2, t0, t1); },
    actions: {
      deployer(tl, it, a) {
        const d = a.duree || 3.5;
        tl.to(it.eventail, { scale: 1, opacity: 1, duration: 0.9, ease: "back.out(1.4)" }, a.t)
          .to(it.eventail, { rotation: 3, duration: 0.15, yoyo: true, repeat: 5 }, a.t + 1.2)
          .to(it.eventail, { scale: 0, opacity: 0, duration: 0.6, ease: "power2.in" }, a.t + d);
        return d;
      },
    },
  });

  // ------------------------------------------------------------------- gnou (troupeau)
  reg("gnou", {
    echelle: 1.6, nom: "Le gnou", hauteur: 130, vitesse: 55,
    dessiner(parent) {
      const corps = g(parent), pattes = [];
      for (const [x, d] of [[-34, -3], [-22, 2], [26, 3], [38, -2]]) { const pg = g(corps); membre(pg, [[x, -62], [x + d, -32], [x + d, -3]], 7); pivot(pg, x, -62); pattes.push(pg); }
      ell(corps, 0, -78, 50, 24, -4);
      membre(corps, [[-48, -86], [-60, -66], [-58, -40]], 4);
      const tete = g(corps); membre(tete, [[36, -90], [58, -112]], 16); ell(tete, 66, -114, 15, 12, 30);
      membre(tete, [[62, -122], [56, -138], [66, -142]], 3.5); pivot(tete, 40, -92);
      return { corps, pattes, tete };
    },
    vie(tl, it, t0, t1) { balance(tl, it.tete, -6, 8, 1.8, t0, t1); },
    actions: {},
  });

  // ------------------------------------------------------- oiseaux (dans le ciel)
  reg("oiseaux", {
    nom: "Les oiseaux", hauteur: 60, vitesse: 120, ciel: true,
    dessiner(parent, o = {}) {
      const n = o.nombre || 7, corps = g(parent), ailes = [], hasard = Doc.rng(o.graine || 7);
      for (let i = 0; i < n; i++) {
        const b = g(corps, { transform: `translate(${(i % 2 ? 1 : -1) * (30 + i * 26)} ${-i * 16 + (hasard() - 0.5) * 26}) scale(${0.8 + hasard() * 0.5})` });
        const aile = g(b); forme(aile, "M-22 2 Q-11 -16 0 0 Q11 -16 22 2 Q11 -6 0 6 Q-11 -6 -22 2 Z"); pivot(aile, 0, 2);
        ailes.push([aile, hasard() * 0.3]);
      }
      return { corps, ailes, pattes: [] };
    },
    vie(tl, it, t0, t1) {
      for (const [aile, ph] of it.ailes) tl.fromTo(aile, { scaleY: 1 }, { scaleY: -0.35, duration: 0.28, yoyo: true, repeat: Math.ceil((t1 - t0) / 0.28), ease: "sine.inOut", immediateRender: false }, t0 + ph);
    },
    actions: {},
  });

  // -------------------------------------------------- actions communes a toutes
  Doc.actionsCommunes = {
    // Marche vers x (le regard suit le sens) ; sans "vers", reste en place.
    marcher(tl, it, a, ctx) {
      const dist = Math.abs(a.vers - ctx.x(it)), v = a.vitesse || it.espece.vitesse || 80;
      const duree = a.duree || Math.max(0.8, dist / v);
      ctx.deplacer(it, a.vers, a.t, duree);
      if (it.pattes.length) pas(tl, it, a, duree, it.espece.id === "tortue" ? 14 : 22, it.espece.id === "tortue" ? 0.9 : 0.32);
      return duree;
    },
    attendre(tl, it, a) { return a.duree || 1; },
  };
})();
