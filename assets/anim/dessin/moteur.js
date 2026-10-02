// Moteur de scenes du dessin anime : une scene = un fond + des objets places
// (personnages, animaux, objets, decor) + une liste d'actions. Plusieurs scenes
// s'enchainent (fondu + nouveau dessin qui se trace). Utilise par scene.html et
// dialogue.html (style trait).
//
//   const { tl, duree, sons } = Scene.monter({ scenes: [...] }, { svg, bulles, titres });
// sons : bruitages [{t, name, duration?, gain?}] signales par les actions (Dessin.son),
// plus le feutre du dessin de chaque scene ; scene.html les publie dans window.SONS.
//
// Format d'une scene (catalog/dessins.json documente les types disponibles) :
//   { "fond": "cafe", "echelle": 1.1, "titre": "Lundi matin",
//     "objets": [ {"id": "lea", "type": "lea", "x": 300, "regard": "droite"},
//                 {"id": "table", "type": "table_ronde", "x": 540},
//                 {"id": "tasse", "type": "tasse", "sur": "table.dessus"},
//                 {"id": "horloge", "type": "horloge", "x": 540, "y": 700} ],
//     "actions": [ {"qui": "lea", "action": "parler", "texte": "Salut !", "expr": "content", "geste": "salut"},
//                  {"qui": "lea", "action": "tenir", "objet": "tasse"},
//                  {"qui": "lea", "action": "boire", "avec": true} ] }
// Objet : x (px, 0-1080) au sol, ou "sur": "id.ancre" (pose sur / tenu par un
// autre objet), ou "y" (px) pour un objet accroche au mur ; "regard"
// gauche/droite ; "echelle" (multiplie celle de la scene) ; "assis": id d'une
// chaise (personnage assis dessus des le debut, declarer la chaise avant).
// Actions : jouees dans l'ordre ; "t" (s, depuis le debut de la scene) sinon a
// la suite de la precedente, ou en meme temps qu'elle avec "avec": true.
// "pause" (sans "qui") avance le temps de "duree". "parler" affiche une bulle.
// Scene : "dessine": false = deja dessinee a la 1re image (pas de trace progressif).
// "ellipse": "Une semaine plus tard" -> carton manuscrit en haut (pages qui s'envolent) au
// debut de la scene, a la place du titre. "suite": true -> meme lieu, meme moment que la scene
// precedente : coupe franche, sans fondu ni nouveau trace.
// Camera (action sans "qui") : {"action": "camera", "cadre": "large" | "buste" | "visage" | "objet",
//   "sur": id (personnage ou objet), "rapide": true (coupe seche + petit souffle)} ; jouee a
//   l'instant de l'action suivante, sans la retarder. Les bulles suivent le cadrage.
// Inserts (gros plan plein cadre sur un objet : CV corrige, ecran, telephone, tampon) :
//   ctx.insert(t, duree, dessiner) -- au-dessus de la scene, sous les bulles.
(() => {
  const { g, el, pinceau, hash, bouillonner, apparition, types } = Dessin;
  const DESSIN = 1.0, PREMIERE = 1.25, ECART = 0.25, FONDU = 0.35;
  const dureeReplique = (texte) => Math.min(4, Math.max(1.4, 0.9 + 0.28 * String(texte).split(/\s+/).length));
  const SENS = { gauche: -1, droite: 1 };
  const INSERT_DECALAGE = 150;
  const BULLE_ETROITE = 600;   // largeur max d'une bulle pendant un nuage de pensee (les deux tiennent cote a cote)

  function monter(def, { svg, bulles, titres }) {
    const scenes = def.scenes || [def];
    const tl = gsap.timeline({ paused: true });
    Dessin.sons.liste = []; Dessin.sons.muet = false;
    let S = 0;
    scenes.forEach((sc, n) => {
      const duree = jouerScene(tl, sc, n, S, { svg, bulles, titres, derniere: n === scenes.length - 1, surtitre: def.surtitre,
        coupeApres: !!(scenes[n + 1] && scenes[n + 1].suite) });
      S += duree;
    });
    return { tl, duree: S, sons: Dessin.sons.liste.slice().sort((x, y) => x.t - y.t) };
  }

  // Carton d'ellipse (« Une semaine plus tard… ») : panneau manuscrit en haut, pages de
  // calendrier qui s'envolent, puis il s'efface (~2,4 s).
  function carton(tl, texte, S, titres) {
    const c = document.createElement("div");
    c.className = "ellipse";
    c.innerHTML = '<span class="t"></span>';
    c.querySelector(".t").textContent = frTypo(texte);
    for (let i = 0; i < 3; i++) { const f = document.createElement("i"); f.className = "feuille"; c.appendChild(f); }
    titres.appendChild(c);
    gsap.set(c, { opacity: 0 });
    tl.fromTo(c, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)", immediateRender: false }, S + 0.1)
      .to(c, { opacity: 0, duration: 0.3 }, S + 2.4);
    c.querySelectorAll(".feuille").forEach((f, i) => {
      gsap.set(f, { opacity: 0 });
      tl.fromTo(f, { opacity: 1, x: 0, y: 0, rotation: 0 }, { opacity: 0, x: (i - 1) * 160 + 60, y: -120 - i * 40, rotation: (i - 1) * 40 + 25,
        duration: 0.7, ease: "power2.out", immediateRender: false }, S + 0.35 + i * 0.22);
    });
    Dessin.son("pages", S + 0.35);
  }

  function jouerScene(tl, sc, n, S, dom) {
    const sol = sc.sol ?? 1650, ech = sc.echelle ?? 1.1;
    const scene = g(dom.svg, { class: "scene" });
    gsap.set(scene, { opacity: n === 0 ? 1 : 0 });
    if (n > 0) tl.set(scene, { opacity: 1 }, S);
    // Camera : tout le decor et les objets dans un groupe recadre ; les inserts restent hors cadre.
    const calque = g(scene, { class: "camera" });
    gsap.set(calque, { svgOrigin: "0 0" });
    const cadres = [{ t: -1, s: 1, x: 0, y: 0 }];
    const finScene = sc.duree !== undefined ? S + sc.duree : Infinity;

    // Fond.
    const fondType = types["fond_" + (sc.fond || "vide")] || types.fond_vide;
    const fondRoot = g(calque, { "data-v": "a" });
    const xsSol = (sc.objets || []).filter((o) => o.x !== undefined && o.y === undefined && !o.sur).map((o) => o.x);
    const fond = fondType.dessiner(fondRoot, pinceau(hash("fond" + (sc.fond || "vide")) ^ n), { sol, xs: xsSol });
    const racines = [fondRoot];

    // Objets : une copie par emplacement (place d'origine, mains, supports) ;
    // une seule visible a la fois (ctx.basculer). Les personnages n'ont qu'une copie.
    const objets = {};     // id -> { def, type, copies: {cle: {root, orient, it}}, visible }
    const cles = {};       // id -> emplacements supplementaires vises par tenir / poser
    for (const a of sc.actions || []) {
      if (a.action === "tenir" && a.objet) (cles[a.objet] ||= new Set()).add(`${a.qui}.main_avant`);
      if (a.action === "poser" && a.sur) (cles[a.objet || "?"] ||= new Set()).add(a.sur);
    }
    const ancre = (cible) => {
      const [id, nom] = String(cible).split(".");
      const o = objets[id];
      const anc = o && o.copies[""].it.ancres && o.copies[""].it.ancres[nom];
      if (!anc) throw new Error(`ancre inconnue « ${cible} »`);
      return anc;
    };
    const creerCopie = (o, cle) => {
      const type = types[o.type];
      if (!type) throw new Error(`type d'objet inconnu « ${o.type} »`);
      let root;
      const cible = cle || o.sur;
      if (cible) {
        const anc = ancre(cible), prise = (cle && cle.endsWith("main_avant")) || (cle && cle.endsWith("main_arriere")) ? (type.prise || [0, 0]) : [0, 0];
        root = g(anc.groupe);
        gsap.set(root, { x: anc.x - prise[0], y: anc.y - prise[1], scale: o.echelle ?? 1 });
      } else {
        root = g(calque, { "data-v": "a" });
        gsap.set(root, { x: o.x ?? 540, y: o.y ?? sol, scale: ech * (o.echelle ?? 1) });
        racines.push(root);
      }
      const orient = g(root);
      if (!cible) gsap.set(orient, { scaleX: SENS[o.regard] || 1 });
      const it = type.dessiner(orient, pinceau(hash(o.id + "|" + (cle || ""))), { ...o, sol });
      it._root = root; it._orient = orient; it._id = o.id;
      return { root, orient, it };
    };
    for (const o of sc.objets || []) {
      const entree = { def: o, type: types[o.type], copies: {}, visible: "" };
      objets[o.id] = entree;
      entree.copies[""] = creerCopie(o, "");
      const it = entree.copies[""].it;
      it._x = o.x ?? 540; it._xInit = it._x; it._regard = SENS[o.regard] || 1;
    }
    for (const [id, set] of Object.entries(cles)) {
      const o = objets[id];
      if (!o) throw new Error(`objet inconnu « ${id} » (tenir / poser)`);
      for (const cle of set) { o.copies[cle] = creerCopie(o.def, cle); gsap.set(o.copies[cle].root, { opacity: 0 }); }
    }
    // Entrees en scene : un personnage qui "entre" commence hors champ.
    for (const a of sc.actions || []) {
      if (a.action !== "entrer" || !objets[a.qui]) continue;
      const it = objets[a.qui].copies[""].it;
      gsap.set(it._root, { x: a.depuis === "droite" ? 1220 : -140 });
      it._x = a.depuis === "droite" ? 1220 : -140;
      break;
    }

    // Contexte donne aux actions (deplacements, regard, bascule d'objets).
    const sieges = {};   // id d'un siege a plusieurs places -> places deja prises
    const nuages = [];   // nuages de pensee {t, d, x, dessiner(cx)}
    const ctx = {
      debutScene: S, sol, ech, calque, finScene,
      objet: (id) => { const o = objets[id]; return o && { x: o.copies[""].it._x, regard: o.copies[""].it._regard, it: o.copies[""].it,
        type: o.type, ech: ech * (o.def.echelle ?? 1), def: o.def }; },
      // Siege a plusieurs places (canape : type.places, en unites dessin) : la premiere libre.
      place(id) {
        const o = objets[id];
        if (!o) return null;
        const it = o.copies[""].it, places = o.type.places;
        if (!places) return { x: it._x, regard: it._regard };
        const prises = (sieges[id] ||= []);
        const k = places.findIndex((_, i) => !prises.includes(i));
        const i = k < 0 ? 0 : k;
        prises.push(i);
        return { x: it._x + places[i] * ech * (o.def.echelle ?? 1), regard: places[i] < 0 ? 1 : -1 };
      },
      racine(grp) { racines.push(grp); },
      // Nuage de pensee : dessine apres le placement des bulles, du cote qu'elles laissent libre.
      nuage(n) { nuages.push(n); },
      // Hors camera (nuage de pensee) : groupe au-dessus de la scene, et point de la scene -> ecran
      // sous le cadrage courant (celui de la derniere action camera deja jouee).
      ecranGroupe: () => g(scene, { "data-v": "a" }),
      ecran(x, y) { const c = cadres[cadres.length - 1]; return [x * c.s + c.x, y * c.s + c.y]; },
      // Insert plein cadre : panneau noir au-dessus de la scene (sous les bulles), dessine par
      // dessiner(groupe, t0, duree) ; borne a la fin de la scene. -> duree jouee.
      insert(t, duree, dessiner) {
        const d = Math.max(0.6, Math.min(duree, finScene - 0.15 - t));
        if (ctx.copie > 0) return d;   // objet en plusieurs copies (place, main) : un seul insert
        const grp = g(scene, { class: "insert", "data-v": "a" });
        gsap.set(grp, { opacity: 0 });
        // Contenu descendu sous la zone des bulles (bas d'une bulle vers y = 740) : la replique dite
        // pendant le gros plan ne le cache plus.
        el("rect", { x: 0, y: 0, width: 1080, height: 1920, fill: "#000000", opacity: 0.5 }, grp);
        dessiner(g(grp, { transform: `translate(0 ${INSERT_DECALAGE})` }), t, d);
        racines.push(grp);
        tl.fromTo(grp, { opacity: 0, scale: 0.9, svgOrigin: "540 1250" }, { opacity: 1, scale: 1, duration: 0.25, ease: "back.out(1.6)", immediateRender: false }, t)
          .to(grp, { opacity: 0, duration: 0.2 }, t + d - 0.2);
        return d;
      },
      x: (it) => it._x, xInitial: (it) => it._xInit,
      placer: (it, x) => { it._x = x; },
      orienter(it, vers, t) {
        let sens = SENS[vers];
        if (!sens && objets[vers]) sens = Math.sign(objets[vers].copies[""].it._x - it._x) || it._regard;
        if (!sens || sens === it._regard) return;
        tl.fromTo(it._orient, { scaleX: it._regard }, { scaleX: sens, duration: 0.14, immediateRender: false }, t);
        it._regard = sens;
      },
      deplacer(it, vers, t, duree) {
        ctx.orienter(it, vers > it._x ? "droite" : "gauche", t);
        tl.fromTo(it._root, { x: it._x }, { x: vers, duration: duree, ease: "none", immediateRender: false }, t);
        it._x = vers;
      },
      basculer(id, cle, t) {
        const o = objets[id];
        if (!o) throw new Error(`objet inconnu « ${id} »`);
        const vise = cle || "";
        for (const [k, c] of Object.entries(o.copies)) tl.set(c.root, { opacity: k === vise ? 1 : 0 }, t);
        o.visible = vise;
      },
    };

    // Pose de depart : assis sur un siege ("assis": id), a sa place et tourne comme lui.
    for (const o of sc.objets || []) {
      if (!o.assis) continue;
      const sup = objets[o.assis];
      if (!sup) throw new Error(`« assis » : siege inconnu « ${o.assis} »`);
      const it = objets[o.id].copies[""].it, p = ctx.place(o.assis);
      it._x = it._xInit = p.x; it._regard = p.regard;
      gsap.set(it._root, { x: it._x }); gsap.set(it._orient, { scaleX: it._regard });
      if (objets[o.id].type.poseInitiale) objets[o.id].type.poseInitiale(it, o);
    }

    // Camera : cadre vise -> echelle et decalage du groupe camera (bornes : jamais hors du decor).
    const CADRES = { large: 1, buste: 1.45, visage: 2.0, objet: 2.2 };
    function cadrer(a) {
      const nom = CADRES[a.cadre] ? a.cadre : "large";
      let s = CADRES[nom], cx = 540, cy = 960, vx = 540, vy = 960;
      const o = a.sur && objets[a.sur];
      if (nom !== "large" && o) {
        const it = o.copies[""].it, e = ech * (o.def.echelle ?? 1);
        if (o.type.categorie === "personnage") {
          cx = it._x; cy = nom === "visage" ? sol - (it.assis ? 742 : 790) * e : sol - (it.assis ? 560 : 620) * e;
          vy = nom === "visage" ? 1080 : 1150;
        } else {   // objet : centre de son dessin (copie visible a ce moment)
          const c = o.copies[o.visible] || o.copies[""];
          const b = c.root.getBBox(), m = dom.svg.getScreenCTM().inverse().multiply(c.root.getScreenCTM());
          const p = new DOMPoint(b.x + b.width / 2, b.y + b.height / 2).matrixTransform(m);
          cx = p.x; cy = p.y; vy = 1150;
          s = Math.min(3, Math.max(1.6, 420 / Math.max(b.width * m.a, b.height * m.d, 1)));
        }
      } else s = 1;
      const x = Math.min(0, Math.max(1080 * (1 - s), vx - s * cx)), y = Math.min(0, Math.max(1920 * (1 - s), vy - s * cy));
      const t = a.t, d = a.rapide ? 0.12 : 0.55;
      tl.to(calque, { x, y, scale: s, duration: d, ease: a.rapide ? "power3.out" : "power2.inOut" }, t);
      if (a.rapide) Dessin.son("zoom", t);
      cadres.push({ t: t + d * 0.5, s, x, y });
    }
    const cadreA = (t) => cadres.filter((c) => c.t <= t).pop();

    // Actions, dans l'ordre.
    let curseur = PREMIERE, prec = { t: PREMIERE, fin: PREMIERE }, fin = PREMIERE;
    const repliques = [];
    for (const a0 of sc.actions || []) {
      const a = { ...a0 };
      const tRel = a.t ?? (a.avec ? prec.t : curseur);
      a.t = S + tRel;
      if (a.action === "pause") { curseur = tRel + (a.duree || 1); prec = { t: tRel, fin: curseur }; fin = Math.max(fin, curseur); continue; }
      if (a.action === "camera") { cadrer(a); continue; }   // ne retarde pas l'action suivante
      const o = objets[a.qui];
      if (!o) throw new Error(`« qui » inconnu : ${a.qui}`);
      const fn = o.type.actions && o.type.actions[a.action];
      if (!fn) throw new Error(`action « ${a.action} » inconnue pour ${o.def.type}`);
      if (a.action === "parler") a.duree = a.duree || dureeReplique(a.texte || "");
      // Une seule copie (la premiere) signale ses bruitages : les autres jouent la meme action.
      let d = 0;
      Object.values(o.copies).forEach((c, i) => {
        Dessin.sons.muet = i > 0; ctx.copie = i;
        d = Math.max(d, fn(tl, c.it, a, ctx) || 0);
      });
      Dessin.sons.muet = false; ctx.copie = 0;
      if (a.action === "parler" && a.texte) repliques.push({ a, it: o.copies[""].it, x: o.copies[""].it._x, ech: ech * (o.def.echelle ?? 1) });
      const finRel = tRel + d;
      if (!a.avec) curseur = finRel + ECART; else curseur = Math.max(curseur, finRel + ECART);
      prec = { t: tRel, fin: finRel };
      fin = Math.max(fin, finRel);
    }
    const duree = sc.duree ?? fin + 1.0;

    // Vie (respiration, clignements...), bouillonnement, apparition dessinee.
    let k = 0;
    for (const o of Object.values(objets))
      for (const c of Object.values(o.copies)) if (o.type.vie) o.type.vie(tl, c.it, S, S + duree, (k++ % 3) * 0.45);
    if (fondType.vie) fondType.vie(tl, fond, S, S + duree);
    racines.forEach((r, i) => bouillonner(tl, r, S, S + duree, (i % 3) * 0.05));
    // "dessine": false -> scene complete des la 1re image (1re image d'un reel : elle decide du scroll).
    // Pas de bruit de feutre a l'apparition : il s'entendait a chaque changement de scene.
    if (sc.dessine !== false && !sc.suite) apparition(tl, calque, S + (n ? 0.05 : 0), DESSIN);
    // Scene suivante dans le meme lieu et le meme moment ("suite") : coupe franche, sans fondu.
    if (!dom.derniere) {
      if (dom.coupeApres) tl.set(scene, { opacity: 0 }, S + duree);
      else tl.to(scene, { opacity: 0, duration: FONDU }, S + duree - 0.05);
    }

    // Titre de la scene (manuscrit, en haut).
    const titre = sc.ellipse ? null : sc.titre ?? (n === 0 ? dom.surtitre : null);
    if (sc.ellipse && dom.titres) carton(tl, sc.ellipse, S, dom.titres);
    if (titre && dom.titres) {
      const t = document.createElement("div");
      t.className = "titre-scene"; t.textContent = frTypo(titre);
      dom.titres.appendChild(t);
      tl.fromTo(t, { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.35, immediateRender: false }, S + 0.1);
      gsap.set(t, { opacity: 0 });
      if (!dom.derniere) tl.to(t, { opacity: 0, duration: FONDU }, S + duree - 0.05);
    }
    // Bulles : au-dessus de la tete de celui qui parle, du cote ou il se trouve. Une bulle
    // s'efface au plus tard quand la suivante s'ouvre (repliques enchainees sur la voix).
    repliques.sort((x, y) => x.a.t - y.a.t);
    repliques.forEach((r, i) => {
      const suivante = repliques[i + 1];
      r.fin = Math.min(r.a.t + r.a.duree + 0.12, suivante ? suivante.a.t - 0.02 : Infinity);
    });
    const chevauche = (r, n) => r.a.t < n.t + n.d && r.fin > n.t;
    for (const r of repliques) {
      // Position a l'ecran sous le cadrage de la camera a cet instant.
      const c = cadreA(r.a.t + 0.2);
      r.x = r.x * c.s + c.x;
      const hautTete0 = sol - (r.it.hautTete || 1000) * r.ech - (r.it.assis ? -48 * r.ech : 0);
      r.haut = Math.max(330, hautTete0 * c.s + c.y);
      const b = document.createElement("div"), gauche = r.x < 540;
      b.className = "bulle " + (gauche ? "g" : "d");
      b.innerHTML = '<span class="nom"></span><span class="t"></span>';
      b.querySelector(".nom").textContent = r.it.nom || "";
      b.querySelector(".t").textContent = frTypo(r.a.texte);
      r.etroite = nuages.some((n) => chevauche(r, n));
      if (r.etroite) b.style.maxWidth = `${BULLE_ETROITE}px`;
      b.style.bottom = `${Math.round(1920 - r.haut + 36)}px`;
      if (gauche) b.style.left = `${Math.max(40, Math.round(r.x - 240))}px`; else b.style.right = `${Math.max(40, Math.round(1080 - r.x - 240))}px`;
      dom.bulles.appendChild(b);
      const rect = b.getBoundingClientRect();
      b.style.setProperty("--queue", `${Math.min(Math.max(r.x - rect.left - 22, 30), rect.width - 80)}px`);
      r.gauche = gauche;
      gsap.set(b, { opacity: 0, scale: 0.4, transformOrigin: `${r.x - rect.left}px 120%` });
      tl.to(b, { opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)" }, r.a.t)
        .to(b, { opacity: 0, scale: 0.85, duration: 0.15 }, r.fin);
    }
    // Nuages : du cote oppose aux bulles ouvertes pendant ce temps (sinon pres de celui qui pense).
    for (const n of nuages) {
      const cotes = new Set(repliques.filter((r) => chevauche(r, n)).map((r) => r.gauche));
      const cx = cotes.size === 1 ? (cotes.has(true) ? 1080 - 215 : 215) : Math.min(865, Math.max(215, n.x));
      n.dessiner(cx);
    }
    return duree;
  }

  window.Scene = { monter, dureeReplique };
})();
