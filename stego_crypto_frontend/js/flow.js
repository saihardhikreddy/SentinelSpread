/* GNU Radio transmission animation: a stage strip plus a live scope.
   The stage lights follow the real request (they advance while the flowgraph runs and snap to the
   end when it answers); the scope draws what each stage does to the signal:

     transmit   Message → Encrypt → Spread → Shape → Channel
     receive    Match → Sync → Costas → Despread → Decrypt

   Top trace: the waveform (bits, then chips, then pulse-shaped, then noisy, then clean again).
   Bottom: the BPSK constellation: tight clusters, smeared by channel noise, rotated by carrier
   drift until the Costas loop locks, or left smeared when it can't. */

import { SF_OPTIONS } from "./radio.js?v=20261002b";

const STAGES = {
  tx: [["Message", "plaintext"], ["Encrypt", "AES-GCM"], ["Spread", "DSSS"], ["Shape", "RRC"], ["Channel", "AWGN"]],
  rx: [["Match", "RRC"], ["Sync", "M&M"], ["Costas", "carrier"], ["Despread", "PN"], ["Decrypt", "AES-GCM"]],
};
const CAPTIONS = {
  tx: ["Reading the message…", "Sealing it with AES-256-GCM and wrapping the key with RSA-OAEP…", "Multiplying every bit by a PN code, SF× faster…", "Shaping each chip with a root-raised-cosine pulse…", "Passing it through noise and a carrier offset…"],
  rx: ["Matched filter: lining the pulses up…", "Symbol timing recovery (Mueller & Müller)…", "Costas loop pulling the carrier phase into lock…", "Despreading with the same PN code…", "Authenticated decryption: every bit must be intact…"],
};

const rand = (() => { let s = 1234567; return () => ((s = (s * 16807) % 2147483647) / 2147483647); })();
const gauss = () => Math.sqrt(-2 * Math.log(rand() + 1e-9)) * Math.cos(2 * Math.PI * rand());

export function createFlow({ phase = "tx", sf = 16, sigma = 0.02 } = {}) {
  const sfIdx = Math.max(0, SF_OPTIONS.indexOf(sf));
  const el = document.createElement("div");
  el.className = "flow";
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", phase === "tx" ? "Animated transmit pipeline" : "Animated receive pipeline");

  const list = document.createElement("ol");
  list.className = "flow-stages";
  const nodes = STAGES[phase].map(([name, sub]) => {
    const li = document.createElement("li");
    li.dataset.state = "idle";
    const dot = document.createElement("i");
    const label = document.createElement("span");
    label.textContent = name;
    const small = document.createElement("small");
    small.textContent = sub === "DSSS" ? `SF ${sf}` : sub;
    li.append(dot, label, small);
    list.append(li);
    return li;
  });
  const canvas = document.createElement("canvas");
  canvas.className = "flow-scope";
  const caption = document.createElement("p");
  caption.className = "flow-caption";
  caption.setAttribute("aria-live", "polite");
  el.append(list, canvas, caption);

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const snr = sigma > 0 ? 10 * Math.log10(0.25 / (sigma * sigma)) : 40;
  // constellation scatter: chip-level SNR drives how smeared the clusters are
  const scatter = Math.min(0.9, sigma * 1.6);

  let stage = 0, state = "run", ok = true, raf = 0, t0 = performance.now(), lastAdvance = performance.now(), lockT = 0;
  const bits = Array.from({ length: 64 }, () => (rand() > 0.5 ? 1 : -1));
  const pts = Array.from({ length: 120 }, (_, i) => ({ s: bits[i % 64], n: [gauss(), gauss()] }));

  function paint() {
    nodes.forEach((n, i) => {
      n.dataset.state = state === "fail" && i === stage ? "fail" : i < stage || state === "done" ? "done" : i === stage ? "active" : "idle";
    });
    list.style.setProperty("--p", String(state === "done" ? 1 : stage / (nodes.length - 1)));
    caption.textContent = state === "done" ? (phase === "tx" ? "On the air." : "Recovered.") : state === "fail" ? "Lost lock: the message could not be recovered." : (CAPTIONS[phase][stage] || "").replace("SF×", `${sf}×`);
  }

  // Stages advance on a timer while the request runs; the last one waits for the answer.
  function tick(now) {
    if (state === "run" && stage < nodes.length - 1 && now - lastAdvance > (phase === "tx" ? 420 : 520)) {
      stage++;
      lastAdvance = now;
      paint();
    }
  }

  function draw(now) {
    if (!el.isConnected) return;          // replaced in the result pane: stop drawing
    raf = requestAnimationFrame(draw);
    tick(now);
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return;
    if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const t = reduce ? 0 : (now - t0) / 1000;

    // ── top: waveform ──
    const wh = h * 0.5;
    g.strokeStyle = "rgba(255,255,255,0.08)";
    g.beginPath(); g.moveTo(0, wh / 2); g.lineTo(w, wh / 2); g.stroke();
    const chipRate = phase === "tx" ? (stage >= 2 ? 6 + sfIdx * 3 : 1.4) : (stage >= 3 ? 1.4 : 6 + sfIdx * 3);
    const shaped = phase === "tx" ? stage >= 3 : stage < 3;
    const noisy = phase === "tx" ? stage >= 4 : stage < 4;
    const clean = state === "done";
    const amp = (phase === "tx" && stage >= 2) || (phase === "rx" && stage < 3) ? 0.55 : 0.8;
    g.beginPath();
    for (let x = 0; x <= w; x += 2) {
      const u = x / w * 9 + t * 2.2;
      const k = Math.floor(u * chipRate / 4);
      let v = bits[((k % 64) + 64) % 64];
      if (shaped) { const k2 = Math.floor((u + 0.5 / chipRate) * chipRate / 4); v = (v + bits[((k2 % 64) + 64) % 64]) / 2 * 1.1 + 0.25 * Math.sin(u * chipRate * 0.8) * 0.3; }
      if (noisy && !clean) v += gauss() * Math.min(1.1, sigma * 2.4);
      const y = wh / 2 - v * amp * (wh / 2 - 6);
      x === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.strokeStyle = state === "fail" ? "rgba(255,122,102,0.9)" : "rgba(142,203,255,0.95)";
    g.lineWidth = 1.5;
    g.shadowColor = "rgba(142,203,255,0.7)"; g.shadowBlur = 8;
    g.stroke();
    g.shadowBlur = 0;

    // ── bottom: constellation ──
    const cx = w / 2, cy = h * 0.75, r = h * 0.17;
    g.strokeStyle = "rgba(255,255,255,0.1)";
    g.beginPath(); g.moveTo(cx - r * 2.4, cy); g.lineTo(cx + r * 2.4, cy); g.moveTo(cx, cy - r * 1.4); g.lineTo(cx, cy + r * 1.4); g.stroke();
    const rxStage = phase === "rx" ? stage : 99;
    const noiseNow = phase === "tx" ? (stage >= 4 ? scatter : 0.04) : scatter;
    // carrier drift rotates the cloud until Costas locks (rx stage >= 2 and success)
    if (phase === "rx" && state === "run" && rxStage >= 2) lockT = Math.min(1, lockT + 0.012);
    if (state === "done") lockT = 1;
    const drift = phase === "tx" ? (stage >= 4 ? 0.6 * Math.sin(t * 1.1) : 0) : state === "fail" ? t * 1.3 : (1 - lockT) * (0.9 + 0.5 * Math.sin(t * 1.5)) + (rxStage < 2 ? 0.2 * t % 6.283 : 0);
    const smear = state === "fail" ? Math.max(noiseNow, 0.7) : phase === "rx" && rxStage >= 3 ? noiseNow * 0.45 : noiseNow;
    g.fillStyle = state === "fail" ? "rgba(255,122,102,0.8)" : "rgba(180,225,255,0.9)";
    for (const p of pts) {
      let x = p.s + p.n[0] * smear * 0.6, y = p.n[1] * smear * 0.6;
      const c = Math.cos(drift), s = Math.sin(drift);
      [x, y] = [x * c - y * s, x * s + y * c];
      g.globalAlpha = 0.55;
      g.beginPath(); g.arc(cx + x * r * 1.5, cy + y * r * 1.5, 2, 0, 6.283); g.fill();
    }
    g.globalAlpha = 1;
    g.fillStyle = "rgba(255,255,255,0.45)";
    g.font = "500 9.5px 'Geist Mono', ui-monospace, monospace";
    g.fillText(`${Number.isFinite(snr) ? snr.toFixed(1) : "∞"} dB per sample`, 10, h - 8);
    g.textAlign = "right";
    g.fillText(phase === "tx" ? "I/Q after channel" : lockT >= 1 ? "locked" : "unlocked", w - 10, h - 8);
    g.textAlign = "left";
  }

  paint();
  raf = requestAnimationFrame(draw);

  return {
    el,
    /** The request answered: jump to the final state. */
    finish(success = true) {
      ok = success;
      stage = nodes.length - 1;
      state = success ? "done" : "fail";
      paint();
    },
    destroy() { cancelAnimationFrame(raf); el.remove(); },
    get ok() { return ok; },
  };
}
