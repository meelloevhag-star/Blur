// Package modelo evalúa en Go el conjunto exportado por atlas/modelos.py (XGBoost bootstrap + NEAT),
// con la misma aritmética que la versión de Python, y lo recarga cuando el archivo cambia.
package modelo

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Portadores en el mismo orden que atlas/ingesta.py (PORTADORES).
var Portadores = []string{"ninguno", "cristalino", "Basilisk", "LWA", "hidrogel", "CNC"}

type nodoNEAT struct {
	ID        int          `json:"id"`
	Sesgo     float64      `json:"sesgo"`
	Respuesta float64      `json:"respuesta"`
	Enlaces   [][2]float64 `json:"enlaces"`
}

type redNEAT struct {
	Entradas []int      `json:"entradas"`
	Salidas  []int      `json:"salidas"`
	Nodos    []nodoNEAT `json:"nodos"`
}

type Paquete struct {
	Version   int       `json:"version"`
	Variables []string  `json:"variables"`
	MaxNorm   []float64 `json:"max_normalizacion"`
	XGB       struct {
		Base      float64          `json:"base"`
		Bootstrap [][][][5]float64 `json:"bootstrap"`
	} `json:"xgb"`
	NEAT     redNEAT        `json:"neat"`
	Soporte  map[string]int `json:"soporte_combinaciones"`
	RangoW0  [2]float64     `json:"rango_w0_mm"`
	RangoEd  [2]float64     `json:"rango_edad_dias"`
	CV       map[string]any `json:"cv"`
	pesoXGB  float64
	pesoNEAT float64
}

// Entrada es una mezcla/ensayo a evaluar (esquema de atlas.ingesta.vector_cierre).
type Entrada struct {
	W0mm           float64 `json:"w0_mm"`
	EdadDias       float64 `json:"edad_dias"`
	Portador       string  `json:"portador"`
	TieneBacterias bool    `json:"tiene_bacterias"`
	Nutriente      string  `json:"nutriente"`
	AmbienteMarino bool    `json:"ambiente_marino"`
	CuradoPrevio   bool    `json:"curado_previo"`
}

type Prediccion struct {
	CierrePct     float64    `json:"cierre_pct"`
	CierreXGBPct  float64    `json:"cierre_xgb_pct"`
	CierreIC95Pct [2]float64 `json:"cierre_ic95_pct"`
	CierreNEATPct float64    `json:"cierre_neat_pct"`
	NDatosComb    int        `json:"n_datos_combinacion"`
	Avisos        []string   `json:"avisos"`
	VersionModelo int        `json:"version_modelo"`
}

func b2f(b bool) float64 {
	if b {
		return 1
	}
	return 0
}

// Vector devuelve el vector crudo en el orden de entrenamiento.
func (e Entrada) Vector() ([]float64, error) {
	x := []float64{e.W0mm, e.EdadDias}
	ok := false
	for _, p := range Portadores {
		v := 0.0
		if strings.EqualFold(p, e.Portador) {
			v, ok = 1, true
		}
		x = append(x, v)
	}
	if !ok {
		return nil, fmt.Errorf("portador desconocido %q (válidos: %v)", e.Portador, Portadores)
	}
	nut := !(e.Nutriente == "" || e.Nutriente == "ninguno")
	return append(x, b2f(e.TieneBacterias), b2f(nut), b2f(e.AmbienteMarino), b2f(e.CuradoPrevio)), nil
}

func Cargar(ruta string) (*Paquete, error) {
	b, err := os.ReadFile(ruta)
	if err != nil {
		return nil, err
	}
	var p Paquete
	if err := json.Unmarshal(b, &p); err != nil {
		return nil, err
	}
	p.pesoXGB, p.pesoNEAT = 0.5, 0.5
	if pesos, ok := p.CV["pesos"].(map[string]any); ok {
		p.pesoXGB, _ = pesos["xgb"].(float64)
		p.pesoNEAT, _ = pesos["neat"].(float64)
	}
	return &p, nil
}

func (p *Paquete) normalizar(x []float64) []float64 {
	out := make([]float64, len(x))
	for i, v := range x {
		out[i] = math.Max(0, math.Min(1, v/p.MaxNorm[i]))
	}
	return out
}

// EvaluarXGB recorre un modelo bootstrap (lista de árboles en formato compacto).
func EvaluarXGB(arboles [][][5]float64, base float64, x []float64) float64 {
	s := base
	for _, t := range arboles {
		i := 0
		for t[i][0] >= 0 {
			if float32(x[int(t[i][0])]) < float32(t[i][1]) { // XGBoost compara en float32
				i = int(t[i][2])
			} else {
				i = int(t[i][3])
			}
		}
		s += t[i][4]
	}
	return s
}

// EvaluarNEAT reproduce neat.nn.FeedForwardNetwork con activación sigmoide de neat-python.
func EvaluarNEAT(r redNEAT, x []float64) float64 {
	v := map[int]float64{}
	for j, k := range r.Entradas {
		v[k] = x[j]
	}
	for _, n := range r.Nodos {
		s := 0.0
		for _, l := range n.Enlaces {
			s += v[int(l[0])] * l[1]
		}
		z := math.Max(-60, math.Min(60, 5*(n.Sesgo+n.Respuesta*s)))
		v[n.ID] = 1 / (1 + math.Exp(-z))
	}
	return v[r.Salidas[0]]
}

func clip01(v float64) float64 { return math.Max(0, math.Min(1, v)) }

func percentil(v []float64, q float64) float64 {
	s := append([]float64(nil), v...)
	sort.Float64s(s)
	pos := q / 100 * float64(len(s)-1)
	lo := int(math.Floor(pos))
	hi := int(math.Ceil(pos))
	return s[lo] + (s[hi]-s[lo])*(pos-float64(lo))
}

func r1(v float64) float64 { return math.Round(v*10) / 10 }

// PredecirVector devuelve las salidas sin redondeo (para pruebas de paridad con Python).
func (p *Paquete) PredecirVector(xc []float64) (media, neat float64, boot []float64) {
	xn := p.normalizar(xc)
	for _, m := range p.XGB.Bootstrap {
		boot = append(boot, clip01(EvaluarXGB(m, p.XGB.Base, xn)))
	}
	for _, b := range boot {
		media += b
	}
	media /= float64(len(boot))
	return media, EvaluarNEAT(p.NEAT, xn), boot
}

func (p *Paquete) Predecir(e Entrada) (Prediccion, error) {
	xc, err := e.Vector()
	if err != nil {
		return Prediccion{}, err
	}
	media, neat, boot := p.PredecirVector(xc)
	claves := []string{}
	for _, v := range xc[2:] {
		claves = append(claves, strconv.Itoa(int(v)))
	}
	n := p.Soporte[strings.Join(claves, "|")]
	pr := Prediccion{
		CierrePct:     r1((p.pesoXGB*media + p.pesoNEAT*neat) * 100),
		CierreXGBPct:  r1(media * 100),
		CierreIC95Pct: [2]float64{r1(percentil(boot, 2.5) * 100), r1(percentil(boot, 97.5) * 100)},
		CierreNEATPct: r1(neat * 100),
		NDatosComb:    n,
		Avisos:        []string{},
		VersionModelo: p.Version,
	}
	if n == 0 {
		pr.Avisos = append(pr.Avisos, "combinación sin datos en Blur: predicción extrapolada")
	}
	if e.W0mm < p.RangoW0[0] || e.W0mm > p.RangoW0[1] {
		pr.Avisos = append(pr.Avisos, fmt.Sprintf("w0 fuera del rango entrenado (%.2f–%.2f mm)", p.RangoW0[0], p.RangoW0[1]))
	}
	if e.EdadDias < p.RangoEd[0] || e.EdadDias > p.RangoEd[1] {
		pr.Avisos = append(pr.Avisos, fmt.Sprintf("edad fuera del rango entrenado (%.0f–%.0f d)", p.RangoEd[0], p.RangoEd[1]))
	}
	return pr, nil
}

// Recargable vigila el archivo y recarga el paquete cuando cambia (p. ej. tras `atlas sync`).
type Recargable struct {
	ruta  string
	mu    sync.RWMutex
	p     *Paquete
	mtime time.Time
}

func NuevoRecargable(ruta string) (*Recargable, error) {
	r := &Recargable{ruta: ruta}
	return r, r.recargar()
}

func (r *Recargable) recargar() error {
	st, err := os.Stat(r.ruta)
	if err != nil {
		return err
	}
	if !st.ModTime().After(r.mtime) {
		return nil
	}
	p, err := Cargar(r.ruta)
	if err != nil {
		return err
	}
	r.mu.Lock()
	r.p, r.mtime = p, st.ModTime()
	r.mu.Unlock()
	return nil
}

func (r *Recargable) Vigilar(cada time.Duration, log func(string, ...any)) {
	for range time.Tick(cada) {
		v := r.Actual().Version
		if err := r.recargar(); err != nil {
			log("recarga del modelo falló: %v", err)
		} else if r.Actual().Version != v {
			log("modelo recargado: v%d → v%d", v, r.Actual().Version)
		}
	}
}

func (r *Recargable) Actual() *Paquete {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.p
}
