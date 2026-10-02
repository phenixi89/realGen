// Personnages "trait blanc" (dialogue.html, style=trait) : dessin a la main
// blanc sur fond noir, dans l'esprit des petites histoires dessinees de TikTok
// (sans en reprendre les personnages). Trait principal + fines passes
// d'esquisse ; personnages de profil : grosse tete ronde, oeil blanc a pupille
// noire, petit nez, bouche ; corps de profil, bras le long du corps, jambes
// fines, pieds ovales. Lea : queue de cheval qui se balance, veste et jupe ;
// Karim : cheveux courts avec un epi, chemise, cravate, pantalon.
//
// Meme interface que perso.js (dessiner, expression, parler, geste, vie,
// regarder) : dialogue.html choisit l'un ou l'autre. En plus :
//   - chaque trait existe en deux variantes tremblees qui alternent ~6 fois
//     par seconde ("boiling lines" du dessin anime) ;
//   - apparition : les traits se dessinent (stroke-dashoffset) ;
//   - effets manga par expression (yeux ^ ^, joues, effroi, goutte, veine) ;
//   - sol(svg, y, xs) : ligne de sol a main levee, cailloux, herbe, ombres.
// Deterministe (pseudo-hasard a graine fixe par personnage) et 100 % timeline :
// seek(t) donne l'etat exact a l'instant t.
// A charger apres gsap et common.js.
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const PERSOS = {
    femme: { nom: "Léa", tenue: "jupe", coiffure: "queue", accessoire: "" },
    homme: { nom: "Karim", tenue: "pantalon", coiffure: "courts", accessoire: "cravate" },
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

  // Pinceau : chaque forme est tracee en deux variantes (classes va / vb) qui
  // alternent ; dans chaque variante, un trait principal assure, puis des
  // passes d'esquisse fines et plus libres (le crayon qui cherche la forme).
  function pinceau(seed) {
    const rnd = mulberry(seed);
    const j = (a) => (rnd() - 0.5) * 2 * a;
    const trace = (parent, pts, { w = 4.2, passes = 3, jit = 1.6, ferme = false, plein = false, alpha = null } = {}) => {
      for (const v of ["va", "vb"]) {
        const grp = g(parent, { class: v });
        for (let k = 0; k < passes; k++) {
          const jk = k ? jit * 1.8 + 1.4 : jit;
          let p = pts.map(([x, y]) => [x + j(jk), y + j(jk)]);
          if (!ferme && p.length > 1) {   // depasse un peu aux extremites, comme un trait rapide
            const [a, b] = [p[0], p[1]], [c, d] = [p[p.length - 1], p[p.length - 2]];
            const o = 0.04 + rnd() * (k ? 0.14 : 0.06);
            p = [[a[0] + (a[0] - b[0]) * o, a[1] + (a[1] - b[1]) * o], ...p, [c[0] + (c[0] - d[0]) * o, c[1] + (c[1] - d[1]) * o]];
          }
          el("path", { d: smooth(p) + (plein ? "Z" : ""), class: "tr", pathLength: 1, fill: plein ? "#ffffff" : "none",
            stroke: "#ffffff", "stroke-width": k ? Math.max(1.1, w * 0.32) : w, "stroke-linecap": "round", "stroke-linejoin": "round",
            opacity: alpha ?? (k ? 0.55 : 0.97) }, grp);
        }
      }
    };
    // Cercle a main levee : un peu plus d'un tour, la fin rentre legerement (spirale)
    // comme un vrai coup de crayon. Le rayon ondule doucement (basses frequences)
    // au lieu de trembler point par point -- sinon le cercle a des bosses de caillou.
    // Passes d'esquisse : tours partiels decales, tres fins.
    const rond = (parent, cx, cy, rx, ry = rx, o = {}) => {
      const passes = o.passes ?? 3, w = o.w ?? 4.2;
      for (let k = 0; k < passes; k++) {
        const n = Math.max(32, Math.round((rx + ry) / 4)), a0 = rnd() * Math.PI * 2;
        const tours = k ? 0.45 + rnd() * 0.5 : 1.04 + rnd() * 0.08;
        const f1 = rnd() * 6.28, f2 = rnd() * 6.28, amp = k ? 0.02 : 0.01, dx = j(k ? 3 : 0.5), dy = j(k ? 3 : 0.5), pts = [];
        for (let i = 0; i <= n; i++) {
          const t = (i / n) * tours, a = a0 + t * Math.PI * 2;
          const r = 1 + amp * (0.6 * Math.sin(2 * a + f1) + 0.4 * Math.sin(3 * a + f2)) - (k ? 0 : 0.035 * Math.max(0, t - 1) / (tours - 1));
          pts.push([cx + dx + Math.cos(a) * rx * r, cy + dy + Math.sin(a) * ry * r]);
        }
        trace(parent, pts, { ...o, passes: 1, ferme: true, jit: o.jit ?? 0.5, w: k ? Math.max(1.1, w * 0.32) : w, alpha: k ? 0.5 : 0.97 });
      }
    };
    return { trace, rond, rnd, j };
  }

  // Bras de profil : les deux partent de l'epaule ; s = cote (bras avant, vers
  // l'interlocuteur) ou -cote (bras arriere). Au repos ils pendent le long du corps.
  const EPAULE = [4, -606], COUDE = [12, -490], POIGNET = [18, -388];
  const OUT = (s, a) => -s * a;   // vers l'avant (bras avant) / l'arriere (bras arriere)

  function dessiner(svg, id, x, y, echelle, cote) {
    const p = PERSOS[id] || PERSOS.femme;
    const P = pinceau(hash(id) ^ 0x51ed);
    const root = g(svg, { transform: `translate(${x} ${y}) scale(${echelle})`, class: "trait-perso", "data-v": "a" });
    const corps = g(root);
    const c = cote;
    const m = (pts) => pts.map(([px, py]) => [px * c, py]);   // coordonnees "regarde a droite" -> cote

    // Corps de profil. Jambes fines (un trait chacune, ou un pantalon), pieds ovales vers l'avant.
    if (p.tenue === "jupe") {
      P.trace(corps, m([[-12, -334], [-13, -180], [-14, -26]]));
      P.trace(corps, m([[18, -334], [19, -180], [20, -26]]));
    } else {
      P.trace(corps, m([[-46, -330], [-40, -180], [-34, -26]]));
      P.trace(corps, m([[-8, -330], [-6, -180], [-4, -26]]));
      P.trace(corps, m([[2, -330], [8, -180], [14, -26]]));
      P.trace(corps, m([[46, -330], [42, -180], [40, -26]]));
    }
    P.rond(corps, (p.tenue === "jupe" ? 0 : -14) * c, -13, 30, 12, { w: 3.6 });
    P.rond(corps, (p.tenue === "jupe" ? 30 : 28) * c, -13, 30, 12, { w: 3.6 });
    if (p.tenue === "jupe") {
      // Veste cintree (dos arrondi, poitrine), revers, puis jupe evasee.
      P.trace(corps, m([[-12, -634], [-40, -616], [-50, -566], [-44, -470]]));
      P.trace(corps, m([[8, -632], [36, -604], [42, -560], [34, -470]]));
      P.trace(corps, m([[-44, -470], [-4, -464], [34, -470]]), { w: 3.4 });
      P.trace(corps, m([[8, -630], [20, -586], [14, -540]]), { w: 2.6, passes: 2 });           // revers
      P.trace(corps, m([[-44, -468], [-62, -400], [-74, -334]]));
      P.trace(corps, m([[34, -468], [52, -400], [66, -334]]));
      P.trace(corps, m([[-74, -334], [-4, -326], [66, -334]]));
    } else {
      // Chemise (dos, poitrine), ceinture, col, cravate.
      P.trace(corps, m([[-12, -634], [-44, -614], [-52, -560], [-50, -332]]));
      P.trace(corps, m([[8, -632], [40, -606], [50, -560], [48, -332]]));
      P.trace(corps, m([[-50, -336], [0, -330], [48, -336]]), { w: 3.6 });
      P.trace(corps, m([[-6, -634], [10, -612], [20, -630]]), { w: 2.6, passes: 2 });           // col
      if (p.accessoire === "cravate")
        P.trace(corps, m([[12, -616], [20, -600], [30, -500], [36, -476], [24, -484], [16, -600], [12, -616]]), { w: 2.6, passes: 2 });
    }
    P.trace(corps, m([[-2, -668], [-6, -632]]), { w: 3.4 });                                    // cou

    // Tete : grosse tete ronde, de profil.
    const tete = g(corps);
    el("circle", { cx: 0, cy: -790, r: 124, fill: "#000000" }, tete);                           // masque le cou derriere
    let queue = null;
    if (p.coiffure === "queue") {
      // Queue de cheval haute, a l'arriere du crane : elle se balance (animee dans vie()).
      queue = g(tete);
      el("path", { d: smooth(m([[-92, -884], [-150, -884], [-190, -836], [-200, -760], [-186, -696], [-170, -730], [-168, -800], [-140, -850], [-100, -860]])) + "Z", fill: "#000000" }, queue);
      P.trace(queue, m([[-96, -886], [-150, -886], [-188, -840], [-200, -764], [-186, -696]]), { w: 3.6 });
      P.trace(queue, m([[-100, -862], [-142, -850], [-168, -800], [-170, -732], [-186, -696]]), { w: 3 });
      P.trace(queue, m([[-110, -874], [-160, -856], [-182, -790], [-180, -730]]), { w: 1.8, passes: 1, jit: 1 });
      P.rond(queue, -96 * c, -874, 13, 15, { w: 3.2, passes: 2 });                               // elastique
      gsap.set(queue, { svgOrigin: `${-96 * c} -874` });
    }
    P.rond(tete, 0, -790, 124, 124, { w: 4.6 });
    if (p.coiffure === "queue") {
      // Ligne de cheveux en S (visage devant, cheveux derriere), meches qui la suivent, frange.
      P.trace(tete, m([[64, -900], [26, -872], [6, -812], [2, -752], [-6, -690]]), { w: 3.8 });
      P.trace(tete, m([[44, -906], [10, -872], [-10, -806], [-14, -740]]), { w: 1.6, passes: 1, jit: 1 });
      P.trace(tete, m([[20, -912], [-12, -870], [-30, -800]]), { w: 1.4, passes: 1, jit: 1 });
      P.trace(tete, m([[56, -906], [90, -884], [106, -852]]), { w: 2.6, passes: 2, jit: 1 });
      P.trace(tete, m([[74, -902], [102, -878], [114, -850]]), { w: 2, passes: 1, jit: 1 });
    } else {
      // Cheveux courts : ligne de cheveux du front a la nuque, meches hachurees au-dessus.
      P.trace(tete, m([[78, -892], [40, -876], [-10, -872], [-64, -846], [-104, -790], [-112, -740]]), { w: 3.8 });
      // Meches : arcs qui suivent l'arrondi du crane sous la ligne de cheveux, et un epi sur le dessus.
      const arc = (r, a0, a1) => { const pts = []; for (let i = 0; i <= 8; i++) { const a = Math.PI * (a0 + (a1 - a0) * i / 8); pts.push([Math.cos(a) * r, -790 + Math.sin(a) * r]); } return m(pts); };
      P.trace(tete, arc(112, 1.08, 1.56), { w: 1.8, passes: 1, jit: 1 });
      P.trace(tete, arc(100, 1.16, 1.48), { w: 1.5, passes: 1, jit: 1 });
      P.trace(tete, arc(116, 1.6, 1.74), { w: 1.6, passes: 1, jit: 1 });
      P.trace(tete, m([[-14, -912], [-22, -940], [-4, -950]]), { w: 3, passes: 2, jit: 0.8 });
      P.trace(tete, m([[4, -913], [6, -936], [22, -942]]), { w: 2.6, passes: 2, jit: 0.8 });
      P.trace(tete, m([[60, -906], [86, -896], [98, -874]]), { w: 2.6, passes: 2, jit: 1 });     // meche sur le front
    }

    // Oeil : blanc plein, pupille noire tout a l'avant avec un reflet ; "^" de joie.
    const ex = 84 * c, ey = -806;
    const yeux = g(tete), oeil = g(yeux);
    el("ellipse", { cx: ex, cy: ey, rx: 17, ry: 20, fill: "#ffffff" }, oeil);
    if (p.coiffure === "queue") P.trace(oeil, m([[100, -822], [112, -832]]), { w: 2.6, passes: 1, jit: 0.6 });   // cil
    const iris = g(oeil);   // apres le blanc de l'oeil, sinon il la recouvre
    const pupille = el("ellipse", { cx: ex + 7 * c, cy: ey + 1, rx: 8, ry: 10, fill: "#000000" }, iris);
    el("circle", { cx: ex + 4 * c, cy: ey - 4, r: 2.6, fill: "#ffffff" }, iris);
    gsap.set(yeux, { svgOrigin: `${ex} ${ey}` });
    gsap.set(pupille, { svgOrigin: `${ex + 7 * c} ${ey + 1}` });
    const joie = g(tete, { opacity: 0 });
    P.trace(joie, m([[68, -800], [84, -818], [100, -800]]), { w: 4, passes: 2 });
    // Sourcil : seulement quand l'expression le demande (invisible au repos).
    const sourcil = g(tete, { opacity: 0 });
    P.trace(sourcil, m([[66, -838], [84, -846], [102, -840]]), { w: 3.4, passes: 2 });
    gsap.set(sourcil, { svgOrigin: `${ex} ${-842}` });
    // Petit nez : une bosse qui depasse a peine du cercle.
    P.trace(tete, m([[118, -796], [130, -782], [134, -772], [126, -767], [118, -766]]), { w: 3, passes: 2, jit: 0.5 });

    // Symboles manga (emanata), un par expression : joues hachurees (content),
    // traits d'effroi + "!" (choc), goutte de sueur (doute, triste), veine en croix (agace).
    const signes = {};
    signes.joues = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.joues, m([[56 + i * 10, -758], [66 + i * 10, -780]]), { w: 2, passes: 1, jit: 0.8 });
    signes.choc = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.choc, m([[30 + i * 20, -884], [30 + i * 20, -850 + (i % 2) * 8]]), { w: 2.2, passes: 1, jit: 0.8 });
    P.trace(signes.choc, m([[124, -1000], [118, -950]]), { w: 6, passes: 1, jit: 1 });
    el("circle", { cx: 116 * c, cy: -930, r: 5, fill: "#ffffff" }, signes.choc);
    signes.goutte = g(tete, { opacity: 0 });
    P.trace(signes.goutte, m([[136, -906], [126, -880], [128, -866], [138, -861], [147, -867], [148, -880], [136, -906]]), { w: 3, passes: 1, jit: 0.6 });
    signes.veine = g(tete, { opacity: 0 });
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]])
      P.trace(signes.veine, m([[44 + sx * 26, -870 + sy * 8], [44 + sx * 10, -870 + sy * 10], [44 + sx * 8, -870 + sy * 26]]), { w: 3.4, passes: 1, jit: 0.6 });

    // Bouches (a l'avant, sous l'oeil), une seule visible a la fois.
    const mx = 92 * c, my = -752;
    const B = (pts) => m(pts.map(([px, py]) => [92 + px, my + py]));
    const BOUCHES = {
      neutre: B([[-12, -2], [-2, 4], [10, -1]]),
      content: B([[-16, -6], [-3, 9], [13, -5]]),
      doute: B([[-13, 2], [-1, -4], [11, 2]]),
      triste: B([[-13, 6], [-1, -5], [11, 6]]),
      agace: B([[-13, -2], [11, 4]]),
    };
    const bouches = {};
    for (const [k, pts] of Object.entries(BOUCHES)) { bouches[k] = g(tete, { opacity: 0 }); P.trace(bouches[k], pts, { w: 3.4, passes: 2, jit: 0.5 }); }
    bouches.choc = g(tete, { opacity: 0 }); P.rond(bouches.choc, mx, my, 8, 11, { w: 3, passes: 2 });
    // Parole : trois ouvertures differentes (moyenne, grande avec la langue, petite "o").
    bouches.ouverte = g(tete, { opacity: 0 }); P.rond(bouches.ouverte, mx, my, 12, 8, { w: 3, passes: 2 });
    bouches.grande = g(tete, { opacity: 0 });
    P.trace(bouches.grande, B([[-15, -6], [12, -8], [11, 8], [-1, 15], [-12, 7], [-15, -6]]), { w: 3, passes: 2, jit: 0.5 });
    P.trace(bouches.grande, B([[-7, 9], [2, 4], [8, 8]]), { w: 2, passes: 1, jit: 0.3 });
    bouches.petite = g(tete, { opacity: 0 }); P.rond(bouches.petite, mx, my + 1, 6, 7, { w: 3, passes: 2 });
    gsap.set(tete, { svgOrigin: "0 -668" });

    // Bras : un trait par segment, main avec paume et doigts.
    const bras = {};
    for (const s of [-c, c]) {
      const haut = g(corps), avant = g(haut);
      P.trace(haut, [[EPAULE[0] * s, EPAULE[1]], [COUDE[0] * s, COUDE[1]]], { w: 3.6 });
      P.trace(avant, [[COUDE[0] * s, COUDE[1]], [POIGNET[0] * s, POIGNET[1]]], { w: 3.6 });
      const [hx, hy] = [POIGNET[0] * s, POIGNET[1]];
      P.rond(avant, hx + 2 * s, hy + 12, 8, 11, { w: 2.6, passes: 2 });
      P.trace(avant, [[hx - 4 * s, hy + 20], [hx - 6 * s, hy + 34]], { w: 2.2, passes: 1, jit: 0.4 });
      P.trace(avant, [[hx + 1 * s, hy + 22], [hx + 1 * s, hy + 37]], { w: 2.2, passes: 1, jit: 0.4 });
      P.trace(avant, [[hx + 6 * s, hy + 20], [hx + 9 * s, hy + 33]], { w: 2.2, passes: 1, jit: 0.4 });
      gsap.set(haut, { svgOrigin: `${EPAULE[0] * s} ${EPAULE[1]}` });
      gsap.set(avant, { svgOrigin: `${COUDE[0] * s} ${COUDE[1]}` });
      bras[s] = { haut, avant, s };
    }

    return { id, nom: p.nom, couleur: "#ffffff", root, corps, tete, queue, yeux, oeil, joie, pupille, signes, iris: [iris], sourcils: [sourcil], bouches, bras, cote, expr: "neutre" };
  }

  // Sol : une ligne d'horizon a main levee, des cailloux, quelques touffes d'herbe
  // et une ombre hachuree sous chaque personnage (xs : leurs positions).
  function sol(svg, y, xs = []) {
    const P = pinceau(424242), grp = g(svg, { class: "trait-perso", "data-v": "a" });
    P.trace(grp, [[-20, y + 6], [240, y + 1], [540, y + 4], [820, y - 1], [1100, y + 3]], { w: 4.4, jit: 2 });
    P.trace(grp, [[60, y + 26], [380, y + 22], [700, y + 27], [1020, y + 23]], { w: 1.4, passes: 1, jit: 2, alpha: 0.4 });
    for (const xc of xs)
      for (let i = 0; i < 9; i++) {
        const x0 = xc - 70 + i * 16;
        P.trace(grp, [[x0, y + 10], [x0 - 14, y + 26]], { w: 1.6, passes: 1, jit: 1, alpha: 0.6 });
      }
    for (const [px, r] of [[150, 9], [470, 6], [610, 11], [960, 7], [1010, 5]])
      P.rond(grp, px, y - r * 0.55, r * 1.6, r, { w: 2.4, passes: 2 });
    for (const px of [80, 545, 1040]) {
      P.trace(grp, [[px, y], [px - 8, y - 22]], { w: 2, passes: 1, jit: 1 });
      P.trace(grp, [[px + 4, y], [px + 6, y - 28]], { w: 2, passes: 1, jit: 1 });
      P.trace(grp, [[px + 8, y], [px + 18, y - 18]], { w: 2, passes: 1, jit: 1 });
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
    tl.to(perso.sourcils[0], { rotation: e.s[0] * perso.cote, y: e.s[1], opacity: nom === "neutre" ? 0 : 1, duration: 0.2, ease: "power2.out" }, at)
      .to(perso.yeux, { scaleY: e.yeux, scaleX: nom === "choc" ? 1.15 : 1, duration: 0.16 }, at)
      // Manga : pupille minuscule sous le choc, yeux en "^" de joie, symbole de l'expression.
      .to(perso.pupille, { scale: nom === "choc" ? 0.4 : 1, duration: 0.12 }, at)
      .set(perso.oeil, { opacity: nom === "content" ? 0 : 1 }, at)
      .set(perso.joie, { opacity: nom === "content" ? 1 : 0 }, at);
    const signe = SIGNES[perso.expr];
    for (const [k, grp] of Object.entries(perso.signes)) tl.to(grp, { opacity: k === signe ? 1 : 0, duration: 0.15 }, at);
    if (signe === "goutte") tl.fromTo(perso.signes.goutte, { y: -6 }, { y: 10, duration: 0.6, ease: "power1.in", immediateRender: false }, at);
    if (signe === "veine") tl.fromTo(perso.signes.veine, { scale: 0.6 }, { scale: 1, svgOrigin: `${44 * perso.cote} -870`, duration: 0.18, yoyo: true, repeat: 3, ease: "power2.out", immediateRender: false }, at);
    if (nom === "choc") tl.fromTo(perso.tete, { y: 0 }, { y: -14, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, at);
    montrerBouche(tl, perso, perso.expr, at);
  }
  // Parole : enchainement fixe de formes de bouche (comme des syllabes), ~9 changements par seconde.
  const SYLLABES = ["grande", "petite", "ouverte", null, "grande", "ouverte", "petite", null, "ouverte", "grande", null, "petite"];
  function parler(tl, perso, de, a) {
    const pas = 0.11;
    for (let t = de, k = 0; t < a - pas; t += pas, k++) montrerBouche(tl, perso, SYLLABES[k % SYLLABES.length] || perso.expr, t);
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
    if (perso.queue) tl.fromTo(perso.queue, { rotation: -3 * perso.cote }, { rotation: 4 * perso.cote, duration: 1.1, yoyo: true,
      repeat: Math.ceil(duree / 1.1), ease: "sine.inOut" }, 0);   // la queue de cheval se balance
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
