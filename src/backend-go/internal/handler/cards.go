package handler

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/google/uuid"
	"github.com/rocjay1/rm-analyzer/internal/models"
)

// HandleCreditCards handles GET, POST, and DELETE requests for credit cards.
func (d *Dependencies) HandleCreditCards(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
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

	case http.MethodPost:
		slog.Info("saving credit card", "method", r.Method, "path", r.URL.Path)
		var card models.CreditCard
		if err := json.NewDecoder(r.Body).Decode(&card); err != nil {
			slog.Warn("invalid credit card request body", "error", err)
			WriteError(w, http.StatusBadRequest, "Invalid request body")
			return
		}

		if card.ID == "" {
			card.ID = uuid.New().String()
		}

		if err := d.Database.SaveCreditCard(r.Context(), card); err != nil {
			slog.Error("failed to save credit card", "card_name", card.Name, "account_number", card.AccountNumber, "error", err)
			WriteError(w, http.StatusInternalServerError, "Failed to save credit card: "+err.Error())
			return
		}

		slog.Info("successfully saved credit card", "card_name", card.Name, "account_number", card.AccountNumber, "id", card.ID)
		WriteJSON(w, http.StatusOK, card)

	case http.MethodDelete:
		id := r.URL.Query().Get("id")
		if id == "" {
			WriteError(w, http.StatusBadRequest, "Missing card ID")
			return
		}

		slog.Info("deleting credit card", "id", id)
		if err := d.Database.DeleteCreditCard(r.Context(), id); err != nil {
			slog.Error("failed to delete credit card", "id", id, "error", err)
			WriteError(w, http.StatusInternalServerError, "Failed to delete credit card: "+err.Error())
			return
		}

		slog.Info("successfully deleted credit card", "id", id)
		WriteJSON(w, http.StatusOK, map[string]string{"status": "deleted"})

	default:
		WriteError(w, http.StatusMethodNotAllowed, "Method not allowed")
	}
}
