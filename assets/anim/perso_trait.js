// Personnages "trait blanc" (dialogue.html, style=trait) : dessin a la main
// blanc sur fond noir, traits tremblés repassés deux fois, grosse tete ronde
// de profil (un oeil, petit sourire), corps en batons, pieds ovales -- le style
// des petites histoires dessinees qui tournent sur TikTok.
//
// Meme interface que perso.js (dessiner, expression, parler, geste, vie,
// regarder) : dialogue.html choisit l'un ou l'autre. En plus :
//   - chaque trait existe en deux variantes tremblees qui alternent ~6 fois
//     par seconde ("boiling lines" du dessin anime) ;
//   - apparition : les traits se dessinent (stroke-dashoffset) ;
//   - sol(svg, y) : le bord de falaise hachure sur lequel ils se tiennent.
// Determinste (pseudo-hasard a graine fixe par personnage) et 100 % timeline :
// seek(t) donne l'etat exact a l'instant t.
// A charger apres gsap et common.js.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const PERSOS = {
    femme: { nom: "Léa", tenue: "robe", coiffure: "chignon", accessoire: "" },
    homme: { nom: "Karim", tenue: "pantalon", coiffure: "meche", accessoire: "cravate" },
  };
  const BOIL = 0.16;   // duree d'une variante de trait (s)

  const mulberry = (seed) => () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const hash = (s) => [...s].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 7);
  const f1 = (v) => Math.round(v * 10) / 10;
  const smooth = (pts) => {
    let d = `M${f1(pts[0][0])} ${f1(pts[0][1])}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += ` C${f1(p1[0] + (p2[0] - p0[0]) / 6)} ${f1(p1[1] + (p2[1] - p0[1]) / 6)} ` +
        `${f1(p2[0] - (p3[0] - p1[0]) / 6)} ${f1(p2[1] - (p3[1] - p1[1]) / 6)} ${f1(p2[0])} ${f1(p2[1])}`;
    }
    return d;
  };
  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const g = (parent, attrs = {}) => el("g", attrs, parent);

  // Pinceau : chaque forme est tracee en deux variantes (classes va / vb), chacune
  // repassee `passes` fois avec un leger decalage -- le trait "vit".
  function pinceau(seed) {
    const rnd = mulberry(seed);
    const j = (a) => (rnd() - 0.5) * 2 * a;
    const trace = (parent, pts, { w = 3.4, passes = 2, jit = 3.2, ferme = false, plein = false, alpha = null } = {}) => {
      for (const v of ["va", "vb"]) {
        const grp = g(parent, { class: v });
        for (let k = 0; k < passes; k++) {
          let p = pts.map(([x, y]) => [x + j(jit), y + j(jit)]);
          if (!ferme && p.length > 1) {   // depasse un peu aux extremites, comme un trait rapide
            const [a, b] = [p[0], p[1]], [c, d] = [p[p.length - 1], p[p.length - 2]];
            const o = 0.06 + rnd() * 0.08;
            p = [[a[0] + (a[0] - b[0]) * o, a[1] + (a[1] - b[1]) * o], ...p, [c[0] + (c[0] - d[0]) * o, c[1] + (c[1] - d[1]) * o]];
          }
          el("path", { d: smooth(p) + (plein ? "Z" : ""), class: "tr", pathLength: 1, fill: plein ? "#ffffff" : "none",
            stroke: "#ffffff", "stroke-width": w * (k ? 0.7 : 1), "stroke-linecap": "round", "stroke-linejoin": "round",
            opacity: alpha ?? (k ? 0.75 : 0.95) }, grp);
        }
      }
    };
    // Cercle a main levee : un peu plus d'un tour, la fin rentre legerement (spirale)
    // comme un vrai coup de crayon. Le rayon ondule doucement (basses frequences)
    // au lieu de trembler point par point -- sinon le cercle a des bosses de caillou.
    // Chaque passe est un tour complet decale, plus fin.
    const rond = (parent, cx, cy, rx, ry = rx, o = {}) => {
      const passes = o.passes ?? 2, w = o.w ?? 3.4;
      for (let k = 0; k < passes; k++) {
        const n = Math.max(32, Math.round((rx + ry) / 4)), a0 = rnd() * Math.PI * 2, tours = 1.04 + rnd() * 0.08;
        const f1 = rnd() * 6.28, f2 = rnd() * 6.28, amp = k ? 0.018 : 0.011, dx = j(k ? 2.2 : 0.6), dy = j(k ? 2.2 : 0.6), pts = [];
        for (let i = 0; i <= n; i++) {
          const t = (i / n) * tours, a = a0 + t * Math.PI * 2;
          const r = 1 + amp * (0.6 * Math.sin(2 * a + f1) + 0.4 * Math.sin(3 * a + f2)) - 0.035 * Math.max(0, t - 1) / (tours - 1);
          pts.push([cx + dx + Math.cos(a) * rx * r, cy + dy + Math.sin(a) * ry * r]);
        }
        trace(parent, pts, { ...o, passes: 1, ferme: true, jit: o.jit ?? 0.7, w: w * (k ? 0.62 : 1), alpha: k ? 0.6 : 0.95 });
      }
    };
    return { trace, rond, rnd, j };
  }

  // Bras : epaule, coude, poignet (cote s = -1 gauche, 1 droite), bras le long du corps au repos.
  const EPAULE = [12, -606], COUDE = [44, -486], POIGNET = [56, -372];
  const OUT = (s, a) => -s * a;

  function dessiner(svg, id, x, y, echelle, cote) {
    const p = PERSOS[id] || PERSOS.femme;
    const P = pinceau(hash(id) ^ 0x51ed);
    const root = g(svg, { transform: `translate(${x} ${y}) scale(${echelle})`, class: "trait-perso", "data-v": "a" });
    const corps = g(root);
    const c = cote;

    // Jambes et pieds ovales.
    const jambes = g(corps);
    for (const s of [-1, 1]) {
      if (p.tenue === "pantalon") {
        P.trace(jambes, [[s * 8, -385], [s * 10, -200], [s * 12, -22]]);
        P.trace(jambes, [[s * 40, -385], [s * 38, -200], [s * 36, -22]]);
      } else {
        P.trace(jambes, [[s * 18, -335], [s * 20, -180], [s * 22, -24]], { w: 3.6 });
      }
      P.rond(jambes, s * 24 + 14 * c, -12, 32, 13);
    }
    // Tenue.
    const torse = g(corps);
    if (p.tenue === "robe") {
      P.trace(torse, [[-24, -628], [-38, -560], [-70, -440], [-100, -338], [-50, -330], [0, -334], [50, -330], [100, -338], [70, -440], [38, -560], [24, -628]]);
      P.trace(torse, [[-26, -626], [0, -618], [26, -626]], { w: 3 });
    } else {
      P.trace(torse, [[-30, -628], [-52, -580], [-50, -390], [0, -386], [50, -390], [52, -580], [30, -628]]);
      P.trace(torse, [[-12, -628], [0, -600], [12, -628]], { w: 3 });                 // col
      if (p.accessoire === "cravate") P.trace(torse, [[0, -604], [-9, -585], [-6, -470], [0, -452], [6, -470], [9, -585], [0, -604]], { w: 2.6, passes: 1 });
      else P.trace(torse, [[0, -600], [2, -400]], { w: 2.6, passes: 1 });                // boutonnage
    }
    P.trace(corps, [[0, -626], [0, -668]], { w: 3.2 });                                    // cou

    // Tete : grosse tete ronde, de profil (regarde du cote `cote`).
    const tete = g(corps);
    el("circle", { cx: 0, cy: -790, r: 124, fill: "#000000" }, tete);                       // masque le cou derriere
    P.rond(tete, 0, -790, 124, 124, { w: 3.8 });
    if (p.coiffure === "chignon") {
      el("circle", { cx: -88 * c, cy: -900, r: 46, fill: "#000000" }, tete);
      P.rond(tete, -88 * c, -900, 46, 44, { w: 3 });
      P.rond(tete, -86 * c, -902, 30, 28, { w: 2.4, passes: 1 });
      P.rond(tete, -90 * c, -898, 16, 15, { w: 2.2, passes: 1 });
      // Cheveux : ligne en S de la nuque au sommet, meches sur l'arriere.
      P.trace(tete, [[30 * c, -912], [-10 * c, -880], [-40 * c, -820], [-58 * c, -740], [-80 * c, -688]], { w: 3 });
      P.trace(tete, [[-118 * c, -820], [-126 * c, -760], [-122 * c, -700]], { w: 2.4, passes: 1 });
      P.trace(tete, [[-110 * c, -840], [-130 * c, -770], [-134 * c, -720]], { w: 2, passes: 1 });
    } else {
      // Meche : touffes en epis qui depassent du crane, bord interieur en
      // arc sur le front, quelques meches dedans (coordonnees "regarde a droite", x * c).
      const m = (pts) => pts.map(([x, y]) => [x * c, y]);
      el("path", { d: smooth(m([[-118, -840], [-112, -900], [-80, -930], [-60, -918], [-40, -958], [-10, -936], [16, -968], [40, -940],
        [72, -952], [88, -916], [114, -902], [104, -866], [60, -892], [0, -904], [-60, -894], [-118, -840]])) + "Z", fill: "#000000" }, tete);
      P.trace(tete, m([[-118, -840], [-112, -900], [-80, -930], [-60, -918], [-40, -958], [-10, -936], [16, -968], [40, -940],
        [72, -952], [88, -916], [114, -902], [104, -866]]), { w: 3.2, jit: 2.5 });
      P.trace(tete, m([[104, -866], [60, -892], [0, -904], [-60, -894], [-118, -840]]), { w: 3, jit: 2.5 });
      P.trace(tete, m([[-70, -900], [-48, -930]]), { w: 2.2, passes: 1 });
      P.trace(tete, m([[-6, -910], [10, -944]]), { w: 2.2, passes: 1 });
      P.trace(tete, m([[54, -904], [70, -934]]), { w: 2.2, passes: 1 });
    }
    // Oeil facon manga (de profil) : grand contour, paupiere superieure epaisse,
    // iris blanc, pupille noire avec reflets ; cils pour la robe. Variante "^"
    // (yeux fermes de joie) pour l'expression content.
    const ex = 58 * c, ey = -805;
    const m = (pts) => pts.map(([x, y]) => [x * c, y]);
    const yeux = g(tete), oeil = g(yeux), iris = g(oeil);
    P.rond(oeil, ex, ey, 22, 27, { w: 2.6, passes: 1 });
    P.trace(oeil, [[ex - 24 * c, ey - 12], [ex - 2 * c, ey - 30], [ex + 22 * c, ey - 20]], { w: 5.5, passes: 1, jit: 1.5 });
    if (p.tenue === "robe") {
      P.trace(oeil, [[ex + 18 * c, ey - 22], [ex + 32 * c, ey - 32]], { w: 3, passes: 1, jit: 1 });
      P.trace(oeil, [[ex + 21 * c, ey - 15], [ex + 35 * c, ey - 20]], { w: 3, passes: 1, jit: 1 });
    }
    el("ellipse", { cx: ex + 4 * c, cy: ey + 3, rx: 14, ry: 18, fill: "#ffffff" }, iris);
    const pupille = el("ellipse", { cx: ex + 5 * c, cy: ey + 4, rx: 7, ry: 10, fill: "#000000" }, iris);
    el("circle", { cx: ex + 1 * c, cy: ey - 3, r: 4.2, fill: "#ffffff" }, iris);
    el("circle", { cx: ex + 9 * c, cy: ey + 10, r: 2, fill: "#ffffff" }, iris);
    gsap.set(yeux, { svgOrigin: `${ex} ${ey}` });
    gsap.set(pupille, { svgOrigin: `${ex + 5 * c} ${ey + 4}` });
    const joie = g(tete, { opacity: 0 });
    P.trace(joie, [[ex - 20 * c, ey + 6], [ex, ey - 14], [ex + 20 * c, ey + 6]], { w: 4.5, passes: 1 });
    const sourcil = g(tete);
    P.trace(sourcil, [[ex - 22 * c, ey - 44], [ex, ey - 52], [ex + 20 * c, ey - 46]], { w: 3.4 });
    gsap.set(sourcil, { svgOrigin: `${ex} ${ey - 48}` });

    // Symboles manga (emanata), un par expression : joues hachurees (content),
    // traits d'effroi + "!" (choc), goutte de sueur (doute, triste), veine en croix sur le front (agace).
    const signes = {};
    signes.joues = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.joues, m([[50 + i * 11, -752], [62 + i * 11, -778]]), { w: 2.2, passes: 1, jit: 1 });
    signes.choc = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.choc, m([[8 + i * 22, -884], [8 + i * 22, -846 + (i % 2) * 8]]), { w: 2.4, passes: 1, jit: 1 });
    P.trace(signes.choc, m([[118, -1000], [112, -950]]), { w: 6, passes: 1, jit: 1 });
    el("circle", { cx: 110 * c, cy: -930, r: 5, fill: "#ffffff" }, signes.choc);
    signes.goutte = g(tete, { opacity: 0 });
    P.trace(signes.goutte, m([[-128, -900], [-140, -872], [-138, -860], [-128, -854], [-118, -860], [-116, -872], [-128, -900]]), { w: 3, passes: 1, jit: 0.8 });
    signes.veine = g(tete, { opacity: 0 });
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]])
      P.trace(signes.veine, m([[40 + sx * 28, -868 + sy * 9], [40 + sx * 11, -868 + sy * 11], [40 + sx * 9, -868 + sy * 28]]), { w: 3.6, passes: 1, jit: 0.8 });
    P.trace(tete, [[-6 * c, -812], [-14 * c, -790], [-4 * c, -770]], { w: 2.4, passes: 1 });   // oreille

    // Bouches (au bout du profil), une seule visible a la fois.
    const mx = 80 * c, my = -738;
    const BOUCHES = {
      neutre: [[mx - 14 * c, my], [mx + 10 * c, my - 2]],
      content: [[mx - 20 * c, my - 6], [mx - 4 * c, my + 8], [mx + 14 * c, my - 6]],
      doute: [[mx - 16 * c, my + 2], [mx - 2 * c, my - 4], [mx + 12 * c, my + 2]],
      triste: [[mx - 16 * c, my + 6], [mx - 2 * c, my - 6], [mx + 12 * c, my + 6]],
      agace: [[mx - 16 * c, my - 2], [mx + 12 * c, my + 4]],
    };
    const bouches = {};
    for (const [k, pts] of Object.entries(BOUCHES)) { bouches[k] = g(tete, { opacity: 0 }); P.trace(bouches[k], pts, { w: 3.2, passes: 1 }); }
    bouches.choc = g(tete, { opacity: 0 }); P.rond(bouches.choc, mx, my, 9, 12, { w: 3, passes: 1 });
    bouches.ouverte = g(tete, { opacity: 0 }); P.rond(bouches.ouverte, mx, my, 13, 9, { w: 3, passes: 1 });
    gsap.set(tete, { svgOrigin: "0 -668" });

    // Bras en deux segments (baton) + main en trois traits.
    const bras = {};
    for (const s of [-1, 1]) {
      const haut = g(corps), avant = g(haut);
      P.trace(haut, [[EPAULE[0] * s, EPAULE[1]], [COUDE[0] * s, COUDE[1]]], { w: 3.4 });
      P.trace(avant, [[COUDE[0] * s, COUDE[1]], [POIGNET[0] * s, POIGNET[1]]], { w: 3.4 });
      const [hx, hy] = [POIGNET[0] * s, POIGNET[1]];
      P.trace(avant, [[hx, hy], [hx - 6 * s, hy + 24]], { w: 2.6, passes: 1 });
      P.trace(avant, [[hx, hy], [hx + 4 * s, hy + 26]], { w: 2.6, passes: 1 });
      P.trace(avant, [[hx, hy], [hx + 14 * s, hy + 18]], { w: 2.6, passes: 1 });
      gsap.set(haut, { svgOrigin: `${EPAULE[0] * s} ${EPAULE[1]}` });
      gsap.set(avant, { svgOrigin: `${COUDE[0] * s} ${COUDE[1]}` });
      bras[s] = { haut, avant, s };
    }

    return { id, nom: p.nom, couleur: "#ffffff", root, corps, tete, yeux, oeil, joie, pupille, signes, iris: [iris], sourcils: [sourcil], bouches, bras, cote, expr: "neutre" };
  }

  // Bord de falaise hachure sur toute la largeur, a la hauteur y.
  function sol(svg, y) {
    const P = pinceau(424242), grp = g(svg, { class: "trait-perso", "data-v": "a" });
    P.trace(grp, [[-20, y + 4], [300, y], [620, y + 3], [900, y - 2], [1100, y + 2]], { w: 4, jit: 3 });
    for (let i = 0; i < 46; i++) {
      const x = -10 + i * 24 + P.j(8), len = 60 + P.rnd() * 220;
      P.trace(grp, [[x, y + 8], [x + 30 + P.j(20), y + 8 + len]], { w: 1.6 + P.rnd() * 1.4, passes: 1, jit: 2 });
    }
    return grp;
  }

  // --- Animation (toujours via la timeline) ---------------------------------
  const EXPR = {
    neutre: { s: [0, 0], yeux: 1 }, content: { s: [-6, -6], yeux: 0.8 }, choc: { s: [0, -14], yeux: 1.35 },
    doute: { s: [-14, -8], yeux: 0.9 }, triste: { s: [-14, 2], yeux: 0.85 }, agace: { s: [16, 4], yeux: 0.7 },
  };
  const SIGNES = { content: "joues", choc: "choc", doute: "goutte", triste: "goutte", agace: "veine" };
  const montrerBouche = (tl, perso, nom, at) => {
    for (const [k, b] of Object.entries(perso.bouches)) tl.set(b, { opacity: k === nom ? 1 : 0 }, at);
  };
  function expression(tl, perso, nom, at) {
    const e = EXPR[nom] || EXPR.neutre;
    perso.expr = EXPR[nom] ? nom : "neutre";
    tl.to(perso.sourcils[0], { rotation: e.s[0] * perso.cote, y: e.s[1], duration: 0.2, ease: "power2.out" }, at)
      .to(perso.yeux, { scaleY: e.yeux, scaleX: nom === "choc" ? 1.15 : 1, duration: 0.16 }, at)
      // Manga : pupille minuscule sous le choc, yeux en "^" de joie, symbole de l'expression.
      .to(perso.pupille, { scale: nom === "choc" ? 0.4 : 1, duration: 0.12 }, at)
      .set(perso.oeil, { opacity: nom === "content" ? 0 : 1 }, at)
      .set(perso.joie, { opacity: nom === "content" ? 1 : 0 }, at);
    const signe = SIGNES[perso.expr];
    for (const [k, grp] of Object.entries(perso.signes)) tl.to(grp, { opacity: k === signe ? 1 : 0, duration: 0.15 }, at);
    if (signe === "goutte") tl.fromTo(perso.signes.goutte, { y: -6 }, { y: 10, duration: 0.6, ease: "power1.in", immediateRender: false }, at);
    if (signe === "veine") tl.fromTo(perso.signes.veine, { scale: 0.6 }, { scale: 1, svgOrigin: `${40 * perso.cote} -868`, duration: 0.18, yoyo: true, repeat: 3, ease: "power2.out", immediateRender: false }, at);
    if (nom === "choc") tl.fromTo(perso.tete, { y: 0 }, { y: -14, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, at);
    montrerBouche(tl, perso, perso.expr, at);
  }
  function parler(tl, perso, de, a) {
    const pas = 0.14;
    for (let t = de, k = 0; t < a - pas; t += pas, k++) montrerBouche(tl, perso, k % 2 === 0 ? "ouverte" : perso.expr, t);
    montrerBouche(tl, perso, perso.expr, a);
    const n = Math.max(1, Math.floor((a - de) / 0.7));
    tl.to(perso.tete, { rotation: 3 * perso.cote, duration: 0.35, yoyo: true, repeat: n * 2 - 1, ease: "sine.inOut" }, de);
  }
  const poser = (tl, b, at, d = 0.35) => tl.to([b.haut, b.avant], { rotation: 0, duration: d, ease: "power2.inOut" }, at);
  function geste(tl, perso, nom, at) {
    const bv = perso.bras[perso.cote], bl = perso.bras[-perso.cote];
    if (nom === "salut") {   // main levee pres de la tete, petit signe
      tl.to(bv.haut, { rotation: OUT(bv.s, 120), duration: 0.3, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, -80), duration: 0.3, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, -60), duration: 0.16, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.32);
      poser(tl, bv, at + 1.1);
    } else if (nom === "montre") {
      tl.to(bv.haut, { rotation: OUT(bv.s, 72), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 14), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 4), duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut" }, at + 0.35);
      poser(tl, bv, at + 1.3);
    } else if (nom === "hausse") {
      for (const b of [bv, bl]) {
        tl.to(b.haut, { rotation: OUT(b.s, 34), duration: 0.25, ease: "power2.out" }, at)
          .to(b.avant, { rotation: OUT(b.s, 78), duration: 0.25, ease: "power2.out" }, at);
        poser(tl, b, at + 1.0);
      }
      tl.to(perso.corps, { y: -10, duration: 0.25 }, at).to(perso.corps, { y: 0, duration: 0.35 }, at + 1.0)
        .to(perso.tete, { rotation: -6 * perso.cote, duration: 0.25 }, at).to(perso.tete, { rotation: 0, duration: 0.35 }, at + 1.0);
    } else if (nom === "explique") {
      tl.to(bv.haut, { rotation: OUT(bv.s, 28), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 70), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 52), duration: 0.24, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.3);
      poser(tl, bv, at + 1.4);
    }
  }
  // Vie : traits qui "bouillonnent", balancement leger, clignements ; apparition dessinee.
  function vie(tl, perso, duree, decalage) {
    let k = 0;
    for (let t = decalage * 0.07; t < duree; t += BOIL, k++) tl.set(perso.root, { attr: { "data-v": k % 2 ? "b" : "a" } }, t);
    tl.to(perso.corps, { rotation: 0.8 * perso.cote, svgOrigin: "0 0", duration: 1.7, yoyo: true, repeat: Math.ceil(duree / 1.7), ease: "sine.inOut" }, 0);
    for (let t = 1.1 + decalage; t < duree; t += 2.9 + decalage * 0.4)
      tl.to(perso.yeux, { scaleY: 0.1, duration: 0.06, yoyo: true, repeat: 1 }, t);
    const traits = perso.root.querySelectorAll(".tr"), t0 = decalage * 0.25;
    tl.fromTo(traits, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.35, stagger: 0.9 / traits.length, ease: "none" }, t0)
      .fromTo(perso.iris, { opacity: 0 }, { opacity: 1, duration: 0.15 }, t0 + 1.0);   // la pupille, une fois le visage dessine
  }
  const regarder = (tl, perso, dx, at) => tl.to(perso.iris, { x: Math.sign(dx) * 3, duration: 0.2 }, at);
  // Le sol se dessine et "bouillonne" aussi.
  function animerSol(tl, grp, duree) {
    let k = 0;
    for (let t = 0.05; t < duree; t += BOIL, k++) tl.set(grp, { attr: { "data-v": k % 2 ? "b" : "a" } }, t);
    const traits = grp.querySelectorAll(".tr");
    tl.fromTo(traits, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.3, stagger: 0.6 / traits.length, ease: "none" }, 0);
  }

  window.PersoTrait = { PERSOS, EXPR, dessiner, sol, animerSol, expression, parler, geste, vie, regarder,
    ids: Object.keys(PERSOS), expressions: Object.keys(EXPR), gestes: ["explique", "montre", "hausse", "salut"] };
})();
