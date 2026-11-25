/**
 * Portada: relieve real de las Lomas de Lachay (DEM Copernicus) grabado en líneas.
 *
 * Técnica (skill interactive-topography): una sola rejilla de alturas medida; cada fila tierra adentro
 * se proyecta en perspectiva y se dibuja como una línea de cresta, de atrás hacia adelante, tapando
 * lo que queda detrás. La franja de nubes (300–1 000 m) se resalta. El cursor ilumina las líneas
 * cercanas y, al presionar, una onda sísmica de granos cruza el relieve y vuelve a su sitio.
 * La capa estática se dibuja una vez; solo se redibuja la capa en movimiento.
 */
interface Rejilla { nx: number; ny: number; h: number[]; lugar: string }

const NIEBLA = [300, 1000];
const quieto = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export async function iniciarPortada(el: HTMLElement, alEntrar: () => void) {
  const fondo = el.querySelector<HTMLCanvasElement>("#portada-relieve")!;
  const capa = el.querySelector<HTMLCanvasElement>("#portada-luz")!;
  let datos: Rejilla;
  try {
    datos = await (await fetch("fondo/portada_lachay.json")).json();
  } catch {
    return;            // sin relieve, la portada sigue siendo legible
  }
  const cx = fondo.getContext("2d")!, lx = capa.getContext("2d")!;
  let W = 0, H = 0, dpr = 1;
  // muestreo más ralo en pantallas chicas
  let paso = 1;
  type P = { x: number; y: number; h: number };
  let filas: P[][] = [];
  const granos: { fila: number; col: number; sem: number }[] = [];
  let semilla = 4242;
  const azar = () => { semilla = (Math.imul(semilla, 1664525) + 1013904223) >>> 0; return semilla / 4294967296; };
  for (let i = 0; i < 2600; i++) granos.push({ fila: Math.floor(azar() * datos.ny), col: Math.floor(azar() * datos.nx), sem: azar() });

  const tok = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  function proyectar() {
    const { nx, ny, h } = datos;
    const horizonte = H * 0.3, suelo = H * 1.02, esc = Math.min(W, H * 1.8);
    filas = [];
    for (let r = 0; r < ny; r += paso) {
      const t = r / (ny - 1);                 // 0 = mar (adelante), 1 = interior (atrás)
      const prof = 1 + t * 3.2;
      const base = horizonte + (suelo - horizonte) / prof;
      const fila: P[] = [];
      for (let c = 0; c < nx; c += paso) {
        const u = c / (nx - 1) - 0.5;
        const hm = h[r * nx + c];
        const x = W / 2 + (u * esc * 1.5) / prof;
        const y = base - (Math.max(hm, 0) / 2900) * H * 0.62 / prof;
        fila.push({ x, y, h: hm });
      }
      filas.push(fila);
    }
  }

  function dibujarFondo() {
    const bg = tok("--portada-fondo"), linea = tok("--portada-linea"), niebla = tok("--portada-niebla"), mar = tok("--portada-mar");
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx.fillStyle = bg;
    cx.fillRect(0, 0, W, H);
    for (let k = filas.length - 1; k >= 0; k--) {
      const f = filas[k];
      const t = k / (filas.length - 1);
      // tapar lo que queda detrás
      cx.beginPath();
      cx.moveTo(f[0].x, H);
      f.forEach((p) => cx.lineTo(p.x, p.y));
      cx.lineTo(f[f.length - 1].x, H);
      cx.closePath();
      cx.fillStyle = bg;
      cx.fill();
      const alfa = 0.18 + 0.62 * (1 - t);
      cx.lineWidth = 0.6 + 0.7 * (1 - t);
      // tramos de tierra (color base o franja de nubes) y de mar (punteado)
      for (let i = 1; i < f.length; i++) {
        const a = f[i - 1], b = f[i];
        if (a.h <= 0 && b.h <= 0) {
          if (i % 3) continue;
          cx.fillStyle = mar; cx.globalAlpha = alfa * 0.7;
          cx.fillRect(b.x, b.y, 1.1, 1.1);
          continue;
        }
        const enNiebla = (a.h + b.h) / 2 >= NIEBLA[0] && (a.h + b.h) / 2 <= NIEBLA[1];
        cx.strokeStyle = enNiebla ? niebla : linea;
        cx.globalAlpha = enNiebla ? Math.min(1, alfa * 1.35) : alfa;
        cx.beginPath(); cx.moveTo(a.x, a.y); cx.lineTo(b.x, b.y); cx.stroke();
      }
      cx.globalAlpha = 1;
    }
  }

  // ---------------- capa en movimiento: luz del cursor + onda sísmica ----------------
  const cursor = { x: -999, y: -999, activo: false };
  let onda: { x: number; y: number; t0: number; max: number } | null = null;
  let raf = 0;
  function pedir() { if (!raf) raf = requestAnimationFrame(dibujarLuz); }

  function dibujarLuz(ahora: number) {
    raf = 0;
    lx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lx.clearRect(0, 0, W, H);
    const R = Math.min(220, W * 0.22);
    if (cursor.activo) {
      lx.save();
      const g = lx.createRadialGradient(cursor.x, cursor.y, 0, cursor.x, cursor.y, R);
      g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(1, "rgba(255,255,255,0)");
      lx.lineWidth = 1.2;
      lx.strokeStyle = tok("--portada-brillo");
      lx.beginPath();
      for (const f of filas) {
        if (f[0].y < cursor.y - R * 2 && f[f.length - 1].y < cursor.y - R * 2) continue;
        let dentro = false;
        for (const p of f) {
          const cerca = Math.abs(p.x - cursor.x) < R && Math.abs(p.y - cursor.y) < R && p.h > 0;
          if (cerca && !dentro) { lx.moveTo(p.x, p.y); dentro = true; } else if (cerca) lx.lineTo(p.x, p.y); else dentro = false;
        }
      }
      lx.stroke();
      lx.globalCompositeOperation = "destination-in";      // la luz se apaga hacia el borde del círculo
      lx.fillStyle = g;
      lx.fillRect(cursor.x - R, cursor.y - R, R * 2, R * 2);
      lx.restore();
    }
    let sigue = false;
    if (onda && !quieto()) {
      const dur = 1.6, t = (ahora - onda.t0) / 1000 / dur;
      const frente = t * (onda.max + 120), ancho = 70;
      lx.fillStyle = tok("--portada-grano");
      for (const g of granos) {
        const fila = filas[Math.min(filas.length - 1, Math.floor(g.fila / paso))];
        const p = fila?.[Math.min(fila.length - 1, Math.floor(g.col / paso))];
        if (!p || p.h <= 0) continue;
        const dx = p.x - onda.x, dy = p.y - onda.y, d = Math.hypot(dx, dy) || 1;
        const s = (d - frente) / ancho;
        const empuje = Math.exp(-s * s) * 14 - Math.exp(-((s + 1.3) ** 2)) * 5;   // cresta y retroceso
        if (Math.abs(empuje) < 0.15) continue;
        const a = Math.min(1, Math.abs(empuje) / 8) * (1 - Math.min(1, t));
        lx.globalAlpha = a * (0.5 + 0.5 * g.sem);
        lx.fillRect(p.x + (dx / d) * empuje, p.y + (dy / d) * empuje - Math.abs(empuje) * 0.6, 1.6, 1.6);
      }
      lx.globalAlpha = 1;
      if (t < 1) sigue = true; else onda = null;
    }
    if (sigue) pedir();
  }

  function medir() {
    const r = el.getBoundingClientRect();
    W = r.width; H = r.height;
    dpr = Math.min(devicePixelRatio || 1, 2);
    paso = W < 700 ? 2 : 1;
    for (const c of [fondo, capa]) { c.width = W * dpr; c.height = H * dpr; c.style.width = `${W}px`; c.style.height = `${H}px`; }
    proyectar();
    dibujarFondo();
    pedir();
  }
  new ResizeObserver(medir).observe(el);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { dibujarFondo(); pedir(); });
  new MutationObserver(() => { dibujarFondo(); pedir(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  el.addEventListener("pointermove", (e) => { cursor.x = e.clientX; cursor.y = e.clientY; cursor.activo = e.pointerType !== "touch"; pedir(); });
  el.addEventListener("pointerleave", () => { cursor.activo = false; pedir(); });
  el.addEventListener("pointerdown", (e) => {
    if ((e.target as HTMLElement).closest("button, a")) return;
    const max = Math.max(...[[0, 0], [W, 0], [0, H], [W, H]].map(([x, y]) => Math.hypot(x - e.clientX, y - e.clientY)));
    onda = { x: e.clientX, y: e.clientY, t0: performance.now(), max };
    pedir();
  });

  el.querySelector<HTMLElement>("#portada-lugar")!.textContent = datos.lugar;
  const entrar = () => {
    el.classList.add("saliendo");
    setTimeout(() => { el.hidden = true; alEntrar(); }, quieto() ? 0 : 650);
  };
  el.querySelectorAll<HTMLElement>("[data-entrar]").forEach((b) => b.addEventListener("click", entrar));
  el.addEventListener("keydown", (e) => { if (e.key === "Escape") entrar(); });
}
