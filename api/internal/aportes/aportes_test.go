package aportes

import (
	"os"
	"path/filepath"
	"testing"
)

func fila() map[string]string {
	return map[string]string{"autor_aporte": "A", "institucion": "U", "tipo_fuente": "tesis", "doi_o_url": "x",
		"norma_ensayo": "EN 12390-8", "id_probeta": "P1", "nivel_proteccion": "1", "ambiente_marino": "1",
		"w0_mm": "0.3", "edad_dias": "28", "wt_mm": "0.1", "lat": "-5.08", "lon": "-81.1"}
}

func TestValidar(t *testing.T) {
	if e := Validar(fila()); len(e) != 0 {
		t.Fatal(e)
	}
	f := fila()
	f["w0_mm"] = "5"
	delete(f, "wt_mm")
	if e := Validar(f); len(e) != 2 {
		t.Fatalf("se esperaban 2 errores: %v", e)
	}
}

func TestGuardar(t *testing.T) {
	d := t.TempDir()
	a, _ := Nuevo(d)
	if err := a.Guardar([]map[string]string{fila(), fila()}); err != nil {
		t.Fatal(err)
	}
	fs, _ := filepath.Glob(filepath.Join(d, "*.csv"))
	b, _ := os.ReadFile(fs[0])
	if len(b) == 0 {
		t.Fatal("vacío")
	}
}
