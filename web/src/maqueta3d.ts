/**
 * Maqueta 3D del tramo de costa (10 km × 38 km) desde el DEM Copernicus.
 *
 * - Plataforma giratoria (skill 3d-feature-objects): pose base de tres cuartos; con el cursor encima,
 *   el movimiento horizontal orienta ±0,7 rad y la maqueta sigue girando 0,58 rad/s; al salir vuelve a
 *   su pose por el camino angular más corto; suavizado 1−exp(−10·dt); sin cuadros cuando se asienta.
 * - Neblina que se desprende (skill hover-particle-dissolve): granos repartidos por área de triángulo,
 *   concentrados en la franja de nubes (300–1 000 m). El cursor, con un rayo contra el terreno real,
 *   suelta los granos alrededor del punto tocado y el viento del mar los lleva cerro arriba; al salir
 *   vuelven a su sitio. El terreno se mantiene entero (es un mapa, no se borra): los granos son la niebla.
 */
import type { Terreno } from "./tipos";

declare const THREE: any;

const EXAG = 2.2;                          // exageración vertical
const FRANJAS_KM = [[0, 0.5], [0.5, 2], [2, 5], [5, 10], [10, 20], [20, 35]];
const NIEBLA = [300, 1000];

export interface Maqueta {
  mostrar(t: Terreno, franja: number): void;
  girar(): void;
  soplar(): void;
  destruir(): void;
}

export function crearMaqueta(canvas: HTMLCanvasElement): Maqueta | null {
  if (typeof THREE === "undefined") return null;
  let renderer: any;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  } catch {
    return null;
  }
  const quieto = matchMedia("(prefers-reduced-motion: reduce)");
  const escena = new THREE.Scene();
  const camara = new THREE.PerspectiveCamera(30, 1, 0.1, 400);
  const giro = new THREE.Group();          // plataforma neutra
  const pose = new THREE.Group();          // pose compuesta de tres cuartos
  pose.rotation.y = -0.55;
  giro.add(pose);
  escena.add(giro);

  const u = { brocha: { value: new THREE.Vector3(0, -99, 0) }, cantidad: { value: 0 }, reloj: { value: 0 },
    densidad: { value: 1 }, vMin: { value: 0 }, vMax: { value: 0 }, oscuro: { value: 0 } };
  const campo = `uniform vec3 brocha; uniform float cantidad;
    float erosion(vec3 p){ float g=.25*sin(dot(p,vec3(1.9,.7,1.3)))+.15*cos(dot(p,vec3(-1.4,2.9,2.3)));
      return clamp(.08+distance(p,brocha)*.32+g,.04,9.); }`;

  let terreno: any = null, granos: any = null, mar: any = null;
  let base = 0, objetivo = 0, angulo = 0, deriva = 0, encima = false, px = 0, activo = false, previa = false;
  const apuntar = new THREE.Vector3(), ejemplo = new THREE.Vector3();
  let raf = 0, prev = 0;

  function limpiar() {
    for (const o of [terreno, granos, mar]) if (o) { pose.remove(o); o.geometry.dispose(); o.material.dispose(); }
    terreno = granos = mar = null;
  }

  function mostrar(t: Terreno, franja: number) {
    limpiar();
    const { nu, nv, h } = t;
    const [u0, u1] = t.u_km, [v0, v1] = t.v_km;
    const vc = (v0 + v1) / 2 - 4;
    const pos = new Float32Array(nu * nv * 3), alt = new Float32Array(nu * nv), vv = new Float32Array(nu * nv);
    for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) {
      const k = i * nv + j, hk = h[k];
      const x = u0 + (u1 - u0) * i / (nu - 1), v = v0 + (v1 - v0) * j / (nv - 1);
      pos.set([x, Math.max(hk, -40) / 1000 * EXAG, -(v - vc)], k * 3);
      alt[k] = hk; vv[k] = v;
    }
    const idx: number[] = [];
    for (let i = 0; i < nu - 1; i++) for (let j = 0; j < nv - 1; j++) {
      const a = i * nv + j, b = a + nv, c = a + 1, d = b + 1;
      if (Math.max(h[a], h[b], h[c], h[d]) <= 0) continue;          // celdas de puro mar
      idx.push(a, b, c, c, b, d);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("altura", new THREE.BufferAttribute(alt, 1));
    geo.setAttribute("v", new THREE.BufferAttribute(vv, 1));
    geo.setIndex(idx);
    geo.computeVertexNormals();
    const [fv0, fv1] = FRANJAS_KM[franja] ?? [0, 0];
    u.vMin.value = fv0; u.vMax.value = fv1;
    const mat = new THREE.ShaderMaterial({
      uniforms: u, extensions: { derivatives: true },
      vertexShader: `attribute float altura; attribute float v; varying float H, V; varying vec3 N, P;
        void main(){ H=altura; V=v; N=normalize(normalMatrix*normal); vec4 p=modelViewMatrix*vec4(position,1.); P=-p.xyz;
          gl_Position=projectionMatrix*p; }`,
      fragmentShader: `uniform float vMin, vMax, oscuro; varying float H, V; varying vec3 N, P;
        vec3 rampa(float h){
          vec3 c=mix(vec3(.86,.80,.66), vec3(.74,.62,.43), smoothstep(0.,500.,h));
          c=mix(c, vec3(.55,.44,.32), smoothstep(500.,1500.,h));
          return mix(c, vec3(.42,.35,.29), smoothstep(1500.,3000.,h)); }
        void main(){
          if(H<=0.) discard;
          vec3 c=rampa(H);
          float lomas=smoothstep(${NIEBLA[0] - 60}.,${NIEBLA[0] + 40}.,H)*(1.-smoothstep(${NIEBLA[1] - 40}.,${NIEBLA[1] + 80}.,H));
          c=mix(c, vec3(.36,.58,.45), .45*lomas);
          float l=max(dot(normalize(N), normalize(vec3(-.45,.8,.5))),0.);
          c*=.38+.72*l;
          float w=fwidth(H);
          float iso=1.-smoothstep(0.,w*1.2,abs(mod(H+100.,200.)-100.));
          c=mix(c, c*.82, .55*iso);
          float lim=max(1.-smoothstep(0.,w*1.6,abs(H-${NIEBLA[0]}.)), 1.-smoothstep(0.,w*1.6,abs(H-${NIEBLA[1]}.)));
          c=mix(c, vec3(.08,.42,.32), .85*lim);
          float enF=step(vMin,V)*step(V,vMax);
          c=mix(c, c*1.18+vec3(.04,.06,.05), .7*enF);
          float borde=enF*(1.-smoothstep(0.,.25,min(V-vMin, vMax-V)));
          c=mix(c, vec3(.05,.12,.11), .9*borde);
          gl_FragColor=vec4(c,1.); }`,
    });
    terreno = new THREE.Mesh(geo, mat);
    pose.add(terreno);

    // mar: plano translúcido a nivel 0 frente a la costa
    const mg = new THREE.PlaneGeometry(u1 - u0, 9);
    mg.rotateX(-Math.PI / 2);
    mg.translate((u0 + u1) / 2, -0.012, -(v0 - vc) - 4.5 + 3);
    mar = new THREE.Mesh(mg, new THREE.MeshBasicMaterial({ color: 0x3f7f9b, transparent: true, opacity: .55 }));
    pose.add(mar);

    // granos de neblina: muestreo por área, 85 % en la franja de nubes
    const area: number[] = [], pesos: number[] = [];
    let total = 0;
    const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3(), tri = new THREE.Triangle(A, B, C);
    for (let i = 0; i < idx.length; i += 3) {
      A.fromArray(pos, idx[i] * 3); B.fromArray(pos, idx[i + 1] * 3); C.fromArray(pos, idx[i + 2] * 3);
      const hm = (alt[idx[i]] + alt[idx[i + 1]] + alt[idx[i + 2]]) / 3;
      const w = hm >= NIEBLA[0] && hm <= NIEBLA[1] ? 1 : 0.06;
      total += tri.getArea() * w; area.push(total); pesos.push(w);
    }
    let semilla = 911;
    const azar = () => { semilla = (Math.imul(semilla, 1664525) + 1013904223) >>> 0; return semilla / 4294967296; };
    const n = 9000, casas = new Float32Array(n * 3), sem = new Float32Array(n);
    for (let i = 0; i < n && total > 0; i++) {
      const pick = azar() * total;
      let lo = 0, hi = area.length - 1;
      while (lo < hi) { const m = (lo + hi) >>> 1; if (area[m] < pick) lo = m + 1; else hi = m; }
      const s = lo * 3, r = Math.sqrt(azar()), q = azar(), wts = [1 - r, r * (1 - q), r * q];
      for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) casas[i * 3 + k] += pos[idx[s + j] * 3 + k] * wts[j];
      casas[i * 3 + 1] += 0.04;
      sem[i] = azar();
    }
    const cg = new THREE.BufferGeometry();
    cg.setAttribute("position", new THREE.BufferAttribute(casas, 3));
    cg.setAttribute("semilla", new THREE.BufferAttribute(sem, 1));
    granos = new THREE.Points(cg, new THREE.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false,
      vertexShader: campo + `uniform float reloj, densidad; attribute float semilla; varying float alfa, tono;
        void main(){ float d=erosion(position); float libre=smoothstep(d-.05,d+.16,cantidad);
          alfa=.18+.82*libre; tono=semilla;
          float vuelo=semilla<.65?.35:(semilla<.91?1.2:2.6);
          vec3 flujo=vec3(sin(position.z*.9+reloj*.8+semilla*6.),.6+.4*cos(position.x*1.3+reloj+semilla*3.),-1.);
          vec3 p=position+libre*vuelo*(flujo*vec3(.35,.5,.9));
          gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);
          gl_PointSize=densidad*(1.4+2.2*semilla)*(1.+libre); }`,
      fragmentShader: `uniform float oscuro; varying float alfa, tono; void main(){ float r=length(gl_PointCoord-.5); if(r>.5) discard;
        vec3 c=mix(vec3(.93,.96,.97), vec3(.78,.88,.9), tono);
        gl_FragColor=vec4(c, alfa*(.55+.25*oscuro)*(1.-smoothstep(.2,.5,r))); }`,
    }));
    granos.frustumCulled = false;
    pose.add(granos);

    // punto de ejemplo para el botón: el de la franja de nubes más cercano al centro
    ejemplo.set(0, 0.8, 0);
    let mejor = Infinity;
    for (let i = 0; i < n; i += 7) { const d = Math.abs(casas[i * 3]) + Math.abs(casas[i * 3 + 2] + 6); if (d < mejor) { mejor = d; ejemplo.fromArray(casas, i * 3); } }
    encuadrar();
    pedir();
  }

  function encuadrar() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    u.densidad.value = Math.min(devicePixelRatio || 1, 2);
    renderer.setPixelRatio(u.densidad.value);
    renderer.setSize(w, h, false);
    camara.aspect = w / h;
    const dist = 46 / Math.min(1.25, camara.aspect);
    camara.position.set(0, dist * 0.55, dist * 0.84);
    camara.lookAt(0, 1.2, -2);
    camara.updateProjectionMatrix();
    pedir();
  }

  const ray = new THREE.Raycaster(), puntero = new THREE.Vector2();
  function golpe(e: PointerEvent) {
    const r = canvas.getBoundingClientRect();
    px = ((e.clientX - r.left) / r.width) * 2 - 1;
    encima = true;
    if (!terreno) return pedir();
    puntero.set(px, 1 - ((e.clientY - r.top) / r.height) * 2);
    ray.setFromCamera(puntero, camara);
    const p = ray.intersectObject(terreno, false)[0];
    activo = !!p;
    if (p) { terreno.worldToLocal(apuntar.copy(p.point)); if (!u.cantidad.value) u.brocha.value.copy(apuntar); }
    pedir();
  }
  function soltar() { encima = false; activo = false; pedir(); }

  function pedir() { if (!raf && !document.hidden) raf = requestAnimationFrame(dibujar); }
  function dibujar(ahora: number) {
    raf = 0;
    const dt = Math.min(0.06, (ahora - prev) / 1000 || 0.016);
    prev = ahora;
    const mov = !quieto.matches;
    if (encima && mov) deriva += 0.58 * dt;
    const meta = encima && mov ? base + px * 0.7 + deriva : base;
    let delta = meta - angulo;
    delta = Math.atan2(Math.sin(delta), Math.cos(delta));
    angulo = mov ? angulo + delta * (1 - Math.exp(-10 * dt)) : meta;
    giro.rotation.y = angulo;
    if (!encima) deriva = Math.atan2(Math.sin(deriva), Math.cos(deriva)) * Math.exp(-6 * dt);
    const tgt = mov && (activo || previa) ? 1 : 0;
    u.brocha.value.lerp(activo ? apuntar : previa ? ejemplo : u.brocha.value, 1 - Math.exp(-16 * dt));
    u.cantidad.value += (tgt - u.cantidad.value) * (1 - Math.exp(-(tgt ? 7.5 : 3.5) * dt));
    if (!tgt && u.cantidad.value < 0.002) u.cantidad.value = 0;
    u.reloj.value = ahora / 1000;
    u.oscuro.value = document.documentElement.dataset.tema === "oscuro" || matchMedia("(prefers-color-scheme: dark)").matches ? 1 : 0;
    renderer.render(escena, camara);
    if (Math.abs(delta) > 0.0008 || encima || tgt || u.cantidad.value > 0) pedir();
  }

  canvas.addEventListener("pointermove", golpe);
  canvas.addEventListener("pointerdown", golpe);
  for (const ev of ["pointerleave", "pointercancel"]) canvas.addEventListener(ev, soltar);
  canvas.addEventListener("pointerup", (e) => { if (e.pointerType === "touch") soltar(); });
  const ro = new ResizeObserver(encuadrar);
  ro.observe(canvas);
  document.addEventListener("visibilitychange", () => { if (document.hidden) soltar(); else pedir(); });

  return {
    mostrar,
    girar() { base += Math.PI / 4; pedir(); },
    soplar() { previa = !previa; if (previa && !u.cantidad.value) u.brocha.value.copy(ejemplo); pedir(); },
    destruir() { cancelAnimationFrame(raf); ro.disconnect(); limpiar(); renderer.dispose(); },
  };
}
