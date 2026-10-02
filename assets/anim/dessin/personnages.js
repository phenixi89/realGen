// Personnages du dessin anime (types "lea", "karim") : profil, regard vers la droite
// (le moteur les retourne avec `regard`). Trait blanc, oeil blanc a pupille noire,
// petit nez, bouche ; corps de profil, bras articules (epaule, coude), jambes
// articulees a la hanche (marche), mains avec doigts.
//
// Ancres (pour tenir / porter un objet) : main_avant, main_arriere, tete.
// Actions : parler, expression, geste (salut, montre, hausse, explique), marcher,
// entrer, sortir, regarder, tenir, poser, boire, telephoner, sauter.
// Effets manga par expression : yeux ^ ^ et joues (content), effroi + "!" (choc),
// goutte de sueur (doute, triste), veine en croix (agace).
(() => {
  const { g, el, smooth } = Dessin;
  const MODELES = {
    // Accessoire colore (touche de couleur legere) : chouchou corail pour Lea, cravate bleue pour Karim.
    lea: { nom: "Léa", tenue: "jupe", coiffure: "queue", cravate: false, couleur: "#ff7a6b" },
    karim: { nom: "Karim", tenue: "pantalon", coiffure: "courts", cravate: true, couleur: "#4f8dff" },
  };
  // Bras : les deux partent de l'epaule ; s = 1 bras avant (cote du regard), -1 bras arriere.
  const EPAULE = [4, -606], COUDE = [12, -490], POIGNET = [18, -388];
  const OUT = (s, a) => -s * a;   // rotation vers l'avant (bras avant) / l'arriere (bras arriere)
  const HANCHE = { jupe: [[-12, -334], [18, -334]], pantalon: [[-27, -330], [24, -330]] };

  function dessiner(parent, P, opts) {
    const p = MODELES[opts.type] || MODELES.lea;
    const corps = g(parent);

    // Jambes (groupes pivotant a la hanche) et pieds ovales vers l'avant.
    const jambes = [];
    HANCHE[p.tenue].forEach(([hx, hy], i) => {
      const jg = g(corps);
      if (p.tenue === "jupe") P.trace(jg, [[hx, hy], [hx - 1, -180], [hx - 2 + i * 4, -26]]);
      else {
        const [a, b] = i ? [2, 46] : [-46, -8];
        P.trace(jg, [[a, -330], [a + (i ? 6 : 6), -180], [a + (i ? 12 : 12), -26]]);
        P.trace(jg, [[b, -330], [b - 2, -180], [b - 4 + (i ? 0 : 4), -26]]);
      }
      P.rond(jg, (p.tenue === "jupe" ? [0, 30] : [-14, 28])[i], -13, 30, 12, { w: 3.6 });
      gsap.set(jg, { svgOrigin: `${hx} ${hy}` });
      jambes.push(jg);
    });

    // Buste de profil.
    if (p.tenue === "jupe") {
      P.trace(corps, [[-12, -634], [-40, -616], [-50, -566], [-44, -470]]);
      P.trace(corps, [[8, -632], [36, -604], [42, -560], [34, -470]]);
      P.trace(corps, [[-44, -470], [-4, -464], [34, -470]], { w: 3.4 });
      P.trace(corps, [[8, -630], [20, -586], [14, -540]], { w: 2.6, passes: 2 });              // revers
      P.trace(corps, [[-44, -468], [-62, -400], [-74, -334]]);
      P.trace(corps, [[34, -468], [52, -400], [66, -334]]);
      P.trace(corps, [[-74, -334], [-4, -326], [66, -334]]);
    } else {
      P.trace(corps, [[-12, -634], [-44, -614], [-52, -560], [-50, -332]]);
      P.trace(corps, [[8, -632], [40, -606], [50, -560], [48, -332]]);
      P.trace(corps, [[-50, -336], [0, -330], [48, -336]], { w: 3.6 });
      P.trace(corps, [[-6, -634], [10, -612], [20, -630]], { w: 2.6, passes: 2 });              // col
      if (p.cravate) {
        P.lavis(corps, [[12, -616], [20, -600], [30, -500], [36, -476], [24, -484], [16, -600]], p.couleur, 0.55);
        P.trace(corps, [[12, -616], [20, -600], [30, -500], [36, -476], [24, -484], [16, -600], [12, -616]], { w: 2.6, passes: 2 });
      }
    }
    P.trace(corps, [[-2, -668], [-6, -632]], { w: 3.4 });                                       // cou

    // Tete.
    const tete = g(corps);
    el("circle", { cx: 0, cy: -790, r: 124, fill: "#000000" }, tete);
    let queue = null;
    if (p.coiffure === "queue") {
      queue = g(tete);
      el("path", { d: smooth([[-92, -884], [-150, -884], [-190, -836], [-200, -760], [-186, -696], [-170, -730], [-168, -800], [-140, -850], [-100, -860]]) + "Z", fill: "#000000" }, queue);
      P.trace(queue, [[-96, -886], [-150, -886], [-188, -840], [-200, -764], [-186, -696]], { w: 3.6 });
      P.trace(queue, [[-100, -862], [-142, -850], [-168, -800], [-170, -732], [-186, -696]], { w: 3 });
      P.trace(queue, [[-110, -874], [-160, -856], [-182, -790], [-180, -730]], { w: 1.8, passes: 1, jit: 1 });
      P.lavisRond(queue, -96, -874, 15, 17, p.couleur, 0.7);
      P.rond(queue, -96, -874, 13, 15, { w: 3.2, passes: 2 });
      gsap.set(queue, { svgOrigin: "-96 -874" });
    }
    P.rond(tete, 0, -790, 124, 124, { w: 4.6 });
    if (p.coiffure === "queue") {
      P.trace(tete, [[64, -900], [26, -872], [6, -812], [2, -752], [-6, -690]], { w: 3.8 });
      P.trace(tete, [[44, -906], [10, -872], [-10, -806], [-14, -740]], { w: 1.6, passes: 1, jit: 1 });
      P.trace(tete, [[20, -912], [-12, -870], [-30, -800]], { w: 1.4, passes: 1, jit: 1 });
      P.trace(tete, [[56, -906], [90, -884], [106, -852]], { w: 2.6, passes: 2, jit: 1 });
      P.trace(tete, [[74, -902], [102, -878], [114, -850]], { w: 2, passes: 1, jit: 1 });
    } else {
      P.trace(tete, [[78, -892], [40, -876], [-10, -872], [-64, -846], [-104, -790], [-112, -740]], { w: 3.8 });
      const arc = (r, a0, a1) => { const pts = []; for (let i = 0; i <= 8; i++) { const a = Math.PI * (a0 + (a1 - a0) * i / 8); pts.push([Math.cos(a) * r, -790 + Math.sin(a) * r]); } return pts; };
      P.trace(tete, arc(112, 1.08, 1.56), { w: 1.8, passes: 1, jit: 1 });
      P.trace(tete, arc(100, 1.16, 1.48), { w: 1.5, passes: 1, jit: 1 });
      P.trace(tete, arc(116, 1.6, 1.74), { w: 1.6, passes: 1, jit: 1 });
      P.trace(tete, [[-14, -912], [-22, -940], [-4, -950]], { w: 3, passes: 2, jit: 0.8 });
      P.trace(tete, [[4, -913], [6, -936], [22, -942]], { w: 2.6, passes: 2, jit: 0.8 });
      P.trace(tete, [[60, -906], [86, -896], [98, -874]], { w: 2.6, passes: 2, jit: 1 });
    }

    // Oeil : blanc plein, pupille noire a l'avant avec un reflet ; "^" de joie.
    const ex = 84, ey = -806;
    const yeux = g(tete), oeil = g(yeux);
    el("ellipse", { cx: ex, cy: ey, rx: 17, ry: 20, fill: "#ffffff", class: "plein" }, oeil);
    if (p.coiffure === "queue") P.trace(oeil, [[100, -822], [112, -832]], { w: 2.6, passes: 1, jit: 0.6 });
    const iris = g(oeil);   // apres le blanc de l'oeil, sinon il la recouvre
    const pupille = el("ellipse", { cx: ex + 7, cy: ey + 1, rx: 8, ry: 10, fill: "#000000" }, iris);
    el("circle", { cx: ex + 4, cy: ey - 4, r: 2.6, fill: "#ffffff" }, iris);
    gsap.set(yeux, { svgOrigin: `${ex} ${ey}` });
    gsap.set(pupille, { svgOrigin: `${ex + 7} ${ey + 1}` });
    const joie = g(tete, { opacity: 0 });
    P.trace(joie, [[68, -800], [84, -818], [100, -800]], { w: 4, passes: 2 });
    const sourcil = g(tete, { opacity: 0 });
    P.trace(sourcil, [[66, -838], [84, -846], [102, -840]], { w: 3.4, passes: 2 });
    gsap.set(sourcil, { svgOrigin: `${ex} -842` });
    P.trace(tete, [[118, -796], [130, -782], [134, -772], [126, -767], [118, -766]], { w: 3, passes: 2, jit: 0.5 });   // nez

    // Symboles manga.
    const signes = {};
    signes.joues = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.joues, [[56 + i * 10, -758], [66 + i * 10, -780]], { w: 2, passes: 1, jit: 0.8 });
    signes.choc = g(tete, { opacity: 0 });
    for (let i = 0; i < 4; i++) P.trace(signes.choc, [[30 + i * 20, -884], [30 + i * 20, -850 + (i % 2) * 8]], { w: 2.2, passes: 1, jit: 0.8 });
    P.trace(signes.choc, [[124, -1000], [118, -950]], { w: 6, passes: 1, jit: 1 });
    el("circle", { cx: 116, cy: -930, r: 5, fill: "#ffffff" }, signes.choc);
    signes.goutte = g(tete, { opacity: 0 });
    P.trace(signes.goutte, [[136, -906], [126, -880], [128, -866], [138, -861], [147, -867], [148, -880], [136, -906]], { w: 3, passes: 1, jit: 0.6 });
    signes.veine = g(tete, { opacity: 0 });
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]])
      P.trace(signes.veine, [[44 + sx * 26, -870 + sy * 8], [44 + sx * 10, -870 + sy * 10], [44 + sx * 8, -870 + sy * 26]], { w: 3.4, passes: 1, jit: 0.6 });
    gsap.set(signes.veine, { svgOrigin: "44 -870" });

    // Bouches (a l'avant, sous l'oeil), une seule visible a la fois.
    const my = -752, B = (pts) => pts.map(([px, py]) => [92 + px, my + py]);
    const FORMES = {
      neutre: B([[-12, -2], [-2, 4], [10, -1]]), content: B([[-16, -6], [-3, 9], [13, -5]]),
      doute: B([[-13, 2], [-1, -4], [11, 2]]), triste: B([[-13, 6], [-1, -5], [11, 6]]), agace: B([[-13, -2], [11, 4]]),
    };
    const bouches = {};
    for (const [k, pts] of Object.entries(FORMES)) { bouches[k] = g(tete, { opacity: k === "neutre" ? 1 : 0 }); P.trace(bouches[k], pts, { w: 3.4, passes: 2, jit: 0.5 }); }
    bouches.choc = g(tete, { opacity: 0 }); P.rond(bouches.choc, 92, my, 8, 11, { w: 3, passes: 2 });
    bouches.ouverte = g(tete, { opacity: 0 }); P.rond(bouches.ouverte, 92, my, 12, 8, { w: 3, passes: 2 });
    bouches.grande = g(tete, { opacity: 0 });
    P.trace(bouches.grande, B([[-15, -6], [12, -8], [11, 8], [-1, 15], [-12, 7], [-15, -6]]), { w: 3, passes: 2, jit: 0.5 });
    P.trace(bouches.grande, B([[-7, 9], [2, 4], [8, 8]]), { w: 2, passes: 1, jit: 0.3 });
    bouches.petite = g(tete, { opacity: 0 }); P.rond(bouches.petite, 92, my + 1, 6, 7, { w: 3, passes: 2 });
    gsap.set(tete, { svgOrigin: "0 -668" });

    // Bras (arriere puis avant), main avec paume et doigts ; ancre au creux de la main.
    const bras = {}, ancres = {};
    for (const s of [-1, 1]) {
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
      ancres[s > 0 ? "main_avant" : "main_arriere"] = { groupe: avant, x: hx + 2 * s, y: hy + 16 };
    }
    ancres.tete = { groupe: tete, x: 0, y: -915 };
    return { nom: p.nom, corps, tete, queue, jambes, yeux, oeil, joie, pupille, iris, sourcil, signes, bouches, bras, ancres,
      expr: "neutre", tient: null, poseBras: null, hautTete: 1000 };
  }

  // --- Animations -------------------------------------------------------------
  const EXPR = {
    neutre: { s: [0, 0], yeux: 1 }, content: { s: [-6, -6], yeux: 0.8 }, choc: { s: [0, -14], yeux: 1.35 },
    doute: { s: [-14, -8], yeux: 0.9 }, triste: { s: [-14, 2], yeux: 0.85 }, agace: { s: [16, 4], yeux: 0.7 },
  };
  const SIGNES = { content: "joues", choc: "choc", doute: "goutte", triste: "goutte", agace: "veine" };
  const montrerBouche = (tl, it, nom, at) => { for (const [k, b] of Object.entries(it.bouches)) tl.set(b, { opacity: k === nom ? 1 : 0 }, at); };

  function expression(tl, it, nom, at) {
    const e = EXPR[nom] || EXPR.neutre;
    it.expr = EXPR[nom] ? nom : "neutre";
    tl.to(it.sourcil, { rotation: e.s[0], y: e.s[1], opacity: it.expr === "neutre" ? 0 : 1, duration: 0.2, ease: "power2.out" }, at)
      .to(it.yeux, { scaleY: e.yeux, scaleX: nom === "choc" ? 1.15 : 1, duration: 0.16 }, at)
      .to(it.pupille, { scale: nom === "choc" ? 0.4 : 1, duration: 0.12 }, at)
      .set(it.oeil, { opacity: nom === "content" ? 0 : 1 }, at)
      .set(it.joie, { opacity: nom === "content" ? 1 : 0 }, at);
    const signe = SIGNES[it.expr];
    for (const [k, grp] of Object.entries(it.signes)) tl.to(grp, { opacity: k === signe ? 1 : 0, duration: 0.15 }, at);
    if (signe === "goutte") tl.fromTo(it.signes.goutte, { y: -6 }, { y: 10, duration: 0.6, ease: "power1.in", immediateRender: false }, at);
    if (signe === "veine") tl.fromTo(it.signes.veine, { scale: 0.6 }, { scale: 1, duration: 0.18, yoyo: true, repeat: 3, ease: "power2.out", immediateRender: false }, at);
    if (nom === "choc") tl.fromTo(it.tete, { y: 0 }, { y: -14, duration: 0.14, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, at);
    montrerBouche(tl, it, it.expr, at);
    return 0.3;
  }
  // Parole : enchainement fixe de formes de bouche (~9 par seconde) et la tete qui accompagne.
  const SYLLABES = ["grande", "petite", "ouverte", null, "grande", "ouverte", "petite", null, "ouverte", "grande", null, "petite"];
  function parler(tl, it, a) {
    const de = a.t + 0.05, fin = a.t + a.duree - 0.1, pas = 0.11;
    if (a.expr) expression(tl, it, a.expr, a.t - 0.1);
    if (a.geste) geste(tl, it, a.geste, a.t + 0.1);
    for (let t = de, k = 0; t < fin - pas; t += pas, k++) montrerBouche(tl, it, SYLLABES[k % SYLLABES.length] || it.expr, t);
    montrerBouche(tl, it, it.expr, fin);
    const n = Math.max(1, Math.floor((fin - de) / 0.7));
    tl.to(it.tete, { rotation: 3, duration: 0.35, yoyo: true, repeat: n * 2 - 1, ease: "sine.inOut" }, de);
    return a.duree;
  }
  // Pose des bras au repos (ou "tenir" quand la main avant porte un objet).
  const repos = (tl, it, b, at, d = 0.35) => {
    const tenir = b.s > 0 && it.tient;
    tl.to(b.haut, { rotation: tenir ? OUT(1, 12) : 0, duration: d, ease: "power2.inOut" }, at)
      .to(b.avant, { rotation: tenir ? OUT(1, 78) : 0, duration: d, ease: "power2.inOut" }, at);
  };
  function geste(tl, it, nom, at) {
    const bv = it.bras[1], bl = it.bras[-1];
    if (nom === "salut") {
      tl.to(bv.haut, { rotation: OUT(1, 120), duration: 0.3, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, -80), duration: 0.3, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, -60), duration: 0.16, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.32);
      repos(tl, it, bv, at + 1.1);
    } else if (nom === "montre") {
      tl.to(bv.haut, { rotation: OUT(1, 72), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, 14), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, 4), duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut" }, at + 0.35);
      repos(tl, it, bv, at + 1.3);
    } else if (nom === "hausse") {
      for (const b of [bv, bl]) {
        tl.to(b.haut, { rotation: OUT(b.s, 34), duration: 0.25, ease: "power2.out" }, at)
          .to(b.avant, { rotation: OUT(b.s, 78), duration: 0.25, ease: "power2.out" }, at);
        repos(tl, it, b, at + 1.0);
      }
      tl.to(it.corps, { y: -10, duration: 0.25 }, at).to(it.corps, { y: 0, duration: 0.35 }, at + 1.0)
        .to(it.tete, { rotation: -6, duration: 0.25 }, at).to(it.tete, { rotation: 0, duration: 0.35 }, at + 1.0);
    } else if (nom === "explique") {
      tl.to(bv.haut, { rotation: OUT(1, 28), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, 70), duration: 0.28, ease: "power2.out" }, at)
        .to(bv.avant, { rotation: OUT(1, 52), duration: 0.24, yoyo: true, repeat: 3, ease: "sine.inOut" }, at + 0.3);
      repos(tl, it, bv, at + 1.4);
    }
    return 1.4;
  }
  // Marche : jambes et bras en balancier, petit rebond ; le moteur deplace l'objet (ctx.deplacer).
  function marcher(tl, it, a, ctx) {
    const dist = Math.abs(a.vers - ctx.x(it)), duree = a.duree || Math.max(0.6, dist / 260);
    ctx.deplacer(it, a.vers, a.t, duree);
    const pas = 0.26, n = Math.max(1, Math.round(duree / pas));
    const [j0, j1] = it.jambes;
    tl.fromTo(j0, { rotation: -16 }, { rotation: 16, duration: pas, yoyo: true, repeat: n - 1, ease: "sine.inOut", immediateRender: false }, a.t)
      .fromTo(j1, { rotation: 16 }, { rotation: -16, duration: pas, yoyo: true, repeat: n - 1, ease: "sine.inOut", immediateRender: false }, a.t)
      .to([j0, j1], { rotation: 0, duration: 0.15 }, a.t + n * pas)
      .fromTo(it.corps, { y: 0 }, { y: -8, duration: pas / 2, yoyo: true, repeat: n * 2 - 1, ease: "sine.inOut", immediateRender: false }, a.t);
    if (!it.tient) tl.fromTo(it.bras[1].haut, { rotation: 14 }, { rotation: -14, duration: pas, yoyo: true, repeat: n - 1, ease: "sine.inOut", immediateRender: false }, a.t);
    tl.fromTo(it.bras[-1].haut, { rotation: -14 }, { rotation: 14, duration: pas, yoyo: true, repeat: n - 1, ease: "sine.inOut", immediateRender: false }, a.t)
      .to(it.bras[-1].haut, { rotation: 0, duration: 0.15 }, a.t + n * pas);
    if (!it.tient) tl.to(it.bras[1].haut, { rotation: 0, duration: 0.15 }, a.t + n * pas);
    return duree;
  }
  // Tenir / poser : le bras avant se tend, le moteur bascule l'objet de sa place a la main.
  function tenir(tl, it, a, ctx) {
    const b = it.bras[1];
    tl.to(b.haut, { rotation: OUT(1, 40), duration: 0.3, ease: "power2.out" }, a.t)
      .to(b.avant, { rotation: OUT(1, 30), duration: 0.3, ease: "power2.out" }, a.t);
    ctx.basculer(a.objet, `${a.qui}.main_avant`, a.t + 0.3);
    it.tient = a.objet;
    repos(tl, it, b, a.t + 0.45, 0.4);
    return 0.9;
  }
  function poser(tl, it, a, ctx) {
    const b = it.bras[1];
    tl.to(b.haut, { rotation: OUT(1, 40), duration: 0.3, ease: "power2.out" }, a.t)
      .to(b.avant, { rotation: OUT(1, 30), duration: 0.3, ease: "power2.out" }, a.t);
    ctx.basculer(a.objet || it.tient, a.sur || null, a.t + 0.3);
    it.tient = null;
    repos(tl, it, b, a.t + 0.45, 0.4);
    return 0.9;
  }
  // Boire (tasse en main) / telephoner (telephone a l'oreille) : la main monte vers le visage.
  function versVisage(tl, it, at, duree, haut, avant) {
    const b = it.bras[1];
    tl.to(b.haut, { rotation: OUT(1, haut), duration: 0.35, ease: "power2.out" }, at)
      .to(b.avant, { rotation: OUT(1, avant), duration: 0.35, ease: "power2.out" }, at);
    repos(tl, it, b, at + duree - 0.35, 0.35);
  }
  const boire = (tl, it, a) => { const d = a.duree || 1.6; versVisage(tl, it, a.t, d, 34, 128); tl.to(it.tete, { rotation: -8, duration: 0.3, yoyo: true, repeat: 1, repeatDelay: d - 0.9 }, a.t + 0.2); return d; };
  const telephoner = (tl, it, a) => { const d = a.duree || 2.5; versVisage(tl, it, a.t, d, 22, 150); return d; };
  function sauter(tl, it, a) {
    const n = a.fois || 2;
    for (let i = 0; i < n; i++) tl.to(it.corps, { y: -70, duration: 0.2, yoyo: true, repeat: 1, ease: "power2.out" }, a.t + i * 0.45);
    return n * 0.45;
  }
  function regarder(tl, it, a, ctx) { ctx.orienter(it, a.vers, a.t); return 0.2; }
  function entrer(tl, it, a, ctx) {
    const depuis = a.depuis === "droite" ? 1220 : -140, vers = a.vers ?? ctx.xInitial(it);
    ctx.placer(it, depuis, ctx.debutScene);
    return marcher(tl, it, { ...a, vers }, ctx);
  }
  const sortir = (tl, it, a, ctx) => marcher(tl, it, { ...a, vers: a.vers === "gauche" ? -160 : 1240 }, ctx);

  // Vie : respiration, queue de cheval, clignements ; regard pose a l'apparition.
  function vie(tl, it, t0, t1, decalage) {
    tl.to(it.corps, { rotation: 0.8, svgOrigin: "0 0", duration: 1.7, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.7), ease: "sine.inOut" }, t0);
    if (it.queue) tl.fromTo(it.queue, { rotation: -3 }, { rotation: 4, duration: 1.1, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.1), ease: "sine.inOut", immediateRender: false }, t0);
    for (let t = t0 + 1.1 + decalage; t < t1; t += 2.9 + decalage * 0.4)
      tl.to(it.yeux, { scaleY: 0.1, duration: 0.06, yoyo: true, repeat: 1 }, t);
    tl.fromTo(it.iris, { opacity: 0 }, { opacity: 1, duration: 0.15, immediateRender: false }, t0 + 0.9);
  }

  for (const type of Object.keys(MODELES))
    Dessin.enregistrer(type, {
      categorie: "personnage", hauteur: 1030, nom: MODELES[type].nom, ancres: ["main_avant", "main_arriere", "tete"],
      dessiner, vie, expressions: Object.keys(EXPR), gestes: ["salut", "montre", "hausse", "explique"],
      actions: { parler, expression: (tl, it, a) => expression(tl, it, a.expr, a.t), geste: (tl, it, a) => geste(tl, it, a.geste, a.t),
        marcher, entrer, sortir, regarder, tenir, poser, boire, telephoner, sauter },
    });
})();
