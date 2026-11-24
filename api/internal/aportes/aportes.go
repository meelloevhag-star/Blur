// Package aportes recibe ensayos de terceros, los valida con las mismas reglas que
// biocrete_neat/aportes/validar_aportes.py y los guarda como CSV (plantilla_aportes_atlas.csv)
// listos para `python -m atlas sync --aportes <carpeta>`. Nada se corrige ni se imputa.
package aportes

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Columnas = plantilla base de Blur + campos extendidos del Atlas (mismo orden que el CSV de plantilla).
var Columnas = []string{"autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo", "fecha_ensayo",
	"id_probeta", "a_c", "nivel_proteccion", "ambiente_marino", "usa_lactato", "curado_previo", "w0_mm",
	"edad_dias", "wt_mm", "cierre_pct", "notas", "portador", "tiene_bacterias", "cepa", "dosis_bacteria",
	"nutriente", "nutriente_dosis_kg_m3", "tipo_cemento", "adicion_mineral", "agregado_tmn_mm", "lat", "lon",
	"temperatura_c", "humedad_relativa_pct", "regimen_exposicion"}

var obligatorios = []string{"autor_aporte", "institucion", "tipo_fuente", "doi_o_url", "norma_ensayo",
	"id_probeta", "nivel_proteccion", "ambiente_marino", "w0_mm", "edad_dias"}
var tiposFuente = map[string]bool{"tesis": true, "articulo": true, "laboratorio": true, "dataset": true}
var rangos = map[string][2]float64{"w0_mm": {0, 2}, "edad_dias": {0, 1000}, "wt_mm": {0, 3}, "cierre_pct": {0, 100},
	"a_c": {0.2, 0.9}, "lat": {-90, 90}, "lon": {-180, 180}, "temperatura_c": {-20, 50}, "humedad_relativa_pct": {0, 100}}
var binarios = []string{"ambiente_marino", "usa_lactato", "curado_previo", "tiene_bacterias"}

func num(s string) (float64, bool) {
	s = strings.ReplaceAll(strings.TrimSpace(s), ",", ".")
	if s == "" {
		return 0, false
	}
	v, err := strconv.ParseFloat(s, 64)
	return v, err == nil
}

// Validar devuelve la lista de problemas (vacía = fila aceptada).
func Validar(f map[string]string) []string {
	var errs []string
	for _, k := range obligatorios {
		if strings.TrimSpace(f[k]) == "" {
			errs = append(errs, "falta "+k)
		}
	}
	if t := f["tipo_fuente"]; t != "" && !tiposFuente[t] {
		errs = append(errs, "tipo_fuente debe ser tesis|articulo|laboratorio|dataset")
	}
	for k, r := range rangos {
		if s := f[k]; strings.TrimSpace(s) != "" {
			v, ok := num(s)
			if !ok || v < r[0] || v > r[1] {
				errs = append(errs, fmt.Sprintf("%s fuera de rango [%g, %g]", k, r[0], r[1]))
			}
		}
	}
	for _, k := range binarios {
		if s := strings.TrimSpace(f[k]); s != "" && s != "0" && s != "1" {
			errs = append(errs, k+" debe ser 0 o 1")
		}
	}
	if n := strings.TrimSpace(f["nivel_proteccion"]); n != "" && !strings.Contains("0123", n) {
		errs = append(errs, "nivel_proteccion debe ser 0-3")
	}
	_, hayWt := num(f["wt_mm"])
	_, hayC := num(f["cierre_pct"])
	if !hayWt && !hayC {
		errs = append(errs, "se necesita wt_mm o cierre_pct")
	}
	if strings.Contains(strings.ToLower(f["notas"]), "fila de ejemplo") {
		errs = append(errs, "es la fila de ejemplo de la plantilla")
	}
	return errs
}

type Almacen struct {
	dir string
	mu  sync.Mutex
}

func Nuevo(dir string) (*Almacen, error) {
	return &Almacen{dir: dir}, os.MkdirAll(dir, 0o755)
}

func (a *Almacen) archivoDelDia() string {
	return filepath.Join(a.dir, "aportes_"+time.Now().UTC().Format("20060102")+".csv")
}

// Guardar añade filas ya validadas al CSV del día.
func (a *Almacen) Guardar(filas []map[string]string) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	ruta := a.archivoDelDia()
	_, err := os.Stat(ruta)
	nuevo := os.IsNotExist(err)
	fh, err := os.OpenFile(ruta, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer fh.Close()
	w := csv.NewWriter(fh)
	if nuevo {
		w.Write(Columnas)
	}
	for _, f := range filas {
		reg := make([]string, len(Columnas))
		for i, c := range Columnas {
			reg[i] = f[c]
		}
		w.Write(reg)
	}
	w.Flush()
	return w.Error()
}

func (a *Almacen) Archivos() ([]string, error) {
	return filepath.Glob(filepath.Join(a.dir, "aportes_*.csv"))
}
