/**
 * Linterna del cursor (skill gradient-border-flashlight): un solo puntero ilumina la superficie y el
 * tramo de borde más cercano de cada tarjeta, incluidas las vecinas al otro lado del espacio entre ellas.
 * Se escriben coordenadas sin recortar para que el borde de la tarjeta vecina tome la parte correcta.
 */
const RADIO = 255;

export function iniciarLuz(raiz: HTMLElement = document.body) {
  if (matchMedia("(hover: none), (forced-colors: active)").matches) return;
  const visibles = new Set<HTMLElement>();
  const io = new IntersectionObserver((es) => es.forEach((e) => (e.isIntersecting ? visibles.add(e.target as HTMLElement) : visibles.delete(e.target as HTMLElement))));
  const vistos = new WeakSet<HTMLElement>();

  function preparar() {
    raiz.querySelectorAll<HTMLElement>(".luz").forEach((t) => {
      if (vistos.has(t)) return;
      vistos.add(t);
      const capa = document.createElement("span");
      capa.className = "luz-capa";
      capa.setAttribute("aria-hidden", "true");
      t.prepend(capa);
      io.observe(t);
    });
  }
  preparar();
  new MutationObserver(preparar).observe(raiz, { childList: true, subtree: true });

  const p = { x: -9999, y: -9999 };
  let raf = 0;
  function pintar() {
    raf = 0;
    const rects = [...visibles].map((t) => [t, t.getBoundingClientRect()] as const);   // leer todo antes de escribir
    for (const [t, r] of rects) {
      const x = p.x - r.left, y = p.y - r.top;
      const dx = Math.max(0, -x, x - r.width), dy = Math.max(0, -y, y - r.height);
      const encendida = Math.hypot(dx, dy) < RADIO;
      t.style.setProperty("--lx", `${x}px`);
      t.style.setProperty("--ly", `${y}px`);
      t.classList.toggle("luz-on", encendida);
    }
  }
  const pedir = () => { if (!raf) raf = requestAnimationFrame(pintar); };
  document.addEventListener("pointermove", (e) => { if (e.pointerType === "touch") return; p.x = e.clientX; p.y = e.clientY; pedir(); }, { passive: true });
  document.addEventListener("scroll", pedir, { capture: true, passive: true });
  addEventListener("resize", pedir);
  const apagar = () => { p.x = p.y = -9999; pedir(); };
  document.addEventListener("pointerleave", apagar);
  addEventListener("blur", apagar);
}
