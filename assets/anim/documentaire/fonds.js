// Moments de la journee et habitats du documentaire. Un habitat empile des plans (ciel, loin, moyen, sol,
// avant) qui defilent a des vitesses differentes quand la camera bouge (parallaxe) ; leurs couleurs viennent
// du moment : tout est teinte par la lumiere, jamais de couleur "posee".
(() => {
  const { g, el, mix, rng, forme, ell, membre, lisse } = Doc;

  // ciel : du haut vers l'horizon. sil : couleur des silhouettes au premier plan. astre : soleil ou lune.
  Doc.MOMENTS = {
    aube:       { ciel: ["#2a2f63", "#a9527f", "#ff9a62", "#ffd9a0"], sil: "#1b1626", astre: { x: 300, y: 1230, r: 150, c: "#fff0c2" }, lueur: "#ff9a62", etoiles: 0 },
    jour:       { ciel: ["#2f78c8", "#6cb0e6", "#bfe2f4", "#f7e8c0"], sil: "#2a2116", astre: { x: 800, y: 470, r: 100, c: "#fffbe2" }, lueur: "#ffe9a8", etoiles: 0 },
    crepuscule: { ciel: ["#1a1d49", "#6a3a7c", "#e2603e", "#ffb347"], sil: "#110c16", astre: { x: 640, y: 1210, r: 175, c: "#ffd27a" }, lueur: "#ff8a3d", etoiles: 0 },
    nuit:       { ciel: ["#040613", "#0b1738", "#183059", "#2b4a78"], sil: "#03050b", astre: { x: 770, y: 430, r: 78, c: "#e8eefc" }, lueur: "#7ea0d8", etoiles: 70 },
  };
  Doc.HABITATS = ["savane", "foret", "desert", "montagne", "mare"];

  const HOR = 1330, SOL = 1500, W = 1080, H = 1920;
  Doc.HOR = HOR; Doc.SOL = SOL;

  function colline(parent, rand, base, amp, couleur, { pas = 150, from = -120, to = 1200 } = {}) {
    const pts = [];
    for (let x = from; x <= to; x += pas) pts.push([x, base - amp * (0.3 + rand() * 0.7)]);
    return forme(parent, lisse(pts) + ` L${to} 1900 L${from} 1900 Z`, { fill: couleur });
  }
  const touffe = (parent, x, y, h, couleur, rand) => {
    for (let i = 0; i < 7; i++) {
      const dx = (i - 3) * 9, hh = h * (0.55 + rand() * 0.5), pen = (i - 3) * 6 + (rand() - 0.5) * 10;
      forme(parent, `M${x + dx - 4} ${y} Q${x + dx + pen * 0.3} ${y - hh * 0.6} ${x + dx + pen} ${y - hh} Q${x + dx + pen * 0.3 + 3} ${y - hh * 0.5} ${x + dx + 5} ${y} Z`, { fill: couleur });
    }
  };

  // Terre : eclairee par la lumiere au ras du sol, noire en bas (la ou passent les sous-titres).
  function terre(L, M, y) {
    const id = "terre" + L.uid, gr = el("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 }, el("defs", {}, L.sol));
    el("stop", { offset: 0, "stop-color": mix(M.ciel[3], M.sil, 0.68) }, gr); el("stop", { offset: 0.3, "stop-color": mix(M.ciel[3], M.sil, 0.9) }, gr); el("stop", { offset: 1, "stop-color": M.sil }, gr);
    el("rect", { x: -200, y, width: W + 400, height: H - y + 100, fill: `url(#${id})` }, L.sol);
  }

  // ------------------------------------------------------------------ ciel commun
  function ciel(L, M, uid, rand) {
    const defs = el("defs", {}, L.ciel);
    const gr = el("linearGradient", { id: "ciel" + uid, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
    M.ciel.forEach((c, i) => el("stop", { offset: i / (M.ciel.length - 1), "stop-color": c }, gr));
    el("rect", { x: -200, y: -100, width: W + 400, height: HOR + 160, fill: `url(#ciel${uid})` }, L.ciel);
    const a = M.astre, lu = el("radialGradient", { id: "lueur" + uid }, defs);
    el("stop", { offset: 0, "stop-color": M.lueur, "stop-opacity": 0.85 }, lu); el("stop", { offset: 1, "stop-color": M.lueur, "stop-opacity": 0 }, lu);
    el("circle", { cx: a.x, cy: a.y, r: a.r * 4.4, fill: `url(#lueur${uid})` }, L.ciel);
    el("circle", { cx: a.x, cy: a.y, r: a.r, fill: a.c }, L.ciel);
    if (M.etoiles) {
      el("circle", { cx: a.x + 26, cy: a.y - 14, r: a.r * 0.9, fill: M.ciel[1], opacity: 0.55 }, L.ciel);   // croissant
      L.etoiles = [];
      for (let i = 0; i < M.etoiles; i++) L.etoiles.push(el("circle", { cx: rand() * W, cy: rand() * 900, r: 1 + rand() * 2.2, fill: "#fff", opacity: 0.35 + rand() * 0.6 }, L.ciel));
    } else {
      L.nuages = [];      // nuages etires, teintes par la lumiere
      for (let i = 0; i < 5; i++) {
        const gn = g(L.ciel, { opacity: 0.5 }), y = 380 + i * 150 + rand() * 60, x = rand() * W, c = mix(M.ciel[2], M.lueur, 0.45);
        for (let k = 0; k < 4; k++) ell(gn, x + k * 70 - 100, y + (k % 2) * 8, 110 + rand() * 60, 14 + rand() * 8).setAttribute("fill", c);
        L.nuages.push(gn);
      }
    }
  }

  // ----------------------------------------------------------------- habitats
  const HAB = {
    savane(L, M, rand) {
      const h = M.ciel[3], loin = mix(h, M.sil, 0.28), moyen = mix(h, M.sil, 0.55);
      colline(L.loin, rand, HOR - 20, 120, loin, { pas: 210 });
      colline(L.moyen, rand, HOR + 30, 80, moyen, { pas: 170 });
      for (const [x, s] of [[170, 1], [800, 1.25], [1010, 0.8]]) {      // acacias (houppier plat)
        const a = g(L.moyen, { transform: `translate(${x} ${HOR + 52}) scale(${s})` });
        forme(a, "M-9 0 C-6 -90 -2 -150 -22 -214 L-12 -216 C6 -160 4 -100 10 0 Z", { fill: moyen });
        for (const [cx, cy, rx, ry] of [[-20, -230, 90, 20], [34, -250, 76, 18], [-70, -214, 54, 14], [80, -226, 50, 13]]) ell(a, cx, cy, rx, ry).setAttribute("fill", moyen);
      }
      el("rect", { x: -200, y: HOR + 60, width: W + 400, height: H, fill: mix(h, M.sil, 0.78) }, L.sol);
      colline(L.sol, rand, SOL + 40, 40, mix(h, M.sil, 0.82), { pas: 260 });
      terre(L, M, SOL + 30);
      for (let i = 0; i < 14; i++) touffe(L.avant, rand() * W, 1700 + rand() * 260, 90 + rand() * 110, M.sil, rand);
    },
    foret(L, M, rand) {
      const h = M.ciel[3], vert = mix("#16301f", M.ciel[1], 0.25), brume = mix(h, "#ffffff", 0.2);
      el("rect", { x: -200, y: -100, width: W + 400, height: 2100, fill: mix(M.ciel[2], vert, 0.55) }, L.ciel);
      const tronc = (parent, x, w, couleur) => forme(parent, `M${x - w / 2} 1900 L${x - w * 0.34} -200 L${x + w * 0.34} -200 L${x + w / 2} 1900 Z`, { fill: couleur });
      for (let i = 0; i < 9; i++) tronc(L.loin, 40 + i * 130 + rand() * 40, 34 + rand() * 22, mix(vert, h, 0.3 - rand() * 0.08));
      const rayons = g(L.loin, { opacity: 0.2 });
      for (const x of [140, 400, 690]) forme(rayons, `M${x} -100 L${x + 100} -100 L${x + 400} 1900 L${x + 140} 1900 Z`, { fill: M.lueur });
      L.brume = [el("rect", { x: -200, y: HOR - 160, width: W + 400, height: 330, fill: brume, opacity: 0.22 }, L.loin)];
      for (let i = 0; i < 6; i++) tronc(L.moyen, 20 + i * 210 + rand() * 60, 66 + rand() * 40, mix(vert, M.sil, 0.55 + rand() * 0.1));
      for (let i = 0; i < 8; i++) ell(L.moyen, rand() * W, rand() * 160 - 40, 120 + rand() * 120, 70 + rand() * 50).setAttribute("fill", mix(vert, M.sil, 0.6));   // canopee
      terre(L, M, HOR + 40);
      tronc(L.avant, -30, 190, M.sil); tronc(L.avant, 1110, 220, M.sil);
      for (let i = 0; i < 9; i++) {      // fougeres
        const x = rand() * W, y = 1780 + rand() * 140;
        for (let k = 0; k < 7; k++) forme(L.avant, `M${x} ${y} Q${x + (k - 3) * 40} ${y - 90 - rand() * 50} ${x + (k - 3) * 70} ${y - 40 + rand() * 30} Q${x + (k - 3) * 36} ${y - 60} ${x} ${y} Z`, { fill: M.sil });
      }
    },
    desert(L, M, rand) {
      const h = M.ciel[3], loin = mix(h, M.sil, 0.22), moyen = mix(h, M.sil, 0.5);
      colline(L.loin, rand, HOR - 10, 90, loin, { pas: 300 });
      colline(L.moyen, rand, HOR + 40, 120, moyen, { pas: 340 });
      for (const [x, s] of [[110, 1], [960, 1.3]]) {      // cactus
        const c = g(L.moyen, { transform: `translate(${x} ${HOR + 70}) scale(${s})`, color: moyen });
        membre(c, [[0, 0], [0, -250]], 38); membre(c, [[0, -100], [-62, -100], [-62, -180]], 26); membre(c, [[0, -140], [58, -140], [58, -210]], 24);
      }
      el("rect", { x: -200, y: HOR + 70, width: W + 400, height: H, fill: mix(h, M.sil, 0.7) }, L.sol);
      colline(L.sol, rand, SOL + 36, 50, mix(h, M.sil, 0.85), { pas: 420 });
      terre(L, M, SOL + 36);
      for (let i = 0; i < 6; i++) {
        ell(L.avant, rand() * W, 1810 + rand() * 80, 30 + rand() * 50, 14 + rand() * 12).setAttribute("fill", M.sil);
        touffe(L.avant, rand() * W, 1850 + rand() * 60, 90 + rand() * 90, M.sil, rand);
      }
    },
    montagne(L, M, rand) {
      const h = M.ciel[3], pic = (parent, base, haut, couleur, neige) => {
        const pts = []; let x = -160;
        while (x < 1240) { pts.push([x, base - haut * (0.35 + rand() * 0.65)]); x += 110 + rand() * 110; pts.push([x - 40, base - haut * (0.1 + rand() * 0.2)]); }
        forme(parent, "M" + pts.map((p) => p.join(" ")).join(" L") + " L1240 1900 L-160 1900 Z", { fill: couleur });
      };
      pic(L.loin, HOR + 10, 520, mix(h, M.sil, 0.25), true);
      pic(L.moyen, HOR + 60, 340, mix(h, M.sil, 0.5), false);
      for (const [x, s] of [[90, 1.1], [980, 1.4], [820, 0.9]]) {      // sapins
        const a = g(L.moyen, { transform: `translate(${x} ${HOR + 80}) scale(${s})` });
        for (let k = 0; k < 4; k++) forme(a, `M${-70 + k * 12} ${-k * 60} L0 ${-110 - k * 60} L${70 - k * 12} ${-k * 60} Z`, { fill: mix(h, M.sil, 0.62) });
      }
      el("rect", { x: -200, y: HOR + 80, width: W + 400, height: H, fill: mix(h, M.sil, 0.78) }, L.sol);
      terre(L, M, SOL + 26);
      for (let i = 0; i < 8; i++) touffe(L.avant, rand() * W, 1760 + rand() * 200, 90 + rand() * 100, M.sil, rand);
    },
    mare(L, M, rand) {
      const h = M.ciel[3], loin = mix(h, M.sil, 0.3);
      colline(L.loin, rand, HOR - 4, 60, loin, { pas: 120 });
      const eau = el("linearGradient", { id: "eau" + L.uid, x1: 0, y1: 0, x2: 0, y2: 1 }, el("defs", {}, L.moyen));
      el("stop", { offset: 0, "stop-color": mix(h, M.ciel[2], 0.4) }, eau); el("stop", { offset: 1, "stop-color": mix(M.ciel[0], M.sil, 0.6) }, eau);
      el("rect", { x: -200, y: HOR, width: W + 400, height: SOL - HOR + 160, fill: `url(#eau${L.uid})` }, L.moyen);
      L.reflets = [];
      for (let i = 0; i < 12; i++) L.reflets.push(el("rect", { x: M.astre.x - 90 + rand() * 180 - i * 4, y: HOR + 12 + i * 11, width: 60 + rand() * 140, height: 4, rx: 2, fill: M.astre.c, opacity: 0.5 - i * 0.03 }, L.moyen));
      for (const [x, s] of [[70, 0.9], [990, 1.1]]) {
        const a = g(L.moyen, { transform: `translate(${x} ${HOR + 4}) scale(${s})` });
        forme(a, "M-6 0 C-4 -90 0 -150 -12 -190 L-2 -192 C10 -150 8 -80 8 0 Z", { fill: loin });
        for (const [cx, cy, rx, ry] of [[-10, -196, 60, 24], [26, -176, 44, 20], [-50, -170, 36, 18]]) ell(a, cx, cy, rx, ry).setAttribute("fill", loin);
      }
      forme(L.sol, lisse([[-200, SOL + 10], [200, SOL - 26], [560, SOL - 6], [900, SOL - 28], [1280, SOL + 4]]) + ` L1280 ${H} L-200 ${H} Z`, { fill: M.sil });
      for (let i = 0; i < 12; i++) {      // roseaux
        const x = (i % 2 ? 960 : 20) + (rand() - 0.5) * 220, y = 1790 + rand() * 130, hh = 200 + rand() * 200;
        forme(L.avant, `M${x - 4} ${y} Q${x + 12} ${y - hh * 0.6} ${x + 22} ${y - hh} Q${x + 10} ${y - hh * 0.55} ${x + 4} ${y} Z`, { fill: M.sil });
        if (i % 3 === 0) ell(L.avant, x + 22, y - hh + 16, 8, 26, 10).setAttribute("fill", M.sil);
      }
    },
  };

  // Monte le decor dans `racine` -> { plans: {nom: {g, k}}, M, L }. k = part du mouvement de la camera.
  Doc.monterDecor = (racine, habitat, moment, graine = 1) => {
    const M = Doc.MOMENTS[moment] || Doc.MOMENTS.crepuscule, rand = rng(graine * 97 + 13);
    const L = { uid: String(graine) }, plans = {};
    for (const [nom, k] of [["ciel", 0.06], ["loin", 0.22], ["moyen", 0.5], ["sol", 1], ["acteurs", 1], ["avant", 1.5]]) { L[nom] = g(racine); plans[nom] = { g: L[nom], k }; }
    ciel(L, M, L.uid, rand);
    (HAB[habitat] || HAB.savane)(L, M, rand);
    return { plans, M, L };
  };
})();
