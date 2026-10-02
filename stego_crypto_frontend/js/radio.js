/* Live transmission client, shared by the Workbench "Transmit a message" tool and the
   chapter 02 live check. Both end up emitting `ss:radio` so every readout stays in step. */

import { getJSON, postJSON, ApiError } from "./api.js?v=20261002b";

export const SF_OPTIONS = [16, 32, 64, 128];
const BUNDLE_OVERHEAD = 306;          // RSA-wrapped key + nonce + tag + header, measured from the flowgraph
const FIXED_CHIPS = 512 + 255 + 512;  // lock tones + preamble + trail flush
const SPS = 4, SAMPLE_RATE = 200_000;

let statusCache = null;
export async function radioStatus() {
  if (statusCache) return statusCache;
  try {
    statusCache = await getJSON("/api/radio/status");
  } catch {
    statusCache = { available: false, signal_power: 0.25, spreading_factors: SF_OPTIONS, max_message_chars: 1000, detail: "The radio API is not reachable." };
  }
  return statusCache;
}

/** Predicted size of a transmission before sending it (exact for the current flowgraph). */
export function estimate(message, sf) {
  const bundleBytes = BUNDLE_OVERHEAD + new TextEncoder().encode(message).length;
  const chips = bundleBytes * 8 * sf + FIXED_CHIPS;
  return { bundleBytes, chips, processingGainDb: 10 * Math.log10(sf), durationS: (chips * SPS) / SAMPLE_RATE };
}

/** Per-sample SNR of the channel for a given noise sigma (signal power is constant). */
export const snrDb = (sigma, power = 0.25) => (sigma > 0 ? 10 * Math.log10(power / (sigma * sigma)) : Infinity);

const emit = (detail) => document.dispatchEvent(new CustomEvent("ss:radio", { detail }));
const busy = (on, phase) => document.dispatchEvent(new CustomEvent("ss:radio-busy", { detail: { on, phase } }));

export async function transmit({ message, spreadingFactor, noiseVoltage }) {
  const t0 = performance.now();
  busy(true, "tx");
  try {
    const tx = await postJSON("/api/radio/transmit", { message, spreading_factor: spreadingFactor, noise_voltage: noiseVoltage });
    tx.elapsedMs = performance.now() - t0;
    emit({ stage: "transmit", tx });
    return tx;
  } finally {
    busy(false, "tx");
  }
}

/** Resolves to the receive result, or throws ApiError (with `.data` readings when decoding failed). */
export async function receive(tx) {
  const t0 = performance.now();
  busy(true, "rx");
  try {
    const rx = await postJSON("/api/radio/receive", { transmission_id: tx.transmission_id });
    rx.elapsedMs = performance.now() - t0;
    emit({ stage: "receive", tx, rx, ok: true });
    return rx;
  } catch (err) {
    if (err instanceof ApiError && err.status === 400 && err.data) emit({ stage: "receive", tx, rx: err.data, ok: false });
    throw err;
  } finally {
    busy(false, "rx");
  }
}

/* ─── chapter 02: live readings ─── */

const fmtSigma = (v) => v.toFixed(4);
const fmtDrift = (v) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(5)} rad/symbol`;

export function initChapterLive() {
  const root = document.getElementById("live-readings");
  if (!root) return;
  const noiseEl = root.querySelector('[data-live="noise"]');
  const driftEl = root.querySelector('[data-live="drift"]');
  const berEl = root.querySelector('[data-live="ber"]');
  const badge = document.querySelector(".live-badge");
  const source = document.getElementById("live-source");
  const button = document.getElementById("live-run");
  const msg = document.getElementById("live-msg");

  const setBadge = (live, text) => { badge.dataset.live = String(live); badge.textContent = text; };

  document.addEventListener("ss:radio", (e) => {
    const { stage, tx, rx, ok } = e.detail;
    if (stage === "transmit") {
      noiseEl.firstChild.textContent = `${fmtSigma(tx.measured_noise_std)} `;
      noiseEl.querySelector("small").textContent = `set ${tx.noise_voltage} · SF ${tx.spreading_factor}`;
      driftEl.firstChild.textContent = "awaiting receive ";
      driftEl.querySelector("small").textContent = `applied ${tx.applied_drift_rad.toFixed(5)} rad/sample`;
      berEl.firstChild.textContent = "awaiting receive ";
      berEl.querySelector("small").textContent = "";
      setBadge(true, "Live · transmitted");
      source.textContent = "Live readings from your most recent transmission.";
    } else if (stage === "receive") {
      driftEl.firstChild.textContent = rx.residual_drift_rad == null ? "n/a " : `${fmtDrift(rx.residual_drift_rad)} `;
      driftEl.querySelector("small").textContent = `applied ${tx.applied_drift_rad.toFixed(5)} rad/sample`;
      berEl.firstChild.textContent = `${rx.bit_errors} / ${rx.total_bits} bits `;
      berEl.querySelector("small").textContent = `BER ${rx.ber.toFixed(4)} · EVM ${rx.evm_db.toFixed(1)} dB${ok ? "" : " · not decodable"}`;
      setBadge(true, ok ? "Live · decoded" : "Live · lost lock");
    }
  });

  if (!button) return;
  button.addEventListener("click", async () => {
    const label = button.textContent;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = "Running the flowgraph…";
    try {
      const status = await radioStatus();
      if (!status.available) throw new ApiError(status.detail || "The GNU Radio runtime isn’t available.");
      const tx = await transmit({ message: msg.dataset.message, spreadingFactor: 16, noiseVoltage: 0.02 });
      await receive(tx);
    } catch (err) {
      setBadge(false, "Live check failed");
      source.textContent = err.message;
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.textContent = label;
    }
  });
}
