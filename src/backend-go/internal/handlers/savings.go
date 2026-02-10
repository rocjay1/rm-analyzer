package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/rocjay1/rm-analyzer/internal/models"
)

// HandleSavings handles GET and POST requests for savings data.
func (d *Dependencies) HandleSavings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		d.getSavings(w, r)
	case http.MethodPost:
		d.saveSavings(w, r)
	default:
		WriteError(w, http.StatusMethodNotAllowed, "Method not allowed")
	}
}

func (d *Dependencies) getSavings(w http.ResponseWriter, r *http.Request) {
	month := r.URL.Query().Get("month")
	if month == "" {
		slog.Warn("get savings request missing month parameter", "path", r.URL.Path)
		WriteError(w, http.StatusBadRequest, "month parameter is required")
		return
	}

	slog.Info("fetching savings data", "month", month)
	data, err := d.Database.GetSavings(r.Context(), month)
	if err != nil {
		slog.Error("failed to get savings", "month", month, "error", err)
		WriteError(w, http.StatusInternalServerError, "Failed to get savings: "+err.Error())
		return
	}

	slog.Info("successfully retrieved savings", "month", month, "items_count", len(data.Items))
	WriteJSON(w, http.StatusOK, data)
}

func (d *Dependencies) saveSavings(w http.ResponseWriter, r *http.Request) {
	month := r.URL.Query().Get("month")
	if month == "" {
		slog.Warn("save savings request missing month parameter", "path", r.URL.Path)
		WriteError(w, http.StatusBadRequest, "month parameter is required")
		return
	}

	var data models.SavingsData
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		slog.Warn("invalid savings request body", "month", month, "error", err)
		WriteError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	slog.Info("saving savings data", "month", month, "items_count", len(data.Items))
	if err := d.Database.SaveSavings(r.Context(), month, &data); err != nil {
		slog.Error("failed to save savings", "month", month, "error", err)
		WriteError(w, http.StatusInternalServerError, "Failed to save savings: "+err.Error())
		return
	}

	slog.Info("successfully saved savings", "month", month, "items_count", len(data.Items))
	WriteJSON(w, http.StatusOK, map[string]string{"status": "success"})
}
