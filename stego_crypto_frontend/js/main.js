import { createScrollConductor } from "./conductor.js?v=20261002b";
import { createWorld, CHAPTERS } from "./world.js?v=20261002b";
import { initWorkbench } from "./workbench.js?v=20261002b";
import { health } from "./api.js?v=20261002b";

const motionQuery = matchMedia("(prefers-reduced-motion: reduce)");
const body = document.body;
const $ = (id) => document.getElementById(id);
body.classList.toggle("reduce-motion", motionQuery.matches);

/* ─── Preloader ─── */
const boot = $("boot"), bootFill = $("boot-fill"), bootPct = $("boot-pct");
let bootValue = 0, bootDone = false;
function setBoot(v) {
  bootValue = Math.max(bootValue, v);
  bootFill.style.width = `${bootValue}%`;
  bootPct.textContent = String(Math.round(bootValue)).padStart(3, "0");
}
const bootTimer = setInterval(() => setBoot(Math.min(88, bootValue + 3 + Math.random() * 6)), 110);
function finishBoot() {
  if (bootDone) return;
  bootDone = true;
  clearInterval(bootTimer);
  setBoot(100);
  setTimeout(() => boot.classList.add("is-done"), motionQuery.matches ? 0 : 420);
}
setTimeout(finishBoot, 6000); // never hold the page hostage

/* ─── Split display headings into words; the heading keeps its full accessible label ─── */
for (const h of document.querySelectorAll(".copy h1, .copy h2")) {
  h.setAttribute("aria-label", h.textContent.replace(/\s+/g, " ").trim());
  let i = 0;
  const wrap = (node) => {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        child.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.append(" "); return; }
          const w = document.createElement("span");
          w.className = "w";
          w.setAttribute("aria-hidden", "true");
          const inner = document.createElement("span");
          inner.textContent = part;
          inner.style.setProperty("--i", i++);
          w.append(inner);
          frag.append(w);
        });
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        wrap(child);
      }
    }
  };
  wrap(h);
}

/* ─── Annotation tags: pinned to satellite parts every frame ─── */
const tags = [...document.querySelectorAll(".tag[data-part]")];
let focusPart = null;
let activeCopy = null;
function placeTags(world) {
  const copyRect = activeCopy ? activeCopy.getBoundingClientRect() : null;
  for (const tag of tags) {
    const anchor = world.anchors[tag.dataset.part];
    if (!anchor) continue;
    const s = world.project(anchor);
    // never let an annotation sit under the active copy panel: it would blur through the glass
    const hidden = s.visible && copyRect && s.x > copyRect.left - 24 && s.x < copyRect.right + 24 && s.y > copyRect.top - 24 && s.y < copyRect.bottom + 24;
    s.visible = s.visible && !hidden;
    tag.classList.toggle("is-on", s.visible);
    tag.classList.toggle("is-focus", s.visible && tag.dataset.part === focusPart);
    if (s.visible) tag.style.transform = `translate3d(${s.x - 5}px, ${s.y - 7}px, 0)`;
  }
}

/* ─── World ─── */
function worldNotice(why) {
  const n = document.createElement("p");
  n.className = "world-notice";
  n.setAttribute("role", "status");
  n.textContent = `The 3D view couldn’t start${why ? ` (${why})` : ""}. Try a hard reload (Ctrl+Shift+R); the story and the workbench still work.`;
  document.body.append(n);
}
let world = null;
try {
  world = createWorld($("world"), { reducedMotion: motionQuery.matches, onFirstFrame: finishBoot, onFrame: placeTags, onError: (e) => worldNotice(e?.message?.slice(0, 80)) });
} catch (err) {
  console.error("WebGL world unavailable:", err);
  worldNotice(err?.message?.slice(0, 80));
}
if (!world) { body.classList.add("no-webgl"); finishBoot(); }
else world.ready.then(() => setBoot(94));

/* ─── Chapters ↔ scroll ─── */
const debug = new URLSearchParams(location.search).has("debug");
const sections = [...document.querySelectorAll("[data-chapter]")];
const railButtons = document.querySelectorAll(".rail [data-goto]");
const last = sections.length - 1;

const conductor = createScrollConductor({
  sections,
  reducedMotion: motionQuery.matches,
  onUpdate(state) { world?.setProgress(state.smooth); },
  onChapterChange(index) {
    sections.forEach((s, i) => s.classList.toggle("is-active", i === index));
    railButtons.forEach((b) => (Number(b.dataset.goto) === index ? b.setAttribute("aria-current", "step") : b.removeAttribute("aria-current")));
    body.dataset.side = CHAPTERS[index]?.side || "left";
    body.classList.toggle("in-workbench", index === last);
    focusPart = CHAPTERS[index]?.part ?? null;
    body.classList.add("story-ready");
    activeCopy = sections[index]?.querySelector(".copy") ?? null;
  },
}).start();

// ?debug: expose the rig and skip camera damping, for framing checks.
if (debug) { window.__ss = { world, conductor }; conductor.setReducedMotion(true); }

for (const btn of document.querySelectorAll("[data-goto]")) {
  btn.addEventListener("click", () => conductor.goTo(Number(btn.dataset.goto)));
}

motionQuery.addEventListener("change", (e) => {
  body.classList.toggle("reduce-motion", e.matches);
  conductor.setReducedMotion(e.matches);
  world?.setReducedMotion(e.matches);
});

document.fonts?.ready.then(() => conductor.measure());

/* ─── Cursor (fine pointers, motion allowed) ─── */
if (matchMedia("(pointer: fine)").matches && !motionQuery.matches) {
  const cur = $("cursor");
  let x = innerWidth / 2, y = innerHeight / 2, cx = x, cy = y;
  addEventListener("pointermove", (e) => {
    x = e.clientX; y = e.clientY;
    body.classList.add("has-cursor");
    cur.classList.toggle("is-hot", Boolean(e.target.closest?.("a, button, [role=tab], label")));
  }, { passive: true });
  document.addEventListener("pointerleave", () => body.classList.remove("has-cursor"));
  (function follow() {
    cx += (x - cx) * 0.22; cy += (y - cy) * 0.22;
    cur.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
    requestAnimationFrame(follow);
  })();
}

/* ─── Workbench + API status ─── */
initWorkbench();

const status = $("api-status");
async function ping() {
  const up = await health();
  status.dataset.state = up ? "up" : "down";
  status.querySelector(".label").textContent = up ? "API connected" : "API offline";
}
ping();
setInterval(ping, 15000);
