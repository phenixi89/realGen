// Personnages dessines en SVG et animes par GSAP (dialogue.html) : style
// colore, aplats + ombres douces, contours teintes (jamais noirs). Plan taille
// (buste, bras, tete) : ce qui se lit sur un telephone.
//
// Un personnage = des pieces (corps, tete, cheveux, yeux, sourcils, bouches,
// bras) animees separement :
//   expressions : neutre, content, choc, doute, triste, agace ;
//   gestes      : salut, montre (vers l'autre personnage), hausse (epaules) ;
//   parole      : la bouche alterne ouverte / expression pendant la replique ;
//   vie         : respiration, clignements, regard vers celui qui parle.
// Tout passe par la timeline (tl.set / tl.to, aucun tl.call) : seek(t) donne
// l'etat EXACT a l'instant t, dans les deux sens -- rendu reproductible.
//
// Ajouter un personnage = ajouter une entree a PERSOS (couleurs + coiffure).
// A charger apres gsap et common.js.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const PERSOS = {
    femme: {
      nom: "Léa", peau: "#f4c7a1", peauOmbre: "#e0a47f", joues: "#ff8a8a",
      cheveux: "#7b3f1d", cheveuxReflet: "#a85a2c", haut: "#ff5c8a", hautOmbre: "#d93a6a",
      col: "#ffe066", yeux: "#3b2416", levres: "#c2185b", coiffure: "longs", accessoire: "boucles",
    },
    homme: {
      nom: "Karim", peau: "#c98a5b", peauOmbre: "#a96e44", joues: "#e07a5f",
      cheveux: "#2b1b12", cheveuxReflet: "#4a3123", haut: "#2ec4b6", hautOmbre: "#1a9488",
      col: "#ffffff", yeux: "#22150c", levres: "#8d4a2f", coiffure: "courts", accessoire: "lunettes",
    },
  };
  // Bras au repos : legerement ecarte du corps (cote s = -1 gauche, 1 droite).
  const REPOS = (s) => -6 * s;
  // Teinte de contour : la couleur de la piece, assombrie.
  const ink = (c) => `color-mix(in srgb,${c} 55%,#1a1030)`;

  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const g = (parent, attrs = {}) => el("g", attrs, parent);

  // Bouches (y = -578, centre de la bouche), une par expression + "ouverte" (parole).
  const BOUCHES = {
    neutre: { d: "M-30,-580 Q0,-570 30,-580", rempli: false },
    content: { d: "M-44,-590 Q0,-538 44,-590 Q0,-578 -44,-590Z", rempli: true },
    choc: { d: "M-20,-578 Q-22,-612 0,-612 Q22,-612 20,-578 Q22,-544 0,-544 Q-22,-544 -20,-578Z", rempli: true },
    doute: { d: "M-32,-574 Q2,-588 34,-584", rempli: false },
    triste: { d: "M-32,-566 Q0,-594 32,-566", rempli: false },
    agace: { d: "M-30,-576 L30,-576", rempli: false },
    ouverte: { d: "M-28,-586 Q0,-592 28,-586 Q24,-556 0,-552 Q-24,-556 -28,-586Z", rempli: true },
  };
  // Sourcils [gauche, droite] : rotation (deg) et decalage vertical ; yeux : echelle verticale.
  const EXPR = {
    neutre: { sg: [0, 0], sd: [0, 0], yeux: 1 },
    content: { sg: [-4, -10], sd: [4, -10], yeux: 0.8 },
    choc: { sg: [0, -26], sd: [0, -26], yeux: 1.35 },
    doute: { sg: [-12, -20], sd: [10, 4], yeux: 0.9 },
    triste: { sg: [-16, -6], sd: [16, -6], yeux: 0.85 },
    agace: { sg: [16, 4], sd: [-16, 4], yeux: 0.75 },
  };

  function dessiner(svg, id, x, y, echelle, cote) {
    const p = PERSOS[id] || PERSOS.femme;
    const root = g(svg, { transform: `translate(${x} ${y}) scale(${echelle})` });
    const corps = g(root);           // respire, sautille quand il parle
    const ombreSol = el("ellipse", { cx: 0, cy: 10, rx: 230, ry: 26, fill: "rgba(0,0,0,.22)" }, root);
    root.insertBefore(ombreSol, corps);

    // Cheveux longs : derriere la tete et les epaules.
    if (p.coiffure === "longs") {
      el("path", { d: "M-150,-650 Q-165,-800 0,-805 Q165,-800 150,-650 L165,-440 Q120,-400 70,-430 L-70,-430 Q-120,-400 -165,-440Z",
        fill: p.cheveux, stroke: ink(p.cheveux), "stroke-width": 6, "stroke-linejoin": "round" }, corps);
    }
    // Buste : haut colore, ombre laterale, col.
    el("path", { d: "M-185,0 L-178,-360 Q-170,-460 -60,-470 L60,-470 Q170,-460 178,-360 L185,0Z",
      fill: p.haut, stroke: ink(p.haut), "stroke-width": 7, "stroke-linejoin": "round" }, corps);
    el("path", { d: `M${110 * cote},-455 Q${172 * cote},-430 ${178 * cote},-360 L${185 * cote},0 L${120 * cote},0 Q${135 * cote},-250 ${110 * cote},-455Z`,
      fill: p.hautOmbre, opacity: 0.55 }, corps);
    el("path", { d: "M-62,-470 L0,-395 L62,-470 L40,-480 L0,-430 L-40,-480Z", fill: p.col, stroke: ink(p.col), "stroke-width": 5, "stroke-linejoin": "round" }, corps);
    // Cou.
    el("path", { d: "M-34,-540 L-34,-470 Q0,-445 34,-470 L34,-540Z", fill: p.peauOmbre, stroke: ink(p.peau), "stroke-width": 5 }, corps);

    // Bras : pivot a l'epaule, main au bout ; dessines devant le buste.
    const bras = {};
    for (const s of [-1, 1]) {
      const b = g(corps);
      el("path", { d: `M${150 * s - 36},-455 Q${150 * s},-485 ${150 * s + 36},-455 L${168 * s + 34},-140 Q${168 * s},-118 ${168 * s - 34},-140Z`,
        fill: s === cote ? p.hautOmbre : p.haut, stroke: ink(p.haut), "stroke-width": 6, "stroke-linejoin": "round" }, b);
      el("circle", { cx: 168 * s, cy: -112, r: 40, fill: p.peau, stroke: ink(p.peau), "stroke-width": 6 }, b);
      gsap.set(b, { svgOrigin: `${150 * s} -455`, rotation: REPOS(s) });
      bras[s] = b;
    }

    // Tete.
    const tete = g(corps);
    for (const s of [-1, 1]) el("circle", { cx: 112 * s, cy: -640, r: 24, fill: p.peauOmbre, stroke: ink(p.peau), "stroke-width": 5 }, tete);
    if (p.accessoire === "boucles") for (const s of [-1, 1]) el("circle", { cx: 116 * s, cy: -606, r: 11, fill: "#ffd23f", stroke: ink("#ffd23f"), "stroke-width": 4 }, tete);
    el("ellipse", { cx: 0, cy: -640, rx: 112, ry: 132, fill: p.peau, stroke: ink(p.peau), "stroke-width": 7 }, tete);
    el("path", { d: `M${70 * cote},-740 Q${125 * cote},-650 ${70 * cote},-540 Q${100 * cote},-560 ${108 * cote},-640 Q${105 * cote},-710 ${70 * cote},-740Z`, fill: p.peauOmbre, opacity: 0.5 }, tete);
    for (const s of [-1, 1]) el("ellipse", { cx: 62 * s, cy: -598, rx: 24, ry: 14, fill: p.joues, opacity: 0.45 }, tete);
    el("path", { d: "M-6,-628 Q-14,-602 2,-600", fill: "none", stroke: p.peauOmbre, "stroke-width": 6, "stroke-linecap": "round" }, tete);

    // Yeux (blanc + iris qui suit l'interlocuteur) et sourcils.
    const yeux = g(tete), iris = [];
    for (const s of [-1, 1]) {
      el("ellipse", { cx: 42 * s, cy: -652, rx: 20, ry: 24, fill: "#ffffff", stroke: ink(p.peau), "stroke-width": 4 }, yeux);
      const i = g(yeux);
      el("circle", { cx: 42 * s, cy: -650, r: 13, fill: p.yeux }, i);
      el("circle", { cx: 42 * s + 5, cy: -656, r: 4.5, fill: "#ffffff" }, i);
      iris.push(i);
    }
    gsap.set(yeux, { svgOrigin: "0 -652" });
    const sourcils = [-1, 1].map((s) => {
      const sc = el("path", { d: `M${42 * s - 26},-694 Q${42 * s},-704 ${42 * s + 26},-694`, fill: "none", stroke: p.cheveux,
        "stroke-width": 10, "stroke-linecap": "round" }, tete);
      gsap.set(sc, { svgOrigin: `${42 * s} -698` });
      return sc;
    });
    if (p.accessoire === "lunettes") {
      for (const s of [-1, 1]) el("circle", { cx: 42 * s, cy: -652, r: 36, fill: "rgba(255,255,255,.12)", stroke: "#ff9f1c", "stroke-width": 8 }, tete);
      el("path", { d: "M-8,-656 Q0,-664 8,-656", fill: "none", stroke: "#ff9f1c", "stroke-width": 7 }, tete);
    }

    // Bouches : une seule visible a la fois.
    const bouches = {};
    for (const [k, b] of Object.entries(BOUCHES)) {
      bouches[k] = el("path", b.rempli
        ? { d: b.d, fill: "#7a1f35", stroke: p.levres, "stroke-width": 6, "stroke-linejoin": "round", opacity: 0 }
        : { d: b.d, fill: "none", stroke: p.levres, "stroke-width": 8, "stroke-linecap": "round", opacity: 0 }, tete);
    }
    const dents = el("path", { d: "M-34,-588 Q0,-580 34,-588 L30,-578 Q0,-572 -30,-578Z", fill: "#ffffff", opacity: 0 }, tete);

    // Coiffure de face (frange / dessus).
    if (p.coiffure === "longs") {
      el("path", { d: "M-122,-640 Q-130,-790 0,-792 Q130,-790 122,-640 Q100,-720 30,-735 Q-20,-690 -122,-640Z",
        fill: p.cheveux, stroke: ink(p.cheveux), "stroke-width": 6, "stroke-linejoin": "round" }, tete);
      el("path", { d: "M-60,-760 Q0,-785 60,-765", fill: "none", stroke: p.cheveuxReflet, "stroke-width": 12, "stroke-linecap": "round" }, tete);
    } else {
      el("path", { d: "M-116,-660 Q-120,-800 0,-798 Q120,-800 116,-660 Q105,-735 40,-740 Q-10,-760 -70,-735 Q-105,-720 -116,-660Z",
        fill: p.cheveux, stroke: ink(p.cheveux), "stroke-width": 6, "stroke-linejoin": "round" }, tete);
      el("path", { d: "M-50,-775 Q10,-792 60,-770", fill: "none", stroke: p.cheveuxReflet, "stroke-width": 12, "stroke-linecap": "round" }, tete);
    }
    gsap.set(tete, { svgOrigin: "0 -520" });

    return { id, nom: p.nom, root, corps, tete, yeux, iris, sourcils, bouches, dents, bras, cote, expr: "neutre" };
  }

  // --- Animation (toujours via la timeline) ---------------------------------
  const montrerBouche = (tl, perso, nom, at) => {
    for (const [k, b] of Object.entries(perso.bouches)) tl.set(b, { opacity: k === nom ? 1 : 0 }, at);
    tl.set(perso.dents, { opacity: nom === "content" ? 1 : 0 }, at);
  };

  function expression(tl, perso, nom, at) {
    const e = EXPR[nom] || EXPR.neutre;
    perso.expr = EXPR[nom] ? nom : "neutre";
    const [sg, sd] = perso.sourcils;
    tl.to(sg, { rotation: e.sg[0], y: e.sg[1], duration: 0.18, ease: "back.out(2)" }, at)
      .to(sd, { rotation: e.sd[0], y: e.sd[1], duration: 0.18, ease: "back.out(2)" }, at)
      .to(perso.yeux, { scaleY: e.yeux, duration: 0.15 }, at);
    if (nom === "choc") tl.fromTo(perso.tete, { y: 0 }, { y: -18, duration: 0.12, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, at);
    montrerBouche(tl, perso, perso.expr, at);
  }

  // Parole : la bouche alterne ouverte / expression (rythme fixe, ~7 syllabes/s), petit rebond du corps.
  function parler(tl, perso, de, a) {
    const pas = 0.14;
    for (let t = de, k = 0; t < a - pas; t += pas, k++) montrerBouche(tl, perso, k % 2 === 0 ? "ouverte" : perso.expr, t);
    montrerBouche(tl, perso, perso.expr, a);
    const n = Math.max(1, Math.floor((a - de) / 0.6));
    tl.to(perso.corps, { y: -8, duration: 0.3, yoyo: true, repeat: n * 2 - 1, ease: "sine.inOut" }, de);
  }

  function geste(tl, perso, nom, at) {
    const vers = perso.cote, loin = -perso.cote;   // bras cote interlocuteur / cote exterieur
    const bv = perso.bras[vers], bl = perso.bras[loin];
    const sens = (s) => -s;                          // signe de rotation qui ecarte le bras du corps, cote s
    if (nom === "salut") {
      tl.to(bl, { rotation: sens(loin) * 182, duration: 0.3, ease: "back.out(1.6)" }, at)
        .to(bl, { rotation: sens(loin) * 166, duration: 0.18, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.3)
        .to(bl, { rotation: REPOS(loin), duration: 0.35, ease: "power2.inOut" }, at + 1.1);
    } else if (nom === "montre") {
      tl.to(bv, { rotation: sens(vers) * 58, duration: 0.3, ease: "back.out(1.8)" }, at)
        .to(bv, { rotation: sens(vers) * 52, duration: 0.25, yoyo: true, repeat: 1 }, at + 0.35)
        .to(bv, { rotation: REPOS(vers), duration: 0.4, ease: "power2.inOut" }, at + 1.3);
    } else if (nom === "hausse") {
      for (const b of [bv, bl]) {
        const s = b === bv ? vers : loin;
        tl.to(b, { rotation: sens(s) * 24, duration: 0.25, ease: "power2.out" }, at)
          .to(b, { rotation: REPOS(s), duration: 0.35, ease: "power2.inOut" }, at + 0.9);
      }
      tl.to(perso.tete, { y: 14, rotation: 6 * perso.cote, duration: 0.25 }, at)
        .to(perso.tete, { y: 0, rotation: 0, duration: 0.35 }, at + 0.9);
    }
  }

  // Vie : respiration, clignements a des instants fixes (decales par personnage).
  function vie(tl, perso, duree, decalage) {
    tl.to(perso.corps, { scaleY: 1.012, svgOrigin: "0 0", duration: 1.6, yoyo: true,
      repeat: Math.ceil(duree / 1.6), ease: "sine.inOut" }, 0);
    for (let t = 0.8 + decalage; t < duree; t += 2.6 + decalage * 0.5)
      tl.to(perso.yeux, { scaleY: 0.08, duration: 0.06, yoyo: true, repeat: 1 }, t);
  }

  // Regard : les iris glissent vers le personnage qui parle.
  const regarder = (tl, perso, dx, at) => tl.to(perso.iris, { x: dx, duration: 0.2 }, at);

  window.Perso = { PERSOS, EXPR, dessiner, expression, parler, geste, vie, regarder,
    ids: Object.keys(PERSOS), expressions: Object.keys(EXPR), gestes: ["salut", "montre", "hausse"] };
})();
