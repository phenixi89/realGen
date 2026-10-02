// Moteur de dessin anime "trait blanc" : socle commun des fonds, personnages,
// animaux et objets (assets/anim/dessin/*.js), assemble par moteur.js.
//
//   Dessin.pinceau(graine)   -> { trace, rond, rect, texte, lavis, lavisRond, rnd, j } : traits a main levee,
//                              lavis = touche de couleur legere sous le trait
//   Dessin.enregistrer(type, definition)  -> ajoute un type au registre
//   Dessin.types[type]       -> { categorie, hauteur, ancres, dessiner, vie, actions }
//   Dessin.son(nom, t, {duree, gain}) -> bruitage a l'instant t (s) : collecte par le
//     moteur (Scene.monter -> sons), mixe par scripts/audio_gen.py (catalog/audio.json "bruitages")
//
// Trait : un trait principal assure + des passes d'esquisse fines ; chaque trait
// existe en deux variantes (classes va / vb) que l'attribut data-v d'un objet de
// premier niveau fait alterner ("boiling lines"). Les cercles ondulent en basses
// frequences et finissent par un leger depassement (pas de bosses de "caillou").
// Tout est deterministe (pseudo-hasard a graine fixe) : deux rendus donnent les
// memes images. Coordonnees "unites dessin" : un personnage fait ~1100 unites
// de haut, origine au sol sous ses pieds, regard vers la droite (x > 0).
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const mulberry = (seed) => () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const hash = (s) => [...String(s)].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 7);
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
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const g = (parent, attrs = {}) => el("g", attrs, parent);

  function pinceau(seed) {
    const rnd = mulberry(seed);
    const j = (a) => (rnd() - 0.5) * 2 * a;
    // Polyligne lissee. passes : 1 principal + (passes - 1) esquisses fines.
    const trace = (parent, pts, { w = 4.2, passes = 3, jit = 1.6, ferme = false, plein = false, alpha = null, couleur = "#ffffff" } = {}) => {
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
          el("path", { d: smooth(p) + (plein ? "Z" : ""), class: "tr", pathLength: 1, fill: plein ? couleur : "none",
            stroke: couleur, "stroke-width": k ? Math.max(1.1, w * 0.32) : w, "stroke-linecap": "round", "stroke-linejoin": "round",
            opacity: alpha !== null ? alpha * (k ? 0.6 : 1) : (k ? 0.55 : 0.97) }, grp);
        }
      }
    };
    // Cercle / ellipse a main levee (voir en-tete). Passes d'esquisse : tours partiels decales.
    const rond = (parent, cx, cy, rx, ry = rx, o = {}) => {
      const passes = o.passes ?? 3, w = o.w ?? 4.2;
      for (let k = 0; k < passes; k++) {
        const n = Math.max(32, Math.round((rx + ry) / 4)), a0 = rnd() * Math.PI * 2;
        const tours = k ? 0.45 + rnd() * 0.5 : 1.04 + rnd() * 0.08;
        const fa = rnd() * 6.28, fb = rnd() * 6.28, amp = k ? 0.02 : 0.01, dx = j(k ? 3 : 0.5), dy = j(k ? 3 : 0.5), pts = [];
        for (let i = 0; i <= n; i++) {
          const t = (i / n) * tours, a = a0 + t * Math.PI * 2;
          const r = 1 + amp * (0.6 * Math.sin(2 * a + fa) + 0.4 * Math.sin(3 * a + fb)) - (k ? 0 : 0.035 * Math.max(0, t - 1) / (tours - 1));
          pts.push([cx + dx + Math.cos(a) * rx * r, cy + dy + Math.sin(a) * ry * r]);
        }
        trace(parent, pts, { ...o, passes: 1, ferme: true, jit: o.jit ?? 0.5, w: k ? Math.max(1.1, w * 0.32) : w,
          alpha: (o.alpha ?? 1) * (k ? 0.5 : 0.97) });
      }
    };
    // Rectangle a main levee (cotes legerement de travers, coins qui depassent).
    const rect = (parent, x, y, w, h, o = {}) => {
      trace(parent, [[x, y], [x + w, y]], o); trace(parent, [[x + w, y], [x + w, y + h]], o);
      trace(parent, [[x + w, y + h], [x, y + h]], o); trace(parent, [[x, y + h], [x, y]], o);
    };
    // Texte manuscrit (police HandT, cf. dessin.css).
    const texte = (parent, x, y, txt, { taille = 40, ancre = "middle", alpha = 1 } = {}) => {
      const t = el("text", { x, y, "text-anchor": ancre, "font-size": taille, fill: "#ffffff", opacity: alpha, class: "manuscrit" }, parent);
      t.textContent = txt;
      return t;
    };
    // Lavis : touche de couleur legere et transparente sous le trait, un peu
    // decalee (effet aquarelle). pts = contour ; ou ellipse via lavisRond.
    const lavis = (parent, pts, couleur, alpha = 0.35) => {
      const p = pts.map(([x, y]) => [x + j(4) + 3, y + j(4) + 2]);
      return el("path", { d: smooth([...p, p[0]]) + "Z", fill: couleur, opacity: alpha, class: "lavis" }, parent);
    };
    const lavisRond = (parent, cx, cy, rx, ry, couleur, alpha = 0.35) => {
      const pts = [];
      for (let i = 0; i < 14; i++) { const a = (i / 14) * Math.PI * 2; pts.push([cx + Math.cos(a) * rx * (1 + j(0.06)), cy + Math.sin(a) * ry * (1 + j(0.06))]); }
      return lavis(parent, pts, couleur, alpha);
    };
    return { trace, rond, rect, texte, lavis, lavisRond, rnd, j };
  }

  // Bouillonnement : alterne les variantes de trait d'un objet de premier niveau.
  const BOIL = 0.16;
  function bouillonner(tl, root, debut, fin, decalage = 0) {
    let k = 0;
    for (let t = debut + decalage; t < fin; t += BOIL, k++) tl.set(root, { attr: { "data-v": k % 2 ? "b" : "a" } }, t);
  }
  // Apparition : les traits d'un groupe se dessinent (stroke-dashoffset), en `duree` secondes.
  function apparition(tl, grp, t0, duree = 1.0) {
    const traits = grp.querySelectorAll(".tr");
    if (traits.length) tl.fromTo(traits, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: Math.min(0.35, duree / 2), stagger: (duree * 0.65) / traits.length, ease: "none", immediateRender: false }, t0);
    const pleins = grp.querySelectorAll(".plein");
    if (pleins.length) tl.fromTo(pleins, { opacity: 0 }, { opacity: 1, duration: 0.15, immediateRender: false }, t0 + duree * 0.8);
    // Les lavis de couleur arrivent a la fin du trace (comme une aquarelle posee apres le dessin).
    const lavis = [...grp.querySelectorAll(".lavis")];
    for (const l of lavis) { const a = +l.getAttribute("opacity") || 0.35; tl.fromTo(l, { opacity: 0 }, { opacity: a, duration: 0.4, immediateRender: false }, t0 + duree * 0.85); }
  }

  const types = {};
  const enregistrer = (type, def) => { types[type] = { categorie: "objet", hauteur: 300, ancres: {}, actions: {}, ...def }; };
  // Bruitages : les actions les signalent ici ; le moteur vide la liste a chaque montage
  // et coupe la collecte (muet) pendant qu'il joue les copies d'un meme objet.
  const sons = { liste: [], muet: false };
  const son = (nom, t, o = {}) => {
    if (sons.muet) return;
    const s = { t: Math.round(t * 1000) / 1000, name: nom };
    if (o.duree) s.duration = Math.round(o.duree * 100) / 100;
    if (o.gain) s.gain = o.gain;
    sons.liste.push(s);
  };
  window.Dessin = { NS, el, g, smooth, mulberry, hash, pinceau, bouillonner, apparition, BOIL, types, enregistrer, son, sons };
})();
