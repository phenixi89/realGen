// Outils communs du documentaire (assets/anim/documentaire.html) : SVG, couleurs, hasard reproductible.
// Tout ce qui est "au hasard" vient d'un generateur a graine : le rendu est identique d'un lancement a l'autre.
window.Doc = window.Doc || {};
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const g = (parent, attrs) => el("g", attrs, parent);
  const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const rgb = ([r, gg, b]) => "#" + [r, gg, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
  // Melange de deux couleurs #rrggbb (t = 0 -> a, 1 -> b).
  const mix = (a, b, t) => { const A = hex(a), B = hex(b); return rgb(A.map((v, i) => v + (B[i] - v) * t)); };
  const rng = (seed) => () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  // Silhouettes : remplies de la couleur --sil du moment (posee sur le groupe racine).
  const forme = (parent, d, extra) => el("path", { d, fill: "currentColor", ...extra }, parent);
  const ell = (parent, cx, cy, rx, ry, rot = 0) =>
    el("ellipse", { cx, cy, rx, ry, fill: "currentColor", transform: rot ? `rotate(${rot} ${cx} ${cy})` : null }, parent);
  const membre = (parent, pts, w) => el("path", {
    d: "M" + pts.map((p) => p.join(" ")).join(" L"), stroke: "currentColor", "stroke-width": w,
    "stroke-linecap": "round", "stroke-linejoin": "round", fill: "none" }, parent);
  // Courbe lissee passant par les points (Catmull-Rom -> Bezier), fermee ou non.
  const lisse = (pts, ferme = false) => {
    const n = pts.length, P = (i) => pts[(i + n) % n];
    let d = `M${pts[0][0]} ${pts[0][1]}`;
    for (let i = 0; i < (ferme ? n : n - 1); i++) {
      const p0 = ferme ? P(i - 1) : pts[Math.max(i - 1, 0)], p1 = P(i), p2 = P(i + 1), p3 = ferme ? P(i + 2) : pts[Math.min(i + 2, n - 1)];
      d += ` C${p1[0] + (p2[0] - p0[0]) / 6} ${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6} ${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]} ${p2[1]}`;
    }
    return d + (ferme ? " Z" : "");
  };
  Object.assign(Doc, { NS, el, g, mix, rng, forme, ell, membre, lisse });
})();
