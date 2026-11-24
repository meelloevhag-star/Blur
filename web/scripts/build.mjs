// Compila el frontend en dos salidas:
//   dist/            página completa (para servir con la API en Go: -web ../web/dist)
//   dist-artefacto/  fragmento para publicar como página estática (Leaflet desde cdnjs, todo lo demás en línea)
import { build } from "esbuild";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(raiz, "..");
const artefacto = process.argv.includes("--artefacto");
const LEAFLET = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js";
const FUENTES = "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@87.5,600..700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap";
const TITULO = "BioCrete Atlas";

const js = (await build({ entryPoints: [join(raiz, "src/main.ts")], bundle: true, minify: true, format: "iife",
  target: "es2020", write: false })).outputFiles[0].text;
const css = readFileSync(join(raiz, "node_modules/leaflet/dist/leaflet.css"), "utf8") + "\n" + readFileSync(join(raiz, "src/estilos.css"), "utf8");
const cuerpo = readFileSync(join(raiz, "src/cuerpo.html"), "utf8");
const datos = [["atlas/salida/web/zonas_ligero_per.geojson", "zonas_ligero_per.geojson"],
  ["atlas/salida/web/detalle", "detalle"], ["atlas/datos/geo/departamentos_per.geojson", "departamentos_per.geojson"]];

const salida = join(raiz, artefacto ? "dist-artefacto" : "dist");
mkdirSync(salida, { recursive: true });
rmSync(join(salida, "detalle"), { recursive: true, force: true });
for (const [o, d] of datos) cpSync(join(repo, o), join(salida, d), { recursive: true });
const cabeza = `<title>${TITULO}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="${FUENTES}">`;
if (artefacto) {
  writeFileSync(join(salida, "index.html"),
    `${cabeza}\n<style>\n${css}\n</style>\n${cuerpo}\n<script src="${LEAFLET}"></script>\n<script>\n${js}\n</script>\n`);
} else {
  writeFileSync(join(salida, "app.js"), js);
  writeFileSync(join(salida, "estilos.css"), css);
  writeFileSync(join(salida, "index.html"), `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
${cabeza}
<link rel="stylesheet" href="estilos.css"></head>
<body>
${cuerpo}
<script src="${LEAFLET}"></script>
<script src="app.js"></script>
</body></html>
`);
}
console.log(`listo → ${salida}`);
