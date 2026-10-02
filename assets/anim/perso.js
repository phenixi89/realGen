// Personnages dessines en SVG et animes par GSAP (dialogue.html), style
// illustration editoriale : proportions realistes, palette sobre (bleu nuit,
// camel, une couleur d'accent du theme), tenues pro, visage minimal (yeux en
// points, traits fins), aplats sans contour avec ombres douces. Cadres a mi-corps,
// assis derriere un bureau (le bureau est dessine par le gabarit).
//
// Un personnage = des pieces animees separement :
//   expressions : neutre, content, choc, doute, triste, agace (sourcils, yeux, bouche) ;
//   gestes      : explique (mains devant soi), montre (vers l'autre), hausse
//                 (epaules, paumes ouvertes), salut ; bras en deux segments (coude) ;
//   parole      : la bouche alterne ouverte / expression, la tete accompagne ;
//   vie         : respiration, clignements, regard vers celui qui parle.
// Tout passe par la timeline (tl.set / tl.to, aucun tl.call) : seek(t) donne
// l'etat EXACT a l'instant t, dans les deux sens -- rendu reproductible.
//
// Ajouter un personnage = ajouter une entree a PERSOS (couleurs, coiffure,
// accessoire, visage doux/carre). Une couleur "var(--c1)" suit le theme du reel.
// A charger apres gsap et common.js.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const PERSOS = {
    femme: {
      nom: "Léa", peau: "#efc6a4", peauOmbre: "#d9a682", cheveux: "#3a2418", cheveuxReflet: "#5b3b27",
      veste: "#27324d", vesteOmbre: "#1b2338", interieur: "var(--c1)", levres: "#a3544b",
      coiffure: "carre", accessoire: "collier", visage: "doux", cils: true,
    },
    homme: {
      nom: "Karim", peau: "#e6b993", peauOmbre: "#cc9a75", cheveux: "#3d2c21", cheveuxReflet: "#5e4636",
      veste: "#a8825f", vesteOmbre: "#8a6847", interieur: "#dce6f2", levres: "#a0604e",
      coiffure: "raie", accessoire: "lunettes", visage: "carre", cils: false,
    },
  };

  // Bouches (fines, centrees en y = -955), une par expression + "ouverte" (parole).
  const BOUCHES = {
    neutre: { d: "M-15,-955 Q0,-952 15,-955" },
    content: { d: "M-19,-958 Q0,-943 19,-958" },
    choc: { d: "M-8,-955 Q-8,-967 0,-967 Q8,-967 8,-955 Q8,-943 0,-943 Q-8,-943 -8,-955Z", rempli: true },
    doute: { d: "M-15,-952 Q3,-960 17,-958" },
    triste: { d: "M-15,-950 Q0,-959 15,-950" },
    agace: { d: "M-15,-954 L15,-954" },
    ouverte: { d: "M-14,-959 Q0,-961 14,-959 Q11,-945 0,-943 Q-11,-945 -14,-959Z", rempli: true },
  };
  // Sourcils [gauche, droite] : [rotation (deg), decalage vertical] ; yeux : echelle verticale.
  const EXPR = {
    neutre: { sg: [0, 0], sd: [0, 0], yeux: 1 },
    content: { sg: [-3, -4], sd: [3, -4], yeux: 0.8 },
    choc: { sg: [0, -11], sd: [0, -11], yeux: 1.3 },
    doute: { sg: [-8, -9], sd: [7, 2], yeux: 0.9 },
    triste: { sg: [-11, -3], sd: [11, -3], yeux: 0.85 },
    agace: { sg: [11, 3], sd: [-11, 3], yeux: 0.75 },
  };
  // Bras : epaule, coude, poignet (cote s = -1 gauche, 1 droite) ; au repos le
  // bras tombe le long du corps et l'avant-bras est pose a plat sur le bureau.
  const EPAULE = [150, -855], COUDE = [168, -620], POIGNET = [168, -405];
  const OUT = (s, a) => -s * a;   // rotation qui ecarte du corps (a > 0) ou rapproche (a < 0), cote s
  const REPOS = { haut: (s) => OUT(s, 4), avant: (s) => OUT(s, -85) };

  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) {
      // Couleurs du theme (var(--c1)...) : seulement via style, pas en attribut.
      if ((k === "fill" || k === "stroke") && String(v).startsWith("var(")) n.style[k] = v;
      else n.setAttribute(k, v);
    }
    if (parent) parent.appendChild(n);
    return n;
  };
  const g = (parent, attrs = {}) => el("g", attrs, parent);
  // Formes du visage : doux (menton fin, joues arrondies), carre (machoire marquee).
  const VISAGES = {
    doux: "M-64,-1030 Q-66,-962 -42,-934 Q-18,-910 0,-909 Q18,-910 42,-934 Q66,-962 64,-1030 Q62,-1102 0,-1103 Q-62,-1102 -64,-1030Z",
    carre: "M-67,-1032 Q-68,-972 -54,-948 Q-30,-912 0,-909 Q30,-912 54,-948 Q68,-972 67,-1032 Q65,-1104 0,-1105 Q-65,-1104 -67,-1032Z",
  };

  function dessiner(svg, id, x, y, echelle, cote) {
    const p = PERSOS[id] || PERSOS.femme;
    const root = g(svg, { transform: `translate(${x} ${y}) scale(${echelle})` });
    const corps = g(root);

    // Cheveux de derriere (carre : tombent jusqu'au menton).
    if (p.coiffure === "carre") {
      el("path", { d: "M-84,-1030 Q-92,-1116 0,-1118 Q92,-1116 84,-1030 L90,-918 Q66,-900 44,-914 L-44,-914 Q-66,-900 -90,-918Z", fill: p.cheveux }, corps);
    }
    // Buste : veste ouverte sur un haut, revers, ombre laterale.
    el("path", { d: "M-160,-868 Q-172,-858 -170,-815 L-140,-300 L140,-300 L170,-815 Q172,-858 160,-868 Q95,-893 42,-900 L0,-860 L-42,-900 Q-95,-893 -160,-868Z", fill: p.veste }, corps);
    el("path", { d: "M-44,-898 L-34,-300 L34,-300 L44,-898 Q0,-884 -44,-898Z", fill: p.interieur }, corps);
    el("path", { d: `M${120 * cote},-880 Q${165 * cote},-860 ${168 * cote},-815 L${140 * cote},-300 L${105 * cote},-300 Q${118 * cote},-600 ${120 * cote},-880Z`, fill: p.vesteOmbre, opacity: 0.7 }, corps);
    for (const s of [-1, 1]) el("path", { d: `M${44 * s},-898 L${76 * s},-872 L${38 * s},-690 L${30 * s},-760Z`, fill: p.vesteOmbre }, corps);
    // Cou, puis collier ou col de chemise.
    el("path", { d: "M-22,-940 L-22,-880 Q0,-866 22,-880 L22,-940Z", fill: p.peauOmbre }, corps);
    if (p.accessoire === "collier") el("path", { d: "M-30,-888 Q0,-850 30,-888", fill: "none", stroke: "#d9b45a", "stroke-width": 3 }, corps);
    else for (const s of [-1, 1]) el("path", { d: `M0,-872 L${30 * s},-902 L${44 * s},-876Z`, fill: p.interieur, stroke: "rgba(0,0,0,.12)", "stroke-width": 2 }, corps);

    // Tete.
    const tete = g(corps);
    for (const s of [-1, 1]) el("ellipse", { cx: 68 * s, cy: -1008, rx: 10, ry: 17, fill: p.peauOmbre }, tete);
    el("path", { d: VISAGES[p.visage] || VISAGES.doux, fill: p.peau }, tete);
    el("path", { d: `M${40 * cote},-1090 Q${74 * cote},-1040 ${60 * cote},-962 Q${50 * cote},-935 ${30 * cote},-922 Q${62 * cote},-990 ${40 * cote},-1090Z`, fill: p.peauOmbre, opacity: 0.45 }, tete);
    // Nez : arete + aile (trait fin), ombre sous le menton.
    el("path", { d: "M3,-1010 Q10,-988 3,-980 M-7,-982 Q-3,-976 3,-980", fill: "none", stroke: p.peauOmbre, "stroke-width": 3.2, "stroke-linecap": "round" }, tete);
    el("path", { d: "M-26,-922 Q0,-912 26,-922", fill: "none", stroke: p.peauOmbre, "stroke-width": 3, "stroke-linecap": "round", opacity: 0.6 }, tete);

    // Yeux en amande : iris sombre + reflet (il suit l'interlocuteur), paupiere
    // superieure (avec un trait de cil vers l'exterieur si cils), sourcils fins.
    const yeux = g(tete), iris = [];
    for (const s of [-1, 1]) {
      const x = 26 * s, i = g(yeux);
      el("ellipse", { cx: x, cy: -1011, rx: 6.5, ry: 7.5, fill: "#241914" }, i);
      el("circle", { cx: x + 2.2, cy: -1013.5, r: 1.8, fill: "#ffffff", opacity: 0.85 }, i);
      iris.push(i);
      el("path", { d: `M${x - 12},-1012 Q${x},-1024 ${x + 12},-1012`, fill: "none", stroke: "#2a1d18", "stroke-width": p.cils ? 4 : 3,
        "stroke-linecap": "round" }, yeux);
      if (p.cils) el("path", { d: `M${x + 11 * s},-1013 L${x + 15 * s},-1017`, fill: "none", stroke: "#2a1d18", "stroke-width": 3, "stroke-linecap": "round" }, yeux);
    }
    gsap.set(yeux, { svgOrigin: "0 -1012" });
    const sourcils = [-1, 1].map((s) => {
      const sc = el("path", { d: `M${26 * s - 15},-1033 Q${26 * s},-1040 ${26 * s + 15},-1034`, fill: "none", stroke: p.cheveux,
        "stroke-width": 5, "stroke-linecap": "round" }, tete);
      gsap.set(sc, { svgOrigin: `${26 * s} -1036` });
      return sc;
    });
    if (p.accessoire === "lunettes") {
      // Monture fine couleur ecaille.
      for (const s of [-1, 1]) el("rect", { x: 26 * s - 18, y: -1025, width: 36, height: 25, rx: 9, fill: "rgba(255,255,255,.06)", stroke: "#6b4a32", "stroke-width": 2.6 }, tete);
      el("path", { d: "M-8,-1014 Q0,-1018 8,-1014", fill: "none", stroke: "#6b4a32", "stroke-width": 2.6 }, tete);
    }
    const bouches = {};
    for (const [k, b] of Object.entries(BOUCHES)) {
      bouches[k] = el("path", b.rempli
        ? { d: b.d, fill: "#5a2a26", opacity: 0 }
        : { d: b.d, fill: "none", stroke: p.levres, "stroke-width": 4.5, "stroke-linecap": "round", opacity: 0 }, tete);
    }
    // Coiffure de face.
    if (p.coiffure === "carre") {
      el("path", { d: "M-74,-1026 Q-80,-1112 0,-1110 Q76,-1108 74,-1018 Q56,-1076 -6,-1082 Q-44,-1062 -74,-1026Z", fill: p.cheveux }, tete);
      el("path", { d: "M-30,-1092 Q20,-1100 54,-1080", fill: "none", stroke: p.cheveuxReflet, "stroke-width": 7, "stroke-linecap": "round" }, tete);
    } else {
      // Courts, raie sur le cote, un peu de volume sur le dessus.
      el("path", { d: "M-70,-1026 Q-80,-1114 -8,-1122 Q76,-1124 73,-1032 Q68,-1076 36,-1086 Q4,-1094 -22,-1080 Q-52,-1068 -70,-1026Z", fill: p.cheveux }, tete);
      el("path", { d: "M-24,-1116 Q-31,-1098 -26,-1080", fill: "none", stroke: p.cheveuxReflet, "stroke-width": 3, "stroke-linecap": "round" }, tete);
      el("path", { d: "M-8,-1110 Q30,-1116 56,-1094", fill: "none", stroke: p.cheveuxReflet, "stroke-width": 6, "stroke-linecap": "round" }, tete);
    }
    gsap.set(tete, { svgOrigin: "0 -935" });

    // Bras en deux segments, devant le buste : epaule -> coude -> main.
    const bras = {};
    for (const s of [-1, 1]) {
      const haut = g(corps), avant = g(haut);
      el("line", { x1: EPAULE[0] * s, y1: EPAULE[1], x2: COUDE[0] * s, y2: COUDE[1], stroke: p.vesteOmbre, "stroke-width": 64, "stroke-linecap": "round" }, haut);
      el("line", { x1: COUDE[0] * s, y1: COUDE[1], x2: POIGNET[0] * s, y2: POIGNET[1] + 10, stroke: p.vesteOmbre, "stroke-width": 56, "stroke-linecap": "round" }, avant);
      el("ellipse", { cx: POIGNET[0] * s, cy: POIGNET[1] + 42, rx: 21, ry: 27, fill: p.peau }, avant);
      gsap.set(haut, { svgOrigin: `${EPAULE[0] * s} ${EPAULE[1]}`, rotation: REPOS.haut(s) });
      gsap.set(avant, { svgOrigin: `${COUDE[0] * s} ${COUDE[1]}`, rotation: REPOS.avant(s) });
      bras[s] = { haut, avant, s };
    }

    return { id, nom: p.nom, couleur: p.veste, root, corps, tete, yeux, iris, sourcils, bouches, bras, cote, expr: "neutre" };
  }

  // --- Animation (toujours via la timeline) ---------------------------------
  const montrerBouche = (tl, perso, nom, at) => {
    for (const [k, b] of Object.entries(perso.bouches)) tl.set(b, { opacity: k === nom ? 1 : 0 }, at);
  };

  function expression(tl, perso, nom, at) {
    const e = EXPR[nom] || EXPR.neutre;
    perso.expr = EXPR[nom] ? nom : "neutre";
    const [sg, sd] = perso.sourcils;
    tl.to(sg, { rotation: e.sg[0], y: e.sg[1], duration: 0.22, ease: "power2.out" }, at)
      .to(sd, { rotation: e.sd[0], y: e.sd[1], duration: 0.22, ease: "power2.out" }, at)
      .to(perso.yeux, { scaleY: e.yeux, duration: 0.18 }, at);
    if (nom === "choc") tl.fromTo(perso.tete, { y: 0 }, { y: -8, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, at);
    montrerBouche(tl, perso, perso.expr, at);
  }

  // Parole : la bouche alterne ouverte / expression (~7 syllabes/s), la tete accompagne legerement.
  function parler(tl, perso, de, a) {
    const pas = 0.14;
    for (let t = de, k = 0; t < a - pas; t += pas, k++) montrerBouche(tl, perso, k % 2 === 0 ? "ouverte" : perso.expr, t);
    montrerBouche(tl, perso, perso.expr, a);
    const n = Math.max(1, Math.floor((a - de) / 0.9));
    tl.to(perso.tete, { rotation: 1.6 * perso.cote, duration: 0.45, yoyo: true, repeat: n * 2 - 1, ease: "sine.inOut" }, de);
  }

  const poser = (tl, b, at, d = 0.4) => tl.to(b.haut, { rotation: REPOS.haut(b.s), duration: d, ease: "power2.inOut" }, at)
    .to(b.avant, { rotation: REPOS.avant(b.s), duration: d, ease: "power2.inOut" }, at);

  function geste(tl, perso, nom, at) {
    const bv = perso.bras[perso.cote], bl = perso.bras[-perso.cote];   // cote interlocuteur / cote exterieur
    if (nom === "explique") {
      // Mains levees devant soi, petits mouvements de ponctuation.
      for (const b of [bv, bl]) {
        tl.to(b.haut, { rotation: OUT(b.s, 8), duration: 0.3, ease: "power2.out" }, at)
          .to(b.avant, { rotation: OUT(b.s, -128), duration: 0.3, ease: "power2.out" }, at)
          .to(b.avant, { rotation: OUT(b.s, -112), duration: 0.28, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.32 + (b === bv ? 0 : 0.12));
        poser(tl, b, at + 1.6);
      }
    } else if (nom === "montre") {
      tl.to(bv.haut, { rotation: OUT(bv.s, 22), duration: 0.32, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 70), duration: 0.32, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(bv.s, 62), duration: 0.22, yoyo: true, repeat: 1, ease: "sine.inOut" }, at + 0.4);
      poser(tl, bv, at + 1.4);
    } else if (nom === "hausse") {
      for (const b of [bv, bl]) {
        tl.to(b.haut, { rotation: OUT(b.s, 6), duration: 0.28, ease: "power2.out" }, at)
          .to(b.avant, { rotation: OUT(b.s, -40), duration: 0.28, ease: "power2.out" }, at);
        poser(tl, b, at + 1.0);
      }
      tl.to(perso.corps, { y: -10, duration: 0.28 }, at).to(perso.corps, { y: 0, duration: 0.4 }, at + 1.0)
        .to(perso.tete, { rotation: 5 * perso.cote, duration: 0.28 }, at).to(perso.tete, { rotation: 0, duration: 0.4 }, at + 1.0);
    } else if (nom === "salut") {
      tl.to(bl.haut, { rotation: OUT(bl.s, 30), duration: 0.3, ease: "power2.out" }, at)
        .to(bl.avant, { rotation: OUT(bl.s, 128), duration: 0.3, ease: "power2.out" }, at)
        .to(bl.avant, { rotation: OUT(bl.s, 108), duration: 0.18, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.32);
      poser(tl, bl, at + 1.2);
    }
  }

  // Vie : respiration, clignements a des instants fixes (decales par personnage).
  function vie(tl, perso, duree, decalage) {
    tl.to(perso.corps, { scaleY: 1.008, svgOrigin: "0 -300", duration: 1.8, yoyo: true, repeat: Math.ceil(duree / 1.8), ease: "sine.inOut" }, 0);
    for (let t = 0.9 + decalage; t < duree; t += 2.8 + decalage * 0.4)
      tl.to(perso.yeux, { scaleY: 0.08, duration: 0.06, yoyo: true, repeat: 1 }, t);
  }

  // Regard : les yeux glissent vers le personnage qui parle (dx en unites du personnage).
  const regarder = (tl, perso, dx, at) => tl.to(perso.iris, { x: dx, duration: 0.2 }, at);

  window.Perso = { PERSOS, EXPR, dessiner, expression, parler, geste, vie, regarder,
    ids: Object.keys(PERSOS), expressions: Object.keys(EXPR), gestes: ["explique", "montre", "hausse", "salut"] };
})();
