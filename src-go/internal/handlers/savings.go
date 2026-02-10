package handlers

import (
	"encoding/json"
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
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (d *Dependencies) getSavings(w http.ResponseWriter, r *http.Request) {
	month := r.URL.Query().Get("month")
	if month == "" {
		WriteError(w, http.StatusBadRequest, "month parameter is required")
		return
	}

	data, err := d.Database.GetSavings(r.Context(), month)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to get savings: "+err.Error())
		return
	}

	WriteJSON(w, http.StatusOK, data)
}

func (d *Dependencies) saveSavings(w http.ResponseWriter, r *http.Request) {
	month := r.URL.Query().Get("month")
	if month == "" {
		WriteError(w, http.StatusBadRequest, "month parameter is required")
		return
	}

	var data models.SavingsData
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if err := d.Database.SaveSavings(r.Context(), month, &data); err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to save savings: "+err.Error())
		return
	}

	WriteJSON(w, http.StatusOK, map[string]string{"status": "success"})
}
