/* SentinelSpread world: the SENTINEL ring ship in deep space, the camera circling it chapter by
   chapter. Native scroll drives a fractional chapter value; camera endpoints and every
   mechanism/look channel are interpolated from the ledger below.

   Camera language: eased travel between endpoints, a slow arc while you dwell in a chapter,
   banking that follows lateral speed, a lens that breathes on fast moves, and in the opening
   shot a drag-to-rotate turntable with inertia. */

import * as THREE from "three";
import { createPost } from "./world/post.js?v=20261002b";
import { buildSpace } from "./world/space.js?v=20261002b";
import { buildShip } from "./world/ship.js?v=20261002b";

/* Chapter ledger. side: where the copy sits. part: tag to emphasise. orbit: degrees swept
   while dwelling in the chapter. fx: open (bay door), beam (downlink), holo (hologram),
   audio (waveform ring), bloom, warm (grade), exposure, dim (world level). */
export const CHAPTERS = [
  { id: "hero", side: "left", part: null, cam: [33.5, 10.5, 19.5], tgt: [-4.5, -0.5, 4.2], fov: 40, orbit: 14, tilt: 4, roll: 0, ctl: [30, -7, 10],
    fx: { open: 0, beam: 0.55, holo: 0, audio: 0, bloom: 0.85, warm: 0.3, exposure: 1.05, dim: 1 } },
  { id: "encrypt", side: "left", part: "core", cam: [13.5, 1.25, 1.69], tgt: [9.13, -0.71, -1.17], fov: 42, orbit: -18, tilt: -5, roll: -8, ctl: [26, 7, 28],
    fx: { open: 1, beam: 0, holo: 0, audio: 0, bloom: 0.95, warm: 0.3, exposure: 1.05, dim: 1 } },
  { id: "transmit", side: "left", part: "hga", cam: [4.56, 4.75, 14], tgt: [-0.88, 5.43, 2.11], fov: 44, orbit: 22, tilt: 6, roll: 9, ctl: [18, 13, 20],
    fx: { open: 0, beam: 1, holo: 0, audio: 0, bloom: 1.05, warm: 0.25, exposure: 1.05, dim: 1 } },
  { id: "image", side: "left", part: "lens", cam: [2.22, 6.76, -8.18], tgt: [-2.47, 4.4, -11.27], fov: 42, orbit: -20, tilt: 5, roll: -10, ctl: [10, 16, 8],     // measured: smoothest, clears the hull (was whipping the view 8°/step)
    fx: { open: 0, beam: 0.2, holo: 1, audio: 0, bloom: 0.95, warm: 0.3, exposure: 1.05, dim: 1 } },
  { id: "audio", side: "right", part: "audio", cam: [-3.61, 4.05, 4.12], tgt: [-8.16, 2.05, 1.53], fov: 44, orbit: 24, tilt: -6, roll: 6, ctl: [4, 1, 22],        // a low pass; measured clearance 2.0, 2.9°/step
    fx: { open: 0, beam: 0.2, holo: 0, audio: 1, bloom: 1.0, warm: 0.3, exposure: 1.05, dim: 1 } },
  { id: "orbit", side: "left", part: null, cam: [-22, 11, 40], tgt: [-6, -5, -30], fov: 42, orbit: -10, tilt: 3, roll: -4, ctl: [-42, 26, 44],
    fx: { open: 0, beam: 0.7, holo: 0, audio: 0, bloom: 0.9, warm: 0.3, exposure: 1.0, dim: 1 } },
  { id: "workbench", side: "left", part: null, cam: [27, 13, 31], tgt: [-2, -1, 0], fov: 44, orbit: 0, tilt: 0, roll: 0, ctl: [27, 13, 31],
    fx: { open: 0, beam: 0.7, holo: 0, audio: 0, bloom: 0.9, warm: 0.3, exposure: 0.62, dim: 0.5 } },
];

const FX_KEYS = Object.keys(CHAPTERS[0].fx);
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const easeIO = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const smooth = (e0, e1, x) => { const t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
const damp = (cur, target, lambda, dt) => cur + (target - cur) * (1 - Math.exp(-lambda * dt));
const Y = new THREE.Vector3(0, 1, 0);

export function createWorld(canvas, { reducedMotion = false, onFirstFrame, onFrame, onError } = {}) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance" });
  } catch {
    return null;
  }
  if (!renderer.capabilities.isWebGL2) return null;
  renderer.setClearColor(0x03040a, 1);
  renderer.toneMapping = THREE.NoToneMapping;   // tone mapping happens in the composite pass

  const coarse = matchMedia("(pointer: coarse)").matches;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.05, 1200);
  scene.add(camera);

  const uniforms = { uTime: { value: 0 }, uScale: { value: 1000 }, uDim: { value: 1 } };
  const space = buildSpace(scene, camera, uniforms);
  // the sun casts soft shadows over the ship, so modules, trusses and wings shade one another
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  Object.assign(space.key.shadow.camera, { left: -17, right: 17, top: 17, bottom: -17, near: 20, far: 120 });
  space.key.shadow.mapSize.set(coarse ? 1024 : 2048, coarse ? 1024 : 2048);
  space.key.shadow.bias = -0.0004;
  space.key.shadow.normalBias = 0.04;
  space.key.castShadow = true;
  const post = createPost(renderer, { lite: coarse });
  post.params.uAberr.value = 0.22;
  post.params.uScan.value = 0;
  post.params.uGrain.value = 0.03;
  let ship = null;

  // Each chapter-to-chapter move is a quadratic Bezier bent through that chapter's `ctl`, so every
  // move swoops a different way (under, over, around) instead of one smooth drift.
  let rigPos = [], rigCtl = [], rigTgt = [], mobile = null;
  function buildRig() {
    const isMobile = innerWidth < 720;
    if (isMobile === mobile) return;
    mobile = isMobile;
    const away = (pt, tgt) => (mobile ? tgt.clone().add(pt.clone().sub(tgt).multiplyScalar(1.45)) : pt.clone());
    rigTgt = CHAPTERS.map((c) => new THREE.Vector3(...c.tgt));
    rigPos = CHAPTERS.map((c, i) => away(new THREE.Vector3(...c.cam), rigTgt[i]));
    rigCtl = CHAPTERS.map((c, i) => away(new THREE.Vector3(...c.ctl), rigTgt[Math.min(i + 1, CHAPTERS.length - 1)]));
  }
  const bezier = (p0, c, p1, t, out) => {
    const u = 1 - t;
    return out.set(
      u * u * p0.x + 2 * u * t * c.x + t * t * p1.x,
      u * u * p0.y + 2 * u * t * c.y + t * t * p1.y,
      u * u * p0.z + 2 * u * t * c.z + t * t * p1.z,
    );
  };

  function resize() {
    if (!innerWidth || !innerHeight) return;   // a hidden or zero-size pane: nothing to render into
    renderer.setPixelRatio(Math.min(devicePixelRatio, coarse ? 1.25 : 1.5));
    renderer.setSize(innerWidth, innerHeight, false);
    const { width, height } = renderer.getDrawingBufferSize(new THREE.Vector2());
    post.resize(width, height);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    buildRig();
  }

  /* ─── input: pointer parallax everywhere, drag-to-rotate in the opening shot ─── */
  const pointer = { x: 0, y: 0, sx: 0, sy: 0 };
  const fine = matchMedia("(pointer: fine)").matches && !reducedMotion;
  const spin = { yaw: 0, pitch: 0, vYaw: 0, vPitch: 0, dragging: false, lastX: 0, lastY: 0, idle: 0 };
  let progress = 0;
  const heroWeight = () => 1 - smooth(0.15, 0.8, progress);

  addEventListener("pointermove", (e) => {
    pointer.x = (e.clientX / innerWidth) * 2 - 1;
    pointer.y = (e.clientY / innerHeight) * 2 - 1;
    if (!spin.dragging) return;
    const dx = e.clientX - spin.lastX, dy = e.clientY - spin.lastY;
    spin.lastX = e.clientX; spin.lastY = e.clientY;
    spin.vYaw = -dx * 0.0055;
    spin.vPitch = e.pointerType === "touch" ? 0 : dy * 0.004;
    spin.yaw += spin.vYaw;
    spin.pitch = clamp(spin.pitch + spin.vPitch, -0.55, 0.65);
  }, { passive: true });
  addEventListener("pointerdown", (e) => {
    if (heroWeight() < 0.5 || e.button > 0) return;
    if (e.target.closest("a, button, input, select, textarea, label, .chips, .bar, .rail, .workbench")) return;
    spin.dragging = true; spin.lastX = e.clientX; spin.lastY = e.clientY; spin.idle = 0;
    document.body.classList.add("is-dragging");
  });
  const release = () => { spin.dragging = false; document.body.classList.remove("is-dragging"); };
  addEventListener("pointerup", release);
  addEventListener("pointercancel", release);

  const fx = { ...CHAPTERS[0].fx };
  const pos = new THREE.Vector3(), tgt = new THREE.Vector3(), off = new THREE.Vector3(), right = new THREE.Vector3(), up = new THREE.Vector3();
  const prevPos = new THREE.Vector3();
  let time = 0, lastNow = 0, raf = 0, frames = 0, first = true, roll = 0, breathe = 0, lastP = 0;
  let boost = 0, boostTarget = 0, boostHold = 0;       // a live GNU Radio transmission drives the dish beam
  document.addEventListener("ss:radio-busy", (e) => {
    boostTarget = e.detail.on ? 1 : 0;
    if (e.detail.on) boostHold = 0; else boostHold = 1.4;   // let the burst finish visibly
  });

  function resolve(dt) {
    const n = CHAPTERS.length - 1;
    const p = clamp(progress, 0, n);
    const i = Math.min(Math.floor(p), n - 1);
    const local = p - i;
    const A = CHAPTERS[i], B = CHAPTERS[i + 1];
    const t = easeIO(local);
    for (const k of FX_KEYS) fx[k] = lerp(A.fx[k], B.fx[k], t);
    boostHold = Math.max(0, boostHold - dt);
    boost = damp(boost, boostTarget || boostHold > 0 ? 1 : 0, boostTarget || boostHold > 0 ? 6 : 2, dt);
    fx.boost = boost;

    // eased travel along this segment's own swoop; the look-at target glides on a gentler ease
    bezier(rigPos[i], rigCtl[i], rigPos[i + 1], t, pos);
    tgt.lerpVectors(rigTgt[i], rigTgt[i + 1], smooth(0, 1, local));

    // dwell sweep: orbit (yaw) and tilt (pitch) around the subject while scrolling inside a chapter,
    // each chapter with its own signed amounts, zero at the boundaries
    const near = Math.round(p);
    const dwell = p - near;                                       // -0.5 … 0.5
    const fade = 1 - smooth(0.32, 0.5, Math.abs(dwell));
    const C = CHAPTERS[near];
    off.subVectors(pos, tgt).applyAxisAngle(Y, THREE.MathUtils.degToRad(C.orbit) * dwell * fade);
    right.crossVectors(Y, off).normalize();
    off.applyAxisAngle(right, THREE.MathUtils.degToRad(C.tilt) * dwell * fade);
    // behind the Workbench the ship turns slowly, so the clear glass has something moving behind it
    if (!reducedMotion) off.applyAxisAngle(Y, time * 0.045 * smooth(n - 1, n, p));
    pos.copy(tgt).add(off);

    // opening shot: drag-to-rotate turntable around the ship, with inertia and idle drift
    const hw = heroWeight();
    if (!spin.dragging) {
      // release inertia, time-based: a flick carries on for roughly a third of a turn at most
      spin.yaw += spin.vYaw * 18 * dt; spin.pitch = clamp(spin.pitch + spin.vPitch * 18 * dt, -0.55, 0.65);
      spin.vYaw *= Math.exp(-3.2 * dt); spin.vPitch *= Math.exp(-3.2 * dt);
      spin.idle += dt;
      if (!reducedMotion && spin.idle > 2.5) spin.yaw += dt * 0.035 * Math.min(1, (spin.idle - 2.5) / 3);
      if (hw < 0.02) { spin.yaw = damp(spin.yaw, 0, 1.2, dt); spin.pitch = damp(spin.pitch, 0, 1.2, dt); }
    }
    if (hw > 0.001) {
      const yaw = spin.yaw * hw, pitch = spin.pitch * hw;
      pos.applyAxisAngle(Y, yaw); tgt.applyAxisAngle(Y, yaw);
      right.crossVectors(Y, pos).normalize();
      pos.applyAxisAngle(right, -pitch);
    }

    camera.position.copy(pos);
    // pointer parallax in the camera's own plane, scaled to shot distance
    pointer.sx = damp(pointer.sx, pointer.x, 2.5, dt);
    pointer.sy = damp(pointer.sy, pointer.y, 2.5, dt);
    camera.lookAt(tgt);
    if (fine && !spin.dragging) {
      const kp = pos.distanceTo(tgt) * 0.03 * (1 - smooth(n - 1, n, p));
      right.setFromMatrixColumn(camera.matrix, 0);
      up.setFromMatrixColumn(camera.matrix, 1);
      camera.position.addScaledVector(right, pointer.sx * kp).addScaledVector(up, -pointer.sy * kp * 0.6);
      camera.lookAt(tgt);
    }

    // banking: roll into lateral motion, and a lens that opens on fast moves
    right.setFromMatrixColumn(camera.matrix, 0);
    const lateral = dt > 0 ? camera.position.clone().sub(prevPos).dot(right) / dt : 0;
    prevPos.copy(camera.position);
    const dutch = reducedMotion ? 0 : THREE.MathUtils.degToRad(lerp(A.roll, B.roll, t));   // authored roll per chapter
    roll = damp(roll, reducedMotion ? 0 : clamp(-lateral * 0.012, -0.16, 0.16), 3, dt);
    camera.rotateZ(roll + dutch);
    const speed = dt > 0 ? Math.abs(p - lastP) / dt : 0;
    lastP = p;
    breathe = damp(breathe, reducedMotion ? 0 : Math.min(speed * 5, 7), 2.5, dt);
    const fov = lerp(A.fov, B.fov, t) + (mobile ? 8 : 0) + breathe;
    if (Math.abs(camera.fov - fov) > 1e-3) { camera.fov = fov; camera.updateProjectionMatrix(); }

    uniforms.uScale.value = renderer.domElement.height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
    uniforms.uDim.value = fx.dim;
  }

  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = lastNow ? Math.min((now - lastNow) / 1000, 1 / 30) : 1 / 60;
    lastNow = now;
    frames++;
    if (progress > CHAPTERS.length - 1.02 && frames % 4) return;   // dim backdrop under the workbench

    renderFrame(dt);
    onFrame?.(api);

    if (first) { first = false; onFirstFrame?.(); }
  }

  function renderFrame(dt) {
    if (!reducedMotion) time += dt;
    uniforms.uTime.value = time;
    resolve(dt);
    ship.update(time, fx);
    space.update(camera);

    const P = post.params;
    P.uTime.value = time;
    P.uBloom.value = fx.bloom;
    P.uWarm.value = fx.warm;
    P.uExposure.value = fx.exposure;
    post.render(scene, camera);
  }

  function onVisibility() {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; lastNow = 0; }
    else if (ship && !raf) raf = requestAnimationFrame(frame);
  }

  resize();
  addEventListener("resize", resize, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); cancelAnimationFrame(raf); raf = 0; document.body.classList.add("no-webgl"); });

  // Load the ship, then compile every program before the first visible frame.
  const ready = buildShip(scene, renderer, uniforms)
    .then((s) => { ship = s; return renderer.compileAsync ? renderer.compileAsync(scene, camera) : null; })
    .then(() => { raf = requestAnimationFrame(frame); })
    .catch((err) => { console.error("World failed to load:", err); document.body.classList.add("no-webgl"); onFirstFrame?.(); onError?.(err); });

  const tmp = new THREE.Vector3();
  const api = {
    ready,
    get anchors() { return ship?.anchors ?? {}; },
    debug: {
      scene, camera, post,
      /** ?debug: mean milliseconds per frame over n synchronous renders, with a GPU flush at the end. */
      bench(n = 60) {
        const gl = renderer.getContext();
        gl.finish();
        const t0 = performance.now();
        for (let i = 0; i < n; i++) renderFrame(1 / 60);
        gl.finish();
        return (performance.now() - t0) / n;
      },
    },
    setProgress(p) { progress = p; },
    setReducedMotion(v) { reducedMotion = v; },
    /** Ship-local point → CSS pixels; `visible` is false when behind the camera or off-frame. */
    project(v) {
      if (!ship) return { x: 0, y: 0, visible: false };
      tmp.copy(v).applyMatrix4(ship.object.matrixWorld).project(camera);
      return { x: (tmp.x + 1) / 2 * innerWidth, y: (1 - tmp.y) / 2 * innerHeight, visible: tmp.z < 1 && Math.abs(tmp.x) < 1.2 && Math.abs(tmp.y) < 1.2 };
    },
  };
  return api;
}
