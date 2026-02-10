package main

import (
	"errors"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/handlers"
	"github.com/rocjay1/rm-analyzer/internal/services"
	"github.com/shopspring/decimal"
)

func init() {
	decimal.MarshalJSONWithoutQuotes = true
}

func main() {
	// Initialize Services
	dbService, err := services.NewDatabaseService()
	if err != nil {
		log.Fatalf("Failed to init DatabaseService: %v", err)
	}

	blobService, err := services.NewBlobService()
	if err != nil {
		log.Fatalf("Failed to init BlobService: %v", err)
	}

	queueService, err := services.NewQueueService()
	if err != nil {
		log.Fatalf("Failed to init QueueService: %v", err)
	}

	emailService, err := services.NewEmailService(nil)
	if err != nil {
		log.Printf("Failed to init EmailService (continuing anyway): %v", err)
	}

	deps := &handlers.Dependencies{
		Database: dbService,
		Blob:     blobService,
		Queue:    queueService,
		Email:    emailService,
	}

	// Router
	mux := http.NewServeMux()

	// API Routes
	mux.HandleFunc("/api/savings", deps.HandleSavings)
	mux.HandleFunc("/api/cards", deps.HandleCreditCards)
	mux.HandleFunc("/api/upload", deps.HandleUpload)
	mux.HandleFunc("/ProcessQueue", deps.ProcessQueue)

	// Health check (optional, good for debugging)
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	// Get port from environment or default to 8080
	port := os.Getenv("FUNCTIONS_CUSTOMHANDLER_PORT")
	if port == "" {
		port = "8080"
	}

	// Wrap mux with logging middleware
	loggedMux := loggingMiddleware(mux)

	log.Printf("Starting server on port %s", port)
	if err := http.ListenAndServe(":"+port, loggedMux); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("Server failed: %v", err)
	}
}

type responseWriter struct {
	http.ResponseWriter
	status int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &responseWriter{ResponseWriter: w, status: http.StatusOK}

		next.ServeHTTP(rw, r)

		duration := time.Since(start)
		log.Printf("[Request] %s %s | %d | %v", r.Method, r.URL.Path, rw.status, duration)
	})
}
