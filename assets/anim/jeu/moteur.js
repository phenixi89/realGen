// Moteur du jeu : monte une scene (niveau, personnages, boss, repliques, evenements) en une fonction rendre(t) qui
// dessine l'image EXACTE a l'instant t (sans etat cache). Format d'une scene (JSON, parametre ?plan=) :
//   { niveau, boss ("" ou id), quete, etat: {coeurs, xp, niv, bossPv}, duree,
//     repliques: [{qui: "martin"|"lea", texte, t, duree}],
//     evenements: [{t, type, ...}] }
// Evenements (valeurs absolues, calculees a l'ecriture par 1_generate_script.py) :
//   apparition {}                   le boss entre (invisible avant)
//   objet {nom}                     fenetre « OBJET OBTENU ! »
//   degats {de, vers}               Martin attaque, le boss perd des points de vie (bossPv de -> vers)
//   blessure {de, vers}             le boss attaque, Martin perd un coeur (coeurs de -> vers)
//   xp {de, vers}                   la barre d'experience monte
//   niveau {vers}                   « NIVEAU n ! », la barre repart de zero
//   victoire {}                     le boss est vaincu, Martin saute de joie
(() => {
  const { R, texte, boite, coupe, hasard, lerp, facile, x, W, H, SOL } = Jeu;
  const NOMS = { martin: "MARTIN", lea: "LÉA" }, COUL = { martin: "#7fe3d6", lea: "#ff9b8f" };
  const BOSS_NOM = { robot_trieur: "LE ROBOT TRIEUR", fantome: "LE FANTÔME", paperasse: "LA PAPERASSE" };

  Jeu.monter = (plan) => {
    const typo = (s) => String(s).replace(/ +([?!:;»])/g, "\u00a0$1").replace(/« +/g, "«\u00a0");
    const duree = Math.max(plan.duree || 6, 2), reps = (plan.repliques || []).map((r) => Object.assign({}, r, { texte: typo(r.texte) })).sort((a, b) => a.t - b.t);
    const evs = (plan.evenements || []).slice().sort((a, b) => a.t - b.t), e0 = Object.assign({ coeurs: 3, xp: 0, niv: 1, bossPv: 100 }, plan.etat || {});
    const niveau = Jeu.niveau(plan.niveau), boss = plan.boss || "";
    const apparition = evs.find((e) => e.type === "apparition"), victoire = evs.find((e) => e.type === "victoire");
    const sons = [];
    reps.forEach((r) => sons.push({ t: r.t, name: "blip", gain: 0.7 }));
    const SON = { apparition: "boss", objet: "objet", degats: "degats", blessure: "blessure", niveau: "niveau", victoire: "victoire" };
    evs.forEach((e) => {
      if (e.type === "degats") sons.push({ t: e.t, name: "coup" }, { t: e.t + 0.25, name: "degats" });
      else if (e.type === "blessure") sons.push({ t: e.t + 0.25, name: "blessure" });
      else if (SON[e.type]) sons.push({ t: e.t, name: SON[e.type] });
    });

    // Etat du HUD a l'instant t : les valeurs bougent en douceur apres chaque evenement.
    const etat = (t) => {
      const s = { coeurs: e0.coeurs, xp: e0.xp, niv: e0.niv, bossPv: e0.bossPv, perdu: -1 };
      for (const e of evs) {
        if (e.t > t) break;
        const u = (t - e.t);
        if (e.type === "degats") s.bossPv = lerp(e.de, e.vers, (u - 0.25) / 0.4);
        else if (e.type === "blessure") { s.coeurs = u >= 0.25 ? e.vers : e.de; if (u >= 0.25 && u < 0.6) s.perdu = e.vers; }
        else if (e.type === "xp") s.xp = lerp(e.de, e.vers, u / 0.6);
        else if (e.type === "niveau") { s.niv = u >= 0.5 ? e.vers : e.vers - 1; s.xp = u < 0.5 ? lerp(e.xp_de, 100, u / 0.5) : u < 1.0 ? 100 : lerp(100, 0, (u - 1.0) / 0.5); }
        else if (e.type === "victoire") s.bossPv = 0;
      }
      return s;
    };
    const dans = (type, t, fenetre) => evs.filter((e) => e.type === type && t >= e.t && t < e.t + fenetre);
    const replique = (t) => { let cur = null; for (const r of reps) if (r.t <= t) cur = r; return cur; };

    function rendre(t) {
      const S = etat(t), r = replique(t), parle = r && t < r.t + r.duree ? r.qui : "";
      // Secousse de l'ecran : coup porte ou recu.
      let sx = 0, sy = 0;
      for (const e of evs) if ((e.type === "degats" || e.type === "blessure") && t >= e.t + 0.25 && t < e.t + 0.5) { sx = ((Math.floor(t * 40) % 2) * 2 - 1) * 2; sy = ((Math.floor(t * 31) % 2) * 2 - 1); }
      x.setTransform(1, 0, 0, 1, 0, 0); x.fillStyle = "#000"; x.fillRect(0, 0, W, H);
      x.save(); x.translate(sx, sy);
      x.drawImage(niveau.image, 0, 0); niveau.anime(t);

      // --- boss
      const att = dans("blessure", t, 0.5)[0], hit = dans("degats", t, 0.5)[0];
      let bossVisible = !!boss;
      let bx = 168, by = SOL - 96 + Math.round(Math.sin(t * 3));
      if (apparition) {
        if (t < apparition.t) bossVisible = false; else bx += Math.round((1 - facile((t - apparition.t) / 0.9)) * 120);
      }
      let mort = 0;
      if (victoire && t >= victoire.t) mort = (t - victoire.t);
      if (att) bx -= Math.round(Math.sin(((t - att.t) / 0.5) * Math.PI) * 26);
      if (bossVisible && (!victoire || t < victoire.t + 1.2)) {
        const blanc = (hit && t >= hit.t + 0.25 && t < hit.t + 0.45) || (mort > 0 && Math.floor(mort * 14) % 2 === 0);
        Jeu.boss(boss, bx, by, { t, flash: blanc, regard: 1 });
      }
      if (mort > 0.6 && mort < 1.6) {       // explosion de particules
        const h = hasard(9);
        for (let i = 0; i < 26; i++) { const a = h() * 6.28, v = 30 + h() * 60, u = mort - 0.6; R(i % 3 ? "#ffd84d" : "#ff6b35", bx + 48 + Math.cos(a) * v * u, by + 48 + Math.sin(a) * v * u + 40 * u * u, 4, 4); }
      }

      // --- personnages
      const marche = apparition && t < apparition.t + 0.9 ? 1 : 0;
      let mx = 62, mp = { regard: 1, bouche: parle === "martin" && Math.floor(t * 8) % 2 === 0, jambes: marche ? 1 + (Math.floor(t * 8) % 2) : 0 };
      let my = SOL - 96 - (Math.floor(t * 2) % 2);
      const atq = dans("degats", t, 0.5)[0];
      if (atq) { const u = (t - atq.t) / 0.5; mx += Math.round(Math.sin(Math.min(u * 1.4, 1) * Math.PI) * 66); mp.bras = "avant"; }
      const bl = dans("blessure", t, 0.7)[0];
      if (bl && t >= bl.t + 0.25) { mp.flash = Math.floor(t * 16) % 2 === 0; mx -= Math.round(Math.sin(Math.min((t - bl.t - 0.25) / 0.4, 1) * Math.PI) * 10); }
      if (victoire && t >= victoire.t + 0.4) { mp.bras = "haut"; my -= Math.round(Math.abs(Math.sin((t - victoire.t) * 5)) * 14); }
      Jeu.martin(mx, my, mp);
      const lp = { regard: 1, bouche: parle === "lea" && Math.floor(t * 8) % 2 === 0, bras: parle === "lea" && r && /[:«]/.test(r.texte) ? "pointe" : "bas" };
      if (victoire && t >= victoire.t + 0.4) lp.bras = "haut";
      Jeu.lea(6, SOL - 96 - (Math.floor(t * 2 + 1) % 2), lp);
      if (atq) {       // eclat de l'attaque
        const u = (t - atq.t) / 0.5;
        if (u > 0.25 && u < 0.6) { for (let i = 0; i < 4; i++) R("#fffbe0", 128 + 18 * i + Math.round(u * 20), SOL - 60 - 12 * i + (i % 2) * 14, 8, 4); }
      }
      x.restore();

      // --- HUD
      boite(6, 50, 258, 40);
      R("#e8b08a", 12, 56, 24, 24); R("#23233a", 12, 56, 24, 8); R("#111", 15, 66, 8, 5); R("#111", 25, 66, 8, 5); R("#cfe8ff", 16, 67, 6, 3); R("#cfe8ff", 26, 67, 6, 3);
      texte("MARTIN", 42, 68, "#fff"); texte("NIV " + S.niv, 42, 82, "#ffd84d");
      for (let i = 0; i < 3; i++) Jeu.coeur(150 + i * 14, 56, i < S.coeurs, S.perdu === i);
      texte("XP", 148, 85, "#9bd1ff"); R("#ffffff", 168, 77, 88, 9); R("#22304a", 169, 78, 86, 7); R("#4cd964", 169, 78, Math.round(86 * Math.min(S.xp, 100) / 100), 7); R("#9bf0a3", 169, 78, Math.round(86 * Math.min(S.xp, 100) / 100), 2);
      boite(6, 96, 258, 22, "#241848"); texte("QUÊTE", 12, 111, "#ffd84d"); texte((plan.quete || "").slice(0, 25), 58, 111, "#fff");
      if (boss && bossVisible && (!victoire || t < victoire.t + 1.2)) {       // barre de vie du boss
        boite(6, 122, 258, 28, "#2a0f1a"); texte(BOSS_NOM[boss] || "LE BOSS", 12, 135, "#ff8f8f");
        R("#ffffff", 12, 139, 246, 7); R("#33141f", 13, 140, 244, 5); R("#ff4d4d", 13, 140, Math.round(244 * Math.max(S.bossPv, 0) / 100), 5); R("#ff9b9b", 13, 140, Math.round(244 * Math.max(S.bossPv, 0) / 100), 1);
      }

      // --- boite de dialogue
      if (r) {
        boite(6, 304, 258, 78);
        const q = r.qui, nom = NOMS[q] || q.toUpperCase();
        if (q === "lea") { R("#e8b08a", 12, 312, 22, 22); R("#7a3a1e", 12, 312, 22, 8); R("#1a1a2e", 17, 321, 3, 5); R("#1a1a2e", 26, 321, 3, 5); R("#ff6b5a", 32, 314, 5, 5); }
        else { R("#e8b08a", 12, 312, 22, 22); R("#23233a", 12, 312, 22, 8); R("#111", 15, 321, 8, 5); R("#111", 25, 321, 8, 5); R("#cfe8ff", 16, 322, 6, 3); R("#cfe8ff", 26, 322, 6, 3); }
        texte(nom, 42, 326, COUL[q] || "#fff");
        const n = Math.floor(Math.min(1, (t - r.t) / Math.max(r.duree * 0.7, 0.4)) * r.texte.length);
        coupe(r.texte, 238).forEach((l, i) => { const deja = coupe(r.texte, 238).slice(0, i).join(" ").length + (i ? 1 : 0); texte(l.slice(0, Math.max(0, n - deja)), 12, 352 + i * 12, "#fff"); });
        if (n >= r.texte.length && Math.floor(t * 3) % 2 === 0) { R("#fff", 246, 372, 8, 3); R("#fff", 248, 375, 4, 2); }
      }

      // --- fenetres d'evenements
      for (const e of evs) {
        const u = t - e.t;
        if (e.type === "objet" && u >= 0 && u < 2.2) {
          const y = 146 - Math.round((1 - facile(u / 0.3)) * 16);
          boite(24, y, 222, 40, "#10331f", "#4cd964"); texte("OBJET OBTENU !", 74, y + 16, "#4cd964");
          Jeu.parchemin(34, y + 9); texte((e.nom || "").slice(0, 19), 74, y + 32, "#fff");
        }
        if (e.type === "niveau" && u >= 0.2 && u < 2.0) {
          const y = 122; boite(30, y, 210, 34, "#3a2a00", "#ffd84d"); texte("NIVEAU " + e.vers + " !", 55, y + 24, "#ffd84d", 16);   // a la place de la barre du boss, deja vaincu
          Jeu.etoile(38, y + 13); Jeu.etoile(224, y + 13);
        }
        if (e.type === "apparition" && u >= 0 && u < 1.6) {
          if (Math.floor(u * 6) % 2 === 0) { boite(35, 154, 200, 30, "#3a0a0a", "#ff4d4d"); texte("UN BOSS APPARAÎT !", 63, 174, "#ff9b9b"); }
        }
        if (e.type === "victoire" && u >= 0.5 && u < 2.1) {
          boite(40, 152, 190, 34, "#3a2a00", "#ffd84d"); texte("VICTOIRE !", 55, 176, "#ffd84d", 16);
        }
      }
      // Lignes de balayage : leger effet d'ecran cathodique.
      x.fillStyle = "rgba(0,0,0,0.07)"; for (let yy = 0; yy < H; yy += 2) x.fillRect(0, yy, W, 1);
    }
    return { rendre, duree, sons };
  };
})();
