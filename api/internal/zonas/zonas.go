// Package zonas sirve el GeoJSON de recetas que genera `python -m atlas construir`.
package zonas

import (
	"encoding/json"
	"os"
	"sync"
	"time"
)

type Coleccion struct {
	Type     string           `json:"type"`
	Metadata map[string]any   `json:"metadata"`
	Features []map[string]any `json:"features"`
}

type Almacen struct {
	ruta   string
	mu     sync.RWMutex
	col    *Coleccion
	ligera []byte
	porID  map[string]map[string]any
	mtime  time.Time
}

func Nuevo(ruta string) (*Almacen, error) {
	a := &Almacen{ruta: ruta}
	return a, a.Recargar()
}

// claves que se conservan en la versión ligera (para pintar el mapa sin descargar todas las recetas)
var ligeras = []string{"id", "pais", "departamento", "franja", "dist_mar_km", "regimen", "indice_niebla",
	"deposicion_cl_mg_m2_d", "clase_iso9223", "ideal_cierre_pct", "ideal_vida_anios", "ideal_costo_m3",
	"ideal_disponibilidad", "economica_costo_m3"}

func (a *Almacen) Recargar() error {
	st, err := os.Stat(a.ruta)
	if err != nil {
		return err
	}
	if !st.ModTime().After(a.mtime) {
		return nil
	}
	b, err := os.ReadFile(a.ruta)
	if err != nil {
		return err
	}
	var c Coleccion
	if err := json.Unmarshal(b, &c); err != nil {
		return err
	}
	por := map[string]map[string]any{}
	lig := Coleccion{Type: c.Type, Metadata: c.Metadata}
	for _, f := range c.Features {
		props, _ := f["properties"].(map[string]any)
		id, _ := props["id"].(string)
		por[id] = f
		p := map[string]any{}
		for _, k := range ligeras {
			p[k] = props[k]
		}
		lig.Features = append(lig.Features, map[string]any{"type": "Feature", "id": id, "geometry": f["geometry"], "properties": p})
	}
	lb, _ := json.Marshal(lig)
	a.mu.Lock()
	a.col, a.porID, a.ligera, a.mtime = &c, por, lb, st.ModTime()
	a.mu.Unlock()
	return nil
}

func (a *Almacen) Ligera() []byte {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.ligera
}

func (a *Almacen) Zona(id string) (map[string]any, bool) {
	a.mu.RLock()
	defer a.mu.RUnlock()
	f, ok := a.porID[id]
	return f, ok
}

func (a *Almacen) Metadata() map[string]any {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.col.Metadata
}
