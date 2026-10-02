/* SENTINEL ring ship: the detailed hull is modelled in Blender (models/build_ship.py →
   assets/sentinel_ship.glb). This module loads it and attaches the live effects to the
   anchors the model carries. In three.js module-local frames: +X tangent, +Y up, -Z outward.
     A_core  / BayDoor  command module cipher core            channel: open
     Dish    / A_dish   hub dish + the downlink beam home       channel: beam
     F_imaging / A_lens imaging lens + carrier hologram        channel: holo
     A_comms            helix antenna + waveform ring           channel: audio */

import * as THREE from "three";
import { GLTFLoader } from "../../vendor/addons/loaders/GLTFLoader.js";
import { plateTexture, photoTexture, glyphTexture, glowTexture } from "./textures.js?v=20261002b";
import { SUN_DIR, HOME, NOISE_GLSL } from "./space.js?v=20261002b";

const ICE = new THREE.Color(0.45, 0.78, 1.7);
const additive = (extra = {}) => ({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, ...extra });

function envMap(renderer) {
  const W = 512, H = 256;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const x = c.getContext("2d");
  const g = x.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#03050c"); g.addColorStop(0.5, "#070b18"); g.addColorStop(1, "#0a1226");
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  const blob = (dir, r, stops) => {
    const u = Math.atan2(dir.z, dir.x) / (2 * Math.PI) + 0.5, v = Math.asin(dir.y) / Math.PI + 0.5;
    const s = x.createRadialGradient(u * W, (1 - v) * H, 0, u * W, (1 - v) * H, r);
    stops.forEach(([o, col]) => s.addColorStop(o, col));
    x.fillStyle = s; x.fillRect(0, 0, W, H);
  };
  blob(new THREE.Vector3(-0.37, -0.14, -0.92).normalize(), 150, [[0, "rgba(90,130,170,0.55)"], [1, "rgba(60,90,140,0)"]]);
  blob(SUN_DIR, 70, [[0, "rgba(255,255,255,1)"], [0.15, "rgba(220,232,255,0.6)"], [1, "rgba(180,200,255,0)"]]);
  const tex = new THREE.CanvasTexture(c);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromEquirectangular(tex).texture;
  pmrem.dispose(); tex.dispose();
  return env;
}

function latticeGeo(size, n) {
  const h = size / 2, step = size / n, v = [];
  for (let i = 0; i <= n; i++) for (let j = 0; j <= n; j++) {
    const a = -h + i * step, b = -h + j * step;
    v.push(-h, a, b, h, a, b, a, -h, b, a, h, b, a, b, -h, a, b, h);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  return g;
}

/* ─── cipher core in the command bay ─── */
function buildCore() {
  const g = new THREE.Group();
  const lattice = new THREE.LineSegments(latticeGeo(0.42, 3), new THREE.LineBasicMaterial({ color: ICE.clone().multiplyScalar(1.4), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  const glyphs = glyphTexture();
  glyphs.repeat.set(1.5, 1);
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.33, 0.11, 64, 1, true), new THREE.MeshBasicMaterial({ map: glyphs, color: ICE, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: ICE, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  glow.scale.set(1.3, 1.3, 1);
  const light = new THREE.PointLight(0x7fb8ff, 0, 4, 2);
  light.position.set(0, 0, -0.35);
  g.add(lattice, band, glow, light);
  return { group: g, lattice, band, glow, light, glyphs };
}

/* ─── carrier hologram projected by the imaging lens ─── */
function buildHologram(uniforms) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { ...uniforms, tPhoto: { value: photoTexture() }, uHolo: { value: 0 } }, ...additive({ side: THREE.DoubleSide }),
    vertexShader: /* glsl */ `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      ${NOISE_GLSL}
      uniform sampler2D tPhoto; uniform float uTime; uniform float uHolo; uniform float uDim;
      varying vec2 vUv;
      void main() {
        float head = fract(uTime * 0.07);
        float rowY = 1.0 - vUv.y;
        float behind = step(rowY, head);
        float near = smoothstep(0.07, 0.0, abs(rowY - head));
        vec2 grid = vec2(80.0, 48.0);
        vec2 px = mix(vUv, (floor(vUv * grid) + 0.5) / grid, near);
        vec3 c = pow(texture2D(tPhoto, px).rgb, vec3(2.2));
        c = mix(c, vec3(dot(c, vec3(0.3, 0.55, 0.15))) * vec3(0.7, 0.85, 1.1), 0.45);
        float flip = step(0.93, hash3(vec3(floor(vUv * grid), floor(uTime * 2.0)))) * behind;
        c += vec3(0.5, 0.8, 1.6) * flip * 0.3;
        c += vec3(0.6, 0.9, 1.8) * 1.8 * exp(-pow((rowY - head) * 220.0, 2.0));
        vec2 blk = fract(vUv * grid / 8.0);
        c += vec3(0.6, 0.5, 1.4) * (step(blk.x, 0.03) + step(blk.y, 0.05)) * (0.5 + 0.5 * sin(uTime * 1.3)) * 0.05;
        float scan = 0.86 + 0.14 * sin(vUv.y * 300.0 + uTime * 8.0);
        float edge = max(step(vUv.x, 0.006) + step(0.994, vUv.x), step(vUv.y, 0.01) + step(0.99, vUv.y));
        c = mix(c * scan, vec3(0.6, 0.95, 1.8), edge);
        gl_FragColor = vec4(c * uHolo * (0.93 + 0.07 * hash1(floor(uTime * 24.0))) * uDim, 1.0);
      }
    `,
  });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.56), mat);
  return { plane, mat };
}

/* ─── waveform ring around the helix antenna ─── */
function buildWaveRing(uniforms) {
  const N = 180;
  const barGeo = new THREE.BoxGeometry(0.018, 1, 0.018);
  barGeo.translate(0, 0.5, 0);
  const idx = new Float32Array(N);
  for (let i = 0; i < N; i++) idx[i] = i;
  barGeo.setAttribute("aI", new THREE.InstancedBufferAttribute(idx, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { ...uniforms, uAudio: { value: 0 } }, ...additive(),
    vertexShader: /* glsl */ `
      ${NOISE_GLSL}
      attribute float aI; uniform float uTime; uniform float uAudio; uniform float uDim;
      varying vec3 vColor; varying float vA;
      void main() {
        float t = aI / ${N.toFixed(1)};
        float ang = t * 6.28318;
        float w = sin(ang * 6.0 - uTime * 2.2) * 0.55 + sin(ang * 17.0 + uTime * 3.1) * 0.3 + sin(ang * 3.0 + uTime) * 0.25;
        vec3 p = position * vec3(1.0, (abs(w) * 0.75 + 0.04) * uAudio, 1.0);
        p += vec3(cos(ang) * 1.1, -0.35, sin(ang) * 1.1);
        float lsb = step(0.8, hash1(aI * 3.7 + floor(uTime * 2.5)));
        float tip = smoothstep(0.75, 1.0, position.y);
        vColor = mix(vec3(0.55, 0.8, 1.4), vec3(0.8, 0.55, 1.9) * 1.6, tip * lsb);
        vA = uAudio * uDim * (0.5 + 0.5 * tip);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `varying vec3 vColor; varying float vA; void main() { gl_FragColor = vec4(vColor * vA, 1.0); }`,
  });
  const ring = new THREE.InstancedMesh(barGeo, mat, N);
  ring.frustumCulled = false;
  const guide = new THREE.Mesh(new THREE.TorusGeometry(1.1, 0.004, 4, 160), new THREE.MeshBasicMaterial({ color: ICE, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  guide.rotation.x = Math.PI / 2;
  guide.position.y = -0.35;
  const g = new THREE.Group();
  g.add(ring, guide);
  return { group: g, mat, guide };
}

/* ─── downlink beam: white-hot core, soft sheath, 16-chip packets, wavefront rings ─── */
function buildBeam(uniforms) {
  const L = 150;
  const g = new THREE.Group();     // +Y is the beam direction, origin at the dish focus
  const u = { ...uniforms, uBeam: { value: 0 } };

  const core = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, L, 8, 1, true).translate(0, L / 2, 0), new THREE.ShaderMaterial({
    uniforms: u, ...additive(),
    vertexShader: /* glsl */ `varying float vT; void main() { vT = uv.y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `uniform float uBeam; uniform float uDim; varying float vT;
      void main() { float a = exp(-vT * 3.2) * smoothstep(0.0, 0.004, vT); gl_FragColor = vec4(vec3(0.75, 0.9, 1.6) * 2.6 * a * uBeam * uDim, 1.0); }`,
  }));

  const sheath = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, L, 32, 1, true).translate(0, L / 2, 0), new THREE.ShaderMaterial({
    uniforms: u, ...additive({ side: THREE.DoubleSide }),
    vertexShader: /* glsl */ `
      varying float vT; varying float vFacing;
      void main() {
        vT = uv.y;
        vec4 w = modelMatrix * vec4(position, 1.0);
        vec3 n = normalize(mat3(modelMatrix) * normal);
        vFacing = abs(dot(n, normalize(cameraPosition - w.xyz)));
        gl_Position = projectionMatrix * viewMatrix * w;
      }
    `,
    fragmentShader: /* glsl */ `uniform float uBeam; uniform float uDim; uniform float uTime; varying float vT; varying float vFacing;
      void main() {
        float a = pow(vFacing, 3.0) * exp(-vT * 2.6) * smoothstep(0.0, 0.01, vT) * (0.85 + 0.15 * sin(vT * 400.0 - uTime * 12.0));
        gl_FragColor = vec4(vec3(0.35, 0.62, 1.4) * 0.5 * a * uBeam * uDim, 1.0);
      }`,
  }));

  // chip packets: 16 chips per bit, bits spaced along the beam, streaming home
  const N = 16 * 18;
  const pos = new Float32Array(N * 3), idx = new Float32Array(N);
  for (let i = 0; i < N; i++) idx[i] = i;
  const pg = new THREE.BufferGeometry();
  pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pg.setAttribute("aI", new THREE.BufferAttribute(idx, 1));
  const packets = new THREE.Points(pg, new THREE.ShaderMaterial({
    uniforms: u, ...additive(),
    vertexShader: /* glsl */ `
      ${NOISE_GLSL}
      attribute float aI; uniform float uTime; uniform float uBeam; uniform float uDim; uniform float uScale;
      varying float vA; varying float vChip;
      void main() {
        float bitI = floor(aI / 16.0), chipI = mod(aI, 16.0);
        float t = fract(uTime * 0.05 + bitI / 18.0);
        float along = t * 70.0 + chipI * 0.11;
        vChip = step(0.5, hash1(bitI * 31.0 + chipI * 7.0 + floor(uTime * 0.05 + bitI / 18.0) * 13.0));
        vec3 p = vec3(0.0, along, 0.0);
        p.x += (vChip * 2.0 - 1.0) * 0.06;          // ±1 chips ride either side of the core
        vA = uBeam * uDim * smoothstep(0.0, 0.03, t) * (1.0 - smoothstep(0.55, 1.0, t));
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = clamp(0.07 * uScale / -mv.z, 1.0, 10.0);
      }
    `,
    fragmentShader: /* glsl */ `varying float vA; varying float vChip;
      void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d);
        vec3 c = mix(vec3(0.55, 0.8, 1.6), vec3(0.9, 0.95, 1.6), vChip) * 2.2;
        gl_FragColor = vec4(c * a * vA, 1.0); }`,
  }));
  packets.frustumCulled = false;

  const rings = [];
  for (let k = 0; k < 4; k++) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1, 0.012, 6, 96), new THREE.MeshBasicMaterial({ color: ICE, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    ring.rotation.x = Math.PI / 2;
    ring.userData.phase = k / 4;
    rings.push(ring);
  }
  const flare = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: ICE.clone().multiplyScalar(1.5), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  g.add(sheath, core, packets, ...rings, flare);
  return { group: g, u, rings, flare };
}

export async function buildShip(scene, renderer, uniforms) {
  scene.environment = envMap(renderer);
  const gltf = await new GLTFLoader().loadAsync(new URL("../../assets/sentinel_ship.glb?v=20261002b", import.meta.url).href);
  const model = gltf.scene;
  const ship = new THREE.Group();
  ship.rotation.set(0.32, 0.25, -0.1);
  ship.add(model);
  scene.add(ship);

  model.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    m.envMapIntensity = m.name === "Glass" ? 2.4 : m.name === "Metal" ? 1.6 : 1.1;
    if (m.name === "Window") m.emissiveIntensity = 1.2;
    o.castShadow = o.receiveShadow = !(m.name === "Light" || m.name === "Window");
  });
  const node = (name) => {
    const n = model.getObjectByName(name);
    if (!n) throw new Error(`ship model is missing node ${name}`);
    return n;
  };
  ship.updateMatrixWorld(true);

  // cipher core + plate
  const core = buildCore();
  node("A_core").add(core.group);
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.55), new THREE.MeshStandardMaterial({ map: plateTexture(), metalness: 0.1, roughness: 0.55 }));
  plate.rotation.y = Math.PI;      // face outward (-Z)
  node("A_plate").add(plate);
  const door = node("BayDoor");

  // hologram + projection rays
  const holo = buildHologram(uniforms);
  const fImg = node("F_imaging");
  holo.plane.position.set(1.7, 0.75, -4.2);
  holo.plane.rotation.y = Math.PI + 0.38;
  fImg.add(holo.plane);
  holo.plane.updateMatrix();
  const lensLocal = fImg.worldToLocal(node("A_lens").getWorldPosition(new THREE.Vector3()));
  const lp = [];
  for (const [cx, cy] of [[-1.3, -0.78], [1.3, -0.78], [1.3, 0.78], [-1.3, 0.78]]) {
    const p = new THREE.Vector3(cx, cy, 0).applyMatrix4(holo.plane.matrix);
    lp.push(lensLocal.x, lensLocal.y, lensLocal.z, p.x, p.y, p.z);
  }
  const rayGeo = new THREE.BufferGeometry();
  rayGeo.setAttribute("position", new THREE.Float32BufferAttribute(lp, 3));
  const rays = new THREE.LineSegments(rayGeo, new THREE.LineBasicMaterial({ color: ICE, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  fImg.add(rays);

  // waveform ring
  const wave = buildWaveRing(uniforms);
  node("A_comms").add(wave.group);

  // dish aimed home; the beam leaves from its focus
  const dish = node("Dish");
  const mountShip = ship.worldToLocal(dish.getWorldPosition(new THREE.Vector3()));
  const homeShip = ship.worldToLocal(HOME.clone());
  const dirShip = homeShip.clone().sub(mountShip).normalize();
  const dirModel = dirShip.clone().transformDirection(model.matrix.clone().invert());
  dish.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dirModel);
  const beam = buildBeam(uniforms);
  beam.group.position.copy(mountShip).addScaledVector(dirShip, 1.0);
  beam.group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dirShip);
  ship.add(beam.group);

  ship.updateMatrixWorld(true);
  const local = (name, offset = new THREE.Vector3()) => ship.worldToLocal(node(name).localToWorld(offset.clone()));
  const anchors = {
    core: local("A_core"),
    hga: local("A_dish", new THREE.Vector3(0, 0.9, 0)),
    lens: ship.worldToLocal(holo.plane.getWorldPosition(new THREE.Vector3())),
    audio: local("A_comms", new THREE.Vector3(0, 0.6, 0)),
    lander: local("A_lander"),
  };

  return {
    object: ship,
    anchors,
    update(time, fx) {
      ship.rotation.y = 0.25 + Math.sin(time * 0.05) * 0.03;
      ship.position.y = Math.sin(time * 0.3) * 0.08;

      door.rotation.y = -fx.open * 1.9;
      const on = THREE.MathUtils.smoothstep(fx.open, 0.25, 0.9);
      core.lattice.material.opacity = on * 0.9;
      core.lattice.rotation.set(time * 0.6, time * 0.45, 0);
      core.band.material.opacity = on * 0.85;
      core.band.rotation.y = time * 0.5;
      core.glyphs.offset.x = time * 0.05;
      core.glow.material.opacity = on * (0.5 + 0.15 * Math.sin(time * 3));
      core.light.intensity = on * 6;

      const boost = fx.boost || 0;                       // a live transmission is running
      beam.u.uBeam.value = fx.beam + boost * 1.3;
      for (const r of beam.rings) {
        const t = (time * (0.55 + boost * 1.6) + r.userData.phase) % 1;
        r.position.y = 0.2 + t * (7 + boost * 9);
        r.scale.setScalar(0.35 + t * (2.4 + boost * 1.6));
        r.material.opacity = (fx.beam + boost) * (1 - t) * 0.55;
      }
      beam.flare.scale.setScalar(2.2 + boost * (5 + Math.sin(time * 18) * 0.8));
      beam.flare.material.opacity = boost * 0.8;
      holo.mat.uniforms.uHolo.value = fx.holo;
      rays.material.opacity = fx.holo * 0.3;
      wave.mat.uniforms.uAudio.value = fx.audio;
      wave.guide.material.opacity = fx.audio * 0.6;
    },
  };
}
