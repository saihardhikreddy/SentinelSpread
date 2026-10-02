/* Workbench: every <form data-tool> maps to one handler below.
   Results are built with DOM nodes (never innerHTML) so payload text can't inject markup. */

import { postJSON, postForm, fileToDataURL, fileToBase64, ApiError, MSG } from "./api.js?v=20261002b";
import { radioStatus, estimate, snrDb, transmit, receive } from "./radio.js?v=20261002b";
import { createFlow } from "./flow.js?v=20261002b";

/* ─── tiny DOM helpers ─── */

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c != null && c !== false) node.append(c);
  return node;
}

const fmt = (v, digits = 2) => (typeof v === "number" && Number.isFinite(v) ? v.toLocaleString(undefined, { maximumFractionDigits: digits }) : String(v));

function readings(pairs) {
  return h("dl", { class: "readings" }, pairs.filter(Boolean).map(([k, v]) => h("div", {}, h("dt", { text: k }), h("dd", { text: v }))));
}

function verdict(text, good) {
  return h("p", { class: "verdict", "data-good": good == null ? null : String(good), text });
}

function download(href, filename, label = "Download") {
  return h("a", { class: "btn btn--small", href, download: filename }, label);
}

function copyButton(getText, label = "Copy") {
  const btn = h("button", { type: "button", class: "btn btn--small", text: label });
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(getText());
      btn.textContent = "Copied";
    } catch {
      btn.textContent = "Copy failed";
    }
    setTimeout(() => (btn.textContent = label), 1400);
  });
  return btn;
}

function textOut(text, mono = false) {
  return h("div", { class: "out-block" },
    h(mono ? "pre" : "p", { class: mono ? null : "text-out", text }),
    h("div", { class: "result-actions" }, copyButton(() => text, "Copy")));
}

/** Plain-language error, with the library's own wording tucked into a collapsed "Details" line. */
function errorView(err) {
  const message = err?.message || String(err);
  const detail = err instanceof ApiError ? err.raw : err?.detail;
  return [
    h("p", { class: "error", role: "alert", text: message }),
    detail && detail !== message && h("details", { class: "error-details" }, h("summary", { text: "Details" }), h("code", { text: detail })),
  ];
}

const clock = (t) => (Number.isFinite(t) ? `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}` : "–:––");

/** Small glass audio player. A hidden <audio> element underneath is the actual source. */
function player(src, label) {
  const audio = h("audio", { preload: "metadata", src, hidden: true });
  const toggle = h("button", { type: "button", class: "btn btn--small player-toggle", "aria-label": `Play: ${label}` },
    h("span", { class: "player-icon", "aria-hidden": "true" }), h("span", { class: "player-label", text: "Play" }));
  const fill = h("i", { class: "player-fill" });
  const track = h("div", { class: "player-track", role: "slider", tabindex: "0", "aria-label": `Seek: ${label}`, "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": "0" }, fill);
  const time = h("span", { class: "player-time", text: "0:00 / –:––" });
  const el = h("div", { class: "player", "data-state": "paused" }, toggle, track, time, audio);

  const paint = () => {
    const d = audio.duration, t = audio.currentTime, pct = d ? (t / d) * 100 : 0;
    fill.style.width = `${pct}%`;
    track.setAttribute("aria-valuenow", String(Math.round(pct)));
    track.setAttribute("aria-valuetext", `${clock(t)} of ${clock(d)}`);
    time.textContent = `${clock(t)} / ${clock(d)}`;
  };
  const setState = (playing) => {
    el.dataset.state = playing ? "playing" : "paused";
    toggle.querySelector(".player-label").textContent = playing ? "Pause" : "Play";
    toggle.setAttribute("aria-label", `${playing ? "Pause" : "Play"}: ${label}`);
    paint();
  };
  const seek = (frac) => { if (audio.duration) { audio.currentTime = Math.min(1, Math.max(0, frac)) * audio.duration; paint(); } };

  toggle.addEventListener("click", () => (audio.paused ? audio.play().catch(() => {}) : audio.pause()));
  audio.addEventListener("play", () => setState(true));
  audio.addEventListener("pause", () => setState(false));
  audio.addEventListener("ended", () => { setState(false); paint(); });
  audio.addEventListener("timeupdate", paint);
  audio.addEventListener("loadedmetadata", paint);
  track.addEventListener("pointerdown", (e) => {
    const r = track.getBoundingClientRect();
    const move = (ev) => seek((ev.clientX - r.left) / r.width);
    move(e);
    track.setPointerCapture(e.pointerId);
    track.addEventListener("pointermove", move);
    track.addEventListener("pointerup", () => track.removeEventListener("pointermove", move), { once: true });
  });
  track.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 0.05, ArrowUp: 0.05, ArrowLeft: -0.05, ArrowDown: -0.05 }[e.key];
    if (step != null && audio.duration) { e.preventDefault(); seek(audio.currentTime / audio.duration + step); }
    else if (e.key === "Home" || e.key === "End") { e.preventDefault(); seek(e.key === "Home" ? 0 : 1); }
  });
  return el;
}

function show(form, ...nodes) {
  const out = form.querySelector(".result");
  out.replaceChildren(...nodes.flat(Infinity).filter(Boolean));
}

class UserError extends Error {
  constructor(message, detail) { super(message); this.detail = detail; }
}
const need = (value, message) => {
  if (!value || (typeof value === "string" && !value.trim())) throw new UserError(message);
  return value;
};

const pem = (id, what) => need(document.getElementById(id).value.trim(), `Generate or paste a ${what} key in "RSA key pair" first.`);

function psnrGood(m) {
  return m.psnr_db === "inf" || m.psnr_db === Infinity || Number(m.psnr_db) >= 40;
}

function imageMetrics(m) {
  return [
    readings([
      ["PSNR", m.psnr_db === "inf" ? "∞ (identical)" : `${fmt(m.psnr_db)} dB`],
      ["MSE", fmt(m.mse, 6)],
      ["Size", `${m.width} × ${m.height}`],
      ["Channels", String(m.channels)],
    ]),
    verdict(m.quality_verdict, psnrGood(m)),
  ];
}

/* ─── plots ─── */

function plot(series, { height = 150, bars = false } = {}) {
  const canvas = h("canvas", { class: "plot", role: "img", "aria-label": series.map((s) => s.label).join(" vs ") });
  requestAnimationFrame(() => {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = canvas.clientWidth || 600;
    canvas.width = w * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const all = series.flatMap((s) => s.data);
    let lo = Math.min(...all), hi = Math.max(...all);
    if (bars) lo = 0;
    if (hi === lo) hi = lo + 1;
    const pad = 8;
    const X = (i, n) => pad + (i / Math.max(1, n - 1)) * (w - pad * 2);
    const Y = (v) => height - pad - ((v - lo) / (hi - lo)) * (height - pad * 2);
    ctx.strokeStyle = "rgba(233,230,223,0.08)";
    ctx.beginPath(); ctx.moveTo(pad, Y((lo + hi) / 2)); ctx.lineTo(w - pad, Y((lo + hi) / 2)); ctx.stroke();
    for (const s of series) {
      ctx.strokeStyle = ctx.fillStyle = s.color;
      ctx.lineWidth = s.width || 1.25;
      if (bars) {
        const bw = Math.max(1, (w - pad * 2) / s.data.length);
        s.data.forEach((v, i) => { if (v) ctx.fillRect(X(i, s.data.length), Y(v), bw, height - pad - Y(v)); });
      } else {
        ctx.beginPath();
        s.data.forEach((v, i) => (i ? ctx.lineTo(X(i, s.data.length), Y(v)) : ctx.moveTo(X(i, s.data.length), Y(v))));
        ctx.stroke();
      }
    }
  });
  return canvas;
}

const legend = (...items) => h("p", { class: "plot-label" }, items.map(([c, t]) => h("span", {}, h("i", { style: `background:${c}` }), t)));

/* ─── image diff map (client-side) ─── */

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new UserError("Could not decode one of the images."));
    img.src = src;
  });
}

async function diffMap(srcA, srcB) {
  const [a, b] = await Promise.all([loadImage(srcA), loadImage(srcB)]);
  const w = a.naturalWidth, hgt = a.naturalHeight;
  const ctx = (img) => {
    const c = document.createElement("canvas");
    c.width = w; c.height = hgt;
    const x = c.getContext("2d", { willReadFrequently: true });
    x.drawImage(img, 0, 0, w, hgt);
    return x.getImageData(0, 0, w, hgt).data;
  };
  const da = ctx(a), db = ctx(b);
  const diff = new Uint8ClampedArray(w * hgt);
  let max = 0, changed = 0;
  for (let i = 0, p = 0; i < da.length; i += 4, p++) {
    const d = Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i + 1] - db[i + 1]), Math.abs(da[i + 2] - db[i + 2]));
    diff[p] = d;
    if (d) changed++;
    if (d > max) max = d;
  }
  const out = document.createElement("canvas");
  out.width = w; out.height = hgt;
  out.className = "diff";
  out.setAttribute("role", "img");
  out.setAttribute("aria-label", "Amplified pixel difference map");
  const octx = out.getContext("2d");
  const img = octx.createImageData(w, hgt);
  const gain = max ? 255 / max : 0;
  for (let p = 0; p < diff.length; p++) {
    const v = diff[p] * gain;
    img.data[p * 4] = v * 0.56;       // ice ramp to match the palette
    img.data[p * 4 + 1] = v * 0.8;
    img.data[p * 4 + 2] = v;
    img.data[p * 4 + 3] = 255;
  }
  octx.putImageData(img, 0, 0);
  return { canvas: out, max, changedPct: (changed / diff.length) * 100, sizeMismatch: a.naturalWidth !== b.naturalWidth || a.naturalHeight !== b.naturalHeight };
}

function compareSlider(srcA, srcB) {
  const wrap = h("div", { class: "compare" },
    h("img", { src: srcB, alt: "Modified image" }),
    h("div", { class: "top" }, h("img", { src: srcA, alt: "Original image" })));
  const range = h("input", { type: "range", min: "0", max: "100", value: "50", "aria-label": "Comparison split position" });
  range.addEventListener("input", () => wrap.style.setProperty("--split", `${range.value}%`));
  return [h("div", { class: "compare-tags" }, h("span", { text: "Original" }), h("span", { text: "Modified" })), wrap, range];
}

/* ─── state shared between tools ─── */

const state = { eduKeys: null };

/* ─── handlers ─── */

const tools = {
  async "stego-embed"(f) {
    const file = need(f.get("image").size && f.get("image"), "Choose a carrier image.");
    const src = await fileToDataURL(file);
    const r = await postJSON("/api/stego/embed", { image_b64: src, payload_text: f.get("payload") });
    return [
      h("img", { class: "out", src: r.stego_image_b64, alt: "Stego image with the hidden payload" }),
      readings([
        ["Bits written", fmt(r.bits_used, 0)],
        ["Capacity", `${fmt(r.capacity_bytes, 0)} bytes`],
        ["PSNR", `${fmt(r.metrics.psnr_db)} dB`],
        ["MSE", fmt(r.metrics.mse, 6)],
      ]),
      verdict(r.metrics.quality_verdict, psnrGood(r.metrics)),
      h("div", { class: "result-actions" }, download(r.stego_image_b64, `stego_${file.name.replace(/\.\w+$/, "")}.png`, "Download stego PNG")),
    ];
  },

  async "stego-extract"(f) {
    const src = await fileToDataURL(need(f.get("image").size && f.get("image"), "Choose a stego image."));
    const r = await postJSON("/api/stego/extract", { stego_image_b64: src });
    return [textOut(r.extracted_text), readings([["Payload", `${fmt(r.length_bytes, 0)} bytes`]])];
  },

  async "audio-embed"(f) {
    const file = need(f.get("file").size && f.get("file"), "Choose a WAV file.");
    const r = await postForm("/api/stego/audio/embed-details", { text: f.get("text"), password: f.get("password"), file });
    const pd = r.plot_data || {};
    return [
      player(r.stego_audio_b64, "stego audio preview"),
      readings([
        ["Encrypted payload", `${fmt(r.payload_bytes, 0)} bytes`],
        ["Capacity used", `${fmt(r.capacity_used_pct)} %`],
        ["Sample rate", `${fmt(r.sample_rate, 0)} Hz`],
        ["PSNR", `${fmt(r.metrics?.psnr_db)} dB`],
      ]),
      readings([["Cipher", r.cipher_algo], ["Header", r.magic_header]]),
      pd.orig_waveform && [
        legend(["#7d8ba3", "Original"], ["#8ecbff", "Stego"]),
        plot([{ label: "Original", data: pd.orig_waveform, color: "#7d8ba3", width: 2 }, { label: "Stego", data: pd.stego_waveform, color: "#8ecbff" }]),
        legend(["#8ecbff", `LSB changes, first ${fmt(pd.sample_count, 0)} samples (${fmt(pd.duration_ms)} ms)`]),
        plot([{ label: "LSB changes", data: pd.lsb_deltas, color: "#8ecbff" }], { height: 70, bars: true }),
      ],
      h("div", { class: "result-actions" }, download(r.stego_audio_b64, `stego_${file.name.replace(/\.\w+$/, "")}.wav`, "Download stego WAV")),
    ];
  },

  async "audio-extract"(f) {
    const file = need(f.get("file").size && f.get("file"), "Choose a stego WAV file.");
    let r;
    try {
      r = await postForm("/api/stego/audio/extract", { password: f.get("password"), file });
    } catch (err) {
      // A wrong key surfaces from the backend as a padding/decoding failure.
      throw new UserError("Nothing could be decrypted: wrong password, or this file holds no hidden message.", err instanceof ApiError ? err.raw : err.message);
    }
    return [textOut(r.extracted_text), readings([["Cipher", r.cipher_algo], ["Key derivation", r.derived_key_hint]])];
  },

  async "wm-text"(f) {
    const file = need(f.get("image").size && f.get("image"), "Choose an image.");
    const r = await postJSON("/api/watermark/visible-text", {
      image_b64: await fileToDataURL(file),
      text: f.get("text"),
      font_size: Number(f.get("font_size")) || 28,
      opacity: Number(f.get("opacity")),
      position: f.get("position"),
      color_hex: f.get("color_hex"),
    });
    return [h("img", { class: "out", src: r.watermarked_image_b64, alt: "Image with visible text watermark" }), ...imageMetrics(r.metrics),
      h("div", { class: "result-actions" }, download(r.watermarked_image_b64, "watermarked.png", "Download PNG"))];
  },

  async "wm-logo"(f) {
    const base = need(f.get("base").size && f.get("base"), "Choose a base image.");
    const logo = need(f.get("logo").size && f.get("logo"), "Choose a logo image.");
    const r = await postJSON("/api/watermark/visible-logo", {
      base_image_b64: await fileToDataURL(base),
      logo_image_b64: await fileToDataURL(logo),
      opacity: Number(f.get("opacity")),
      scale: Number(f.get("scale")),
      position: f.get("position"),
    });
    return [h("img", { class: "out", src: r.watermarked_image_b64, alt: "Image with logo watermark" }), ...imageMetrics(r.metrics),
      h("div", { class: "result-actions" }, download(r.watermarked_image_b64, "watermarked.png", "Download PNG"))];
  },

  async "wm-dct-embed"(f) {
    const file = need(f.get("image").size && f.get("image"), "Choose an image.");
    const strength = Number(f.get("strength"));
    const r = await postJSON("/api/watermark/invisible-dct-embed", { image_b64: await fileToDataURL(file), watermark_text: f.get("watermark_text"), strength });
    document.getElementById("dct-bits").value = r.watermark_bit_length;
    document.getElementById("dct-strength").value = strength;
    return [
      h("img", { class: "out", src: r.watermarked_image_b64, alt: "Image with invisible DCT watermark" }),
      readings([["Bit length (keep this)", fmt(r.watermark_bit_length, 0)], ["Capacity", `${fmt(r.max_capacity_bits, 0)} bits`], ["PSNR", `${fmt(r.metrics.psnr_db)} dB`]]),
      verdict(r.metrics.quality_verdict, psnrGood(r.metrics)),
      h("p", { class: "placeholder", text: "Bit length and strength are filled into “Read an invisible mark”." }),
      h("div", { class: "result-actions" }, download(r.watermarked_image_b64, "dct_watermarked.png", "Download PNG")),
    ];
  },

  async "wm-dct-extract"(f) {
    const file = need(f.get("image").size && f.get("image"), "Choose the marked image.");
    const r = await postJSON("/api/watermark/invisible-dct-extract", {
      image_b64: await fileToDataURL(file),
      watermark_bit_length: Number(need(f.get("watermark_bit_length"), "Enter the bit length reported when embedding.")),
      strength: Number(f.get("strength")) || 20,
    });
    return [textOut(r.extracted_text), readings([["Bits read", fmt(r.bits_extracted, 0)]])];
  },

  async "rsa-keys"(f) {
    const r = await postJSON("/api/crypto/generate-rsa-keys", { key_size: Number(f.get("key_size")) });
    document.getElementById("pub-pem").value = r.public_key_pem;
    document.getElementById("priv-pem").value = r.private_key_pem;
    document.dispatchEvent(new Event("ss:keys"));
    return null;   // this form shows its result in the two PEM fields
  },

  async "hybrid-encrypt"(f) {
    const r = await postJSON("/api/crypto/encrypt-hybrid", { plaintext: f.get("plaintext"), public_key_pem: pem("pub-pem", "public") });
    const json = JSON.stringify(r, null, 2);
    document.getElementById("hybrid-envelope").value = json;
    return [textOut(json, true),
      h("p", { class: "placeholder", text: "Also copied into “Hybrid decrypt”." })];
  },

  async "hybrid-decrypt"(f) {
    let payload;
    try { payload = JSON.parse(f.get("payload")); } catch (e) { throw new UserError(MSG.badEnvelope, `JSON.parse: ${e.message}`); }
    const missing = ["enc_key_b64", "nonce_b64", "ciphertext_b64"].filter((k) => typeof payload?.[k] !== "string" || !payload[k]);
    if (missing.length) throw new UserError(MSG.badEnvelope, `Missing or empty field${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}`);
    const r = await postJSON("/api/crypto/decrypt-hybrid", { payload, private_key_pem: pem("priv-pem", "private") });
    return [textOut(r.plaintext)];
  },

  async "file-crypt"(f) {
    const file = need(f.get("file").size && f.get("file"), "Choose a file.");
    const enc = f.get("direction") === "encrypt";
    const r = enc
      ? await postForm("/api/crypto/encrypt-file", { public_key_pem: pem("pub-pem", "public"), file })
      : await postForm("/api/crypto/decrypt-file", { private_key_pem: pem("priv-pem", "private"), file });
    const url = URL.createObjectURL(r.blob);
    return [readings([["Output", r.filename], ["Size", `${fmt(r.blob.size, 0)} bytes`]]),
      h("div", { class: "result-actions" }, download(url, r.filename, enc ? "Download encrypted file" : "Download decrypted file"))];
  },

  async "sign-verify"(f, action) {
    const message = f.get("message");
    if (action === "verify") {
      const r = await postJSON("/api/crypto/verify", {
        message,
        signature_b64: need(f.get("signature").trim(), "Paste a signature, or sign the message first."),
        public_key_pem: pem("pub-pem", "public"),
      });
      return [verdict(r.valid ? "Valid signature for this message and key" : "Signature does not match", r.valid)];
    }
    const r = await postJSON("/api/crypto/sign", { message, private_key_pem: pem("priv-pem", "private") });
    document.getElementById("sig-b64").value = r.signature_b64;
    return [textOut(r.signature_b64, true)];
  },

  async aes(f, action) {
    const password = f.get("password");
    if (action === "decrypt") {
      const r = await postJSON("/api/crypto/decrypt-aes", { ciphertext_payload: f.get("text").trim(), password });
      return [textOut(r.plaintext)];
    }
    const r = await postJSON("/api/crypto/encrypt-aes", { plaintext: f.get("text"), password });
    return [textOut(r.ciphertext_payload, true),
      h("p", { class: "placeholder", text: "Paste this back into the same box and press Decrypt to reverse it." })];
  },

  async hash(f) {
    const file = f.get("file");
    const body = file && file.size ? { data_b64: await fileToBase64(file) } : { text: need(f.get("text"), "Enter text or choose a file.") };
    const r = await postJSON("/api/crypto/hash", body);
    return [textOut(r.hash_sha256, true), readings([["Input", file && file.size ? `${file.name}, ${fmt(file.size, 0)} bytes` : "Text"]])];
  },

  async "edu-keys"(f) {
    const r = await postJSON("/api/crypto-edu/generate-keys", { bits: Number(f.get("bits")) });
    state.eduKeys = r.keypair;
    document.dispatchEvent(new Event("ss:edu-keys"));
    const k = r.keypair;
    const bits = (s) => `${BigInt(s).toString(2).length} bits`;
    const row = (label, value, note) => [h("dt", { text: `${label}${note ? ` · ${note}` : ""}` }), h("dd", { text: value })];
    return [h("dl", {},
      row("p", k.p, bits(k.p)),
      row("q", k.q, bits(k.q)),
      row("n = p·q", k.n, bits(k.n)),
      row("φ(n) = (p−1)(q−1)", k.phi),
      row("e", k.publicKey.e),
      row("d = e⁻¹ mod φ(n)", k.privateKey.d),
    ), h("div", { class: "result-actions" }, copyButton(() => JSON.stringify(k, null, 2), "Copy all as JSON"))];
  },

  async "edu-crypt"(f) {
    const k = need(state.eduKeys, "Generate primes in “Textbook RSA, step by step” first.");
    const plaintext = f.get("plaintext");
    const { ciphertext } = await postJSON("/api/crypto-edu/encrypt", { plaintext, public_key: k.publicKey });
    const { plaintext: back } = await postJSON("/api/crypto-edu/decrypt", { ciphertext, private_key: k.privateKey });
    return [readings([["c = mᵉ mod n", ciphertext]]), readings([["m = cᵈ mod n", back]]), verdict(back === plaintext ? "Round trip matches the original" : "Round trip does not match", back === plaintext)];
  },

  async "miller-rabin"(f) {
    const r = await postJSON("/api/crypto-edu/miller-rabin", { n: need(f.get("n").trim(), "Enter a whole number."), rounds: Number(f.get("rounds")) || 20 });
    return [verdict(r.is_prime ? `${r.n} is probably prime` : `${r.n} is composite`, r.is_prime),
      h("p", { class: "placeholder", text: r.is_prime ? `Chance this is wrong: at most 4^−${r.rounds}.` : "A witness proved it composite; this verdict is certain." })];
  },

  async "compare-images"(f) {
    const a = need(f.get("original").size && f.get("original"), "Choose the original image.");
    const b = need(f.get("modified").size && f.get("modified"), "Choose the modified image.");
    const [srcA, srcB] = await Promise.all([fileToDataURL(a), fileToDataURL(b)]);
    const [r, d] = await Promise.all([postJSON("/api/metrics/compare", { original_image_b64: srcA, modified_image_b64: srcB }), diffMap(srcA, srcB)]);
    return [
      ...imageMetrics(r.metrics),
      ...compareSlider(srcA, srcB),
      legend(["#8ecbff", d.max ? `Difference map, amplified ×${fmt(255 / d.max, 1)} (largest change ${d.max} levels, ${fmt(d.changedPct)} % of pixels)` : "No pixel differs"]),
      d.canvas,
      d.sizeMismatch && h("p", { class: "placeholder", text: "Sizes differ: the modified image was scaled to the original for the map." }),
    ];
  },

  async transmit(f, _action, form) {
    const message = need(f.get("message"), "Type a message to transmit.");
    const status = await radioStatus();
    if (!status.available) throw new UserError(status.detail || "The GNU Radio runtime isn’t available on this machine.");
    const sf = Number(f.get("spreading_factor")), sigma = Number(f.get("noise_voltage"));
    renderGate(form, { message, sf, sigma, est: estimate(message, sf), snr: snrDb(sigma, status.signal_power) });
    return null;                       // the staged flow renders its own result
  },

  async "compare-audio"(f) {
    const r = await postForm("/api/metrics/compare-audio", {
      original_file: need(f.get("original_file").size && f.get("original_file"), "Choose the original WAV."),
      modified_file: need(f.get("modified_file").size && f.get("modified_file"), "Choose the modified WAV."),
    });
    const m = r.metrics;
    return [
      readings([["PSNR", `${fmt(m.psnr_db)} dB`], ["SNR", `${fmt(m.snr_db)} dB`], ["MSE", fmt(m.mse, 6)]]),
      readings([["Duration", `${fmt(m.duration_sec)} s`], ["Sample rate", `${fmt(m.sample_rate, 0)} Hz`], ["Format", `${m.sample_width}-bit, ${m.channels} ch`]]),
      verdict(m.quality_verdict, m.verdict_badge === "success"),
    ];
  },
};

/* ─── Transmit: confirm gate → transmit → receive, staged inside the result pane ─── */

const busy = (text) => h("p", { class: "busy", role: "status" }, h("span", { class: "spin", "aria-hidden": "true" }), text);
const stageLabel = (n, text) => h("p", { class: "stage-label" }, h("b", { text: n }), text);
const consoleBlock = (text) => (text ? h("details", { class: "console-log" }, h("summary", { text: "GNU Radio console output" }), h("pre", { text })) : null);
const driftText = (v) => (v == null ? "n/a" : `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(5)} rad/symbol`);

function renderGate(form, p) {
  const e = p.est;
  show(form,
    stageLabel("1", "Review before sending"),
    readings([
      ["Encrypted bundle", `≈ ${e.bundleBytes} bytes`],
      ["Chips on air", `≈ ${fmt(e.chips, 0)}`],
      ["Processing gain", `${e.processingGainDb.toFixed(1)} dB · SF ${p.sf}`],
      ["Air time", `≈ ${e.durationS.toFixed(2)} s`],
      ["Channel SNR", Number.isFinite(p.snr) ? `${p.snr.toFixed(1)} dB per sample` : "noiseless"],
    ]),
    h("p", { class: "note", text: "Nothing has been sent. After you confirm, the message is encrypted with AES-256-GCM, spread across the chips above, pulse-shaped and passed through the noisy channel." }),
    h("div", { class: "result-actions" },
      h("button", { type: "button", class: "btn btn--primary", text: "Transmit", onclick: () => stageTransmit(form, p) }),
      h("button", { type: "button", class: "btn", text: "Cancel", onclick: () => show(form, h("p", { class: "placeholder", text: "Cancelled. Nothing was transmitted." })) })));
  form.querySelector(".result .btn--primary")?.focus();
}

async function stageTransmit(form, p) {
  const flow = createFlow({ phase: "tx", sf: p.sf, sigma: p.sigma });
  show(form, stageLabel("2", "Transmitting"), flow.el);
  let tx;
  try {
    tx = await transmit({ message: p.message, spreadingFactor: p.sf, noiseVoltage: p.sigma });
  } catch (err) {
    flow.finish(false);
    return show(form, stageLabel("2", "Transmission failed"), flow.el, h("p", { class: "error", role: "alert", text: err.message }),
      h("div", { class: "result-actions" }, h("button", { type: "button", class: "btn", text: "Back", onclick: () => renderGate(form, p) })));
  }
  flow.finish(true);
  show(form,
    stageLabel("2", "Transmitted"),
    flow.el,
    readings([
      ["Encrypted bundle", `${tx.bundle_bytes} bytes`],
      ["Chips on air", fmt(tx.num_chips, 0)],
      ["Processing gain", `${tx.processing_gain_db.toFixed(1)} dB`],
      ["Air time", `${tx.duration_s.toFixed(2)} s`],
      ["Channel SNR", tx.snr_db == null ? "noiseless" : `${tx.snr_db.toFixed(1)} dB per sample`],
      ["Measured noise σ", tx.measured_noise_std.toFixed(4)],
    ]),
    player(tx.wav_url, "the rendered signal, slowed for listening"),
    h("p", { class: "note", text: "The real part of the baseband signal, played about four times slower. Encrypted and spread, it sounds like static, which is the point." }),
    h("div", { class: "result-actions" },
      h("button", { type: "button", class: "btn btn--primary", text: "Despread & decrypt", onclick: () => stageReceive(form, p, tx) }),
      download(tx.wav_url, `sentinel_${tx.transmission_id}.wav`, "Download WAV")));
}

async function stageReceive(form, p, tx) {
  const flow = createFlow({ phase: "rx", sf: p.sf, sigma: p.sigma });
  show(form, stageLabel("3", "Receiving"), flow.el);
  const again = h("button", { type: "button", class: "btn", text: "Transmit again", onclick: () => renderGate(form, p) });
  try {
    const rx = await receive(tx);
    flow.finish(true);
    const exact = rx.recovered_text === p.message;
    show(form,
      stageLabel("3", "Received"),
      flow.el,
      verdict(exact ? "Exact match with the message you sent" : "Decoded, but it differs from the original", exact),
      textOut(rx.recovered_text),
      readings([
        ["Bit errors", `${rx.bit_errors} / ${fmt(rx.total_bits, 0)}`],
        ["BER", rx.ber.toFixed(4)],
        ["EVM", `${rx.evm_db.toFixed(1)} dB`],
        ["Residual drift", driftText(rx.residual_drift_rad)],
      ]),
      consoleBlock(rx.console),
      h("div", { class: "result-actions" }, again));
  } catch (err) {
    flow.finish(false);
    const d = err instanceof ApiError ? err.data : null;
    show(form,
      stageLabel("3", "Not decodable"),
      flow.el,
      verdict("Could not recover the message", false),
      h("p", { class: "error", role: "alert", text: err.message }),
      d && readings([["Bit errors", `${d.bit_errors} / ${fmt(d.total_bits, 0)}`], ["BER", d.ber.toFixed(4)], ["EVM", `${d.evm_db.toFixed(1)} dB`]]),
      consoleBlock(d?.console),
      h("div", { class: "result-actions" }, again));
  }
}

async function initTransmit() {
  const form = document.querySelector('form[data-tool="transmit"]');
  if (!form) return;
  const status = await radioStatus();
  const slider = form.querySelector('[name="noise_voltage"]');
  const hint = form.querySelector("[data-snr]");
  const update = () => {
    const sigma = Number(slider.value), snr = snrDb(sigma, status.signal_power);
    const lock = sigma <= 0.3 ? "the receiver holds lock" : sigma <= 0.36 ? "right at the edge of lock" : "expect to lose lock";
    hint.textContent = Number.isFinite(snr) ? `≈ ${snr.toFixed(1)} dB signal-to-noise per sample · ${lock}` : "Noiseless channel";
  };
  slider.addEventListener("input", update);
  update();
  if (!status.available) {
    form.querySelector('button[type="submit"]').disabled = true;
    show(form, h("p", { class: "error", role: "alert", text: status.detail || "The GNU Radio runtime isn’t available on this machine." }));
  }
}

/* ─── wiring ─── */

function initForms() {
  for (const form of document.querySelectorAll("form[data-tool]")) {
    const handler = tools[form.dataset.tool];
    if (!handler) continue;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitter = e.submitter || form.querySelector('[type="submit"]');
      const buttons = form.querySelectorAll('button[type="submit"]');
      const label = submitter.textContent;
      buttons.forEach((b) => (b.disabled = true));
      submitter.setAttribute("aria-busy", "true");
      submitter.textContent = "Working…";
      const started = performance.now();
      try {
        const nodes = await handler(new FormData(form), submitter.value, form);
        if (nodes) {
          const secs = (performance.now() - started) / 1000;
          const chars = nodes.flat(Infinity).filter(Boolean).reduce((n, el) => n + (el.querySelector?.(".out-block pre, .out-block .text-out")?.textContent.length ?? 0), 0);
          show(form, nodes, h("p", { class: "result-meta", text: `Done in ${secs < 1 ? `${Math.round(secs * 1000)} ms` : `${secs.toFixed(1)} s`}${chars ? ` · ${fmt(chars, 0)} characters` : ""}` }));
          form.querySelector(".result")?.removeAttribute("data-error");
        }
      } catch (err) {
        const out = form.querySelector(".result");
        if (out) out.replaceChildren(...errorView(err).filter(Boolean)); else alert(err.message);
      } finally {
        buttons.forEach((b) => (b.disabled = false));
        submitter.removeAttribute("aria-busy");
        submitter.textContent = label;
        document.dispatchEvent(new Event("ss:gate"));   // re-apply "needs keys" gating
      }
    });
  }
}

function initDropzones() {
  for (const drop of document.querySelectorAll(".drop")) {
    const input = drop.querySelector("input[type=file]");
    const title = drop.querySelector(".drop-text b");
    const sub = title.nextSibling;
    const original = { title: title.textContent, sub: sub ? sub.textContent : "" };
    const update = async () => {
      const file = input.files[0];
      drop.classList.toggle("has-file", Boolean(file));
      drop.querySelector("img.thumb")?.remove();
      if (!file) { title.textContent = original.title; if (sub) sub.textContent = original.sub; return; }
      title.textContent = file.name;
      if (sub) sub.textContent = `${fmt(file.size / 1024, 1)} KB`;
      if ("preview" in drop.dataset && file.type.startsWith("image/")) {
        const url = URL.createObjectURL(file);
        drop.prepend(h("img", { class: "thumb", src: url, alt: "" }));
        if (input.form?.dataset.tool === "stego-embed") showCapacity(input.form, url);
      }
    };
    input.addEventListener("change", update);
    ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, () => drop.classList.add("is-over")));
    ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("is-over")));
    input.form?.addEventListener("reset", () => setTimeout(update));
  }
}

async function showCapacity(form, url) {
  const hint = form.querySelector("[data-capacity]");
  try {
    const img = await loadImage(url);
    const r = await postJSON("/api/stego/capacity", { width: img.naturalWidth, height: img.naturalHeight });
    hint.textContent = `${img.naturalWidth} × ${img.naturalHeight} px · holds up to ${fmt(r.capacity_bytes, 0)} bytes of text`;
    hint.hidden = false;
  } catch {
    hint.hidden = true;
  }
}

function initRanges() {
  for (const range of document.querySelectorAll('input[type="range"][name]')) {
    const out = range.closest(".field")?.querySelector(`output[data-for="${range.name}"]`);
    if (!out) continue;
    const decimals = (range.step.split(".")[1] || "").length;
    const sync = () => (out.textContent = Number(range.value).toFixed(decimals));
    range.addEventListener("input", sync);
    sync();
  }
}

/* ─── Console: grouped, searchable tool list; one tool on stage at a time ─── */

const ICONS = {
  transmit: '<circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
  audio: '<path d="M3 12h2l2-6 3 12 3-9 2 6 2-3h4"/>',
  mark: '<path d="M12 3l7 4v5c0 4.5-3 8-7 9-4-1-7-4.5-7-9V7z"/><path d="m9 12 2 2 4-4"/>',
  encrypt: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  learn: '<path d="M18 4H7l6 8-6 8h11"/>',
  measure: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 18 4-6"/>',
};
const icon = (g) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[g] || ""}</svg>`;
const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

const toolList = [];
let current = null;

function selectTool(id, { focusNav = false, focusArticle = false } = {}) {
  const t = toolList.find((x) => x.id === id) || toolList[0];
  if (!t) return;
  for (const x of toolList) {
    const on = x === t;
    x.el.hidden = !on;
    x.btn.toggleAttribute("aria-current", on);
    if (on) x.btn.setAttribute("aria-current", "page");
  }
  current = t;
  try { localStorage.setItem("ss-tool", t.id); } catch { /* storage unavailable */ }
  if (focusNav) t.btn.focus();
  if (focusArticle) t.el.focus({ preventScroll: true });
}

export function openTab(group) {
  const t = toolList.find((x) => x.group === group);
  if (t) selectTool(t.id);
}

function keyStatus(note, ok, text) {
  note.querySelector(".dep-state").textContent = text;
  note.dataset.ok = String(ok);
}

function addDependencyNotes() {
  const pub = document.getElementById("pub-pem"), priv = document.getElementById("priv-pem");
  const needsKeys = ["hybrid-encrypt", "hybrid-decrypt", "file-crypt", "sign-verify"];
  const notes = [];
  for (const tool of needsKeys) {
    const form = document.querySelector(`form[data-tool="${tool}"]`);
    const note = h("p", { class: "dep" },
      h("span", { class: "dep-state" }), " Uses the RSA key pair. ",
      h("button", { type: "button", class: "dep-link", onclick: () => selectTool("tool-rsa-key-pair") }, "Open key pair"));
    form.before(note);
    notes.push(note);
  }
  const refresh = () => {
    const ok = pub.value.includes("BEGIN PUBLIC KEY") && priv.value.includes("BEGIN PRIVATE KEY");
    for (const n of notes) keyStatus(n, ok, ok ? "Keys loaded." : "No keys yet.");
  };
  const gate = (btn, ok, why) => {
    if (!btn) return;
    btn.disabled = !ok;
    btn.title = ok ? "" : why;
    btn.setAttribute("aria-disabled", String(!ok));
  };
  const applyGates = () => {
    const hasPub = pub.value.includes("BEGIN PUBLIC KEY"), hasPriv = priv.value.includes("BEGIN PRIVATE KEY");
    const f = (t) => document.querySelector(`form[data-tool="${t}"]`);
    gate(f("hybrid-encrypt")?.querySelector('[type="submit"]'), hasPub, "Needs a public key");
    gate(f("hybrid-decrypt")?.querySelector('[type="submit"]'), hasPriv, "Needs a private key");
    gate(f("sign-verify")?.querySelector('[value="sign"]'), hasPriv, "Needs a private key");
    gate(f("sign-verify")?.querySelector('[value="verify"]'), hasPub, "Needs a public key");
    const fc = f("file-crypt");
    const decrypting = fc?.querySelector('input[name="direction"]:checked')?.value === "decrypt";
    gate(fc?.querySelector('[type="submit"]'), decrypting ? hasPriv : hasPub, decrypting ? "Needs a private key" : "Needs a public key");
    gate(f("edu-crypt")?.querySelector('[type="submit"]'), Boolean(state.eduKeys), "Generate primes first");
  };
  const refreshAll = () => { refresh(); applyGates(); };
  pub.addEventListener("input", refreshAll);
  priv.addEventListener("input", refreshAll);
  document.addEventListener("ss:keys", refreshAll);
  document.addEventListener("ss:gate", applyGates);
  document.querySelector('form[data-tool="file-crypt"]')?.addEventListener("change", applyGates);
  refreshAll();

  const eduForm = document.querySelector('form[data-tool="edu-crypt"]');
  const eduNote = h("p", { class: "dep" }, h("span", { class: "dep-state" }), " Uses the primes from Textbook RSA. ",
    h("button", { type: "button", class: "dep-link", onclick: () => selectTool("tool-textbook-rsa-step-by-step") }, "Generate primes"));
  eduForm.before(eduNote);
  const eduRefresh = () => { keyStatus(eduNote, Boolean(state.eduKeys), state.eduKeys ? "Primes ready." : "No primes yet."); applyGates(); };
  document.addEventListener("ss:edu-keys", eduRefresh);
  eduRefresh();
}

function initConsole() {
  const nav = document.getElementById("tool-nav");
  const search = document.getElementById("tool-search");
  for (const group of document.querySelectorAll(".tool-group")) {
    const g = group.dataset.group;
    const list = h("ul", { class: "nav-list" });
    const section = h("section", { class: "nav-group", "data-group": g },
      h("h3", { class: "nav-head" }, h("span", { class: "nav-icon" }), group.dataset.label), list);
    section.querySelector(".nav-icon").innerHTML = icon(g);   // static, trusted SVG paths
    for (const el of group.querySelectorAll("article.tool")) {
      const title = el.querySelector("h3").textContent.trim();
      const desc = el.querySelector("header p")?.textContent.trim() ?? "";
      el.id = `tool-${slug(title)}`;
      el.hidden = true;
      el.setAttribute("tabindex", "-1");
      const btn = h("button", { type: "button", class: "nav-item", "aria-controls": el.id },
        h("b", { text: title }), h("span", { text: desc.split(/(?<=\.)\s/)[0] }));
      btn.addEventListener("click", () => selectTool(el.id, { focusArticle: true }));
      list.append(h("li", {}, btn));
      toolList.push({ id: el.id, el, btn, group: g, text: `${title} ${desc} ${group.dataset.label}`.toLowerCase() });
    }
    nav.append(section);
  }

  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    for (const t of toolList) t.btn.parentElement.hidden = Boolean(q) && !t.text.includes(q);
    for (const sec of nav.querySelectorAll(".nav-group")) sec.hidden = ![...sec.querySelectorAll("li")].some((li) => !li.hidden);
  });
  search.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); nav.querySelector("li:not([hidden]) .nav-item")?.focus(); }
    if (e.key === "Enter") { const first = nav.querySelector("li:not([hidden]) .nav-item"); if (first) { e.preventDefault(); first.click(); } }
  });
  nav.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const items = [...nav.querySelectorAll("li:not([hidden]) .nav-item")].filter((b) => !b.closest("[hidden]"));
    const i = items.indexOf(document.activeElement);
    const next = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key];
    e.preventDefault();
    items[Math.max(0, Math.min(items.length - 1, next))]?.focus();
  });
  for (const link of document.querySelectorAll("[data-open-tab]")) {
    link.addEventListener("click", () => openTab(link.dataset.openTab));
  }

  let saved = null;
  try { saved = localStorage.getItem("ss-tool"); } catch { /* storage unavailable */ }
  selectTool(saved && document.getElementById(saved) ? saved : toolList[0].id);
  addDependencyNotes();
}

export function initWorkbench() {
  initConsole();
  initTransmit();
  initDropzones();
  initRanges();
  initForms();
}
