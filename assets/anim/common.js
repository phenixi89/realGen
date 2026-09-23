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

// Theme (catalog/themes.json, passe par catalog.anim_params) : couleurs en
// variables CSS (--c1 primaire, --c2 secondaire, --cbg fond, --cfg texte,
// --chl surligne) et polices TitleFont / TextFont chargees depuis ?ftitle= / ?ftext=.
{
  const css = document.documentElement.style;
  const colors = { c1: "#6c47ff", c2: "#b547ff", cbg: "#140f2e", cfg: "#ffffff", chl: "#ffd700" };
  for (const [k, d] of Object.entries(colors)) css.setProperty(`--${k}`, /^#[0-9a-f]{6}$/i.test(P[k] || "") ? P[k] : d);
  const fonts = [["TitleFont", P.ftitle], ["TextFont", P.ftext]].filter(([, url]) => url)
    .map(([name, url]) => new FontFace(name, `url("${url}")`).load().then((f) => document.fonts.add(f)).catch(() => null));
  window.FONTS_READY = Promise.all(fonts);
}

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
