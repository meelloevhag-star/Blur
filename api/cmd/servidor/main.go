// Servidor HTTP del BioCrete Atlas.
//
//	go run ./cmd/servidor -raiz .. -puerto 8080 [-web ../web/dist]
//
// Variables de entorno: ATLAS_API_KEYS (claves separadas por coma para POST /aportes),
// ATLAS_ADMIN_KEY (para descargar los aportes), ATLAS_CORS (origen permitido, por defecto *).
package main

import (
	"encoding/csv"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/meelloevhag-star/blur/api/internal/aportes"
	"github.com/meelloevhag-star/blur/api/internal/modelo"
	"github.com/meelloevhag-star/blur/api/internal/zonas"
)

type servidor struct {
	modelo  *modelo.Recargable
	zonas   *zonas.Almacen
	aportes *aportes.Almacen
	claves  map[string]bool
	admin   string
	limite  *limitador
}

func jsonResp(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func errorResp(w http.ResponseWriter, code int, msg string) {
	jsonResp(w, code, map[string]string{"error": msg})
}

// limitador: token bucket por IP (aportes y predicciones).
type limitador struct {
	mu     sync.Mutex
	cubos  map[string]*cubo
	tasa   float64
	rafaga float64
}
type cubo struct {
	tokens float64
	ultimo time.Time
}

func (l *limitador) permitir(ip string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	c, ok := l.cubos[ip]
	ahora := time.Now()
	if !ok {
		c = &cubo{tokens: l.rafaga, ultimo: ahora}
		l.cubos[ip] = c
	}
	c.tokens = min(l.rafaga, c.tokens+ahora.Sub(c.ultimo).Seconds()*l.tasa)
	c.ultimo = ahora
	if c.tokens < 1 {
		return false
	}
	c.tokens--
	return true
}

func ipDe(r *http.Request) string {
	h, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return h
}

func (s *servidor) salud(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, 200, map[string]any{"estado": "ok", "modelo_version": s.modelo.Actual().Version})
}

func (s *servidor) version(w http.ResponseWriter, r *http.Request) {
	p := s.modelo.Actual()
	jsonResp(w, 200, map[string]any{"version": p.Version, "variables": p.Variables, "cv": p.CV,
		"metadata_zonas": s.zonas.Metadata()})
}

func (s *servidor) listaZonas(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/geo+json")
	w.Write(s.zonas.Ligera())
}

func (s *servidor) zona(w http.ResponseWriter, r *http.Request) {
	f, ok := s.zonas.Zona(r.PathValue("id"))
	if !ok {
		errorResp(w, 404, "zona no encontrada")
		return
	}
	jsonResp(w, 200, f)
}

func (s *servidor) recomendacion(w http.ResponseWriter, r *http.Request) {
	f, ok := s.zonas.Zona(r.PathValue("id"))
	if !ok {
		errorResp(w, 404, "zona no encontrada")
		return
	}
	p := f["properties"].(map[string]any)
	tipo := r.URL.Query().Get("tipo")
	recetas := p["recetas"].(map[string]any)
	if tipo != "" {
		rec, ok := recetas[tipo]
		if !ok {
			errorResp(w, 400, "tipo debe ser ideal|economica|disponible")
			return
		}
		jsonResp(w, 200, map[string]any{"zona": p["id"], "regimen": p["regimen"], "reglas": p["reglas"], "receta": rec})
		return
	}
	jsonResp(w, 200, map[string]any{"zona": p["id"], "regimen": p["regimen"], "reglas": p["reglas"],
		"recetas": recetas, "referencia_sin_agente": p["referencia_sin_agente"]})
}

func (s *servidor) predecir(w http.ResponseWriter, r *http.Request) {
	if !s.limite.permitir(ipDe(r)) {
		errorResp(w, 429, "demasiadas solicitudes")
		return
	}
	var e modelo.Entrada
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&e); err != nil {
		errorResp(w, 400, "JSON inválido: "+err.Error())
		return
	}
	pr, err := s.modelo.Actual().Predecir(e)
	if err != nil {
		errorResp(w, 400, err.Error())
		return
	}
	jsonResp(w, 200, pr)
}

func leerFilas(r *http.Request) ([]map[string]string, error) {
	cuerpo := io.LimitReader(r.Body, 2<<20)
	if strings.HasPrefix(r.Header.Get("Content-Type"), "text/csv") {
		recs, err := csv.NewReader(cuerpo).ReadAll()
		if err != nil {
			return nil, err
		}
		if len(recs) < 2 {
			return nil, errors.New("CSV sin filas")
		}
		var filas []map[string]string
		for _, rec := range recs[1:] {
			f := map[string]string{}
			for i, c := range recs[0] {
				if i < len(rec) {
					f[strings.TrimSpace(c)] = strings.TrimSpace(rec[i])
				}
			}
			filas = append(filas, f)
		}
		return filas, nil
	}
	var filas []map[string]any
	if err := json.NewDecoder(cuerpo).Decode(&filas); err != nil {
		return nil, err
	}
	out := make([]map[string]string, len(filas))
	for i, f := range filas {
		out[i] = map[string]string{}
		for k, v := range f {
			b, _ := json.Marshal(v)
			out[i][k] = strings.Trim(string(b), `"`)
		}
	}
	return out, nil
}

func (s *servidor) recibirAportes(w http.ResponseWriter, r *http.Request) {
	if len(s.claves) > 0 && !s.claves[r.Header.Get("X-API-Key")] {
		errorResp(w, 401, "clave de API inválida (cabecera X-API-Key)")
		return
	}
	if !s.limite.permitir(ipDe(r)) {
		errorResp(w, 429, "demasiadas solicitudes")
		return
	}
	filas, err := leerFilas(r)
	if err != nil {
		errorResp(w, 400, "no se pudo leer el cuerpo: "+err.Error())
		return
	}
	var ok []map[string]string
	var rechazos []map[string]any
	for i, f := range filas {
		if e := aportes.Validar(f); len(e) > 0 {
			rechazos = append(rechazos, map[string]any{"fila": i + 1, "motivos": e})
		} else {
			f["notas"] = strings.TrimSpace(f["notas"] + " [recibido vía API " + time.Now().UTC().Format(time.RFC3339) + "]")
			ok = append(ok, f)
		}
	}
	if len(ok) > 0 {
		if err := s.aportes.Guardar(ok); err != nil {
			errorResp(w, 500, err.Error())
			return
		}
	}
	jsonResp(w, 200, map[string]any{"aceptadas": len(ok), "rechazadas": rechazos,
		"siguiente_paso": "las filas aceptadas entran al modelo en el próximo `python -m atlas sync`"})
}

func (s *servidor) exportarAportes(w http.ResponseWriter, r *http.Request) {
	if s.admin == "" || r.Header.Get("X-API-Key") != s.admin {
		errorResp(w, 401, "requiere ATLAS_ADMIN_KEY")
		return
	}
	fs, _ := s.aportes.Archivos()
	nombres := []string{}
	for _, f := range fs {
		nombres = append(nombres, filepath.Base(f))
	}
	jsonResp(w, 200, map[string]any{"archivos": nombres})
}

func cors(origen string, h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", origen)
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(204)
			return
		}
		h.ServeHTTP(w, r)
	})
}

func main() {
	raiz := flag.String("raiz", "..", "raíz del repositorio Blur")
	puerto := flag.String("puerto", "8080", "puerto HTTP")
	web := flag.String("web", "", "carpeta del frontend compilado (opcional)")
	pais := flag.String("pais", "per", "país (minúsculas, ISO-3)")
	flag.Parse()

	m, err := modelo.NuevoRecargable(filepath.Join(*raiz, "atlas", "modelos", "modelo_cierre.json"))
	if err != nil {
		log.Fatal("modelo: ", err)
	}
	z, err := zonas.Nuevo(filepath.Join(*raiz, "atlas", "salida", "zonas_"+*pais+".geojson"))
	if err != nil {
		log.Fatal("zonas: ", err)
	}
	a, err := aportes.Nuevo(filepath.Join(*raiz, "atlas", "aportes", "pendientes"))
	if err != nil {
		log.Fatal(err)
	}
	claves := map[string]bool{}
	for _, k := range strings.Split(os.Getenv("ATLAS_API_KEYS"), ",") {
		if k = strings.TrimSpace(k); k != "" {
			claves[k] = true
		}
	}
	if len(claves) == 0 {
		log.Print("AVISO: ATLAS_API_KEYS vacío → POST /aportes abierto (solo para desarrollo)")
	}
	s := &servidor{modelo: m, zonas: z, aportes: a, claves: claves, admin: os.Getenv("ATLAS_ADMIN_KEY"),
		limite: &limitador{cubos: map[string]*cubo{}, tasa: 2, rafaga: 30}}
	go m.Vigilar(30*time.Second, log.Printf)
	go func() {
		for range time.Tick(30 * time.Second) {
			if err := z.Recargar(); err != nil {
				log.Printf("recarga de zonas falló: %v", err)
			}
		}
	}()

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/salud", s.salud)
	mux.HandleFunc("GET /api/modelo/version", s.version)
	mux.HandleFunc("GET /api/zonas", s.listaZonas)
	mux.HandleFunc("GET /api/zonas/{id}", s.zona)
	mux.HandleFunc("GET /api/zonas/{id}/recomendacion", s.recomendacion)
	mux.HandleFunc("POST /api/predecir", s.predecir)
	mux.HandleFunc("POST /api/aportes", s.recibirAportes)
	mux.HandleFunc("GET /api/aportes/archivos", s.exportarAportes)
	mux.HandleFunc("GET /api/openapi.yaml", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, filepath.Join(*raiz, "api", "openapi.yaml"))
	})
	if *web != "" {
		mux.Handle("/", http.FileServer(http.Dir(*web)))
	}
	origen := os.Getenv("ATLAS_CORS")
	if origen == "" {
		origen = "*"
	}
	log.Printf("BioCrete Atlas API en :%s (modelo v%d)", *puerto, m.Actual().Version)
	srv := &http.Server{Addr: ":" + *puerto, Handler: cors(origen, mux), ReadHeaderTimeout: 10 * time.Second}
	log.Fatal(srv.ListenAndServe())
}
