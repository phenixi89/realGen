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

//   - ?fit=S : si l'animation dure plus de S secondes, elle est acceleree
//     pour tenir dans S (surimpression calee sur la duree de sa scene).
window.expose = (tl, extraReady) => {
  const natural = tl.duration(), fit = num("fit", 0);
  const speed = fit > 0 && fit < natural ? natural / fit : 1;
  window.DURATION = natural / speed;
  window.seek = (t) => { tl.seek(Math.min(Math.max(t * speed, 0), natural), false); };
  tl.seek(0);
  const imgs = [...document.images].map((i) => (i.complete ? null : new Promise((r) => (i.onload = i.onerror = r))));
  Promise.all([document.fonts ? document.fonts.ready : null, ...imgs, extraReady || null]).then(() => (window.READY = true));
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
