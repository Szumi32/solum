/* Podglad 3D bransoletki (Three.js). Modul ladowany dopiero po kliknieciu "Obroc w 3D". */
import * as THREE from "../vendor/three/three.module.min.js";
import { GLTFLoader } from "../vendor/three/GLTFLoader.js";
import { OrbitControls } from "../vendor/three/OrbitControls.js";
import { RoomEnvironment } from "../vendor/three/RoomEnvironment.js";

const FLOOR = 0xe2ded5;

function ringShadow(radius) {
  /* Miekki cien w ksztalcie pierscienia, malowany na kanwie zamiast liczonego na zywo */
  const size = 512;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  const outer = 1.3;
  const r = size / 2;
  const grad = g.createRadialGradient(r, r, 0, r, r, r);
  const k = 1 / outer;
  grad.addColorStop(0, "rgba(60,50,40,0)");
  grad.addColorStop(Math.max(0, k - 0.2), "rgba(60,50,40,0)");
  grad.addColorStop(k * 0.96, "rgba(60,50,40,0.24)");
  grad.addColorStop(Math.min(1, k + 0.07), "rgba(60,50,40,0)");
  grad.addColorStop(1, "rgba(60,50,40,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(radius * 2 * outer, radius * 2 * outer), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = 0.002;
  return mesh;
}

/* GLB nie przenosi pochlaniania swiatla wewnatrz bursztynu, wiec ustawiamy je po wczytaniu */
const DEPTH = { koniak: 0xb0560f, miod: 0xdc9526 };
function tuneMaterials(root) {
  root.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material;
    if (!m || !m.transmission) return;
    const key = Object.keys(DEPTH).find((k) => m.name.includes(k));
    if (key) {
      m.attenuationColor = new THREE.Color(DEPTH[key]);
      m.attenuationDistance = 0.55;
      m.thickness = 0.9;
      m.ior = 1.54;
    }
  });
}

export function mountViewer(host, url, { onError } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 0.92;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(FLOOR);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.62;

  const key = new THREE.DirectionalLight(0xfff2e0, 1.5);
  key.position.set(-5, 8, 3);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xeef2ff, 0.3);
  fill.position.set(6, 4, -4);
  scene.add(fill);

  const camera = new THREE.PerspectiveCamera(26, 1, 0.05, 200);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minPolarAngle = 0.05;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 1.1;
  controls.addEventListener("start", () => { controls.autoRotate = false; });

  /* Na telefonie przewijanie strony nie moze utknac na modelu: obrot tylko poziomo jednym palcem */
  renderer.domElement.style.touchAction = "pan-y";

  const note = document.createElement("p");
  note.className = "viewer-note";
  note.textContent = "Przeciągnij, żeby obrócić";
  host.appendChild(note);

  const loader = new GLTFLoader();
  let current = null;
  let shadow = null;
  let token = 0;
  let framed = false;

  function disposeTree(obj) {
    obj.traverse((o) => {
      if (o.isMesh) {
        o.geometry.dispose();
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => {
          Object.values(m).forEach((v) => { if (v && v.isTexture) v.dispose(); });
          m.dispose();
        });
      }
    });
  }

  function load(nextUrl) {
    const my = ++token;
    loader.load(
      nextUrl,
      (gltf) => {
        if (my !== token) { disposeTree(gltf.scene); return; }
        if (current) { scene.remove(current); disposeTree(current); }
        current = gltf.scene;
        scene.add(current);
        tuneMaterials(current);
        const box = new THREE.Box3().setFromObject(current);
        const size = box.getSize(new THREE.Vector3());
        /* Obrecz lezy w srodku ukladu modelu. Srodek obrysu bylby przesuniety przez koncowki nici. */
        current.position.y -= box.min.y;
        const radius = Math.max(-box.min.x, box.min.z < 0 ? -box.min.z : box.max.z);
        const ring = Math.min(size.x, size.z) / 2;
        if (shadow) { scene.remove(shadow); shadow.geometry.dispose(); shadow.material.map.dispose(); shadow.material.dispose(); }
        shadow = ringShadow(ring * 0.94);
        scene.add(shadow);
        controls.target.set(0, size.y * 0.3, 0);
        if (!framed) {
          const d = radius / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.32;
          const el = THREE.MathUtils.degToRad(44);
          const az = THREE.MathUtils.degToRad(18);
          camera.position.set(Math.sin(az) * Math.cos(el) * d, Math.sin(el) * d + size.y * 0.3, Math.cos(az) * Math.cos(el) * d);
          controls.minDistance = d * 0.42;
          controls.maxDistance = d * 1.6;
          framed = true;
        }
      },
      undefined,
      () => { if (my === token && onError) onError(); },
    );
  }

  function resize() {
    const w = host.clientWidth || 1;
    const h = host.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  let visible = true;
  let paused = false;
  new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; }).observe(host);
  renderer.setAnimationLoop(() => {
    if (!visible || paused) return;
    controls.update();
    renderer.render(scene, camera);
  });

  load(url);

  return {
    load,
    pause() { paused = true; },
    resume() { paused = false; resize(); },
  };
}
