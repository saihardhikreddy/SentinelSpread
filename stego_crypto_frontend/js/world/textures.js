/* Runtime-drawn textures (no image assets). Seeded so every load looks identical. */

import * as THREE from "three";

export function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvas(w, h) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  return [c, c.getContext("2d")];
}

/** Soft radial glow, white; tint with the material colour. */
export function glowTexture(size = 256, falloff = [[0, 1], [0.18, 0.55], [0.45, 0.12], [1, 0]]) {
  const [c, x] = canvas(size, size);
  const g = x.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  falloff.forEach(([s, a]) => g.addColorStop(s, `rgba(255,255,255,${a})`));
  x.fillStyle = g;
  x.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Horizontal anamorphic streak. */
export function streakTexture() {
  const [c, x] = canvas(512, 32);
  const g = x.createLinearGradient(0, 0, 512, 0);
  g.addColorStop(0, "rgba(255,255,255,0)");
  g.addColorStop(0.5, "rgba(255,255,255,1)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 512, 32);
  const v = x.getImageData(0, 0, 512, 32);
  for (let y = 0; y < 32; y++) {
    const k = Math.exp(-((y - 15.5) ** 2) / 18);
    for (let i = 0; i < 512; i++) v.data[(y * 512 + i) * 4 + 3] *= k;
  }
  x.putImageData(v, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** A strip of ciphertext glyphs that wraps around the cipher gate. */
export function glyphTexture() {
  const [c, x] = canvas(2048, 128);
  const rnd = mulberry32(4211);
  x.fillStyle = "#000";
  x.fillRect(0, 0, 2048, 128);
  x.font = "500 44px 'IBM Plex Mono', Consolas, monospace";
  x.textBaseline = "middle";
  const hex = "0123456789ABCDEF";
  let px = 8;
  while (px < 2040) {
    const word = Array.from({ length: 2 }, () => hex[(rnd() * 16) | 0]).join("");
    const a = 0.35 + rnd() * 0.65;
    x.fillStyle = `rgba(255,255,255,${a})`;
    x.fillText(word, px, 66);
    px += 74;
  }
  x.fillStyle = "rgba(255,255,255,0.5)";
  x.fillRect(0, 10, 2048, 2);
  x.fillRect(0, 116, 2048, 2);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Solar array: cells in a grid with silver busbars and interconnect gaps. */
export function solarTexture() {
  const W = 512, H = 512, cols = 8, rows = 8;
  const [c, x] = canvas(W, H);
  x.fillStyle = "#8a8f96";
  x.fillRect(0, 0, W, H);
  const cw = W / cols, ch = H / rows, rnd = mulberry32(12);
  for (let r = 0; r < rows; r++) for (let q = 0; q < cols; q++) {
    const g = x.createLinearGradient(q * cw, r * ch, (q + 1) * cw, (r + 1) * ch);
    const tint = 0.9 + rnd() * 0.2;
    g.addColorStop(0, `rgb(${18 * tint},${26 * tint},${58 * tint})`);
    g.addColorStop(1, `rgb(${10 * tint},${16 * tint},${40 * tint})`);
    x.fillStyle = g;
    x.fillRect(q * cw + 3, r * ch + 3, cw - 6, ch - 6);
    x.fillStyle = "rgba(190,200,215,0.55)";
    for (let k = 1; k < 4; k++) x.fillRect(q * cw + 3, r * ch + (ch * k) / 4, cw - 6, 1);
    x.fillRect(q * cw + cw / 2, r * ch + 3, 1.2, ch - 6);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

/** Crinkled multi-layer insulation: colour + matching bump map. */
export function foilTextures() {
  const S = 512;
  const [c, x] = canvas(S, S);
  const [b, y] = canvas(S, S);
  const rnd = mulberry32(8);
  x.fillStyle = "#b8862c"; x.fillRect(0, 0, S, S);
  y.fillStyle = "#808080"; y.fillRect(0, 0, S, S);
  for (let i = 0; i < 900; i++) {
    const px = rnd() * S, py = rnd() * S, w = 20 + rnd() * 90, h = 8 + rnd() * 40, a = rnd() * Math.PI;
    const light = rnd();
    x.save(); x.translate(px, py); x.rotate(a);
    x.fillStyle = `rgba(${light > 0.5 ? "255,226,150" : "90,55,10"},${0.05 + rnd() * 0.12})`;
    x.beginPath(); x.moveTo(-w / 2, 0); x.lineTo(0, -h / 2); x.lineTo(w / 2, 0); x.lineTo(0, h / 2); x.fill();
    x.restore();
    y.save(); y.translate(px, py); y.rotate(a);
    y.fillStyle = `rgba(${light > 0.5 ? "255,255,255" : "0,0,0"},${0.1 + rnd() * 0.2})`;
    y.beginPath(); y.moveTo(-w / 2, 0); y.lineTo(0, -h / 2); y.lineTo(w / 2, 0); y.lineTo(0, h / 2); y.fill();
    y.restore();
  }
  // blanket seams
  x.strokeStyle = "rgba(60,36,6,0.6)"; y.strokeStyle = "rgba(0,0,0,0.7)";
  x.lineWidth = y.lineWidth = 3;
  for (const v of [S / 3, (2 * S) / 3]) { for (const ctx of [x, y]) { ctx.beginPath(); ctx.moveTo(v, 0); ctx.lineTo(v, S); ctx.stroke(); } }
  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  const bump = new THREE.CanvasTexture(b);
  return { map, bump };
}

/** Mission plate on the bus: the visible watermark the imaging chapter talks about. */
export function plateTexture() {
  const [c, x] = canvas(512, 256);
  x.fillStyle = "#d9d6cf"; x.fillRect(0, 0, 512, 256);
  x.strokeStyle = "#1a1a1a"; x.lineWidth = 3; x.strokeRect(10, 10, 492, 236);
  x.fillStyle = "#151515";
  x.font = "600 64px Onest, 'IBM Plex Sans', sans-serif";
  x.fillText("SENTINEL", 34, 112);
  x.font = "500 22px 'IBM Plex Mono', monospace";
  x.fillText("DSSS · AES-256-GCM · LSB", 36, 160);
  x.fillText("DEEP SPACE RELAY · SF16", 36, 196);
  x.fillStyle = "#4f8fd8"; x.fillRect(420, 40, 56, 56);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** White hull plating: panels, seams, rivet lines, faint wear. Colour + bump. */
export function hullTextures() {
  const S = 1024;
  const [c, x] = canvas(S, S);
  const [b, y] = canvas(S, S);
  const rnd = mulberry32(23);
  x.fillStyle = "#e9eae6"; x.fillRect(0, 0, S, S);
  y.fillStyle = "#808080"; y.fillRect(0, 0, S, S);
  const panels = [];
  const split = (px, py, w, h, depth) => {
    if (depth > 3 || (depth > 1 && rnd() < 0.35)) { panels.push([px, py, w, h]); return; }
    if (w > h) { const k = w * (0.35 + rnd() * 0.3); split(px, py, k, h, depth + 1); split(px + k, py, w - k, h, depth + 1); }
    else { const k = h * (0.35 + rnd() * 0.3); split(px, py, w, k, depth + 1); split(px, py + k, w, h - k, depth + 1); }
  };
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) split(i * 256, j * 256, 256, 256, 0);
  for (const [px, py, w, h] of panels) {
    const t = 228 + rnd() * 18;
    x.fillStyle = `rgb(${t},${t + 1},${t - 2})`;
    x.fillRect(px + 2, py + 2, w - 4, h - 4);
    x.strokeStyle = "rgba(90,96,104,0.55)"; x.lineWidth = 2; x.strokeRect(px + 1, py + 1, w - 2, h - 2);
    y.fillStyle = `rgb(${120 + rnd() * 20},${120},${120})`; y.fillRect(px + 2, py + 2, w - 4, h - 4);
    y.strokeStyle = "rgba(0,0,0,0.9)"; y.lineWidth = 3; y.strokeRect(px + 1, py + 1, w - 2, h - 2);
    if (w > 90 && h > 90 && rnd() < 0.4) {
      x.fillStyle = "rgba(60,66,74,0.35)";
      for (let k = 8; k < w - 8; k += 14) { x.fillRect(px + k, py + 6, 2, 2); x.fillRect(px + k, py + h - 8, 2, 2); }
    }
    if (rnd() < 0.12) { x.fillStyle = "rgba(40,48,58,0.85)"; x.fillRect(px + w * 0.3, py + h * 0.3, w * 0.4, h * 0.12); }
  }
  for (let i = 0; i < 260; i++) {
    x.fillStyle = `rgba(110,104,96,${rnd() * 0.05})`;
    x.beginPath(); x.ellipse(rnd() * S, rnd() * S, 10 + rnd() * 80, 4 + rnd() * 20, rnd() * 3, 0, Math.PI * 2); x.fill();
  }
  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = 8;
  map.wrapS = map.wrapT = THREE.RepeatWrapping;
  const bump = new THREE.CanvasTexture(b);
  bump.wrapS = bump.wrapT = THREE.RepeatWrapping;
  return { map, bump };
}

/** The innocent carrier photograph: dusk sky, ridge lines, a low sun, water. */
export function photoTexture() {
  const W = 640, H = 384;
  const [c, x] = canvas(W, H);
  const rnd = mulberry32(77);
  const sky = x.createLinearGradient(0, 0, 0, H * 0.62);
  sky.addColorStop(0, "#0e1a2a");
  sky.addColorStop(0.55, "#3c3f52");
  sky.addColorStop(1, "#b56a3c");
  x.fillStyle = sky;
  x.fillRect(0, 0, W, H);
  const sun = x.createRadialGradient(W * 0.68, H * 0.56, 2, W * 0.68, H * 0.56, 90);
  sun.addColorStop(0, "rgba(255,214,150,1)");
  sun.addColorStop(0.2, "rgba(255,170,90,0.6)");
  sun.addColorStop(1, "rgba(255,120,60,0)");
  x.fillStyle = sun;
  x.fillRect(0, 0, W, H);
  const ridge = (base, amp, color, seed) => {
    const r = mulberry32(seed);
    x.fillStyle = color;
    x.beginPath();
    x.moveTo(0, H);
    let y = base;
    for (let i = 0; i <= W; i += 8) {
      y += (r() - 0.5) * amp;
      y = Math.min(base + amp * 2, Math.max(base - amp * 3, y));
      x.lineTo(i, y);
    }
    x.lineTo(W, H);
    x.fill();
  };
  ridge(H * 0.5, 14, "#2b2c3a", 3);
  ridge(H * 0.57, 12, "#1c1d27", 9);
  const water = x.createLinearGradient(0, H * 0.64, 0, H);
  water.addColorStop(0, "#3a3242");
  water.addColorStop(1, "#0b0f16");
  x.fillStyle = water;
  x.fillRect(0, H * 0.64, W, H * 0.36);
  for (let i = 0; i < 70; i++) {
    x.fillStyle = `rgba(255,190,120,${0.08 + rnd() * 0.25})`;
    x.fillRect(W * 0.6 + (rnd() - 0.5) * 120, H * 0.66 + rnd() * H * 0.3, 20 + rnd() * 50, 1.5);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.magFilter = THREE.NearestFilter;
  return t;
}
