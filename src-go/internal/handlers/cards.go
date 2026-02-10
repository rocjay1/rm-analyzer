package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/rocjay1/rm-analyzer/internal/models"
)

// HandleCreditCards handles GET and POST requests for credit cards.
func (d *Dependencies) HandleCreditCards(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		cards, err := d.Database.GetCreditCards(r.Context())
		if err != nil {
			WriteError(w, http.StatusInternalServerError, "Failed to get credit cards: "+err.Error())
			return
		}
		for i := range cards {
			cards[i].PopulateCalculatedFields()
		}
		WriteJSON(w, http.StatusOK, cards)
		return
	}

	if r.Method == http.MethodPost {
		var card models.CreditCard
		if err := json.NewDecoder(r.Body).Decode(&card); err != nil {
			WriteError(w, http.StatusBadRequest, "Invalid request body")
			return
		}

		// Ensure ID is generated if missing (though front-end handles this or DB upsert)
		// For simplicity we trust simple upsert logic in DB service
		if err := d.Database.SaveCreditCard(r.Context(), card); err != nil {
			WriteError(w, http.StatusInternalServerError, "Failed to save credit card: "+err.Error())
			return
		}

		WriteJSON(w, http.StatusOK, map[string]string{"status": "success"})
		return
	}

	http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
}
