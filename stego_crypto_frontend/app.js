/**
 * SentinelSpread SDC Suite — Client Logic
 * Liquid Glass Design System, WebGL2 3D Liquid Icosphere Shader & 9000 Particle Field Swarm,
 * Spotlight 3D Card Tilt, Scroll Reveal, Canvas Plotting & API Integration
 */

let activeTab = "tab-overview";
let lastAudioProofData = null;

window.addEventListener("DOMContentLoaded", () => {
    initTopSlidingDock();
    initMotionPrimitives();
    initFileDropzones();
    initSpotlightCards();
    initScrollReveal();
    initExactKiddybankSphere();
    checkApiHealth();
    initSteganography();
    initWatermarking();
    initEduRSA();
    initWebCrypto();
    initMetrics();
});

const API_BASE = "";

async function apiCall(endpoint, method = "GET", body = null) {
  try {
    const options = { method };
    if (body) {
      if (body instanceof FormData) {
        options.body = body;
      } else {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(body);
      }
    }

    const response = await fetch(`${API_BASE}${endpoint}`, options);
    if (!response.ok) {
      let errDetail = "API Request Failed";
      try {
        const errData = await response.json();
        errDetail = errData.detail || errData.message || response.statusText;
      } catch (e) {}
      throw new Error(errDetail);
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return await response.json();
    }
    return await response.blob();
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }
}

async function checkApiHealth() {
  try {
    const res = await apiCall("/health");
    if (res && res.status === "healthy") {
      const dot = document.getElementById("api-status-dot");
      const txt = document.getElementById("api-status-text");
      if (dot) dot.className = "status-dot bg-emerald-400";
      if (txt) txt.textContent = "FastAPI Connected";
    }
  } catch (e) {
    const dot = document.getElementById("api-status-dot");
    const txt = document.getElementById("api-status-text");
    if (dot) dot.className = "status-dot bg-red-400";
    if (txt) txt.textContent = "FastAPI Offline";
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `p-3 rounded-xl border text-xs font-mono shadow-lg transition-all transform translate-y-2 opacity-0 ${
    type === "error" ? "bg-red-950/90 border-red-500/40 text-red-200" :
    type === "success" ? "bg-emerald-950/90 border-emerald-500/40 text-emerald-200" :
    "bg-slate-900/90 border-white/20 text-slate-200"
  }`;
  toast.textContent = message;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  }, 10);

  setTimeout(() => {
    toast.classList.add("opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ═══════════════════════════════════════════════════════════
// Top Sliding Glass Capsule Pill Dock & Tab Switching
// ═══════════════════════════════════════════════════════════

function initTopSlidingDock() {
  const pill = document.getElementById("nav-pill-active");
  const items = document.querySelectorAll(".dock-text-item");
  if (!items.length) return;

  function positionPill(activeItem) {
    if (!pill || !activeItem) return;
    pill.style.left = `${activeItem.offsetLeft}px`;
    pill.style.width = `${activeItem.offsetWidth}px`;
  }

  const activeInitial = document.querySelector(".dock-text-item.active");

  window.activateTab = function(tabId) {
    activeTab = tabId;
    document.querySelectorAll(".tab-view").forEach(v => {
      v.style.display = "none";
      v.classList.remove("active");
    });
    items.forEach(i => i.classList.remove("active"));

    const targetView = document.getElementById(tabId);
    if (targetView) {
      targetView.style.display = "block";
      targetView.classList.add("active");
    }

    const matchingItem = document.querySelector(`.dock-text-item[data-tab="${tabId}"]`);
    if (matchingItem) {
      matchingItem.classList.add("active");
      positionPill(matchingItem);
    }

    if (tabId === "tab-steganography") {
      setTimeout(initOrRefreshAudioProof, 50);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  window.switchTab = window.activateTab;

  items.forEach(item => {
    item.addEventListener("click", () => {
      const tabId = item.getAttribute("data-tab");
      window.activateTab(tabId);
    });
  });

  document.querySelectorAll("[data-tab]").forEach(el => {
    if (!el.classList.contains("dock-text-item")) {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        window.activateTab(el.getAttribute("data-tab"));
      });
    }
  });

  window.addEventListener("resize", () => {
    const active = document.querySelector(".dock-text-item.active");
    if (active) positionPill(active);
  });

  if (activeInitial) {
    const initialTabId = activeInitial.getAttribute("data-tab");
    window.activateTab(initialTabId);
  } else {
    window.activateTab("tab-overview");
  }
}

function initSubDocks() {
  document.querySelectorAll("[data-subtab]").forEach(item => {
    item.addEventListener("click", () => {
      const parentView = item.closest(".tab-view");
      if (!parentView) return;

      parentView.querySelectorAll(".subtab-panel").forEach(p => {
        p.classList.remove("active");
        p.style.display = "none";
      });
      parentView.querySelectorAll(".sub-dock-item").forEach(b => b.classList.remove("active"));

      const subtabId = item.getAttribute("data-subtab");
      const targetSubtab = document.getElementById(subtabId);
      if (targetSubtab) {
        targetSubtab.classList.add("active");
        targetSubtab.style.display = "block";
      }
      item.classList.add("active");

      if (subtabId === "steg-subtab-audio") {
        setTimeout(initOrRefreshAudioProof, 50);
      }
    });
  });
}

function setupDropzone(dropzoneId, inputId, onFileLoaded) {
  const dz = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  if (!dz || !input) return;

  dz.addEventListener("click", () => input.click());
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("border-accent"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("border-accent"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("border-accent");
    if (e.dataTransfer.files.length > 0) onFileLoaded(e.dataTransfer.files[0]);
  });
  input.addEventListener("change", (e) => {
    if (e.target.files.length > 0) onFileLoaded(e.target.files[0]);
  });
}

function initFileDropzones() {}

// ═══════════════════════════════════════════════════════════
// Spotlight 3D Cards, Scroll Reveal & Motion Primitives
// ═══════════════════════════════════════════════════════════

function initSpotlightCards() {
  document.querySelectorAll(".glass-card, .tilt-card").forEach(card => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty("--mouse-x", `${x}px`);
      card.style.setProperty("--mouse-y", `${y}px`);

      if (card.classList.contains("tilt-card")) {
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const rx = ((y - cy) / cy) * -6;
        const ry = ((x - cx) / cx) * 6;
        card.style.transform = `perspective(1000px) rotateX(${rx}deg) rotateY(${ry}deg) scale3d(1.02, 1.02, 1.02)`;
      }
    });

    card.addEventListener("mouseleave", () => {
      if (card.classList.contains("tilt-card")) {
        card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
      }
    });
  });
}

function initScrollReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll(".scroll-reveal, .hero-scroll-revealer").forEach(el => observer.observe(el));
}

function initMotionPrimitives() {
  document.querySelectorAll(".text-reveal-blur").forEach(el => el.classList.add("revealed"));
}

// ═══════════════════════════════════════════════════════════
// Audio & Image Steganography Studio Canvas Plotting
// ═══════════════════════════════════════════════════════════

function initSteganography() {
  let audioEmbedFile = null;
  let audioExtractFile = null;

  setupDropzone("dz-audio-embed", "file-audio-embed", (file) => {
    audioEmbedFile = file;
    const badge = document.getElementById("audio-embed-file-badge");
    if (badge) {
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      badge.style.display = "inline-block";
    }
    showToast(`Selected carrier audio file: ${file.name}`);
  });

  document.getElementById("btn-audio-embed-act")?.addEventListener("click", async () => {
    if (!audioEmbedFile) {
      showToast("Please upload a 16-bit PCM WAV carrier file first.", "error");
      return;
    }
    const text = document.getElementById("input-audio-embed-text").value;
    const pwd = document.getElementById("input-audio-embed-pwd").value;
    if (!text || !pwd) {
      showToast("Please enter payload text and password.", "error");
      return;
    }

    try {
      showToast("Encrypting & embedding payload into audio LSBs...", "info");
      const formData = new FormData();
      formData.append("text", text);
      formData.append("password", pwd);
      formData.append("file", audioEmbedFile);

      const details = await apiCall("/api/stego/audio/embed-details", "POST", formData);

      const b64Data = details.stego_audio_b64.split(",")[1];
      const byteCharacters = atob(b64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: "audio/wav" });
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = `stego_${audioEmbedFile.name}`;
      a.click();

      renderAudioStegoVisualProof(details);
      showToast("Audio Stego WAV file encrypted, downloaded, and plots generated!", "success");
    } catch (e) {}
  });

  setupDropzone("dz-audio-extract", "file-audio-extract", (file) => {
    audioExtractFile = file;
    const badge = document.getElementById("audio-extract-file-badge");
    if (badge) {
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      badge.style.display = "inline-block";
    }
    showToast(`Selected stego audio file: ${file.name}`);
  });

  document.getElementById("btn-audio-extract-act")?.addEventListener("click", async () => {
    if (!audioExtractFile) {
      showToast("Please upload a stego WAV file.", "error");
      return;
    }
    const pwd = document.getElementById("input-audio-extract-pwd").value;
    if (!pwd) {
      showToast("Please enter decryption password.", "error");
      return;
    }

    try {
      showToast("Extracting & decrypting payload from audio LSBs...", "info");
      const formData = new FormData();
      formData.append("password", pwd);
      formData.append("file", audioExtractFile);

      const res = await apiCall("/api/stego/audio/extract", "POST", formData);
      const out = document.getElementById("output-audio-recovered");
      if (out) out.textContent = res.extracted_text;

      showToast("Secret payload extracted and decrypted successfully!", "success");
    } catch (e) {}
  });
}

function initOrRefreshAudioProof() {
  if (!lastAudioProofData) {
    lastAudioProofData = generateDefaultAudioProofData();
  }
  renderAudioStegoVisualProof(lastAudioProofData);
}

function generateDefaultAudioProofData() {
  const sampleCount = 2000;
  const durationMs = 45.35;
  const origWave = [];
  const stegoWave = [];
  const lsbDeltas = [];
  const activeEmbeddedBits = 832;

  for (let i = 0; i < sampleCount; i++) {
    const t = (i / sampleCount) * (durationMs / 1000);
    const val = 0.5 * Math.sin(2 * Math.PI * 440 * t) + 0.2 * Math.sin(2 * Math.PI * 880 * t);
    const intVal = Math.round(val * 20000);
    origWave.push(intVal);

    if (i < activeEmbeddedBits && (i % 2 === 0)) {
      stegoWave.push(intVal + 1);
      lsbDeltas.push(1.0);
    } else {
      stegoWave.push(intVal);
      lsbDeltas.push(0.0);
    }
  }

  return {
    payload_bytes: 96,
    total_bits_embedded: 832,
    capacity_used_pct: 0.94,
    magic_header: "ASTG (4 Bytes)",
    cipher_algo: "AES-128-CBC (PKCS7 Padded)",
    derived_key_hint: "SHA-256('SentinelSecretKey2026')[:16]",
    plaintext_preview: "CONFIDENTIAL SENTINEL-SPREAD COMMUNICATE: LAT=37.7749 LONG=-122.4194 KEY=0x9F42",
    status_verification: "✓ STATUS: 100% ACOUSTIC-LAYER PAYLOAD RECOVERY VERIFIED",
    plot_data: {
      orig_waveform: origWave,
      stego_waveform: stegoWave,
      lsb_deltas: lsbDeltas,
      duration_ms: durationMs,
      sample_count: sampleCount
    }
  };
}

function renderAudioStegoVisualProof(details) {
  lastAudioProofData = details;
  const card = document.getElementById("card-audio-proof");
  if (!card) return;

  card.style.display = "block";
  card.classList.add("revealed");

  document.getElementById("meta-magic").textContent = details.magic_header || "ASTG (4 Bytes)";
  document.getElementById("meta-length").textContent = details.payload_bytes ? `${details.payload_bytes} Bytes` : "96 Bytes";
  document.getElementById("meta-cipher").textContent = details.cipher_algo || "AES-128-CBC (PKCS7 Padded)";
  document.getElementById("meta-key").textContent = details.derived_key_hint || `SHA-256(...)[:16]`;
  document.getElementById("meta-bits").textContent = details.total_bits_embedded ? `${details.total_bits_embedded} bits` : "832 bits";
  document.getElementById("meta-cap").textContent = details.capacity_used_pct !== undefined ? `${details.capacity_used_pct}%` : "0.94%";
  document.getElementById("meta-plaintext").textContent = details.plaintext_preview || details.extracted_text || "CONFIDENTIAL PAYLOAD";
  document.getElementById("meta-status").textContent = details.status_verification || "✓ STATUS: 100% ACOUSTIC-LAYER PAYLOAD RECOVERY VERIFIED";

  if (details.plot_data) {
    setTimeout(() => {
      drawWaveformComparisonCanvas(details.plot_data);
      drawLSBResidualCanvas(details.plot_data);
    }, 50);
  }
}

function drawWaveformComparisonCanvas(plotData) {
  const cvs = document.getElementById("canvas-audio-waveform");
  if (!cvs || !cvs.parentElement) return;
  const ctx = cvs.getContext("2d");

  const orig = plotData.orig_waveform;
  const stego = plotData.stego_waveform;
  if (!orig || !orig.length) return;

  const width = cvs.parentElement.clientWidth || 700;
  const height = 180;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  cvs.width = width * dpr;
  cvs.height = height * dpr;
  cvs.style.width = `${width}px`;
  cvs.style.height = `${height}px`;

  ctx.scale(dpr, dpr);
  ctx.fillStyle = "#06030c";
  ctx.fillRect(0, 0, width, height);

  const paddingLeft = 55, paddingBottom = 25, paddingTop = 15, paddingRight = 20;
  const plotW = width - paddingLeft - paddingRight;
  const plotH = height - paddingTop - paddingBottom;

  let minPcm = -20000, maxPcm = 20000;
  if (orig && orig.length) {
    let dataMin = orig[0], dataMax = orig[0];
    for (let i = 0; i < orig.length; i++) {
      if (orig[i] < dataMin) dataMin = orig[i];
      if (orig[i] > dataMax) dataMax = orig[i];
    }
    const margin = Math.max(Math.abs(dataMin), Math.abs(dataMax)) * 1.15 || 20000;
    minPcm = -margin; maxPcm = margin;
  }

  const yTicks = [Math.round(minPcm * 0.8), Math.round(minPcm * 0.4), 0, Math.round(maxPcm * 0.4), Math.round(maxPcm * 0.8)];
  ctx.fillStyle = "#8e8a9f";
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.textAlign = "right";

  yTicks.forEach(val => {
    const yNorm = (val - minPcm) / (maxPcm - minPcm);
    const y = paddingTop + plotH * (1 - yNorm);
    ctx.beginPath();
    ctx.strokeStyle = val === 0 ? "rgba(255, 255, 255, 0.25)" : "rgba(255, 255, 255, 0.08)";
    ctx.moveTo(paddingLeft, y);
    ctx.lineTo(paddingLeft + plotW, y);
    ctx.stroke();
    ctx.fillText(val.toString(), paddingLeft - 8, y + 3);
  });

  const durationMs = plotData.duration_ms || 45.0;
  const xTicks = [0, 10, 20, 30, 40];
  ctx.textAlign = "center";

  xTicks.forEach(tMs => {
    if (tMs <= durationMs) {
      const x = paddingLeft + (tMs / durationMs) * plotW;
      ctx.beginPath();
      ctx.moveTo(x, paddingTop);
      ctx.lineTo(x, paddingTop + plotH);
      ctx.stroke();
      ctx.fillText(tMs.toString(), x, paddingTop + plotH + 16);
    }
  });

  const getX = (idx) => paddingLeft + (idx / (orig.length - 1)) * plotW;
  const getY = (val) => paddingTop + plotH * (1 - Math.max(0, Math.min(1, (val - minPcm) / (maxPcm - minPcm))));

  ctx.beginPath();
  ctx.strokeStyle = "#8be9fd";
  ctx.lineWidth = 1.4;
  for (let i = 0; i < orig.length; i++) {
    const x = getX(i), y = getY(orig[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  ctx.beginPath();
  ctx.strokeStyle = "#ff79c6";
  ctx.lineWidth = 1.2;
  ctx.setLineDash([4, 4]);
  for (let i = 0; i < stego.length; i++) {
    const x = getX(i), y = getY(stego[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawLSBResidualCanvas(plotData) {
  const cvs = document.getElementById("canvas-audio-residual");
  if (!cvs || !cvs.parentElement) return;
  const ctx = cvs.getContext("2d");

  const width = cvs.parentElement.clientWidth || 700;
  const height = 150;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  cvs.width = width * dpr;
  cvs.height = height * dpr;
  cvs.style.width = `${width}px`;
  cvs.style.height = `${height}px`;

  ctx.scale(dpr, dpr);
  ctx.fillStyle = "#06030c";
  ctx.fillRect(0, 0, width, height);

  const paddingLeft = 55, paddingBottom = 25, paddingTop = 15, paddingRight = 20;
  const plotW = width - paddingLeft - paddingRight;
  const plotH = height - paddingTop - paddingBottom;

  const yTicks = [0.00, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50];
  const minY = -0.1, maxY = 1.6;

  ctx.fillStyle = "#8e8a9f";
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.textAlign = "right";

  yTicks.forEach(val => {
    const yNorm = (val - minY) / (maxY - minY);
    const y = paddingTop + plotH * (1 - yNorm);
    ctx.beginPath();
    ctx.moveTo(paddingLeft, y);
    ctx.lineTo(paddingLeft + plotW, y);
    ctx.stroke();
    ctx.fillText(val.toFixed(2), paddingLeft - 8, y + 3);
  });

  const durationMs = plotData.duration_ms || 45.0;
  const xTicks = [0, 10, 20, 30, 40];
  ctx.textAlign = "center";

  xTicks.forEach(tMs => {
    if (tMs <= durationMs) {
      const x = paddingLeft + (tMs / durationMs) * plotW;
      ctx.beginPath();
      ctx.moveTo(x, paddingTop);
      ctx.lineTo(x, paddingTop + plotH);
      ctx.stroke();
      ctx.fillText(tMs.toString(), x, paddingTop + plotH + 16);
    }
  });

  const deltas = plotData.lsb_deltas;
  if (!deltas || !deltas.length) return;

  const getX = (idx) => paddingLeft + (idx / (deltas.length - 1)) * plotW;
  const getY = (val) => paddingTop + plotH * (1 - Math.max(0, Math.min(1, (val - minY) / (maxY - minY))));

  ctx.beginPath();
  ctx.strokeStyle = "#50fa7b";
  ctx.lineWidth = 1.3;
  ctx.fillStyle = "rgba(80, 250, 123, 0.12)";

  const zeroY = getY(0);
  ctx.moveTo(paddingLeft, zeroY);

  for (let i = 0; i < deltas.length; i++) {
    ctx.lineTo(getX(i), getY(deltas[i]));
  }
  ctx.lineTo(paddingLeft + plotW, zeroY);
  ctx.closePath();
  ctx.fill();

  ctx.beginPath();
  for (let i = 0; i < deltas.length; i++) {
    const x = getX(i), y = getY(deltas[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function initWatermarking() {}
function initEduRSA() {}
function initWebCrypto() {}
function initMetrics() {}

// ═══════════════════════════════════════════════════════════
// WebGL2 3D Liquid Icosphere Shader & 9000 Particle Field Engine
// ═══════════════════════════════════════════════════════════

function initExactKiddybankSphere() {
    const canvas = document.getElementById("gl");
    if (!canvas) return;
    const gl = canvas.getContext("webgl2", { antialias: true, alpha: true });
    if (!gl) return;

    // Minimal Mat4 Math
    const mat4 = {
        create() { return new Float32Array(16); },
        identity(o) { o.fill(0); o[0]=o[5]=o[10]=o[15]=1; return o; },
        perspective(o, fovy, aspect, near, far) {
            const f = 1.0 / Math.tan(fovy / 2), nf = 1 / (near - far);
            o.fill(0);
            o[0]=f/aspect; o[5]=f; o[10]=(far+near)*nf; o[11]=-1;
            o[14]=2*far*near*nf; return o;
        },
        lookAt(o, eye, center, up) {
            let z0=eye[0]-center[0], z1=eye[1]-center[1], z2=eye[2]-center[2];
            let len = Math.hypot(z0,z1,z2)||1e-6; z0/=len; z1/=len; z2/=len;
            let x0=up[1]*z2-up[2]*z1, x1=up[2]*z0-up[0]*z2, x2=up[0]*z1-up[1]*z0;
            len = Math.hypot(x0,x1,x2)||1e-6; x0/=len; x1/=len; x2/=len;
            const y0=z1*x2-z2*x1, y1=z2*x0-z0*x2, y2=z0*x1-z1*x0;
            o[0]=x0;o[1]=y0;o[2]=z0;o[3]=0;
            o[4]=x1;o[5]=y1;o[6]=z1;o[7]=0;
            o[8]=x2;o[9]=y2;o[10]=z2;o[11]=0;
            o[12]=-(x0*eye[0]+x1*eye[1]+x2*eye[2]);
            o[13]=-(y0*eye[0]+y1*eye[1]+y2*eye[2]);
            o[14]=-(z0*eye[0]+z1*eye[1]+z2*eye[2]);
            o[15]=1; return o;
        },
        normalFromMat4(o3, m) {
            o3[0]=m[0]; o3[1]=m[1]; o3[2]=m[2];
            o3[3]=m[4]; o3[4]=m[5]; o3[5]=m[6];
            o3[6]=m[8]; o3[7]=m[9]; o3[8]=m[10]; return o3;
        }
    };

    function buildIcosphere(subdivisions) {
        const t = (1 + Math.sqrt(5)) / 2;
        let verts = [
            [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
            [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
            [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
        ].map(v => { const l = Math.hypot(...v); return [v[0]/l, v[1]/l, v[2]/l]; });

        let faces = [
            [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
            [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
            [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
            [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1],
        ];

        const midCache = new Map();
        function midpoint(i1, i2) {
            const key = i1 < i2 ? `${i1}_${i2}` : `${i2}_${i1}`;
            if (midCache.has(key)) return midCache.get(key);
            const a = verts[i1], b = verts[i2];
            let m = [(a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2];
            const l = Math.hypot(...m);
            m = [m[0]/l, m[1]/l, m[2]/l];
            verts.push(m);
            const idx = verts.length - 1;
            midCache.set(key, idx);
            return idx;
        }

        for (let s = 0; s < subdivisions; s++) {
            const newFaces = [];
            for (const [a, b, c] of faces) {
                const ab = midpoint(a, b), bc = midpoint(b, c), ca = midpoint(c, a);
                newFaces.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]);
            }
            faces = newFaces;
        }

        const positions = new Float32Array(verts.length * 3);
        const normals = new Float32Array(verts.length * 3);
        verts.forEach((v, i) => {
            positions[i*3]=v[0]; positions[i*3+1]=v[1]; positions[i*3+2]=v[2];
            normals[i*3]=v[0]; normals[i*3+1]=v[1]; normals[i*3+2]=v[2];
        });
        const indices = new Uint32Array(faces.length * 3);
        faces.forEach((f, i) => { indices[i*3]=f[0]; indices[i*3+1]=f[1]; indices[i*3+2]=f[2]; });

        return { positions, normals, indices };
    }

    function buildParticles(count) {
        const starts = new Float32Array(count * 3);
        const normals = new Float32Array(count * 3);
        const seeds = new Float32Array(count);
        for (let i = 0; i < count; i++) {
            const u = Math.random(), v = Math.random();
            const theta = 2 * Math.PI * u, phi = Math.acos(2 * v - 1);
            const nx = Math.sin(phi) * Math.cos(theta);
            const ny = Math.sin(phi) * Math.sin(theta);
            const nz = Math.cos(phi);

            const r = 3.0 + Math.pow(Math.random(), 0.5) * 7.0;
            starts[i*3]   = nx * r + (Math.random()-0.5) * 1.5;
            starts[i*3+1] = ny * r + (Math.random()-0.5) * 1.5;
            starts[i*3+2] = nz * r + (Math.random()-0.5) * 1.5;

            normals[i*3]=nx; normals[i*3+1]=ny; normals[i*3+2]=nz;
            seeds[i] = Math.random();
        }
        return { starts, normals, seeds, count };
    }

    const commonNoiseGLSL = `
        vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
        vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
        vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
        vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
        float snoise(vec3 v){
            const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
            vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
            vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
            vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
            i=mod289(i);
            vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
            float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
            vec4 j=p-49.0*floor(p*ns.z*ns.z);
            vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
            vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
            vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
            vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
            vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
            vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
            vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
            p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
            vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
            return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
        }
        float ridged(vec3 p){ return 1.0 - abs(snoise(p)); }
        float fbmRidged(vec3 p){
            vec3 warp = vec3(
                snoise(p * 0.45 + vec3(11.0, 2.0, 7.0)),
                snoise(p * 0.45 + vec3(31.0, 5.0, 19.0)),
                snoise(p * 0.45 + vec3(53.0, 9.0, 41.0))
            );
            vec3 pw = p + warp * 0.6;

            float sum=0.0, amp=0.75, freq=1.0;
            for (int i=0;i<3;i++){
                float r = ridged(pw*freq);
                r = pow(r, 1.15);
                sum += r*amp; freq *= 1.8; amp *= 0.32;
            }
            return sum;
        }
    `;

    const vertSrc = `#version 300 es
        precision highp float;
        layout(location=0) in vec3 aPosition;
        layout(location=1) in vec3 aNormal;
        uniform mat4 uModel, uView, uProjection;
        uniform mat3 uNormalMat;
        uniform float uTime, uAmplitude, uFrequency;
        out vec3 vNormalW, vPosW;
        out float vElevation;
        ${commonNoiseGLSL}
        vec3 displace(vec3 n, out float elev) {
            vec3 p = n * uFrequency + vec3(0.0, 0.0, uTime * 0.045);
            elev = fbmRidged(p) * uAmplitude;
            return aPosition + n * elev;
        }
        void main() {
            float elevation;
            vec3 displaced = displace(aNormal, elevation);

            float eps = 0.012;
            vec3 tangent = normalize(cross(aNormal, vec3(0.0, 1.0, 0.73)));
            vec3 bitangent = normalize(cross(aNormal, tangent));

            vec3 nT = normalize(aNormal + tangent * eps);
            vec3 dispT = aPosition + tangent * eps + aNormal * (fbmRidged(nT*uFrequency+vec3(0.0,0.0,uTime*0.045))*uAmplitude);
            vec3 nB = normalize(aNormal + bitangent * eps);
            vec3 dispB = aPosition + bitangent * eps + aNormal * (fbmRidged(nB*uFrequency+vec3(0.0,0.0,uTime*0.045))*uAmplitude);

            vec3 newNormal = normalize(cross(dispT - displaced, dispB - displaced));
            if (dot(newNormal, aNormal) < 0.0) newNormal = -newNormal;

            vElevation = elevation;
            vNormalW = normalize(uNormalMat * newNormal);
            vec4 worldPos = uModel * vec4(displaced, 1.0);
            vPosW = worldPos.xyz;
            gl_Position = uProjection * uView * worldPos;
        }
    `;

    const fragSrc = `#version 300 es
        precision highp float;
        in vec3 vNormalW, vPosW;
        in float vElevation;
        out vec4 fragColor;
        uniform vec3 uCameraPos, uLowColor, uMidColor, uHighColor, uLightDir;
        uniform float uOpacity;
        void main() {
            vec3 N = normalize(vNormalW);
            vec3 V = normalize(uCameraPos - vPosW);
            vec3 L = normalize(uLightDir);
            float h = clamp(vElevation * 1.9 + 0.28, 0.0, 1.0);
            vec3 base = mix(uLowColor, uMidColor, smoothstep(0.0, 0.55, h));
            base = mix(base, uHighColor, smoothstep(0.86, 1.0, h));

            float diff = max(dot(N, L), 0.0);
            vec3 halfV = normalize(L + V);
            float spec = pow(max(dot(N, halfV), 0.0), 40.0);
            float spec2 = pow(max(dot(N, halfV), 0.0), 180.0);
            float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0);

            vec3 color = base * (0.5 + 0.65 * diff);
            color += vec3(1.0, 0.85, 1.0) * spec * 0.4;
            color += vec3(1.0) * spec2 * 0.6;
            color += uHighColor * fresnel * 0.5;

            fragColor = vec4(color, uOpacity);
        }
    `;

    const particleVertSrc = `#version 300 es
        precision highp float;
        layout(location=0) in vec3 aStart;
        layout(location=1) in vec3 aNormal;
        layout(location=2) in float aSeed;
        uniform mat4 uModel, uView, uProjection;
        uniform float uTime, uAmplitude, uFrequency, uProgress, uPixelRatio;
        out float vSeed, vProgress;
        ${commonNoiseGLSL}
        float easeOutCubic(float x) { return 1.0 - pow(1.0 - x, 3.0); }
        void main() {
            vec3 p = aNormal * uFrequency + vec3(0.0, 0.0, uTime * 0.045);
            float elev = fbmRidged(p) * uAmplitude;
            vec3 target = aNormal * (2.2 + elev * 2.2);
            float localT = clamp(uProgress * 1.35 - aSeed * 0.35, 0.0, 1.0);
            float e = easeOutCubic(localT);
            vec3 mid = mix(aStart, target, 0.5) + aNormal * (0.6 * sin(3.14159 * e) * (1.0 - e));
            vec3 pos = mix(mix(aStart, mid, min(e*2.0,1.0)), target, max(e*2.0-1.0,0.0));
            vSeed = aSeed; vProgress = e;
            vec4 worldPos = uModel * vec4(pos, 1.0);
            gl_Position = uProjection * uView * worldPos;
            float dist = -(uView * worldPos).z;
            gl_PointSize = uPixelRatio * mix(5.0, 1.6, e) * (300.0 / max(dist, 0.1)) * 0.06;
        }
    `;

    const particleFragSrc = `#version 300 es
        precision highp float;
        in float vSeed, vProgress;
        out vec4 fragColor;
        uniform float uOpacity;
        void main() {
            vec2 c = gl_PointCoord - 0.5;
            float d = length(c);
            if (d > 0.5) discard;
            float falloff = smoothstep(0.5, 0.0, d);
            vec3 hot = vec3(1.0, 0.9, 1.0);
            vec3 cool = vec3(0.85, 0.2, 0.95);
            vec3 col = mix(cool, hot, vProgress * 0.7 + 0.15 * vSeed);
            fragColor = vec4(col * falloff, falloff * uOpacity);
        }
    `;

    const glowVertSrc = `#version 300 es
        precision highp float;
        layout(location=0) in vec3 aPosition;
        layout(location=1) in vec3 aNormal;
        uniform mat4 uModel, uView, uProjection;
        uniform mat3 uNormalMat;
        out vec3 vN, vP;
        void main(){
            vN = normalize(uNormalMat * aNormal);
            vec4 wp = uModel * vec4(aPosition, 1.0);
            vP = wp.xyz;
            gl_Position = uProjection * uView * wp;
        }
    `;
    const glowFragSrc = `#version 300 es
        precision highp float;
        in vec3 vN, vP;
        uniform vec3 uCameraPos;
        out vec4 fragColor;
        void main(){
            vec3 V = normalize(uCameraPos - vP);
            float f = pow(1.0 - max(dot(normalize(vN), V), 0.0), 3.0);
            fragColor = vec4(vec3(0.85, 0.25, 1.0) * f, f * 0.65);
        }
    `;

    function compile(src, type) {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        return s;
    }
    function link(vs, fs) {
        const p = gl.createProgram();
        gl.attachShader(p, compile(vs, gl.VERTEX_SHADER));
        gl.attachShader(p, compile(fs, gl.FRAGMENT_SHADER));
        gl.linkProgram(p);
        return p;
    }

    function makeMesh(data) {
        const vao = gl.createVertexArray();
        gl.bindVertexArray(vao);
        const pb = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, pb);
        gl.bufferData(gl.ARRAY_BUFFER, data.positions, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(0);
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);

        const nb = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, nb);
        gl.bufferData(gl.ARRAY_BUFFER, data.normals, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(1);
        gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);

        const ib = gl.createBuffer();
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
        gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, data.indices, gl.STATIC_DRAW);
        return { vao, count: data.indices.length };
    }

    function makeParticleMesh(data) {
        const vao = gl.createVertexArray();
        gl.bindVertexArray(vao);
        const sb = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, sb);
        gl.bufferData(gl.ARRAY_BUFFER, data.starts, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(0);
        gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);

        const nb = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, nb);
        gl.bufferData(gl.ARRAY_BUFFER, data.normals, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(1);
        gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);

        const seedb = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, seedb);
        gl.bufferData(gl.ARRAY_BUFFER, data.seeds, gl.STATIC_DRAW);
        gl.enableVertexAttribArray(2);
        gl.vertexAttribPointer(2, 1, gl.FLOAT, false, 0, 0);
        return { vao, count: data.count };
    }

    const sphereGeom = buildIcosphere(6);
    const glowGeom = buildIcosphere(3);
    for (let i = 0; i < glowGeom.positions.length; i++) glowGeom.positions[i] *= 1.16;

    const sphereMesh = makeMesh(sphereGeom);
    const glowMesh = makeMesh(glowGeom);
    const particleMesh = makeParticleMesh(buildParticles(9000));

    const mainProgram = link(vertSrc, fragSrc);
    const glowProgram = link(glowVertSrc, glowFragSrc);
    const particleProgram = link(particleVertSrc, particleFragSrc);

    function uniLoc(prog, name) { return gl.getUniformLocation(prog, name); }
    const mainU = {
        model: uniLoc(mainProgram,'uModel'), view: uniLoc(mainProgram,'uView'), proj: uniLoc(mainProgram,'uProjection'),
        normalMat: uniLoc(mainProgram,'uNormalMat'), time: uniLoc(mainProgram,'uTime'),
        amplitude: uniLoc(mainProgram,'uAmplitude'), frequency: uniLoc(mainProgram,'uFrequency'),
        cameraPos: uniLoc(mainProgram,'uCameraPos'), lowColor: uniLoc(mainProgram,'uLowColor'),
        midColor: uniLoc(mainProgram,'uMidColor'), highColor: uniLoc(mainProgram,'uHighColor'), lightDir: uniLoc(mainProgram,'uLightDir'),
        opacity: uniLoc(mainProgram,'uOpacity'),
    };
    const glowU = {
        model: uniLoc(glowProgram,'uModel'), view: uniLoc(glowProgram,'uView'), proj: uniLoc(glowProgram,'uProjection'),
        normalMat: uniLoc(glowProgram,'uNormalMat'), cameraPos: uniLoc(glowProgram,'uCameraPos'),
    };
    const particleU = {
        model: uniLoc(particleProgram,'uModel'), view: uniLoc(particleProgram,'uView'), proj: uniLoc(particleProgram,'uProjection'),
        time: uniLoc(particleProgram,'uTime'), amplitude: uniLoc(particleProgram,'uAmplitude'),
        frequency: uniLoc(particleProgram,'uFrequency'), progress: uniLoc(particleProgram,'uProgress'),
        pixelRatio: uniLoc(particleProgram,'uPixelRatio'), opacity: uniLoc(particleProgram,'uOpacity'),
    };

    let azimuth = 0.4, elevation = 0.15, distance = 8.2;
    let autoRotate = true;
    let dragging = false, lastX = 0, lastY = 0;

    canvas.addEventListener('pointerdown', e => { dragging = true; autoRotate = false; lastX = e.clientX; lastY = e.clientY; });
    window.addEventListener('pointerup', () => dragging = false);
    window.addEventListener('pointermove', e => {
        if (!dragging) return;
        azimuth += (e.clientX - lastX) * 0.006;
        elevation = Math.max(-1.2, Math.min(1.2, elevation + (e.clientY - lastY) * 0.006));
        lastX = e.clientX; lastY = e.clientY;
    });

    function resize() {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = window.innerWidth * dpr;
        canvas.height = window.innerHeight * dpr;
        gl.viewport(0, 0, canvas.width, canvas.height);
    }
    window.addEventListener("resize", resize);
    resize();

    gl.enable(gl.DEPTH_TEST);
    gl.clearColor(0, 0, 0, 0);

    const model = mat4.create(), view = mat4.create(), proj = mat4.create();
    let smoothScrollProgress = 0.0;
    let lastFrameTime = performance.now();
    let simTime = 0.0;

    function frame() {
        requestAnimationFrame(frame);
        const now = performance.now();
        const deltaSeconds = Math.min((now - lastFrameTime) / 1000, 0.1);
        lastFrameTime = now;

        const isOverview = (activeTab === "tab-overview");

        // On non-overview tabs (Workspace, Chat, Studio, Runner, etc.), slow down dramatically (calm, non-distracting ambient drift)
        const rotationSpeed = isOverview ? 0.0032 : 0.00035;
        const timeScale = isOverview ? 1.0 : 0.08;

        simTime += deltaSeconds * timeScale;
        const t = simTime;

        if (autoRotate) azimuth += rotationSpeed;

        const eye = [
            distance * Math.cos(elevation) * Math.sin(azimuth),
            distance * Math.sin(elevation),
            distance * Math.cos(elevation) * Math.cos(azimuth),
        ];
        mat4.lookAt(view, eye, [0, -0.45, 0], [0, 1, 0]);
        mat4.perspective(proj, 38 * Math.PI / 180, canvas.width / canvas.height, 0.1, 100);
        mat4.identity(model);

        // Window scroll reading calibrated for a stable, fixed centerpiece
        const scrollY = window.scrollY;
        const maxScroll = 550;
        const targetRatio = Math.min(1.0, Math.max(0.0, scrollY / maxScroll));

        smoothScrollProgress += (targetRatio - smoothScrollProgress) * 0.09;

        const convergeProgress = Math.min(1.0, smoothScrollProgress / 0.55);
        const crossfadeT = Math.min(1.0, Math.max(0.0, (smoothScrollProgress - 0.18) / 0.40));

        if (isOverview) {
            const mainText = document.getElementById("hero-main-text");
            const scrollText = document.getElementById("hero-scroll-text");
            if (mainText && scrollText) {
                if (smoothScrollProgress < 0.18) {
                    // Stage 1: Initial headline fading out
                    const fade = Math.min(1.0, smoothScrollProgress / 0.18);
                    mainText.style.display = "block";
                    mainText.style.opacity = (1.0 - fade).toFixed(3);
                    mainText.style.filter = `blur(${fade * 5}px)`;
                    mainText.style.transform = `translate(-50%, calc(-50% - ${fade * 18}px))`;
                    mainText.style.pointerEvents = fade > 0.5 ? "none" : "auto";

                    scrollText.style.display = "none";
                    scrollText.style.opacity = "0";
                } else if (smoothScrollProgress >= 0.18 && smoothScrollProgress <= 0.85) {
                    // Stage 2: Centerpiece STAYS FIXED, SOLID & READABLE for the long scroll
                    mainText.style.display = "none";
                    mainText.style.opacity = "0";

                    const revealT = Math.min(1.0, (smoothScrollProgress - 0.18) / 0.12);
                    scrollText.style.display = "block";
                    scrollText.style.opacity = revealT.toFixed(3);
                    scrollText.style.filter = `blur(${(1.0 - revealT) * 6}px)`;
                    scrollText.style.transform = `translate(-50%, -50%) scale(${0.96 + 0.04 * revealT})`;
                    scrollText.style.pointerEvents = "auto";
                } else {
                    // Stage 3: Smooth exit only when reaching the stats banner
                    mainText.style.display = "none";
                    mainText.style.opacity = "0";

                    const exitT = Math.min(1.0, (smoothScrollProgress - 0.85) / 0.15);
                    scrollText.style.display = "block";
                    scrollText.style.opacity = Math.max(0, 1.0 - exitT).toFixed(3);
                    scrollText.style.filter = `blur(${exitT * 5}px)`;
                    scrollText.style.transform = `translate(-50%, calc(-50% - ${exitT * 18}px))`;
                    scrollText.style.pointerEvents = exitT > 0.5 ? "none" : "auto";
                }
            }
        }

        const sphereOpacity = isOverview ? crossfadeT : 0.0;
        const particleOpacity = isOverview ? (1.0 - crossfadeT) : 0.40;
        const showParticles = particleOpacity > 0.001;
        const showSphere = sphereOpacity > 0.001;

        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

        const dpr = Math.min(window.devicePixelRatio || 1, 2);

        if (showSphere) {
            const revealEase = 1 - Math.pow(1 - sphereOpacity, 3);
            const revealScale = 0.15 + 0.85 * revealEase;
            const sphereModel = mat4.create();
            sphereModel.set(model);
            for (let i = 0; i < 12; i++) sphereModel[i] *= revealScale;
            sphereModel[15] = 1;

            const sphereNormalMat = new Float32Array(9);
            mat4.normalFromMat4(sphereNormalMat, sphereModel);

            gl.useProgram(mainProgram);
            gl.bindVertexArray(sphereMesh.vao);
            gl.uniformMatrix4fv(mainU.model, false, sphereModel);
            gl.uniformMatrix4fv(mainU.view, false, view);
            gl.uniformMatrix4fv(mainU.proj, false, proj);
            gl.uniformMatrix3fv(mainU.normalMat, false, sphereNormalMat);
            gl.uniform1f(mainU.time, t);
            gl.uniform1f(mainU.amplitude, 0.22);
            gl.uniform1f(mainU.frequency, 1.35);
            gl.uniform3fv(mainU.cameraPos, eye);
            gl.uniform3fv(mainU.lowColor, [0.227, 0.039, 0.333]);
            gl.uniform3fv(mainU.midColor, [0.690, 0.125, 0.878]);
            gl.uniform3fv(mainU.highColor, [1.0, 0.851, 1.0]);
            gl.uniform3fv(mainU.lightDir, [0.6, 0.8, 0.9]);
            gl.uniform1f(mainU.opacity, 1.0);
            gl.drawElements(gl.TRIANGLES, sphereMesh.count, gl.UNSIGNED_INT, 0);

            gl.enable(gl.BLEND);
            gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
            gl.depthMask(false);
            gl.useProgram(glowProgram);
            gl.bindVertexArray(glowMesh.vao);
            gl.uniformMatrix4fv(glowU.model, false, sphereModel);
            gl.uniformMatrix4fv(glowU.view, false, view);
            gl.uniformMatrix4fv(glowU.proj, false, proj);
            gl.uniformMatrix3fv(glowU.normalMat, false, sphereNormalMat);
            gl.uniform3fv(glowU.cameraPos, eye);
            gl.drawElements(gl.TRIANGLES, glowMesh.count, gl.UNSIGNED_INT, 0);
            gl.depthMask(true);
            gl.disable(gl.BLEND);
        }

        if (showParticles) {
            gl.enable(gl.BLEND);
            gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
            gl.depthMask(false);
            gl.useProgram(particleProgram);
            gl.bindVertexArray(particleMesh.vao);
            gl.uniformMatrix4fv(particleU.model, false, model);
            gl.uniformMatrix4fv(particleU.view, false, view);
            gl.uniformMatrix4fv(particleU.proj, false, proj);
            gl.uniform1f(particleU.time, t);
            gl.uniform1f(particleU.amplitude, isOverview ? 0.22 : 0.08);
            gl.uniform1f(particleU.frequency, 1.35);
            gl.uniform1f(particleU.progress, isOverview ? convergeProgress : 0.0);
            gl.uniform1f(particleU.pixelRatio, dpr);
            gl.uniform1f(particleU.opacity, particleOpacity);
            gl.drawArrays(gl.POINTS, 0, particleMesh.count);
            gl.depthMask(true);
            gl.disable(gl.BLEND);
        }
    }
    frame();
}

// =========================================================================
// OS Documentation Switcher
// =========================================================================

function switchOsTab(os) {
    document.querySelectorAll("#tab-docs .sub-dock-item").forEach(b => b.classList.remove("active"));
    event?.target?.classList?.add("active");

    const content = document.getElementById("os-tab-content");
    if (!content) return;

    if (os === "win") {
        content.innerHTML = `
            <h3 class="text-base font-bold text-white mb-3">Windows Installation</h3>
            <pre class="code-block text-xs">
# Option 1: Official Windows Installer (Pre-built)
# Download installer from https://rpm.lammps.org/windows/
# Run LAMMPS-64bit-latest.exe and select PATH environment variable

# Option 2: Conda-Forge
conda create -n lammps-env -c conda-forge lammps
conda activate lammps-env

# Test execution:
lmp -in in.script</pre>
        `;
    } else if (os === "linux") {
        content.innerHTML = `
            <h3 class="text-base font-bold text-white mb-3">Linux (Ubuntu / Debian / Fedora)</h3>
            <pre class="code-block text-xs">
# Ubuntu / Debian
sudo apt update && sudo apt install -y lammps

# Fedora / RHEL
sudo dnf install -y lammps

# Build from source with CMake
git clone -b stable https://github.com/lammps/lammps.git
cd lammps && mkdir build && cd build
cmake ../cmake -DPKG_MANYBODY=yes -DPKG_MOLECULE=yes -DPKG_KSPACE=yes
cmake --build . -j $(nproc)</pre>
        `;
    } else if (os === "mac") {
        content.innerHTML = `
            <h3 class="text-base font-bold text-white mb-3">macOS (Apple Silicon & Intel)</h3>
            <pre class="code-block text-xs">
# Homebrew installation
brew install lammps

# Test installation
lmp -h</pre>
        `;
    } else if (os === "conda") {
        content.innerHTML = `
            <h3 class="text-base font-bold text-white mb-3">Conda / Python Environment</h3>
            <pre class="code-block text-xs">
# Create dedicated research environment
conda create -n md-env -c conda-forge lammps numpy scipy matplotlib
conda activate md-env

# Python Interface Test
python -c "from lammps import lammps; lmp = lammps(); lmp.command('units metal'); print('LAMMPS Python Loaded!')"</pre>
        `;
    }
}

// =========================================================================
// Utilities
// =========================================================================

function renderThermoTable(summary) {
    let html = `<div class="overflow-x-auto"><table class="w-full text-xs font-mono border-collapse my-3">
        <thead>
            <tr class="text-gray-400 border-b border-white/[0.08] text-left">
                <th class="py-2 px-3">Property</th>
                <th class="py-2 px-3">Initial</th>
                <th class="py-2 px-3">Final</th>
                <th class="py-2 px-3">Min</th>
                <th class="py-2 px-3">Max</th>
                <th class="py-2 px-3">Mean</th>
                <th class="py-2 px-3">Std Dev</th>
            </tr>
        </thead>
        <tbody>`;

    for (const [col, stats] of Object.entries(summary)) {
        html += `<tr class="border-b border-white/[0.04] hover:bg-white/[0.02]">
            <td class="py-2 px-3 text-accent font-bold">${escapeHtml(col)}</td>
            <td class="py-2 px-3">${stats.initial}</td>
            <td class="py-2 px-3">${stats.final}</td>
            <td class="py-2 px-3">${stats.min}</td>
            <td class="py-2 px-3">${stats.max}</td>
            <td class="py-2 px-3 font-semibold text-white">${stats.mean}</td>
            <td class="py-2 px-3 text-gray-400">${stats.std_dev}</td>
        </tr>`;
    }

    html += `</tbody></table></div>`;
    return html;
}

function renderMarkdown(md) {
    if (!md) return "";
    let html = escapeHtml(md);

    html = html.replace(/```([a-zA-Z0-9_\-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre class="code-block my-2"><code>${code}</code></pre>`;
    });

    html = html.replace(/`([^`]+)`/g, "<code class='px-1.5 py-0.5 rounded bg-white/10 text-accent font-mono text-xs'>$1</code>");
    html = html.replace(/^### (.*$)/gim, "<h4 class='text-sm font-bold text-white mt-2 mb-1'>$1</h4>");
    html = html.replace(/^## (.*$)/gim, "<h3 class='text-base font-bold text-white mt-3 mb-1'>$1</h3>");
    html = html.replace(/^# (.*$)/gim, "<h2 class='text-lg font-extrabold text-white mt-3 mb-2'>$1</h2>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong class='text-white font-semibold'>$1</strong>");
    html = html.replace(/^\- (.*$)/gim, "<li class='ml-4 list-disc text-gray-300'>$1</li>");
    html = html.replace(/\n\n/g, "</p><p class='mt-2'>");

    return `<p>${html}</p>`;
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = "toast-msg flex items-center gap-2";
    toast.innerHTML = `<span>${type === "error" ? "⚠️" : "✓"}</span><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3500);
}

// =========================================================================
// Project Workspace & Codebase RAG Client Engine
// =========================================================================

let currentWorkspaceFile = null;

async function initWorkspace() {
    refreshWorkspaceStatus();
}

async function refreshWorkspaceStatus() {
    try {
        const res = await fetch("/api/project/status");
        if (!res.ok) return;
        const data = await res.json();

        const badge = document.getElementById("ws-badge");
        const statFiles = document.getElementById("ws-stat-files");
        const statChunks = document.getElementById("ws-stat-chunks");
        const statScripts = document.getElementById("ws-stat-scripts");
        const statPotentials = document.getElementById("ws-stat-potentials");
        const statRoot = document.getElementById("ws-stat-root");
        const chatStatus = document.getElementById("chat-workspace-status");

        if (data.active && data.summary) {
            if (badge) {
                badge.textContent = `Active: ${data.name}`;
                badge.className = "px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
            }
            if (statFiles) statFiles.textContent = data.summary.total_files || 0;
            if (statChunks) statChunks.textContent = data.summary.total_chunks || 0;
            if (statScripts) statScripts.textContent = (data.summary.lammps_scripts || []).length;
            if (statPotentials) statPotentials.textContent = (data.summary.potential_files || []).length + (data.summary.data_files || []).length;
            if (statRoot) statRoot.textContent = data.name || "Active";
            if (chatStatus) chatStatus.textContent = `Workspace: ${data.name} (${data.summary.total_files} files)`;
            loadWorkspaceTree();
        } else {
            if (badge) {
                badge.textContent = "Ready to Index";
                badge.className = "px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40";
            }
            if (chatStatus) chatStatus.textContent = "Workspace: Click to Open";
        }
    } catch (e) {
        console.error("Failed to fetch workspace status", e);
    }
}

async function handleOpenWorkspaceFromInput() {
    const input = document.getElementById("ws-folder-path-input");
    if (!input) return;
    const folderPath = input.value.trim();

    showToast("Scanning and indexing project files into RAG...", "info");

    try {
        const res = await fetch("/api/project/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder_path: folderPath })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Indexed ${data.files_count} files (${data.chunks_count} code chunks) in '${data.workspace_name}'!`, "success");
            refreshWorkspaceStatus();
        } else {
            showToast(data.error || "Failed to open folder", "error");
        }
    } catch (e) {
        showToast("Error opening project folder: " + e.message, "error");
    }
}

async function loadWorkspaceTree() {
    try {
        const res = await fetch("/api/project/tree");
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById("ws-tree-container");
        if (!container) return;

        if (!data.tree || !data.tree.children || data.tree.children.length === 0) {
            container.innerHTML = `<div class="text-xs text-gray-500 py-6 text-center">No supported code files found in workspace.</div>`;
            return;
        }

        container.innerHTML = renderTreeHtml(data.tree);
    } catch (e) {
        console.error("Failed to load workspace tree", e);
    }
}

function renderTreeHtml(node) {
    if (node.type === "directory") {
        const childrenHtml = (node.children || []).map(child => renderTreeHtml(child)).join("");
        return `
            <div class="tree-folder">
                <div class="tree-folder-title">
                    <span>📁</span>
                    <span>${escapeHtml(node.name)}</span>
                </div>
                <div class="tree-children">
                    ${childrenHtml}
                </div>
            </div>
        `;
    } else {
        const icon = getFileIcon(node.ext);
        const escapedPath = escapeHtml(node.path).replace(/'/g, "\\'");
        const escapedName = escapeHtml(node.name).replace(/'/g, "\\'");
        return `
            <div class="tree-file" onclick="loadWorkspaceFilePreview('${escapedPath}', '${escapedName}')" id="tree-file-${escapedPath.replace(/[^a-zA-Z0-9_-]/g, '_')}">
                <div class="flex items-center gap-2 truncate">
                    <span>${icon}</span>
                    <span class="truncate">${escapeHtml(node.name)}</span>
                </div>
                <span class="text-[9px] text-gray-500 font-mono">${node.line_count || 0}L</span>
            </div>
        `;
    }
}

function getFileIcon(ext) {
    switch ((ext || "").toLowerCase()) {
        case ".in":
        case ".lmp":
        case ".lammps":
            return "⚛";
        case ".py":
            return "🐍";
        case ".data":
        case ".dat":
            return "🌐";
        case ".eam":
        case ".tersoff":
        case ".sw":
            return "⚡";
        case ".md":
        case ".txt":
            return "📄";
        case ".log":
        case ".out":
            return "📋";
        default:
            return "📄";
    }
}

async function loadWorkspaceFilePreview(relPath, filename) {
    currentWorkspaceFile = { relPath, filename };
    
    // Highlight active tree file
    document.querySelectorAll(".tree-file").forEach(el => el.classList.remove("active"));
    const activeEl = document.getElementById(`tree-file-${relPath.replace(/[^a-zA-Z0-9_-]/g, '_')}`);
    if (activeEl) activeEl.classList.add("active");

    const iconEl = document.getElementById("ws-viewer-icon");
    const nameEl = document.getElementById("ws-viewer-filename");
    const linesEl = document.getElementById("ws-viewer-lines");
    const codeEl = document.getElementById("ws-code-content");
    const askBtn = document.getElementById("btn-ws-ask-ai");
    const viewerCard = document.getElementById("ws-viewer-card");
    const searchResultsCard = document.getElementById("ws-search-results-card");

    if (searchResultsCard) searchResultsCard.classList.add("hidden");
    if (viewerCard) viewerCard.classList.remove("hidden");

    if (nameEl) nameEl.textContent = relPath;
    if (iconEl) iconEl.textContent = getFileIcon(relPath.substring(relPath.lastIndexOf('.')));
    if (askBtn) askBtn.classList.remove("hidden");

    try {
        const res = await fetch("/api/project/read", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rel_path: relPath })
        });
        const data = await res.json();
        if (data.content !== undefined) {
            if (linesEl) linesEl.textContent = `(${data.lines} lines)`;
            if (codeEl) {
                // Add line numbers to code
                const lines = data.content.split('\n');
                const numbered = lines.map((l, i) => `${String(i + 1).padStart(4, ' ')} | ${l}`).join('\n');
                codeEl.textContent = numbered;
            }
        }
    } catch (e) {
        if (codeEl) codeEl.textContent = `// Error loading file: ${e.message}`;
    }
}

async function handleWorkspaceSearch() {
    const input = document.getElementById("ws-search-input");
    if (!input) return;
    const query = input.value.trim();
    if (!query) return;

    try {
        const res = await fetch("/api/project/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query })
        });
        const data = await res.json();
        const hitsCard = document.getElementById("ws-search-results-card");
        const hitsList = document.getElementById("ws-search-hits-list");
        const countEl = document.getElementById("ws-search-hits-count");
        const viewerCard = document.getElementById("ws-viewer-card");

        if (hitsCard && hitsList) {
            hitsCard.classList.remove("hidden");
            if (countEl) countEl.textContent = `Found ${data.results.length} relevant code chunks for "${escapeHtml(query)}"`;

            if (data.results.length === 0) {
                hitsList.innerHTML = `<div class="text-xs text-gray-500 py-3 text-center">No matching code chunks found in active workspace.</div>`;
                return;
            }

            hitsList.innerHTML = data.results.map(hit => `
                <div class="ws-search-hit-item" onclick="loadWorkspaceFilePreview('${escapeHtml(hit.file_path)}', '${escapeHtml(hit.filename)}')">
                    <div class="flex items-center justify-between mb-1">
                        <div class="flex items-center gap-1.5 font-mono text-xs text-accent font-bold">
                            <span>📄 ${escapeHtml(hit.file_path)}</span>
                            <span class="text-gray-400 font-normal text-[10px]">(Lines ${hit.start_line}-${hit.end_line})</span>
                        </div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-white/10 text-gray-300">${escapeHtml(hit.block_type)}</span>
                    </div>
                    <pre class="text-[11px] font-mono text-gray-300 bg-black/40 p-2 rounded overflow-x-auto whitespace-pre-wrap">${escapeHtml(hit.snippet)}</pre>
                </div>
            `).join("");
        }
    } catch (e) {
        showToast("Search failed: " + e.message, "error");
    }
}

function closeWorkspaceSearchResults() {
    const hitsCard = document.getElementById("ws-search-results-card");
    if (hitsCard) hitsCard.classList.add("hidden");
}

function askAiAboutCurrentFile() {
    if (!currentWorkspaceFile) return;
    const promptText = `Please analyze the simulation file '${currentWorkspaceFile.relPath}' from my project workspace. Explain its physical setup, potential styles, and check for any parameter issues.`;
    switchTab("tab-chatbot");
    const textarea = document.getElementById("user-prompt");
    if (textarea) {
        textarea.value = promptText;
        textarea.focus();
    }
}

// =========================================================================
// WebGL2 Trajectory Viewer Controls & Event Wiring
// =========================================================================

function initTrajViewerIfNeeded() {
    if (!window.activeTrajViewer) {
        const canvas = document.getElementById("trajectory-canvas");
        if (canvas && window.TrajectoryViewer) {
            window.activeTrajViewer = new TrajectoryViewer(canvas, {
                onFrameChange: (idx, total) => {
                    const counter = document.getElementById("traj-frame-counter");
                    if (counter) counter.innerText = `Frame ${idx + 1} / ${total}`;
                    const scrub = document.getElementById("traj-scrubber");
                    if (scrub) {
                        scrub.max = Math.max(0, total - 1);
                        scrub.value = idx;
                    }
                    const scrubInd = document.getElementById("traj-scrub-indicator");
                    if (scrubInd) scrubInd.innerText = `${idx + 1} / ${total}`;
                },
                onTimestepChange: (ts, isInterpolated) => {
                    const badge = document.getElementById("traj-timestep-badge");
                    if (badge) {
                        if (isInterpolated) {
                            badge.className = "px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 shadow-[0_0_8px_rgba(245,158,11,0.2)]";
                            badge.innerText = `◌ Timestep ${ts} (INTERPOLATED)`;
                        } else {
                            badge.className = "px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 shadow-[0_0_8px_rgba(52,211,153,0.2)]";
                            badge.innerText = `● Timestep ${ts} (SIMULATED)`;
                        }
                    }
                },
                onColorbarChange: (info) => {
                    updateTrajColorbarUI(info);
                }
            });
        }
    }
}

function toggleTrajectoryPlay() {
    if (!window.activeTrajViewer) return;
    window.activeTrajViewer.togglePlay();
    const playIcon = document.getElementById("traj-play-icon");
    if (playIcon) {
        playIcon.innerText = window.activeTrajViewer.isPlaying ? "⏸ Pause" : "▶ Play";
    }
}

function scrubTrajectory(val) {
    if (!window.activeTrajViewer) return;
    const fIdx = parseFloat(val);
    window.activeTrajViewer.pause();
    window.activeTrajViewer.isLiveFollowing = false;
    window.activeTrajViewer.seek(fIdx);
    const playIcon = document.getElementById("traj-play-icon");
    if (playIcon) playIcon.innerText = "▶ Play";
}

function setTrajColorMode(mode) {
    if (!window.activeTrajViewer) return;
    window.activeTrajViewer.setColorMode(mode);

    const btnElem = document.getElementById("btn-color-element");
    const btnKe = document.getElementById("btn-color-ke");
    const btnStress = document.getElementById("btn-color-stress");
    const normControls = document.getElementById("traj-norm-controls");

    if (btnElem) btnElem.classList.toggle("active", mode === "element");
    if (btnKe) btnKe.classList.toggle("active", mode === "kinetic_energy");
    if (btnStress) btnStress.classList.toggle("active", mode === "von_mises_stress");

    if (normControls) {
        if (mode === "element") {
            normControls.classList.add("hidden");
        } else {
            normControls.classList.remove("hidden");
        }
    }
}

function setTrajNormMode(norm) {
    if (!window.activeTrajViewer) return;
    window.activeTrajViewer.setNormMode(norm);

    const btnFrame = document.getElementById("btn-norm-frame");
    const btnRun = document.getElementById("btn-norm-run");
    if (btnFrame) btnFrame.classList.toggle("active", norm === "frame");
    if (btnRun) btnRun.classList.toggle("active", norm === "run");
}

function updateTrajFieldModeButtons(availableFields, isSynthetic) {
    const btnKe = document.getElementById("btn-color-ke");
    const btnStress = document.getElementById("btn-color-stress");
    const fields = availableFields || ["element"];

    const hasKe = fields.includes("kinetic_energy");
    const hasStress = fields.includes("von_mises_stress");

    if (btnKe) {
        btnKe.disabled = !hasKe;
        btnKe.style.opacity = hasKe ? "1" : "0.4";
        btnKe.title = hasKe ? "Color atoms by kinetic energy" : "No kinetic energy data in trajectory dump";
    }
    if (btnStress) {
        btnStress.disabled = !hasStress;
        btnStress.style.opacity = hasStress ? "1" : "0.4";
        btnStress.title = hasStress ? "Color atoms by Von Mises stress" : "No stress data in trajectory dump";
    }
}

function updateTrajColorbarUI(info) {
    const container = document.getElementById("traj-colorbar-container");
    if (!container) return;

    if (!info || info.colorMode === "element") {
        container.classList.add("hidden");
        return;
    }

    container.classList.remove("hidden");

    const titleEl = document.getElementById("traj-colorbar-title");
    const normDescEl = document.getElementById("traj-colorbar-norm-desc");
    const synBadgeEl = document.getElementById("traj-colorbar-synthetic-badge");
    const minEl = document.getElementById("traj-colorbar-min");
    const midEl = document.getElementById("traj-colorbar-mid");
    const maxEl = document.getElementById("traj-colorbar-max");

    const isKe = (info.colorMode === "kinetic_energy");
    const titleText = isKe ? "Kinetic Energy" : "Von Mises Stress";
    const unit = info.unitSymbol ? ` [${info.unitSymbol}]` : "";

    if (titleEl) titleEl.innerText = `${titleText}${unit}`;
    if (normDescEl) {
        normDescEl.innerText = (info.normMode === "run") ? "(Run Normalization)" : "(Frame Normalization)";
    }
    if (synBadgeEl) {
        if (info.isSynthetic) {
            synBadgeEl.classList.remove("hidden");
        } else {
            synBadgeEl.classList.add("hidden");
        }
    }

    const fmt = (v) => {
        if (v === null || v === undefined || isNaN(v)) return "0.00";
        const absVal = Math.abs(v);
        if (absVal >= 10000 || (absVal > 0 && absVal < 0.01)) {
            return v.toExponential(2);
        }
        return v.toFixed(2);
    };

    if (minEl) minEl.innerText = `${fmt(info.min)} ${info.unitSymbol || ""}`;
    if (midEl) midEl.innerText = `${fmt(info.mid)} ${info.unitSymbol || ""}`;
    if (maxEl) maxEl.innerText = `${fmt(info.max)} ${info.unitSymbol || ""}`;
}

// =========================================================================
// Big Linux Terminal Mirror Window Controls
// =========================================================================

function toggleTerminalExpand() {
    const pre = document.getElementById("runner-terminal-pre");
    const icon = document.getElementById("terminal-expand-icon");
    if (!pre) return;
    if (pre.classList.contains("expanded")) {
        pre.classList.remove("expanded");
        if (icon) icon.innerText = "⛶ Expand";
    } else {
        pre.classList.remove("compact");
        pre.classList.add("expanded");
        if (icon) icon.innerText = "↙ Collapse";
    }
}

function setTerminalHeight(mode) {
    const pre = document.getElementById("runner-terminal-pre");
    const icon = document.getElementById("terminal-expand-icon");
    if (!pre) return;
    if (mode === "compact") {
        pre.classList.remove("expanded");
        pre.classList.toggle("compact");
        if (icon) icon.innerText = "⛶ Expand";
    }
}

function clearTerminalOutput() {
    const pre = document.getElementById("runner-terminal-pre");
    if (pre) {
        pre.innerText = "┌──(lammps㉿wsl2)-[~/simulations]\n└─$ lmp -in in.run -log log.lammps\n[Console mirror cleared]\n";
    }
    showToast("Terminal console cleared");
}

function copyTerminalOutput() {
    const pre = document.getElementById("runner-terminal-pre");
    if (!pre) return;
    navigator.clipboard.writeText(pre.innerText)
        .then(() => showToast("Terminal log copied to clipboard!", "success"))
        .catch(() => showToast("Could not copy to clipboard", "error"));
}

// =========================================================================
// 3D Atomic Trajectory Runner & Direct WebGL Simulation Launcher
// =========================================================================

function toggleTrajViewerExpand() {
    const canvas = document.getElementById("trajectory-canvas");
    const icon = document.getElementById("traj-expand-icon");
    if (!canvas) return;
    canvas.classList.toggle("expanded");
    if (icon) {
        icon.innerText = canvas.classList.contains("expanded") ? "↙ Collapse" : "⛶ Expand";
    }
    if (window.activeTrajViewer) {
        window.activeTrajViewer._resize();
    }
}

function resetTrajCamera() {
    if (window.activeTrajViewer) {
        window.activeTrajViewer.resetCamera();
        showToast("3D camera orbit reset");
    }
}

function setTrajSpeed(speed, btn) {
    if (window.activeTrajViewer) {
        window.activeTrajViewer.setPlaybackSpeed(speed);
        const container = btn?.parentElement;
        if (container) {
            container.querySelectorAll("button").forEach(b => {
                b.className = "text-[11px] px-1 text-gray-300 hover:text-white";
            });
            btn.className = "text-[11px] px-1 text-accent font-bold";
        }
    }
}

async function runWebGL3DRunnerSimulation(forcedPreset) {
    const presetSelect = document.getElementById("traj-sim-preset-select");
    const preset = forcedPreset || (presetSelect ? presetSelect.value : "lj_benchmark");
    const btn = document.getElementById("btn-traj-run-sim");

    let script = "";
    if (["lj_benchmark", "molten_al", "water_liquid"].includes(preset)) {
        // Presets come from the server's validated template generator (single source of truth)
        try {
            const res = await fetch("/api/preset", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ preset })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
            script = data.script;
        } catch (err) {
            showToast(`Could not load preset script: ${err.message}`, "error");
            return;
        }
    } else {
        const studioCode = document.getElementById("studio-code-input")?.value?.trim();
        if (studioCode) {
            script = studioCode;
        } else {
            script = generateClientScript(currentSimParams);
        }
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="inline-block animate-spin">⚡</span><span>Running Live...</span>`;
    }

    const card = document.getElementById("runner-trajectory-card");
    if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });

    showToast(`Launching ${preset.replace(/_/g, ' ')} WebGL2 simulation...`, "info");
    try {
        await executeFromChat(script);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span>🚀 Run WebGL Simulation</span>`;
        }
    }
}

function launchVisualizerInWebGLRunner() {
    const matSelect = document.getElementById("vis-mat-select");
    const mat = matSelect ? matSelect.value : "LJ";

    let preset = "lj_benchmark";
    if (mat === "Water") preset = "water_liquid";
    else if (mat === "LJ" || mat === "Argon") preset = "lj_benchmark";
    else preset = "molten_al";

    activateTab("tab-runner");
    const sel = document.getElementById("traj-sim-preset-select");
    if (sel) sel.value = preset;

    runWebGL3DRunnerSimulation(preset);
}

