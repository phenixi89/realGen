// Contrat commun des gabarits d'animation (cf. scripts/render_js_anim.py) :
//   - la page fait 1080x1920 px, fond transparent sauf gabarit "scene" ;
//   - elle expose window.DURATION (duree naturelle, s) et window.seek(t),
//     qui dessine l'etat EXACT a l'instant t -- rendu image par image,
//     jamais en temps reel, donc identique d'un rendu a l'autre ;
//   - window.READY passe a true une fois images/polices chargees ;
//   - les parametres arrivent par l'URL (?from=42&to=94...).
window.P = Object.fromEntries(new URLSearchParams(location.search));
window.param = (k, d) => (P[k] !== undefined && P[k] !== "" ? P[k] : d);
window.num = (k, d) => (isNaN(parseFloat(P[k])) ? d : parseFloat(P[k]));
window.READY = false;
// Typographie francaise : espace insecable avant ? ! : ; » et apres « (un "?" ne passe jamais seul a la ligne).
window.frTypo = (s) => String(s).replace(/ +([?!:;»])/g, "\u00a0$1").replace(/« +/g, "«\u00a0");

// Theme (catalog/themes.json, passe par catalog.anim_params) : couleurs en
// variables CSS (--c1 primaire, --c2 secondaire, --cbg fond, --cfg texte,
// --chl surligne) et polices TitleFont / TextFont chargees depuis ?ftitle= / ?ftext=.
{
  const css = document.documentElement.style;
  const colors = { c1: "#6c47ff", c2: "#b547ff", cbg: "#140f2e", cfg: "#ffffff", chl: "#ffd700" };
  for (const [k, d] of Object.entries(colors)) css.setProperty(`--${k}`, /^#[0-9a-f]{6}$/i.test(P[k] || "") ? P[k] : d);
  // --c1fg : texte pose sur la couleur primaire -- sombre si elle est tres claire
  // (jaune craie, cyan neon, bleu givre...), blanc sinon (luminance relative sRGB).
  const c1 = /^#[0-9a-f]{6}$/i.test(P.c1 || "") ? P.c1 : colors.c1;
  const lum = [1, 3, 5].map((i) => parseInt(c1.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const light = 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2] > 0.5;
  css.setProperty("--c1fg", light ? "#111827" : "#ffffff");
  // --c1hl : trait de soulignement pose sur la couleur primaire (surligne du theme, ou sombre si elle est claire).
  css.setProperty("--c1hl", light ? "#111827" : "var(--chl)");
  const fonts = [["TitleFont", P.ftitle], ["TextFont", P.ftext]].filter(([, url]) => url)
    .map(([name, url]) => new FontFace(name, `url("${url}")`).load().then((f) => document.fonts.add(f)).catch(() => null));
  window.FONTS_READY = Promise.all(fonts);
}

// Reproduction du zoom ffmpeg zoompan de 3b_build_video_from_screenshots.py,
// image par image, pour qu'une surimpression reste collee a la capture qui
// zoome : ?zoom=in|out|none, ?step, ?zmax, ?fps, ?fx/?fy (point vise, en
// fraction du cadre ; 0.5/0.5 = centre). Fenetre visible clampee au cadre,
// exactement comme zoompan.
window.zoomAt = (t) => {
  const n = Math.round(t * num("fps", 25)), step = num("step", 0.0015), zmax = num("zmax", 1.18);
  const mode = param("zoom", "none");
  if (mode === "out") return n === 0 ? 1 : Math.max(zmax - step * (n - 1), 1);
  if (mode === "in") return Math.min(1 + step * (n + 1), zmax);
  return 1;
};
window.zoomCss = (t, W = 1080, H = 1920) => {
  const z = zoomAt(t), fx = num("fx", 0.5), fy = num("fy", 0.5);
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  const wx = clamp(fx * W - W / z / 2, 0, W - W / z), wy = clamp(fy * H - H / z / 2, 0, H - H / z);
  return `translate(${-wx * z}px, ${-wy * z}px) scale(${z})`;
};

//   - ?fit=S : si l'animation dure plus de S secondes, elle est acceleree
//     pour tenir dans S (surimpression calee sur la duree de sa scene).
window.expose = (tl, extraReady) => {
  const natural = tl.duration(), fit = num("fit", 0);
  const speed = fit > 0 && fit < natural ? natural / fit : 1;
  window.DURATION = natural / speed;
  window.seek = (t) => { tl.seek(Math.min(Math.max(t * speed, 0), natural), false); };
  tl.seek(0);
  const imgs = [...document.images].map((i) => (i.complete ? null : new Promise((r) => (i.onload = i.onerror = r))));
  Promise.all([window.FONTS_READY, document.fonts ? document.fonts.ready : null, ...imgs, extraReady || null]).then(() => (window.READY = true));
  // Apercu dans un navigateur (sans ?render=1) : lecture en boucle.
  if (!P.render) {
    let t0 = performance.now();
    const loop = (now) => {
      const t = ((now - t0) / 1000) % (tl.duration() + 0.8);
      window.seek(t);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
};

// Texture des plans plein cadre (cartes, CTA) : grain de film leger qui
// "vibre" + quelques particules floues qui derivent lentement -- evite le
// rendu d'aplat numerique. Trajectoires calculees (pas de hasard) : rendu
// reproductible. A appeler avant expose(tl), une fois la timeline creee.
window.addAmbient = (tl, count = 14) => {
  const layer = document.createElement("div");
  layer.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden";
  document.body.insertBefore(layer, document.body.children[3] || null);
  for (let i = 0; i < count; i++) {
    const d = document.createElement("div"), size = 10 + ((i * 37) % 28);
    d.style.cssText = `position:absolute;width:${size}px;height:${size}px;border-radius:50%;filter:blur(${2 + (i % 4)}px);` +
      `left:${(i * 173) % 1080}px;top:${(i * 311) % 1920}px;opacity:${0.12 + (i % 5) * 0.05};` +
      `background:${i % 2 ? "var(--c1)" : "var(--c2)"}`;
    layer.appendChild(d);
    tl.to(d, { y: -140 - (i % 6) * 40, x: ((i % 3) - 1) * 60, duration: 12, ease: "none" }, 0);
  }
  const grain = document.createElement("div");
  grain.style.cssText = "position:absolute;inset:-60px;pointer-events:none;opacity:.10;mix-blend-mode:overlay;" +
    "background-image:url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220'>" +
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/></filter>" +
    "<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";
  document.body.appendChild(grain);
  // Le grain saute de place a chaque image (effet pellicule), sans hasard.
  const jitter = { k: 0 };
  tl.to(jitter, { k: 300, duration: 12, ease: "none",
    onUpdate: () => { const k = Math.floor(jitter.k); grain.style.transform = `translate(${(k * 37) % 60 - 30}px, ${(k * 53) % 60 - 30}px)`; } }, 0);
};
