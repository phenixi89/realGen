// Moteur du documentaire : monte un plan (habitat + moment + animaux + camera + legende) en une timeline GSAP
// rejouable image par image. Format d'un plan (JSON, parametre ?plan=) :
//   { habitat, moment, graine, cadre: "large|moyen|serre", mouvement: "fixe|avant|arriere|droite|gauche",
//     sujets: [{ id, espece, x, regard: "droite|gauche", echelle, profondeur (0 proche .. 1 loin), nombre, y (oiseaux) }],
//     actions: [{ qui, action, t, duree, vers }],
//     legende: { titre, latin, detail }, duree }
(() => {
  const { g, mix } = Doc;

  Doc.monter = (plan, { svg, legende }) => {
    const duree = Math.max(plan.duree || 6, 2), d0 = plan.delai || 0;   // delai : le titre occupe l'ecran au debut du reel
    const monde = g(svg);
    const { plans, M, L } = Doc.monterDecor(monde, plan.habitat, plan.moment, plan.graine || 1);
    const tl = gsap.timeline({ paused: true });
    const SOL = Doc.SOL;

    // ------------------------------------------------------------- animaux
    const items = {};
    for (const s of plan.sujets || []) {
      const esp = Doc.especes[s.espece];
      if (!esp) continue;
      const prof = Math.min(Math.max(s.profondeur || 0, 0), 1);
      const ech = (s.echelle || 1) * (esp.echelle || 1) * (1 - 0.35 * prof);
      const pos = g(plans.acteurs.g, { color: mix(M.sil, M.ciel[3], 0.55 * prof) });
      const flip = g(pos), corps = g(flip);
      const parts = esp.dessiner(corps, s);
      const y = esp.ciel ? (s.y || 560) : SOL - 80 * prof;
      const it = { id: s.id || s.espece, espece: esp, g: pos, flip, pattes: [], ...parts, _x: s.x ?? 540, _t: 0.5 + d0, _regard: s.regard === "gauche" ? -1 : 1 };
      gsap.set(pos, { x: it._x, y, scale: ech, svgOrigin: "0 0" });
      gsap.set(flip, { scaleX: it._regard, svgOrigin: "0 0" });
      esp.vie && esp.vie(tl, it, 0, duree);
      items[it.id] = it;
    }
    const ctx = {
      x: (it) => it._x,
      deplacer(it, x, t, d) {
        const sens = x >= it._x ? 1 : -1;
        if (sens !== it._regard) { tl.set(it.flip, { scaleX: sens }, t); it._regard = sens; }
        tl.to(it.g, { x, duration: d, ease: "none" }, t);
        it._x = x;
      },
    };
    for (const a of plan.actions || []) {
      const it = items[a.qui];
      if (!it) continue;
      const act = { ...a, t: a.t !== undefined ? a.t + d0 : it._t };
      const f = it.espece.actions[a.action] || Doc.actionsCommunes[a.action];
      if (!f) continue;
      const d = f(tl, it, act, ctx) || 1;
      it._t = act.t + d + 0.2;
    }

    // -------------------------------------------------------------- camera
    const cadres = { large: 1, moyen: 1.35, serre: 1.9 };
    const s0 = cadres[plan.cadre] || 1, mv = plan.mouvement || "fixe";
    const premier = Object.values(items).find((i) => !i.espece.ciel) || Object.values(items)[0];
    const h = premier ? premier.espece.hauteur * (gsap.getProperty(premier.g, "scaleX")) : 300;
    const fx = premier ? premier._x : 540, fy = premier && !premier.espece.ciel ? SOL - h * 0.55 : 900;
    const zoom = { avant: [s0, s0 * 1.12], arriere: [s0 * 1.12, s0], fixe: [s0, s0 * 1.03], droite: [s0 * 1.05, s0 * 1.05], gauche: [s0 * 1.05, s0 * 1.05] }[mv] || [s0, s0];
    tl.fromTo(monde, { scale: zoom[0], svgOrigin: `${s0 > 1 ? fx : 540} ${s0 > 1 ? fy : 1000}` },
      { scale: zoom[1], duration: duree - d0, ease: "sine.inOut", immediateRender: true }, d0);
    const dx = mv === "droite" ? -150 : mv === "gauche" ? 150 : 0;
    for (const [nom, p] of Object.entries(plans)) {
      if (dx) tl.fromTo(p.g, { x: -dx * p.k * 0.5 }, { x: dx * p.k * 0.5, duration: duree - d0, ease: "sine.inOut" }, d0);
    }
    // Ciel vivant : nuages qui derivent, etoiles qui scintillent, reflets sur l'eau, brume.
    (L.nuages || []).forEach((n, i) => tl.fromTo(n, { x: -40 * (i % 2 ? 1 : -1) }, { x: 60 * (i % 2 ? 1 : -1), duration: duree, ease: "none" }, 0));
    (L.etoiles || []).forEach((e, i) => tl.to(e, { opacity: 0.15, duration: 0.8 + (i % 5) * 0.3, yoyo: true, repeat: Math.ceil(duree / 1.2), ease: "sine.inOut" }, (i % 7) * 0.1));
    (L.reflets || []).forEach((r, i) => tl.to(r, { x: (i % 2 ? 24 : -24), duration: 1.4 + (i % 4) * 0.3, yoyo: true, repeat: Math.ceil(duree / 1.4), ease: "sine.inOut" }, 0));
    (L.brume || []).forEach((b) => tl.fromTo(b, { x: -60 }, { x: 60, duration: duree, ease: "sine.inOut" }, 0));

    // Poussiere / lucioles dans la lumiere (trajectoires calculees : rendu reproductible).
    const rand = Doc.rng((plan.graine || 1) * 31 + 5), part = g(plans.avant.g, { color: M.lueur });
    for (let i = 0; i < 22; i++) {
      const c = Doc.el("circle", { cx: rand() * 1080, cy: 700 + rand() * 1100, r: 2 + rand() * 4, fill: "currentColor", opacity: 0 }, part);
      const t0 = rand() * 2;
      tl.fromTo(c, { y: 0, x: 0, opacity: 0 }, { y: -90 - rand() * 120, x: (rand() - 0.5) * 80, opacity: 0.55, duration: 3 + rand() * 2, ease: "sine.inOut", yoyo: true, repeat: 1 }, t0);
    }

    // ------------------------------------------------------------ legende
    const l = plan.legende || {};
    if (l.titre) {
      legende.querySelector(".titre").textContent = l.titre;
      legende.querySelector(".latin").textContent = l.latin || "";
      legende.querySelector(".detail").textContent = l.detail || "";
      const fin = Math.max(duree - 0.5, d0 + 2);
      tl.fromTo(legende.querySelector(".trait"), { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.out" }, d0 + 0.5)
        .fromTo(legende.querySelector(".titre"), { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.5 }, d0 + 0.7)
        .fromTo(legende.querySelector(".latin"), { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.5 }, d0 + 1.0)
        .fromTo(legende.querySelector(".detail"), { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.5 }, d0 + 1.4)
        .to(legende, { opacity: 0, duration: 0.5 }, fin);
    } else legende.style.display = "none";
    tl.to({}, { duration: duree }, 0);   // fixe la duree totale
    return { tl, duree, M };
  };
})();
