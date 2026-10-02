// Objets et decor du dessin anime (unites dessin, origine au sol sous l'objet,
// sauf objets muraux places avec "y" : origine au centre). Chaque objet peut
// porter une touche de couleur legere (lavis) et avoir des ancres (ou poser un
// autre objet) et des actions.
//   tasse (vapeur), telephone (vibrer), cv, ordinateur (taper), table (bureau),
//   table_ronde (cafe), chaise, plante, horloge (murale), cadre (mural), corbeille,
//   tampon (tamponner), calendrier (mural, defiler), canape (deux places), diptyque (split-screen, comparer).
// "prise" = point saisi par une main (tenir).
// Inserts (gros plan plein cadre, ctx.insert du moteur) : cv.corriger (ligne barree puis
// reecrite a la main), tampon.tamponner, ordinateur.afficher (e-mail a l'ecran),
// telephone.notifier (notification sur l'ecran verrouille).
(() => {
  const { g, el } = Dessin;
  const reg = Dessin.enregistrer;
  const ROUGE = "#ff5a5a", VERT = "#5cc98a";

  // Texte manuscrit ecrit au fil du temps dans un insert : coupe en lignes de `largeur` px,
  // chaque ligne se devoile de gauche a droite (masque). -> { fin (s), bas (y sous la derniere ligne), lignes }
  let nMasque = 0;
  function ecrire(tl, parent, P, x, y, texte, { taille = 56, largeur = 760, t = 0, mps = 3.2, couleur = "#ffffff", ancre = "start" } = {}) {
    const mots = String(texte || "").split(/\s+/).filter(Boolean), lignes = [];
    const mesure = P.texte(parent, 0, -9999, "", { taille });
    let cur = "";
    for (const m of mots) {
      mesure.textContent = cur ? cur + " " + m : m;
      if (cur && mesure.getComputedTextLength() > largeur) { lignes.push(cur); cur = m; } else cur = mesure.textContent;
    }
    if (cur) lignes.push(cur);
    mesure.remove();
    const svg = parent.ownerSVGElement, defs = svg.querySelector("defs") || el("defs", {}, svg);
    let tc = t;
    const res = lignes.map((l, i) => {
      const yy = y + i * taille * 1.22;
      const txt = P.texte(parent, x, yy, l, { taille, ancre });
      txt.setAttribute("fill", couleur);
      const w = txt.getComputedTextLength(), x0 = ancre === "middle" ? x - w / 2 : x;
      const id = "masque-ecrit-" + (++nMasque);
      const cp = el("clipPath", { id }, defs), r = el("rect", { x: x0 - 6, y: yy - taille, width: 0, height: taille * 1.4 }, cp);
      txt.setAttribute("clip-path", `url(#${id})`);
      const d = Math.max(0.25, l.split(/\s+/).length / mps);
      tl.fromTo(r, { attr: { width: 0 } }, { attr: { width: w + 12 }, duration: d, ease: "none", immediateRender: false }, tc);
      tc += d + 0.05;
      return { txt, x0, w, y: yy };
    });
    return { fin: tc, bas: y + lignes.length * taille * 1.22, lignes: res };
  }
  // Feuille de CV plein cadre (fond des inserts cv / tampon) : cadre papier, photo, lignes de titre.
  function feuille(grp, P) {
    el("rect", { x: 0, y: 0, width: 1080, height: 1920, fill: "#000000", opacity: 0.88 }, grp);
    el("rect", { x: 116, y: 646, width: 848, height: 1048, fill: "#fff1c9", opacity: 0.1, class: "lavis" }, grp);
    P.rect(grp, 110, 640, 860, 1060, { w: 4.2, passes: 2 });
    P.rect(grp, 160, 690, 120, 140, { w: 3, passes: 1 });
    P.trace(grp, [[320, 720], [640, 720]], { w: 5, passes: 1 });
    P.trace(grp, [[320, 770], [560, 770]], { w: 3, passes: 1 });
    P.trace(grp, [[320, 810], [600, 810]], { w: 2.4, passes: 1, alpha: 0.6 });
    P.trace(grp, [[160, 880], [920, 880]], { w: 2, passes: 1, alpha: 0.5 });
  }

  reg("tasse", {
    categorie: "objet", hauteur: 70, prise: [30, -30],
    dessiner(parent, P) {
      const corps = g(parent);
      P.lavis(corps, [[-21, -50], [-17, -5], [17, -5], [21, -50]], "#ff8a5c", 0.55);
      P.trace(corps, [[-22, -52], [-18, -4], [18, -4], [22, -52]], { w: 3.4 });
      P.rond(corps, 0, -52, 22, 5, { w: 2.6, passes: 2 });
      P.trace(corps, [[20, -44], [34, -42], [36, -26], [19, -18]], { w: 3 });
      const vapeur = g(parent);
      for (const dx of [-10, 4, 16]) P.trace(vapeur, [[dx, -66], [dx - 6, -82], [dx + 4, -98], [dx - 3, -116]], { w: 2, passes: 1, jit: 1.2, alpha: 0.7 });
      return { corps, vapeur };
    },
    vie(tl, it, t0, t1) {
      tl.fromTo(it.vapeur, { y: 6, opacity: 0.3 }, { y: -10, opacity: 0.9, duration: 1.2, yoyo: true, repeat: Math.ceil((t1 - t0) / 1.2), ease: "sine.inOut", immediateRender: false }, t0);
    },
    actions: {},
  });

  reg("telephone", {
    categorie: "objet", hauteur: 80, prise: [0, -30],
    dessiner(parent, P) {
      const corps = g(parent);
      P.lavis(corps, [[-13, -70], [13, -70], [13, -12], [-13, -12]], "#7fc8ff", 0.4);
      P.rect(corps, -18, -76, 36, 76, { w: 3.2, passes: 2 });
      P.rond(corps, 0, -6, 3, 3, { w: 2, passes: 1 });
      const ondes = g(parent, { opacity: 0 });
      for (const s of [-1, 1]) {
        P.trace(ondes, [[s * 28, -60], [s * 36, -40], [s * 28, -20]], { w: 2.4, passes: 1 });
        P.trace(ondes, [[s * 40, -66], [s * 50, -40], [s * 40, -14]], { w: 2, passes: 1 });
      }
      gsap.set(corps, { svgOrigin: "0 -38" });
      return { corps, ondes };
    },
    actions: {
      vibrer(tl, it, a) {
        const d = a.duree || 1.2, n = Math.round(d / 0.06);
        Dessin.son("vibreur", a.t, { duree: d });
        tl.set(it.ondes, { opacity: 1 }, a.t).set(it.ondes, { opacity: 0 }, a.t + d)
          .fromTo(it.corps, { rotation: -9 }, { rotation: 9, duration: 0.06, yoyo: true, repeat: n - 1, immediateRender: false }, a.t)
          .to(it.corps, { rotation: 0, duration: 0.05 }, a.t + d);
        return d;
      },
      // Gros plan sur l'ecran : heure, puis une notification ("titre" = expediteur, "texte" = message).
      notifier(tl, it, a, ctx) {
        const P = Dessin.pinceau(Dessin.hash("notif" + a.t));
        return ctx.insert(a.t, a.duree || 2.8, (grp, t0) => {
          el("rect", { x: 0, y: 0, width: 1080, height: 1920, fill: "#000000", opacity: 0.88 }, grp);
          el("rect", { x: 250, y: 650, width: 580, height: 990, fill: "#7fc8ff", opacity: 0.12, class: "lavis" }, grp);
          P.rect(grp, 230, 620, 620, 1060, { w: 4.6, passes: 2 });
          P.rect(grp, 250, 650, 580, 990, { w: 2, passes: 1, alpha: 0.5 });
          P.texte(grp, 540, 820, a.heure || "18:42", { taille: 110 });
          const carte = g(grp);
          el("rect", { x: 270, y: 900, width: 540, height: 360, rx: 24, fill: "#000000" }, carte);
          P.rect(carte, 270, 900, 540, 360, { w: 3.4, passes: 2 });
          P.lavisRond(carte, 312, 945, 18, 18, VERT, 0.8);
          P.texte(carte, 344, 958, a.titre || "Nouveau message", { taille: 40, ancre: "start" });
          ecrire(tl, carte, P, 296, 1030, a.texte, { taille: 44, largeur: 490, t: t0 + 0.55, mps: 9 });
          gsap.set(carte, { opacity: 0 });
          tl.fromTo(carte, { opacity: 0, y: -80 }, { opacity: 1, y: 0, duration: 0.3, ease: "back.out(1.6)", immediateRender: false }, t0 + 0.35);
          Dessin.son("notification", t0 + 0.35);
        });
      },
    },
  });

  reg("cv", {
    categorie: "objet", hauteur: 130, prise: [0, -40],
    dessiner(parent, P) {
      const f = g(parent);
      P.lavis(f, [[-44, -118], [44, -118], [44, -2], [-44, -2]], "#fff1c9", 0.2);
      P.rect(f, -45, -120, 90, 120, { w: 3, passes: 2 });
      P.rect(f, -34, -108, 24, 28, { w: 2, passes: 1 });
      P.trace(f, [[0, -102], [32, -102]], { w: 2.4, passes: 1 });
      P.trace(f, [[0, -90], [24, -90]], { w: 1.8, passes: 1 });
      for (let i = 0; i < 4; i++) P.trace(f, [[-34, -66 + i * 14], [30 - (i % 2) * 14, -66 + i * 14]], { w: 1.8, passes: 1 });
      P.texte(f, 22, -84, "CV", { taille: 18 });
      return { f };
    },
    actions: {
      // Gros plan sur le CV : "avant" s'ecrit, se fait barrer en rouge, puis "apres" s'ecrit dessous (surligne vert).
      corriger(tl, it, a, ctx) {
        const P = Dessin.pinceau(Dessin.hash("cv" + a.t));
        const duree = a.duree || Math.min(7, 1.6 + (String(a.avant || "").split(/\s+/).length + String(a.apres || "").split(/\s+/).length) / 3.2 + 1.4);
        return ctx.insert(a.t, duree, (grp, t0) => {
          feuille(grp, P);
          const av = ecrire(tl, grp, P, 170, 990, a.avant, { taille: 54, largeur: 740, t: t0 + 0.35 });
          Dessin.son("feutre", t0 + 0.35, { duree: Math.max(0.4, av.fin - t0 - 0.4) });
          const barre = g(grp);
          for (const l of av.lignes) P.trace(barre, [[l.x0 - 10, l.y - 18], [l.x0 + l.w + 10, l.y - 22]], { w: 7, passes: 2, couleur: ROUGE });
          tl.fromTo(barre.querySelectorAll("path"), { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.3, ease: "power1.in", immediateRender: false }, av.fin + 0.1);
          gsap.set(barre.querySelectorAll("path"), { strokeDashoffset: 1 });
          if (a.apres) {
            const yA = av.bas + 70;
            P.trace(grp, [[150, yA - 20], [180, yA - 34], [150, yA - 48]], { w: 4, passes: 1, couleur: VERT });
            const ap = ecrire(tl, grp, P, 200, yA, a.apres, { taille: 54, largeur: 720, t: av.fin + 0.55 });
            for (const l of ap.lignes) {
              const sl = P.lavis(grp, [[l.x0 - 6, l.y + 4], [l.x0 + l.w + 6, l.y + 4], [l.x0 + l.w + 6, l.y + 18], [l.x0 - 6, l.y + 18]], VERT, 0.55);
              tl.fromTo(sl, { opacity: 0 }, { opacity: 0.55, duration: 0.3, immediateRender: false }, ap.fin);
              gsap.set(sl, { opacity: 0 });
            }
            Dessin.son("feutre", av.fin + 0.55, { duree: Math.max(0.4, ap.fin - av.fin - 0.6) });
            Dessin.son("ding", ap.fin, { gain: 0.7 });
          }
        });
      },
    },
  });

  reg("tampon", {
    categorie: "objet", hauteur: 110, prise: [0, -80],
    dessiner(parent, P) {
      const corps = g(parent);
      P.lavis(corps, [[-30, -28], [30, -28], [30, -6], [-30, -6]], ROUGE, 0.5);
      P.rect(corps, -34, -30, 68, 26, { w: 3.2, passes: 2 });
      P.trace(corps, [[-36, -2], [36, -2]], { w: 4, passes: 1 });
      P.trace(corps, [[-8, -30], [-8, -70]], { w: 3, passes: 1 }); P.trace(corps, [[8, -30], [8, -70]], { w: 3, passes: 1 });
      P.rond(corps, 0, -86, 20, 16, { w: 3.4, passes: 2 });
      gsap.set(corps, { svgOrigin: "0 0" });
      return { corps };
    },
    actions: {
      // Coup de tampon : le tampon s'abat, puis gros plan sur un CV marque "texte" (rouge ou vert).
      tamponner(tl, it, a, ctx) {
        tl.to(it.corps, { y: 30, duration: 0.12, ease: "power3.in" }, a.t).to(it.corps, { y: 0, duration: 0.2 }, a.t + 0.14);
        const P = Dessin.pinceau(Dessin.hash("tampon" + a.t)), couleur = a.couleur === "vert" ? VERT : ROUGE;
        const d = ctx.insert(a.t + 0.1, a.duree || 2.4, (grp, t0) => {
          feuille(grp, P);
          for (let i = 0; i < 6; i++) P.trace(grp, [[160, 960 + i * 70], [880 - (i % 3) * 120, 960 + i * 70]], { w: 2.4, passes: 1, alpha: 0.5 });
          const marque = g(grp);
          const texte = String(a.texte || "REFUSÉ").toUpperCase();
          const t = P.texte(marque, 540, 1240, texte, { taille: texte.length > 9 ? 92 : 120 });
          t.setAttribute("fill", couleur);
          const w = Math.min(820, t.getComputedTextLength() + 80);
          P.rect(marque, 540 - w / 2, 1120, w, 160, { w: 7, passes: 2, couleur });
          gsap.set(marque, { opacity: 0, svgOrigin: "540 1200", rotation: -12 });
          tl.fromTo(marque, { opacity: 0, scale: 2.4 }, { opacity: 0.92, scale: 1, duration: 0.16, ease: "power4.in", immediateRender: false }, t0 + 0.45)
            .fromTo(grp, { x: -10 }, { x: 0, duration: 0.25, ease: "elastic.out(1, 0.3)", immediateRender: false }, t0 + 0.61);
          Dessin.son("tampon", t0 + 0.6);
        });
        return d + 0.1;
      },
    },
  });

  reg("corbeille", {
    categorie: "decor", hauteur: 200,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-62, -176], [62, -176], [48, -4], [-48, -4]], "#9aa7b8", 0.3);
      P.trace(g0, [[-66, -180], [66, -180], [50, 0], [-50, 0], [-66, -180]], { w: 3.6, ferme: true });
      P.rond(g0, 0, -180, 66, 10, { w: 3, passes: 2 });
      for (const x of [-34, 0, 34]) P.trace(g0, [[x * 1.25, -170], [x, -6]], { w: 1.8, passes: 1, alpha: 0.6 });
      P.rond(g0, -18, -192, 20, 16, { w: 2.4, passes: 1 }); P.trace(g0, [[-28, -196], [-10, -188]], { w: 1.6, passes: 1 });
      return {};
    },
  });

  // Calendrier mural (place avec "y") : page du jour ; "defiler" fait s'envoler les pages (le temps passe).
  reg("calendrier", {
    categorie: "decor", hauteur: 160,
    dessiner(parent, P, o) {
      const g0 = g(parent);
      P.lavis(g0, [[-66, -78], [66, -78], [66, -44], [-66, -44]], ROUGE, 0.5);
      P.rect(g0, -70, -80, 140, 160, { w: 3.4, passes: 2 });
      P.trace(g0, [[-70, -44], [70, -44]], { w: 2.6, passes: 1 });
      for (const x of [-36, 36]) P.rond(g0, x, -86, 7, 9, { w: 2.4, passes: 1 });
      const jour0 = Number(o.jour) || 12;
      const nums = [];
      for (let k = 0; k <= 8; k++) { const t = P.texte(g0, 0, 50, String(((jour0 + k - 1) % 31) + 1), { taille: 84 }); gsap.set(t, { opacity: k ? 0 : 1 }); nums.push(t); }
      return { g0, nums, P };
    },
    actions: {
      defiler(tl, it, a, ctx) {
        const n = Math.min(8, a.fois || 3);
        for (let k = 0; k < n; k++) {
          const at = a.t + k * 0.32;
          const page = g(it.g0);
          el("rect", { x: -66, y: -40, width: 132, height: 116, fill: "#000000" }, page);
          it.P.rect(page, -66, -40, 132, 116, { w: 2.6, passes: 1 });
          gsap.set(page, { opacity: 0, svgOrigin: "0 -40" });
          tl.set(page, { opacity: 1 }, at).set(it.nums[k], { opacity: 0 }, at).set(it.nums[k + 1], { opacity: 1 }, at)
            .fromTo(page, { x: 0, y: 0, rotation: 0 }, { x: 140 - k * 30, y: -160, rotation: 50 + k * 15, duration: 0.6, ease: "power2.out", immediateRender: false }, at)
            .to(page, { opacity: 0, duration: 0.2 }, at + 0.45);
        }
        Dessin.son("pages", a.t, { duree: n * 0.32 });
        return n * 0.32 + 0.4;
      },
    },
  });

  // Canape de face, deux places (le moteur assoit le premier a gauche, le second a droite).
  reg("canape", {
    categorie: "decor", hauteur: 420, places: [-190, 190],
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-320, -410], [320, -410], [312, -296], [-312, -296]], "#8f7fd6", 0.25);
      P.trace(g0, [[-324, -284], [-338, -420], [338, -420], [324, -284]], { w: 3.8 });
      P.lavis(g0, [[-300, -286], [300, -286], [300, -126], [-300, -126]], "#8f7fd6", 0.3);
      P.rect(g0, -310, -290, 620, 70, { w: 3.4, passes: 2 });
      P.trace(g0, [[0, -290], [0, -222]], { w: 2.4, passes: 1 });
      for (const s of [-1, 1]) {
        P.trace(g0, [[s * 310, -330], [s * 392, -330], [s * 392, -110], [s * 310, -110]], { w: 3.6 });
        P.trace(g0, [[s * 338, -110], [s * 346, 0]], { w: 3.4 });
      }
      P.trace(g0, [[-310, -220], [-310, -120], [310, -120], [310, -220]], { w: 3.2 });
      return { ancres: { assise: { groupe: g0, x: 0, y: -290 } } };
    },
  });

  reg("ordinateur", {
    categorie: "objet", hauteur: 140,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-74, -126], [74, -126], [74, -36], [-74, -36]], "#7fc8ff", 0.25);
      P.rect(g0, -80, -132, 160, 102, { w: 3.4, passes: 2 });
      P.trace(g0, [[-96, -24], [96, -24], [104, 0], [-104, 0], [-96, -24]], { w: 3.2, passes: 2 });
      P.trace(g0, [[-20, -12], [20, -12]], { w: 2, passes: 1 });
      const lignes = [];
      for (let i = 0; i < 4; i++) { const l = g(g0, { opacity: 0 }); P.trace(l, [[-62, -114 + i * 18], [40 - (i % 2) * 30, -114 + i * 18]], { w: 2.2, passes: 1 }); lignes.push(l); }
      return { lignes };
    },
    actions: {
      taper(tl, it, a) {
        const d = a.duree || 1.6;
        Dessin.son("clavier", a.t, { duree: d });
        it.lignes.forEach((l, i) => tl.set(l, { opacity: 1 }, a.t + (i + 1) * (d / (it.lignes.length + 1))));
        return d;
      },
      // Gros plan sur l'ecran : un e-mail ("titre" = objet, "texte" = corps) qui s'affiche.
      afficher(tl, it, a, ctx) {
        const P = Dessin.pinceau(Dessin.hash("ecran" + a.t));
        const duree = a.duree || Math.min(6, 1.8 + String(a.texte || "").split(/\s+/).length / 4);
        return ctx.insert(a.t, duree, (grp, t0) => {
          el("rect", { x: 0, y: 0, width: 1080, height: 1920, fill: "#000000", opacity: 0.88 }, grp);
          el("rect", { x: 96, y: 686, width: 888, height: 768, fill: "#7fc8ff", opacity: 0.1, class: "lavis" }, grp);
          P.rect(grp, 90, 680, 900, 780, { w: 4.6, passes: 2 });
          P.trace(grp, [[60, 1500], [1020, 1500], [1050, 1560], [30, 1560], [60, 1500]], { w: 4, passes: 2 });
          P.trace(grp, [[90, 760], [990, 760]], { w: 2.4, passes: 1 });
          [[130, ROUGE], [170, "#ffc94d"], [210, VERT]].forEach(([x, c]) => { P.lavisRond(grp, x, 720, 11, 11, c, 0.8); P.rond(grp, x, 720, 11, 11, { w: 2, passes: 1 }); });
          P.texte(grp, 140, 840, "Objet :", { taille: 40, ancre: "start", alpha: 0.6 });
          P.texte(grp, 290, 840, a.titre || "Votre candidature", { taille: 44, ancre: "start" });
          P.trace(grp, [[140, 875], [940, 875]], { w: 1.8, passes: 1, alpha: 0.5 });
          ecrire(tl, grp, P, 140, 960, a.texte, { taille: 50, largeur: 800, t: t0 + 0.4, mps: 7 });
          Dessin.son("notification", t0 + 0.25, { gain: 0.8 });
        });
      },
    },
  });

  // Split-screen : deux versions d'un meme moment cote a cote (« deux lendemains », avant / apres, ce qu'il
  // dit / ce que le recruteur entend). Objet mural invisible ; "comparer" = insert plein cadre.
  reg("diptyque", {
    categorie: "decor", hauteur: 10,
    dessiner(parent) { return { g0: g(parent) }; },
    actions: {
      comparer(tl, it, a, ctx) {
        const P = Dessin.pinceau(Dessin.hash("diptyque" + a.t));
        const mots = (x) => String(x || "").split(/\s+/).filter(Boolean).length;
        const duree = a.duree || Math.min(8, 2.2 + (mots(a.texte_gauche) + mots(a.texte_droite)) / 3.4);
        return ctx.insert(a.t, duree, (grp, t0) => {
          el("rect", { x: 0, y: 0, width: 1080, height: 1920, fill: "#000000", opacity: 0.88 }, grp);
          const cote = (x0, couleur, titre, texte, t) => {
            P.lavis(grp, [[x0 + 6, 566], [x0 + 474, 566], [x0 + 474, 1134], [x0 + 6, 1134]], couleur, 0.13);
            P.rect(grp, x0, 560, 480, 580, { w: 4.4, passes: 2 });
            P.texte(grp, x0 + 240, 650, titre, { taille: 54 });
            P.trace(grp, [[x0 + 50, 690], [x0 + 430, 690]], { w: 2.6, passes: 1, couleur });
            return ecrire(tl, grp, P, x0 + 36, 800, texte, { taille: 52, largeur: 410, t, mps: 5 });
          };
          const gauche = cote(40, ROUGE, a.titre_gauche || "Avant", a.texte_gauche, t0 + 0.4);
          cote(560, VERT, a.titre_droite || "Après", a.texte_droite, gauche.fin + 0.45);
          P.rond(grp, 540, 850, 30, 30, { w: 3.4, passes: 2 });
          P.texte(grp, 540, 866, "VS", { taille: 30 });
          Dessin.son("pop", t0 + 0.1);
          Dessin.son("ding", gauche.fin + 0.45, { gain: 0.7 });
        });
      },
    },
  });

  reg("table", {
    categorie: "decor", hauteur: 450,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-258, -444], [258, -444], [258, -428], [-258, -428]], "#d9a066", 0.45);
      P.rect(g0, -260, -446, 520, 18, { w: 3.6 });
      for (const x of [-232, 232]) P.trace(g0, [[x, -428], [x + Math.sign(x) * 4, 0]], { w: 3.6 });
      P.rect(g0, 90, -428, 130, 64, { w: 2.6, passes: 2 });
      P.trace(g0, [[140, -396], [170, -396]], { w: 3, passes: 1 });
      return { ancres: { dessus: { groupe: g0, x: 0, y: -446 }, dessus_gauche: { groupe: g0, x: -150, y: -446 }, dessus_droite: { groupe: g0, x: 150, y: -446 } } };
    },
  });

  reg("table_ronde", {
    categorie: "decor", hauteur: 440,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavisRond(g0, 0, -424, 148, 14, "#d9a066", 0.45);
      P.rond(g0, 0, -424, 150, 16, { w: 3.6 });
      P.trace(g0, [[0, -408], [0, -18]], { w: 4 });
      P.rond(g0, 0, -10, 70, 10, { w: 3.2 });
      return { ancres: { dessus: { groupe: g0, x: 0, y: -430 }, dessus_gauche: { groupe: g0, x: -80, y: -430 }, dessus_droite: { groupe: g0, x: 80, y: -430 } } };
    },
  });

  reg("chaise", {
    categorie: "decor", hauteur: 600,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavis(g0, [[-60, -282], [70, -282], [70, -270], [-60, -270]], "#d9a066", 0.45);
      P.rect(g0, -62, -286, 134, 16, { w: 3.4 });
      P.trace(g0, [[-58, -286], [-66, -600]], { w: 3.6 });
      P.trace(g0, [[-66, -600], [-40, -604]], { w: 3.4 });
      P.trace(g0, [[-62, -470], [-38, -470]], { w: 2.6, passes: 2 });
      P.trace(g0, [[62, -270], [66, 0]], { w: 3.4 });
      P.trace(g0, [[-54, -270], [-58, 0]], { w: 3.4 });
      return { ancres: { assise: { groupe: g0, x: 0, y: -286 } } };
    },
  });

  reg("plante", {
    categorie: "decor", hauteur: 440,
    dessiner(parent, P) {
      const pot = g(parent), feuilles = g(parent);
      P.lavis(pot, [[-52, -128], [52, -128], [40, -4], [-40, -4]], "#e07a4f", 0.5);
      P.trace(pot, [[-56, -130], [56, -130], [42, 0], [-42, 0], [-56, -130]], { w: 3.6 });
      P.trace(pot, [[-60, -130], [60, -130]], { w: 4 });
      const feuille = (bx, by, tx, ty, l) => {
        const mx = (bx + tx) / 2, my = (by + ty) / 2, nx = -(ty - by), ny = tx - bx, n = Math.hypot(nx, ny) || 1;
        const pts = [[bx, by], [mx + (nx / n) * l, my + (ny / n) * l], [tx, ty], [mx - (nx / n) * l, my - (ny / n) * l], [bx, by]];
        P.lavis(feuilles, pts.slice(0, 4), "#5cc98a", 0.45);
        P.trace(feuilles, pts, { w: 2.8, passes: 2, ferme: true });
        P.trace(feuilles, [[bx, by], [tx, ty]], { w: 1.6, passes: 1 });
      };
      feuille(0, -130, -120, -330, 34); feuille(0, -130, 10, -420, 30); feuille(0, -130, 120, -320, 34);
      feuille(0, -130, -70, -250, 22); feuille(0, -130, 80, -240, 22);
      gsap.set(feuilles, { svgOrigin: "0 -130" });
      return { feuilles };
    },
  });

  // Horloge murale (placee avec "y" : origine au centre) ; les aiguilles tournent.
  reg("horloge", {
    categorie: "decor", hauteur: 130,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.lavisRond(g0, 0, 0, 58, 58, "#ffe08a", 0.3);
      P.rond(g0, 0, 0, 60, 60, { w: 3.6 });
      for (let i = 0; i < 12; i += 3) { const a = (i / 12) * Math.PI * 2; P.trace(g0, [[Math.sin(a) * 46, -Math.cos(a) * 46], [Math.sin(a) * 54, -Math.cos(a) * 54]], { w: 2.6, passes: 1 }); }
      const minutes = g(g0), heures = g(g0);
      P.trace(minutes, [[0, 4], [0, -44]], { w: 2.8, passes: 1 });
      P.trace(heures, [[0, 4], [24, -12]], { w: 3.4, passes: 1 });
      el("circle", { cx: 0, cy: 0, r: 4, fill: "#ffffff" }, g0);
      gsap.set([minutes, heures], { svgOrigin: "0 0" });
      return { minutes, heures };
    },
    vie(tl, it, t0, t1) {
      tl.fromTo(it.minutes, { rotation: 0 }, { rotation: 360 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0)
        .fromTo(it.heures, { rotation: 0 }, { rotation: 30 * ((t1 - t0) / 6), duration: t1 - t0, ease: "none", immediateRender: false }, t0);
    },
  });

  // Cadre mural (diplome) : origine au centre.
  reg("cadre", {
    categorie: "decor", hauteur: 110,
    dessiner(parent, P) {
      const g0 = g(parent);
      P.rect(g0, -70, -50, 140, 100, { w: 3.2, passes: 2 });
      P.rect(g0, -58, -38, 116, 76, { w: 1.8, passes: 1 });
      for (let i = 0; i < 3; i++) P.trace(g0, [[-40, -20 + i * 14], [30 - i * 10, -20 + i * 14]], { w: 1.8, passes: 1 });
      P.lavisRond(g0, 36, 22, 12, 12, "#ffc94d", 0.7);
      P.rond(g0, 36, 22, 11, 11, { w: 2.2, passes: 1 });
      return {};
    },
  });
})();
