package main

import (
	"errors"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/handler"
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
		slog.Error("Failed to init DatabaseService", "error", err)
		os.Exit(1)
	}

	blobService, err := services.NewBlobService()
	if err != nil {
		slog.Error("Failed to init BlobService", "error", err)
		os.Exit(1)
	}

	queueService, err := services.NewQueueService()
	if err != nil {
		slog.Error("Failed to init QueueService", "error", err)
		os.Exit(1)
	}

	emailService, err := services.NewEmailService(nil)
	if err != nil {
		slog.Warn("Failed to init EmailService (continuing anyway)", "error", err)
	}

	deps := &handler.Dependencies{
		Database: dbService,
		Blob:     blobService,
		Queue:    queueService,
		Email:    emailService,
	}

	// Router
	mux := http.NewServeMux()

	// API Routes
	mux.HandleFunc("GET /api/savings", deps.HandleSavings)
	mux.HandleFunc("POST /api/savings", deps.HandleSavings)

	mux.HandleFunc("GET /api/cards", deps.HandleCreditCards)
	mux.HandleFunc("POST /api/cards", deps.HandleCreditCards)
	mux.HandleFunc("DELETE /api/cards", deps.HandleCreditCards)

	mux.HandleFunc("POST /api/upload", deps.HandleUpload)
	mux.HandleFunc("POST /ProcessQueue", deps.ProcessQueue)

	// Health check (optional, good for debugging)
	mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	// Get port from environment or default to 8080
	port := os.Getenv("FUNCTIONS_CUSTOMHANDLER_PORT")
	if port == "" {
		port = "8080"
	}

	// Wrap mux with logging middleware
	loggedMux := loggingMiddleware(mux)

	slog.Info("Starting server", "port", port)
	if err := http.ListenAndServe(":"+port, loggedMux); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("Server failed", "error", err)
		os.Exit(1)
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
		slog.Info("request completed", "method", r.Method, "path", r.URL.Path, "status", rw.status, "duration", duration)
	})
}
