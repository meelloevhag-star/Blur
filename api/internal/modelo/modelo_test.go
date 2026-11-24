package modelo

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
)

// La paridad con Python se verifica con el fixture que genera atlas/tests/test_paridad.py.
func TestParidadConPython(t *testing.T) {
	raiz := filepath.Join("..", "..", "..")
	p, err := Cargar(filepath.Join(raiz, "atlas", "modelos", "modelo_cierre.json"))
	if err != nil {
		t.Skip("sin modelo exportado:", err)
	}
	b, err := os.ReadFile(filepath.Join(raiz, "atlas", "tests", "fixture_paridad.json"))
	if err != nil {
		t.Skip("sin fixture:", err)
	}
	var casos []struct {
		X     []float64 `json:"x"`
		Media float64   `json:"xgb_media"`
		NEAT  float64   `json:"neat"`
	}
	if err := json.Unmarshal(b, &casos); err != nil {
		t.Fatal(err)
	}
	for i, c := range casos {
		m, n, _ := p.PredecirVector(c.X)
		if math.Abs(m-c.Media) > 1e-9 || math.Abs(n-c.NEAT) > 1e-9 {
			t.Fatalf("caso %d: go=(%v,%v) python=(%v,%v)", i, m, n, c.Media, c.NEAT)
		}
	}
	t.Logf("%d casos idénticos a Python (tolerancia 1e-9)", len(casos))
}

func TestPortadorDesconocido(t *testing.T) {
	if _, err := (Entrada{Portador: "magia"}).Vector(); err == nil {
		t.Fatal("se esperaba error")
	}
}
