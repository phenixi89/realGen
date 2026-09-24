// Moteur de dessin "a la main" (schema.html, annotation.html, impact.html...) :
// traits SVG qui se dessinent (stroke-dashoffset), un feutre (ou une craie)
// qui suit la pointe du trait, ecriture manuscrite revelee au fil de la plume.
// Trois supports, choisis par le theme (?dessin=, catalog/themes.json "dessin") :
//   papier -> feutre sombre sur feuille, traits legerement tremblés ;
//   craie  -> craie blanche granuleuse (tableau) ;
//   neon   -> traits lumineux aux couleurs du theme.
// Deterministe (bruit SVG a graine fixe, pseudo-hasard a graine) : deux rendus
// du meme gabarit donnent exactement les memes images.
// A charger apres common.js (et icones.js pour Sketch.icon).
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const SUPPORT = ["papier", "craie", "neon"].includes(P.dessin) ? P.dessin : "papier";
  document.documentElement.dataset.dessin = SUPPORT;
  window.DESSIN = SUPPORT;
  // Encres du support : --ink-ink (trait principal), a1/a2 (accents du theme,
  // assombris sur papier pour rester lisibles), good/bad (coche/croix), hl (surligneur).
  const INKS = {
    papier: { ink: "#1e293b", a1: "color-mix(in srgb,var(--c1) 78%,#000)", a2: "color-mix(in srgb,var(--c2) 72%,#000)",
      good: "#15803d", bad: "#dc2626", hl: "color-mix(in srgb,var(--chl) 75%,transparent)" },
    craie: { ink: "#f8fafc", a1: "var(--c1)", a2: "var(--c2)", good: "#86efac", bad: "#fca5a5",
      hl: "color-mix(in srgb,var(--chl) 38%,transparent)" },
    neon: { ink: "#ffffff", a1: "var(--c1)", a2: "var(--c2)", good: "#4ade80", bad: "#fb7185",
      hl: "color-mix(in srgb,var(--c1) 38%,transparent)" },
  }[SUPPORT];
  for (const [k, v] of Object.entries(INKS)) document.documentElement.style.setProperty(`--ink-${k}`, v);
  window.HAND_READY = P.fhand
    ? new FontFace("HandFont", `url("${P.fhand}")`).load().then((f) => document.fonts.add(f)).catch(() => null)
    : Promise.resolve();

  const mulberry = (seed) => () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const f1 = (v) => Math.round(v * 10) / 10;
  // Catmull-Rom -> courbes de Bezier : polyligne lissee (boucles, fleches).
  const smooth = (pts) => {
    let d = `M${f1(pts[0][0])} ${f1(pts[0][1])}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += ` C${f1(p1[0] + (p2[0] - p0[0]) / 6)} ${f1(p1[1] + (p2[1] - p0[1]) / 6)} ` +
        `${f1(p2[0] - (p3[0] - p1[0]) / 6)} ${f1(p2[1] - (p3[1] - p1[1]) / 6)} ${f1(p2[0])} ${f1(p2[1])}`;
    }
    return d;
  };
  const el = (tag, attrs = {}, parent = null) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  let uid = 0;
  const FILTERS = {
    // Tremble du trait : deplacement par un bruit basse frequence (fixe).
    papier: `<feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="2" seed="4" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G"/>`,
    // Craie : tremble + grain (le trait laisse passer le fond par endroits).
    craie: `<feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="2" seed="7" result="warp"/>
      <feDisplacementMap in="SourceGraphic" in2="warp" scale="6" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="1" seed="3" result="grain"/>
      <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  2.6 0 0 0 -0.55" result="mask"/>
      <feComposite in="d" in2="mask" operator="in"/>`,
    // Neon : trait net + deux halos flous.
    neon: `<feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="5" result="warp"/>
      <feDisplacementMap in="SourceGraphic" in2="warp" scale="3" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feGaussianBlur in="d" stdDeviation="6" result="b1"/><feGaussianBlur in="d" stdDeviation="16" result="b2"/>
      <feMerge><feMergeNode in="b2"/><feMergeNode in="b1"/><feMergeNode in="d"/></feMerge>`,
  };
  // Feutre (papier/neon) ou baton de craie, pointe en (0,0), corps vers le haut-droite.
  const PENS = {
    papier: `<path d="M0 0 L-8 -20 L8 -20 Z" fill="var(--ink-ink)"/>
      <rect x="-15" y="-150" width="30" height="132" rx="7" fill="#f8fafc" stroke="#94a3b8" stroke-width="2"/>
      <rect x="-15" y="-64" width="30" height="16" fill="var(--ink-a1)"/>
      <rect x="-17" y="-205" width="34" height="62" rx="11" fill="var(--ink-a1)"/>`,
    craie: `<rect x="-11" y="-120" width="22" height="124" rx="9" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="2"/>
      <rect x="-11" y="-120" width="22" height="30" rx="9" fill="#e2e8f0"/>`,
    neon: `<path d="M0 0 L-8 -20 L8 -20 Z" fill="var(--c1)"/>
      <rect x="-14" y="-160" width="28" height="142" rx="12" fill="#0f172a" stroke="var(--c1)" stroke-width="3"/>
      <circle cx="0" cy="-4" r="9" fill="var(--c1)" opacity=".8"/>`,
  };

  class Sketch {
    // svg : <svg> plein cadre 1080x1920 SANS viewBox (unites = pixels).
    constructor(svg, opts = {}) {
      this.svg = svg; this.support = SUPPORT; this.width = opts.width || (SUPPORT === "craie" ? 9 : 7);
      this.rnd = mulberry(opts.seed || 7); this.cursor = 0; this.strokes = [];
      this.draw = gsap.timeline();
      const id = `sk${uid++}`;
      const defs = el("defs", {}, svg);
      defs.innerHTML = `<filter id="${id}f" filterUnits="userSpaceOnUse" x="-100" y="-100" width="1280" height="2120">${FILTERS[SUPPORT]}</filter>
        <filter id="${id}s" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="10" dy="14" stdDeviation="8" flood-opacity=".35"/></filter>`;
      this.measure = el("path", {}, defs);
      this.clipDefs = defs; this.id = id;
      this.under = el("g", { filter: `url(#${id}f)` }, svg);   // surligneur, sous l'encre
      if (SUPPORT === "papier") this.under.style.mixBlendMode = "multiply";
      this.ink = el("g", { filter: `url(#${id}f)` }, svg);
      this.pen = el("g", { filter: `url(#${id}s)`, opacity: 0 }, svg);
      el("g", { transform: `rotate(${SUPPORT === "craie" ? 40 : 28})` }, this.pen).innerHTML = PENS[SUPPORT];
      this.showPen = opts.pen !== false;
    }

    lengthOf(d) { this.measure.setAttribute("d", d); return Math.max(this.measure.getTotalLength(), 0.01); }

    color(name) { return name && !name.startsWith("#") && !name.includes("(") ? `var(--ink-${name})` : (name || "var(--ink-ink)"); }

    // Trace un chemin (d) : o.x/o.y/o.scale/o.rotate (transformation), o.color
    // (ink|a1|a2|good|bad|hl ou couleur CSS), o.width (px a l'ecran), o.at/o.dur
    // (s, temps de this.draw ; a la suite du trait precedent par defaut), o.layer.
    path(d, o = {}) {
      const s = o.scale || 1;
      const g = el("g", { transform: `translate(${o.x || 0} ${o.y || 0}) rotate(${o.rotate || 0}) scale(${s})` }, o.layer || this.ink);
      const p = el("path", { d, fill: "none", stroke: this.color(o.color), "stroke-width": (o.width || this.width) / s,
        "stroke-linecap": o.cap || "round", "stroke-linejoin": "round" }, g);
      if (o.opacity !== undefined) p.setAttribute("opacity", o.opacity);
      const len = this.lengthOf(d);
      p.style.strokeDasharray = `${len} ${len}`;
      p.style.strokeDashoffset = len;
      const at = o.at ?? this.cursor;
      const dur = o.dur ?? Math.min(0.9, Math.max(0.14, (len * s) / 1100));
      const ease = o.ease || "power1.inOut";
      this.draw.fromTo(p, { strokeDashoffset: len }, { strokeDashoffset: 0, duration: dur, ease, immediateRender: false }, at);
      this.strokes.push({ start: at, dur, ease: gsap.parseEase(ease), pen: o.pen !== false,
        point: (q) => {
          const pt = p.getPointAtLength(q * len), m = p.getCTM();
          return { x: m.a * pt.x + m.c * pt.y + m.e, y: m.b * pt.x + m.d * pt.y + m.f };
        } });
      this.cursor = at + dur + (o.gap ?? 0.04);
      return p;
    }

    // Icone d'icones.js centree en (cx, cy), de cote size ; traits dans
    // l'ordre, duree totale o.dur repartie selon leur longueur.
    icon(name, cx, cy, size, o = {}) {
      const icon = (window.ICONES || {})[name] || (window.ICONES || {}).question;
      if (!icon) return this.cursor;
      const s = size / 100, lens = icon.d.map((d) => this.lengthOf(d)), total = lens.reduce((a, b) => a + b, 0);
      const dur = o.dur ?? Math.min(1.4, Math.max(0.6, (total * s) / 1400));
      let at = o.at ?? this.cursor;
      icon.d.forEach((d, i) => {
        const di = Math.max(0.05, (dur * lens[i]) / total);
        this.path(d, { ...o, x: cx - size / 2, y: cy - size / 2, scale: s, at, dur: di, gap: 0 });
        at += di;
      });
      this.cursor = at + 0.05;
      return this.cursor;
    }

    // Boucle "entouree au feutre" : ellipse qui deborde un peu d'un tour.
    loop(cx, cy, rx, ry, o = {}) {
      const a0 = -2.4 + this.rnd() * 0.5, tilt = (this.rnd() - 0.5) * 0.14, ph = this.rnd() * 6, pts = [];
      const N = 44, turns = 1.12;
      for (let i = 0; i <= N; i++) {
        const t = i / N, a = a0 + t * Math.PI * 2 * turns, k = (0.97 + 0.07 * t) * (1 + 0.025 * Math.sin(3 * a + ph));
        const x = rx * k * Math.cos(a), y = ry * k * Math.sin(a);
        pts.push([cx + x * Math.cos(tilt) - y * Math.sin(tilt), cy + x * Math.sin(tilt) + y * Math.cos(tilt)]);
      }
      return this.path(smooth(pts), { dur: 0.6, ease: "power2.inOut", ...o });
    }

    // Fleche courbe (bend : courbure, fraction de la longueur, signe = cote).
    arrow(x1, y1, x2, y2, o = {}) {
      const bend = o.bend ?? 0.2, mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
      const cx = mx - dy * bend, cy = my + dx * bend;
      this.path(`M${f1(x1)} ${f1(y1)} Q${f1(cx)} ${f1(cy)} ${f1(x2)} ${f1(y2)}`, { dur: 0.35, ...o });
      const ang = Math.atan2(y2 - cy, x2 - cx), L = o.head || 34, sp = 0.5;
      const h = (s) => `${f1(x2 - L * Math.cos(ang + s * sp))} ${f1(y2 - L * Math.sin(ang + s * sp))}`;
      return this.path(`M${h(1)} L${f1(x2)} ${f1(y2)} L${h(-1)}`, { ...o, at: undefined, dur: 0.16 });
    }

    underline(x1, x2, y, o = {}) {
      const w = x2 - x1, j = () => (this.rnd() - 0.5) * 8;
      return this.path(smooth([[x1, y + j()], [x1 + w * 0.35, y + 5 + j()], [x1 + w * 0.7, y - 3 + j()], [x2, y + 2 + j()]]),
        { dur: 0.3, ...o });
    }

    check(cx, cy, size, o = {}) { return this.path("M16 52 L40 76 L86 24", { x: cx - size / 2, y: cy - size / 2, scale: size / 100, dur: 0.3, color: "good", ...o }); }

    cross(cx, cy, size, o = {}) {
      const base = { x: cx - size / 2, y: cy - size / 2, scale: size / 100, color: "bad", ...o };
      this.path("M22 22 L78 78", { ...base, dur: 0.18 });
      return this.path("M78 22 L22 78", { ...base, at: undefined, dur: 0.18 });
    }

    // Surligneur : bande epaisse translucide, sous l'encre.
    highlight(x, y, w, h, o = {}) {
      return this.path(`M${f1(x)} ${f1(y + h / 2)} L${f1(x + w)} ${f1(y + h / 2 - 4)}`,
        { layer: this.under, color: "hl", width: h, cap: "butt", dur: 0.35, ...o });
    }

    // Ecriture manuscrite : texte coupe en lignes (o.maxWidth), chaque ligne
    // revelee de gauche a droite au rythme de la plume. o.size, o.color,
    // o.anchor ("start" | "middle"), o.speed (caracteres/s), o.lineHeight.
    // -> {end, bottom, lines: [{x, y, w}]}
    text(str, x, y, o = {}) {
      const size = o.size || 64, lh = o.lineHeight || size * 1.18, font = `${size}px HandFont, "Comic Sans MS", cursive`;
      const ctx = (this._ctx ||= document.createElement("canvas").getContext("2d"));
      ctx.font = font;
      const words = String(str).split(/\s+/).filter(Boolean), lines = [];
      for (const w of words) {
        const cur = lines[lines.length - 1];
        if (cur && ctx.measureText(`${cur} ${w}`).width <= (o.maxWidth || 900)) lines[lines.length - 1] = `${cur} ${w}`;
        else lines.push(w);
      }
      // valign "middle" : bloc de lignes centre verticalement sur y.
      if (o.valign === "middle") y = y - ((lines.length - 1) * lh) / 2 + size * 0.33;
      let at = o.at ?? this.cursor;
      const out = [];
      lines.forEach((line, i) => {
        const w = ctx.measureText(line).width, x0 = o.anchor === "middle" ? x - w / 2 : x, base = y + i * lh;
        const cid = `${this.id}c${this.strokes.length}_${i}`;
        const clip = el("clipPath", { id: cid }, this.clipDefs);
        const rect = el("rect", { x: x0 - size * 0.3, y: base - size * 1.1, width: 0, height: size * 1.6 }, clip);
        const t = el("text", { x: x0, y: base, fill: this.color(o.color), "clip-path": `url(#${cid})` }, this.ink);
        t.style.font = font;
        t.textContent = line;
        const dur = Math.max(0.2, line.length / (o.speed || 24));
        this.draw.fromTo(rect, { attr: { width: 0 } }, { attr: { width: w + size * 0.6 }, duration: dur, ease: "none", immediateRender: false }, at);
        this.strokes.push({ start: at, dur, ease: (q) => q, pen: o.pen !== false,
          point: (q) => ({ x: x0 + q * w, y: base - size * 0.28 + Math.sin(q * w / (size * 0.3)) * size * 0.14 }) });
        out.push({ x: x0, y: base, w });
        at += dur + 0.06;
      });
      this.cursor = at;
      return { end: at, bottom: y + (lines.length - 1) * lh + size * 0.35, lines: out };
    }

    // Position du feutre a l'instant t (temps de this.draw) : sur la pointe
    // du trait en cours ; entre deux traits, il glisse (leve) vers le suivant ;
    // entre par le bas-droite et ressort une fois le dessin fini.
    penAt(t) {
      const S = this.strokes.filter((s) => s.pen).sort((a, b) => a.start - b.start);
      const OFF = { x: 1260, y: 2200 };
      if (!S.length || !this.showPen) return { ...OFF, o: 0 };
      const lerp = (a, b, q) => ({ x: a.x + (b.x - a.x) * q, y: a.y + (b.y - a.y) * q });
      const io = (q) => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(Math.max(q, 0), 1));
      const first = S[0];
      if (t < first.start) return { ...lerp(OFF, first.point(0), io((t - first.start + 0.45) / 0.45)), o: 1, up: 1 };
      let prevEnd = null, prev = null;
      for (const s of S) {
        if (t >= s.start && t <= s.start + s.dur) return { ...s.point(s.ease((t - s.start) / s.dur)), o: 1, up: 0 };
        if (t < s.start) {
          const q = io((t - prevEnd) / Math.max(Math.min(s.start - prevEnd, 0.35), 0.01));
          return { ...lerp(prev.point(1), s.point(0), q), o: 1, up: Math.sin(Math.PI * q) };
        }
        if (prevEnd === null || s.start + s.dur > prevEnd) { prevEnd = s.start + s.dur; prev = s; }
      }
      return { ...lerp(prev.point(1), OFF, io((t - prevEnd) / 0.6)), o: 1, up: 1 };
    }

    updatePen(t) {
      const q = this.penAt(t);
      this.pen.setAttribute("transform", `translate(${f1(q.x + 6 * (q.up || 0))} ${f1(q.y - 12 * (q.up || 0))})`);
      this.pen.setAttribute("opacity", q.o);
    }
  }
  window.Sketch = Sketch;
})();
