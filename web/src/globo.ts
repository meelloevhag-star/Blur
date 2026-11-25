/**
 * Globo de entrada (Meridian Earth, skill cobejs): la Tierra gira despacio con la costa peruana
 * encendida (centroides de las celdas). Se puede arrastrar. Al entrar, gira hasta centrar el Perú
 * y se desvanece mientras el mapa vuela hacia la costa.
 */
import createGlobe from "cobe";

export interface Globo { centrarPeru(): Promise<void>; destruir(): void }

const aAngulos = (lat: number, lon: number): [number, number] =>
  [Math.PI - ((lon * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];

/** ¿WebGL por software? (SwiftShader/llvmpipe pintan cobe en negro): entonces se usa el globo de líneas. */
function webglSoftware(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    if (!gl) return true;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const r = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    return /swiftshader|llvmpipe|software/i.test(r);
  } catch { return true; }
}

/**
 * Globo de líneas en Canvas 2D (respaldo, estilo wireframe técnico): esfera ortográfica con retícula
 * cada 15°, el contorno del Perú por departamentos y la costa encendida con las celdas.
 */
function globoLineas(canvas: HTMLCanvasElement, puntos: [number, number][]): Globo {
  const ctx = canvas.getContext("2d")!;
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lon0 = -40, meta: number | null = null, raf = 0, alListo: (() => void) | null = null;
  const lat0 = -8 * Math.PI / 180;
  let deptos: number[][][] = [];
  fetch("departamentos_per.geojson").then((r) => r.json()).then((g) => {
    for (const f of g.features) {
      const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const p of polys) deptos.push(p[0]);
    }
  }).catch(() => {});
  const tok = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  function proy(lat: number, lon: number, R: number, cx: number, cy: number): [number, number, boolean] {
    const f = lat * Math.PI / 180, l = (lon - lon0) * Math.PI / 180;
    const x = Math.cos(f) * Math.sin(l);
    const y = Math.cos(lat0) * Math.sin(f) - Math.sin(lat0) * Math.cos(f) * Math.cos(l);
    const z = Math.sin(lat0) * Math.sin(f) + Math.cos(lat0) * Math.cos(f) * Math.cos(l);
    return [cx + R * x, cy - R * y, z > 0];
  }
  function linea(pts: [number, number][], R: number, cx: number, cy: number) {
    let pen = false;
    ctx.beginPath();
    for (const [la, lo] of pts) {
      const [x, y, v] = proy(la, lo, R, cx, cy);
      if (!v) { pen = false; continue; }
      pen ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      pen = true;
    }
    ctx.stroke();
  }
  function dibujar() {
    raf = 0;
    const dpr = Math.min(devicePixelRatio || 1, 2), w = canvas.offsetWidth || 500;
    if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = w * dpr; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, w);
    const R = w * 0.42, c = w / 2;
    const tinta = tok("--suave") || "#93a7a2", acento = tok("--portada-niebla") || "#5ee0b8";
    const g = ctx.createRadialGradient(c - R * 0.3, c - R * 0.3, R * 0.1, c, c, R * 1.08);
    g.addColorStop(0, "rgba(94,224,184,0.10)"); g.addColorStop(1, "rgba(94,224,184,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(c, c, R * 1.08, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = tinta; ctx.globalAlpha = 0.55; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(c, c, R, 0, Math.PI * 2); ctx.stroke();
    ctx.globalAlpha = 0.18;
    for (let lo = -180; lo < 180; lo += 15) linea(Array.from({ length: 61 }, (_, i) => [-90 + i * 3, lo]), R, c, c);
    for (let la = -75; la <= 75; la += 15) linea(Array.from({ length: 121 }, (_, i) => [la, -180 + i * 3]), R, c, c);
    ctx.globalAlpha = 0.7; ctx.strokeStyle = tinta;
    for (const p of deptos) linea(p.map(([lo, la]) => [la, lo] as [number, number]), R, c, c);
    ctx.globalAlpha = 1; ctx.fillStyle = acento; ctx.shadowColor = acento; ctx.shadowBlur = 6;
    for (const [la, lo] of puntos) { const [x, y, v] = proy(la, lo, R, c, c); if (v) ctx.fillRect(x - 1, y - 1, 2, 2); }
    ctx.shadowBlur = 0;
    if (meta !== null) {
      const d = ((meta - lon0 + 540) % 360) - 180;
      lon0 += d * 0.1;
      if (Math.abs(d) < 0.3 && alListo) { alListo(); alListo = null; }
    } else if (!quieto) lon0 -= 0.12;
    if (!quieto || meta !== null) raf = requestAnimationFrame(dibujar);
  }
  raf = requestAnimationFrame(dibujar);
  requestAnimationFrame(() => canvas.classList.add("visible"));
  return {
    centrarPeru() { if (quieto) return Promise.resolve(); meta = -76; if (!raf) raf = requestAnimationFrame(dibujar);
      return new Promise((r) => { alListo = r; setTimeout(r, 900); }); },
    destruir() { cancelAnimationFrame(raf); },
  };
}

export function crearGlobo(canvas: HTMLCanvasElement, puntos: [number, number][]): Globo | null {
  if (webglSoftware()) return globoLineas(canvas, puntos);
  const oscuro = () => document.documentElement.dataset.theme === "dark";
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let phi = aAngulos(-12, -76)[0] - 1.1, theta = 0.25, arrastre: number | null = null, deltaPhi = 0;
  let meta: [number, number] | null = null, alListo: (() => void) | null = null;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  let ancho = canvas.offsetWidth || 500;
  const marcadores = puntos.map(([lat, lon]) => ({ location: [lat, lon] as [number, number], size: 0.018 }));
  let globo: ReturnType<typeof createGlobe>;
  try {
    globo = createGlobe(canvas, {
      devicePixelRatio: dpr, width: ancho * dpr, height: ancho * dpr, phi, theta,
      dark: oscuro() ? 1 : 0, diffuse: 1.1, mapSamples: 14000, mapBrightness: oscuro() ? 4.2 : 1.6,
      baseColor: oscuro() ? [0.16, 0.22, 0.24] : [0.93, 0.92, 0.88],
      markerColor: oscuro() ? [0.37, 0.84, 0.7] : [0.05, 0.42, 0.35],
      glowColor: oscuro() ? [0.08, 0.16, 0.17] : [0.86, 0.9, 0.88],
      markers: marcadores,
      onRender: (st: Record<string, any>) => {
        if (meta) {
          const d = Math.atan2(Math.sin(meta[0] - phi), Math.cos(meta[0] - phi));
          phi += d * 0.08; theta += (meta[1] - theta) * 0.08;
          if (Math.abs(d) < 0.01 && Math.abs(meta[1] - theta) < 0.01 && alListo) { alListo(); alListo = null; }
        } else if (arrastre === null && !quieto) phi += 0.0028;
        st.phi = phi + deltaPhi; st.theta = theta;
        st.width = ancho * dpr; st.height = ancho * dpr;
        st.dark = oscuro() ? 1 : 0;
      },
    });
  } catch {
    return null;
  }
  const ro = new ResizeObserver(() => { ancho = canvas.offsetWidth || ancho; });
  ro.observe(canvas);
  canvas.addEventListener("pointerdown", (e) => { arrastre = e.clientX - deltaPhi * 200; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing"; });
  canvas.addEventListener("pointermove", (e) => { if (arrastre !== null) deltaPhi = (e.clientX - arrastre) / 200; });
  const soltar = () => { if (arrastre !== null) { phi += deltaPhi; deltaPhi = 0; } arrastre = null; canvas.style.cursor = ""; };
  canvas.addEventListener("pointerup", soltar);
  canvas.addEventListener("pointercancel", soltar);
  requestAnimationFrame(() => canvas.classList.add("visible"));
  return {
    centrarPeru() {
      if (quieto) return Promise.resolve();
      phi += deltaPhi; deltaPhi = 0;
      meta = aAngulos(-10, -76);
      return new Promise((r) => { alListo = r; setTimeout(r, 900); });
    },
    destruir() { ro.disconnect(); globo.destroy(); },
  };
}
