// Niveaux du jeu : un decor fixe (dessine une fois sur un calque) + quelques elements animes (nuages, torches,
// lucioles). Sol des personnages : y = SOL. Les ids sont declares dans catalog/jeu.json (verifies par catalog.py).
(() => {
  const { R, hasard, calque, vers, x } = Jeu, SOL = 284, W = 270, H = 480;
  Jeu.SOL = SOL;

  const ciel = (couleurs, haut = 0, bas = SOL) => {
    const n = couleurs.length, pas = Math.ceil((bas - haut) / n);
    couleurs.forEach((c, i) => R(c, 0, haut + i * pas, W, pas + 1));
  };
  const sol = (herbe, herbeClair, terre, briqueA, briqueB) => {
    R(herbe, 0, SOL, W, 8); R(herbeClair, 0, SOL, W, 2); R(terre, 0, SOL + 8, W, H - SOL - 8); R("#00000033", 0, SOL + 8, W, 2);
    for (let j = 0; j < 14; j++) for (let i = 0; i < 18; i++) R((i + j) % 2 ? briqueA : briqueB, i * 16 - (j % 2) * 8, SOL + 14 + j * 16, 15, 7);
  };
  const montagnes = (col, base, amp, ph, freq = 33) => {
    for (let i = 0; i < W; i++) { const h = Math.floor(base - amp * (Math.abs(Math.sin((i + ph) / freq)) * 0.7 + Math.abs(Math.sin((i + ph) / (freq * 0.4))) * 0.3)); R(col, i, h, 1, SOL - h); }
  };
  const tour = (cx, cy, col, clair, fen) => {
    R(col, cx, cy + 22, 70, 70); R(clair, cx + 2, cy + 24, 66, 68);
    for (let i = 0; i < 5; i++) R(col, cx + i * 15, cy + 14, 8, 10);
    R(col, cx - 10, cy - 6, 22, 98); R(col, cx + 58, cy - 12, 22, 104);
    for (const [tx, ty] of [[cx - 10, cy - 6], [cx + 58, cy - 12]]) for (let i = 0; i < 3; i++) R(col, tx + i * 9, ty - 6, 6, 8);
    R(fen, cx + 1, cy + 8, 4, 8); R(fen, cx + 67, cy + 2, 4, 8); R(fen, cx + 22, cy + 40, 6, 10); R(fen, cx + 42, cy + 40, 6, 10);
    R("#120a1e", cx + 27, cy + 66, 16, 26); R("#120a1e", cx + 30, cy + 60, 10, 8);
  };

  const N = {};
  const def = (id, o) => (N[id] = o);

  def("plaine", {
    fond() {
      ciel(["#5bb8ff", "#7ac8ff", "#9ad6ff", "#b9e4ff", "#d3efff", "#ecf8ff"]);
      R("#fff7c2", 196, 40, 24, 24); R("#fffbe0", 200, 44, 16, 16);
      montagnes("#8fb6e8", 250, 70, 20); montagnes("#6f9bd6", 262, 52, 90, 27);
      for (const [a, b] of [[20, 232], [120, 238], [220, 230]]) { R("#2f8f3c", a, b, 30, 40); R("#3fae4c", a + 4, b - 6, 22, 10); R("#2f8f3c", a + 8, b - 12, 14, 8); R("#6e4426", a + 13, b + 28, 5, 12); }
      sol("#4caf50", "#7bd35c", "#8a5a34", "#7a4d2c", "#935f38");
    },
    anime(t) {
      for (let i = 0; i < 3; i++) { const cx = ((i * 110 + t * (4 + i * 2)) % 340) - 40, cy = 140 + i * 24; R("#ffffff", cx, cy, 30, 8); R("#ffffff", cx + 6, cy - 5, 18, 7); R("#dff0ff", cx, cy + 6, 30, 2); }
    },
  });

  def("foret", {
    fond() {
      ciel(["#2b1b52", "#4a2468", "#7a3374", "#b0476a", "#e0705a", "#f5a45f"]);
      R("#ffd98a", 40, 150, 26, 26);
      const h = hasard(11);
      for (let i = 0; i < 9; i++) { const a = i * 32 - 10, hh = 70 + Math.floor(h() * 40); R("#2a1747", a + 10, SOL - hh, 4, hh); for (let k = 0; k < 5; k++) R("#2a1747", a + 2 - k * 0, SOL - hh + k * 12, 20 + k * 2, 11); }
      for (let i = 0; i < 7; i++) { const a = i * 44 + 8, hh = 90 + Math.floor(h() * 50); R("#1a0f33", a + 12, SOL - hh, 6, hh); for (let k = 0; k < 6; k++) R("#150b2a", a - 2 + k, SOL - hh + k * 14, 28 - k * 0 + k * 2, 13); }
      sol("#1f5a34", "#2f7a46", "#4a3322", "#3d2a1c", "#4d3523");
    },
    anime(t) {
      const h = hasard(5);
      for (let i = 0; i < 16; i++) { const fx = h() * W, fy = 130 + h() * 140, ph = h() * 6, vis = (Math.sin(t * 2 + ph) + 1) / 2; if (vis > 0.35) R(vis > 0.8 ? "#fff6a8" : "#c6e86b", fx + Math.sin(t + ph) * 6, fy + Math.cos(t * 0.8 + ph) * 5, 2, 2); }
    },
  });

  def("donjon", {
    fond() {
      R("#241a38", 0, 0, W, SOL);
      for (let j = 0; j < 20; j++) for (let i = 0; i < 12; i++) { R((i + j) % 2 ? "#2d2246" : "#33274f", i * 24 - (j % 2) * 12, j * 14, 23, 13); }
      R("#120a22", 90, 90, 90, 180); R("#120a22", 99, 76, 72, 20); R("#120a22", 108, 64, 54, 16);     // arche sombre
      R("#3d2f5e", 84, 90, 6, 180); R("#3d2f5e", 180, 90, 6, 180);
      sol("#3a3550", "#524c70", "#2a2540", "#312c48", "#3a3552");
    },
    anime(t) {
      for (const tx of [40, 218]) {
        R("#6e4426", tx, 150, 4, 28); R("#3a2410", tx - 2, 148, 8, 3);
        const f = Math.floor(t * 8 + tx) % 3; R("#ff8c1a", tx - 1, 138 - f, 6, 10 + f); R("#ffd84d", tx, 142 - f, 4, 6); R("#fff3b0", tx + 1, 145, 2, 3);
        R("#ff8c1a22", tx - 14, 126, 32, 40);
      }
    },
  });

  def("ville", {
    fond() {
      ciel(["#7ec3ff", "#9ed2ff", "#bfe0ff", "#dff0ff", "#f5e8d0"]);
      const h = hasard(21), cols = ["#c0805a", "#a8678a", "#6a8bbd", "#d0a050", "#7aa56a"];
      for (let i = 0; i < 6; i++) {
        const a = i * 46 - 8, hh = 90 + Math.floor(h() * 70), c = cols[i % cols.length];
        R("#00000040", a + 3, SOL - hh + 3, 44, hh); R(c, a, SOL - hh, 44, hh); R("#3a2a30", a - 2, SOL - hh - 8, 48, 10);
        for (let wy = 0; wy < 3; wy++) for (let wx = 0; wx < 2; wx++) { R("#ffe9a0", a + 7 + wx * 18, SOL - hh + 12 + wy * 22, 9, 12); R("#2a2a3e", a + 7 + wx * 18, SOL - hh + 12 + wy * 22 + 6, 9, 1); }
      }
      sol("#8a8a98", "#b5b5c4", "#5e5e72", "#6a6a80", "#757590");
    },
    anime(t) {
      for (let i = 0; i < 2; i++) { const cx = ((i * 150 + t * 6) % 320) - 40; R("#ffffff", cx, 60 + i * 30, 26, 7); R("#ffffff", cx + 5, 55 + i * 30, 14, 6); }
    },
  });

  def("chateau", {
    fond() {
      R("#1a0f2a", 0, 0, W, SOL);
      for (let j = 0; j < 20; j++) for (let i = 0; i < 12; i++) R((i + j) % 2 ? "#241638" : "#2b1b42", i * 24 - (j % 2) * 12, j * 14, 23, 13);
      for (const px of [10, 86, 162, 238]) { R("#3a2a5a", px, 60, 22, 210); R("#4a3770", px, 60, 6, 210); R("#3a2a5a", px - 4, 56, 30, 8); R("#3a2a5a", px - 4, 262, 30, 8); }
      R("#2a4a8a", 108, 70, 54, 100); R("#4a7ad0", 112, 74, 20, 44); R("#d04a4a", 136, 74, 22, 44); R("#d0b04a", 112, 122, 46, 44); R("#1a0f2a", 134, 70, 2, 100);   // vitrail
      sol("#5a1a2a", "#8a2a3a", "#3a1020", "#4a1528", "#561a30");
    },
    anime(t) {
      for (const tx of [40, 126, 212]) { const f = Math.floor(t * 8 + tx) % 3; R("#6e4426", tx, 190, 4, 24); R("#ff8c1a", tx - 1, 178 - f, 6, 12 + f); R("#ffd84d", tx, 182 - f, 4, 6); }
    },
  });

  // Decor mis en cache sur un calque (le trace des briques coute cher a chaque image).
  const cache = {};
  Jeu.niveau = (id) => {
    const n = N[id] || N.plaine;
    if (!cache[id]) { const [c, k] = calque(); vers(k); n.fond(); vers(x); cache[id] = c; }
    return { image: cache[id], anime: n.anime };
  };
  Jeu.NIVEAUX = Object.keys(N);
})();
