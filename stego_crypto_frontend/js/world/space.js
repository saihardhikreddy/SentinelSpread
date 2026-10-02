/* Deep space around the ship: nebula + stars, a ringed ice giant, a distant pale-blue
   home world (the downlink target), a white sun, lighting and camera-space motes.
   Colours inside GLSL are linear and may exceed 1.0 for the bloom pass. */

import * as THREE from "three";
import { glowTexture, streakTexture, mulberry32 } from "./textures.js?v=20261002b";

export const SUN_DIR = new THREE.Vector3(0.62, 0.42, 0.66).normalize();
export const GIANT = { center: new THREE.Vector3(-120, -46, -300), radius: 135 };
export const HOME = new THREE.Vector3(139.9, 124.9, -214.6);   // aimed 76° off the mast axis: the tilted dish never reaches the hub (measured in Blender)   // the pale blue dot the downlink aims at

export const NOISE_GLSL = /* glsl */ `
  float hash1(float n) { return fract(sin(n) * 43758.5453123); }
  float hash3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453123); }
  float vnoise(vec3 p) {
    vec3 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float n000 = hash3(i), n100 = hash3(i + vec3(1,0,0)), n010 = hash3(i + vec3(0,1,0)), n110 = hash3(i + vec3(1,1,0));
    float n001 = hash3(i + vec3(0,0,1)), n101 = hash3(i + vec3(1,0,1)), n011 = hash3(i + vec3(0,1,1)), n111 = hash3(i + vec3(1,1,1));
    return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y), mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);
  }
  float fbm(vec3 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; }
    return s;
  }
`;

function buildSky(uniforms) {
  const m = new THREE.ShaderMaterial({
    uniforms, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: /* glsl */ `varying vec3 vDir; void main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      ${NOISE_GLSL}
      uniform float uTime; uniform float uDim;
      varying vec3 vDir;
      void main() {
        vec3 d = normalize(vDir);
        vec3 col = vec3(0.0016, 0.0022, 0.0060);
        // soft nebula: violet core fading into deep blue
        float n1 = fbm(d * 2.2 + vec3(1.3, 0.0, 2.1));
        float n2 = fbm(d * 4.6 + 5.0);
        float veil = smoothstep(0.45, 0.85, n1);
        col += mix(vec3(0.010, 0.016, 0.050), vec3(0.040, 0.016, 0.060), smoothstep(0.5, 0.9, n2)) * veil;
        col += vec3(0.012, 0.030, 0.050) * smoothstep(0.62, 0.95, n2) * veil;
        // galactic band
        vec3 axis = normalize(vec3(-0.25, 0.9, 0.35));
        float band = exp(-pow(dot(d, axis) * 3.0, 2.0));
        col += vec3(0.010, 0.012, 0.022) * band * (0.5 + fbm(d * 8.0));
        for (int k = 0; k < 2; k++) {
          float sc = k == 0 ? 240.0 : 600.0;
          vec3 sp = d * sc;
          float h = hash3(floor(sp) + float(k) * 17.0);
          float thresh = k == 0 ? 0.9972 : 0.995 - band * 0.006;
          float s = step(thresh, h) * smoothstep(0.5, 0.0, length(fract(sp) - 0.5));
          vec3 tint = mix(vec3(0.72, 0.82, 1.0), vec3(0.95, 0.88, 1.0), step(0.6, fract(h * 91.0)));
          float tw = 0.7 + 0.3 * sin(uTime * (1.0 + h * 3.0) + h * 70.0);
          col += tint * s * tw * (k == 0 ? 2.4 : 0.9);
        }
        gl_FragColor = vec4(col * mix(0.55, 1.0, uDim), 1.0);
      }
    `,
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(600, 48, 24), m);
  sky.frustumCulled = false;
  sky.renderOrder = -10;
  return sky;
}

/* ─── ringed ice giant ─── */
function buildGiant(uniforms) {
  const group = new THREE.Group();
  group.position.copy(GIANT.center);
  group.rotation.set(0.18, 0, -0.32);
  const shared = { ...uniforms, uSun: { value: SUN_DIR } };

  const planet = new THREE.Mesh(
    new THREE.SphereGeometry(GIANT.radius, 160, 120),
    new THREE.ShaderMaterial({
      uniforms: shared, fog: false,
      vertexShader: /* glsl */ `
        varying vec3 vN; varying vec3 vLocal; varying vec3 vView;
        void main() {
          vLocal = normalize(position);
          vN = normalize(mat3(modelMatrix) * normal);
          vec4 w = modelMatrix * vec4(position, 1.0);
          vView = normalize(cameraPosition - w.xyz);
          gl_Position = projectionMatrix * viewMatrix * w;
        }
      `,
      fragmentShader: /* glsl */ `
        ${NOISE_GLSL}
        uniform vec3 uSun; uniform float uTime; uniform float uDim;
        varying vec3 vN; varying vec3 vLocal; varying vec3 vView;
        void main() {
          float lat = vLocal.y;
          float warp = fbm(vLocal * vec3(3.0, 14.0, 3.0) + vec3(uTime * 0.003, 0.0, 0.0)) * 0.35;
          float b = sin((lat + warp) * 26.0) * 0.5 + 0.5;
          float b2 = sin((lat + warp * 0.6) * 61.0) * 0.5 + 0.5;
          vec3 c1 = vec3(0.12, 0.26, 0.34), c2 = vec3(0.30, 0.42, 0.52), c3 = vec3(0.24, 0.22, 0.38);
          vec3 albedo = mix(mix(c1, c2, b), c3, b2 * 0.45);
          albedo = mix(albedo, vec3(0.5, 0.6, 0.68), smoothstep(0.82, 0.98, abs(lat)) * 0.5);
          float ndl = dot(vN, uSun);
          vec3 col = albedo * smoothstep(-0.05, 1.0, ndl) * 1.2;
          float rim = pow(1.0 - max(dot(vN, vView), 0.0), 3.0);
          col += vec3(0.25, 0.5, 0.9) * rim * smoothstep(-0.2, 0.5, ndl) * 0.8;
          gl_FragColor = vec4(col * mix(0.5, 1.0, uDim), 1.0);
        }
      `,
    }),
  );

  const C = GIANT.center.toArray().map((v) => v.toFixed(1)).join(", ");
  const rings = new THREE.Mesh(new THREE.RingGeometry(GIANT.radius * 1.3, GIANT.radius * 2.25, 256, 1), new THREE.ShaderMaterial({
    uniforms: shared, transparent: true, depthWrite: false, side: THREE.DoubleSide, fog: false,
    vertexShader: /* glsl */ `
      varying vec3 vW; varying vec3 vLocal;
      void main() { vLocal = position; vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }
    `,
    fragmentShader: /* glsl */ `
      ${NOISE_GLSL}
      uniform vec3 uSun; uniform float uDim;
      varying vec3 vW; varying vec3 vLocal;
      void main() {
        float r = length(vLocal.xy) / ${GIANT.radius.toFixed(1)};
        float t = (r - 1.3) / 0.95;
        float bands = vnoise(vec3(r * 60.0, 0.0, 0.0)) * 0.6 + vnoise(vec3(r * 210.0, 1.0, 0.0)) * 0.4;
        float gap = smoothstep(0.02, 0.0, abs(t - 0.62));
        float a = bands * smoothstep(0.0, 0.06, t) * smoothstep(1.0, 0.85, t) * (1.0 - gap * 0.9);
        // the planet's shadow across the rings
        vec3 toCenter = vec3(${C}) - vW;
        float along = dot(toCenter, -uSun);
        float perp = length(toCenter + uSun * along);
        float shadow = (along < 0.0 && perp < ${GIANT.radius.toFixed(1)}) ? 0.12 : 1.0;
        vec3 c = mix(vec3(0.36, 0.44, 0.52), vec3(0.55, 0.52, 0.62), vnoise(vec3(r * 30.0, 4.0, 0.0)));
        gl_FragColor = vec4(c * shadow * 0.8 * uDim, a * 0.42);
      }
    `,
  }));
  rings.rotation.x = Math.PI / 2 - 0.08;
  group.add(planet, rings);
  return group;
}

function buildHome() {
  const g = new THREE.Group();
  g.position.copy(HOME);
  const disc = new THREE.Mesh(new THREE.SphereGeometry(2.2, 32, 24), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.35, 0.6, 1.2) }));
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: new THREE.Color(0.4, 0.7, 1.6), transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending, depthWrite: false }));
  halo.scale.set(16, 16, 1);
  g.add(disc, halo);
  return g;
}

function buildSun() {
  const g = new THREE.Group();
  const glow = glowTexture();
  const sprite = (s, color, op, tex = glow) => {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color, transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
    sp.scale.set(s[0], s[1], 1);
    return sp;
  };
  g.add(sprite([90, 90], new THREE.Color(0.55, 0.65, 0.9), 0.35), sprite([18, 18], new THREE.Color(9, 9.4, 10), 1), sprite([420, 3.5], new THREE.Color(0.9, 1.1, 1.6), 0.5, streakTexture()));
  return g;
}

function buildMotes(uniforms) {
  const N = 220;
  const pos = new Float32Array(N * 3), seed = new Float32Array(N);
  const rnd = mulberry32(41);
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (rnd() - 0.5) * 14; pos[i * 3 + 1] = (rnd() - 0.5) * 9; pos[i * 3 + 2] = -2 - rnd() * 14; seed[i] = rnd() * 100;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
  const p = new THREE.Points(g, new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
    vertexShader: /* glsl */ `
      attribute float aSeed; uniform float uTime; uniform float uScale; uniform float uDim;
      varying float vA;
      void main() {
        vec3 q = position;
        q.x = mod(q.x + uTime * 0.05 * (0.5 + fract(aSeed)) + 7.0, 14.0) - 7.0;
        vA = (0.08 + 0.12 * fract(aSeed * 7.1)) * smoothstep(-2.0, -5.0, q.z) * uDim;
        vec4 mv = modelViewMatrix * vec4(q, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = clamp(0.035 * uScale / -mv.z, 1.0, 8.0);
      }
    `,
    fragmentShader: /* glsl */ `varying float vA; void main() { float a = smoothstep(0.5, 0.0, length(gl_PointCoord - 0.5)); gl_FragColor = vec4(vec3(0.7, 0.85, 1.0) * a * vA, 1.0); }`,
  }));
  p.frustumCulled = false;
  return p;
}

export function buildSpace(scene, camera, uniforms) {
  const sky = buildSky(uniforms);
  const giant = buildGiant(uniforms);
  const home = buildHome();
  const sun = buildSun();
  camera.add(buildMotes(uniforms));

  const key = new THREE.DirectionalLight(0xf4f7ff, 4.6);
  key.position.copy(SUN_DIR).multiplyScalar(60);
  const fill = new THREE.HemisphereLight(0x8496c0, 0x0b1222, 0.8);
  const bounce = new THREE.DirectionalLight(0x6f86c8, 0.8);   // light off the ice giant
  bounce.position.copy(GIANT.center).normalize().multiplyScalar(60);
  scene.add(sky, giant, home, sun, key, fill, bounce);

  return {
    key,
    update(camera) {
      sky.position.copy(camera.position);
      sun.position.copy(SUN_DIR).multiplyScalar(520).add(camera.position);
    },
  };
}
