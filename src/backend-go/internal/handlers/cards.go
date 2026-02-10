package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/rocjay1/rm-analyzer/internal/models"
)

// HandleCreditCards handles GET and POST requests for credit cards.
func (d *Dependencies) HandleCreditCards(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		slog.Info("fetching credit cards", "method", r.Method, "path", r.URL.Path)
		cards, err := d.Database.GetCreditCards(r.Context())
		if err != nil {
			slog.Error("failed to get credit cards", "error", err)
			WriteError(w, http.StatusInternalServerError, "Failed to get credit cards: "+err.Error())
			return
		}
		slog.Info("successfully retrieved credit cards", "count", len(cards))
		for i := range cards {
			cards[i].PopulateCalculatedFields()
		}
		WriteJSON(w, http.StatusOK, cards)
		return
	}

	if r.Method == http.MethodPost {
		slog.Info("saving credit card", "method", r.Method, "path", r.URL.Path)
		var card models.CreditCard
		if err := json.NewDecoder(r.Body).Decode(&card); err != nil {
			slog.Warn("invalid credit card request body", "error", err)
			WriteError(w, http.StatusBadRequest, "Invalid request body")
			return
		}

		// Ensure ID is generated if missing (though front-end handles this or DB upsert)
		// For simplicity we trust simple upsert logic in DB service
		if err := d.Database.SaveCreditCard(r.Context(), card); err != nil {
			slog.Error("failed to save credit card", "card_name", card.Name, "account_number", card.AccountNumber, "error", err)
			WriteError(w, http.StatusInternalServerError, "Failed to save credit card: "+err.Error())
			return
		}

		slog.Info("successfully saved credit card", "card_name", card.Name, "account_number", card.AccountNumber)
		WriteJSON(w, http.StatusOK, map[string]string{"status": "success"})
		return
	}

	WriteError(w, http.StatusMethodNotAllowed, "Method not allowed")
}
