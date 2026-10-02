/* Native-scroll conductor: maps document scroll to a fractional chapter value.
   Adapted from MengTo/Skills build-threejs-scroll-worlds/references/scroll-conductor.js (MIT).
   Native scroll stays the source of truth; `exact` drives DOM state, `smooth` drives the camera. */

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const damp = (cur, target, lambda, dt) => cur + (target - cur) * (1 - Math.exp(-lambda * dt));

export function createScrollConductor({ sections, damping = 5.2, reducedMotion = false, onUpdate = () => {}, onChapterChange = () => {} }) {
  sections = Array.from(sections);
  let anchors = [];
  let exact = 0;
  let smooth = 0;
  let active = -1;
  let running = false;
  let frame = 0;
  let last = 0;
  let dirty = true;
  let widthAtMeasure = 0;
  let reduce = reducedMotion;
  let observer = null;

  const maxScroll = () => Math.max(1, document.documentElement.scrollHeight - innerHeight);

  function measure() {
    const max = maxScroll();
    widthAtMeasure = innerWidth;
    anchors = sections.map((el, i) => {
      if (i === 0) return 0;
      if (i === sections.length - 1) return clamp(el.offsetTop - innerHeight * 0.15, 0, max);
      return clamp(el.offsetTop + el.offsetHeight * 0.5 - innerHeight * 0.5, 0, max);
    });
    for (let i = 1; i < anchors.length; i++) anchors[i] = Math.max(anchors[i], anchors[i - 1] + 1);
    dirty = true;
  }

  function progressAt(y) {
    y = clamp(y, 0, maxScroll());
    if (y <= anchors[0]) return 0;
    for (let i = 0; i < anchors.length - 1; i++) {
      if (y <= anchors[i + 1]) return i + clamp((y - anchors[i]) / Math.max(1, anchors[i + 1] - anchors[i]), 0, 1);
    }
    return anchors.length - 1;
  }

  const state = () => ({ exact, smooth, index: Math.round(exact), anchors });

  function read() {
    exact = progressAt(scrollY);
    dirty = true;
  }

  function tick(now) {
    if (!running) return;
    const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
    last = now;
    const prev = smooth;
    smooth = reduce ? exact : damp(smooth, exact, damping, dt);
    if (Math.abs(smooth - exact) < 1e-4) smooth = exact;

    const s = state();
    if (s.index !== active) {
      active = s.index;
      onChapterChange(active, s);
    }
    if (dirty || smooth !== prev) {
      dirty = false;
      onUpdate(s, dt);
    }
    frame = requestAnimationFrame(tick);
  }

  function onResize() {
    const coarse = matchMedia("(pointer: coarse)").matches;
    if (coarse && innerWidth === widthAtMeasure) return; // ignore mobile URL-bar resizes
    measure();
    read();
  }

  function onVisibility() {
    if (document.hidden) {
      cancelAnimationFrame(frame);
      frame = 0;
      last = 0;
    } else if (running && !frame) {
      frame = requestAnimationFrame(tick);
    }
  }

  return {
    start() {
      if (running) return this;
      running = true;
      measure();
      read();
      smooth = exact;
      addEventListener("scroll", read, { passive: true });
      addEventListener("resize", onResize, { passive: true });
      document.addEventListener("visibilitychange", onVisibility);
      if ("ResizeObserver" in window) {
        observer = new ResizeObserver(() => { measure(); read(); });
        observer.observe(document.body);
      }
      frame = requestAnimationFrame(tick);
      return this;
    },
    goTo(i) {
      i = clamp(Math.round(i), 0, anchors.length - 1);
      scrollTo({ top: anchors[i], behavior: reduce ? "auto" : "smooth" });
    },
    setReducedMotion(v) { reduce = v; if (v) smooth = exact; dirty = true; },
    getState: state,
    measure,
  };
}
