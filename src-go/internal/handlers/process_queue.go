package handlers

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/rocjay1/rm-analyzer/internal/utils"
	"github.com/shopspring/decimal"
)

// invokeRequest represents the payload from Azure Functions Custom Handler.
type invokeRequest struct {
	Data     map[string]any `json:"Data"`
	Metadata map[string]any `json:"Metadata"`
}

// ProcessQueue handles the queue trigger for processing uploaded CSVs.
func (d *Dependencies) ProcessQueue(w http.ResponseWriter, r *http.Request) {
	var invokeReq invokeRequest
	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		WriteError(w, http.StatusBadRequest, "Failed to read request body")
		return
	}

	if err := json.Unmarshal(bodyBytes, &invokeReq); err != nil {
		WriteError(w, http.StatusBadRequest, "Failed to unmarshal request")
		return
	}

	queueItemVal, ok := invokeReq.Data["queueItem"]
	if !ok {
		queueItemVal, ok = invokeReq.Data["queueitem"]
		if !ok {
			WriteError(w, http.StatusBadRequest, "Missing queueItem in Data")
			return
		}
	}

	queueItemStr, ok := queueItemVal.(string)
	if !ok {
		WriteError(w, http.StatusBadRequest, "queueItem is not a string")
		return
	}

	var queueData map[string]string
	if err := json.Unmarshal([]byte(queueItemStr), &queueData); err != nil {
		log.Printf("Error unmarshaling queueItem: %v", err)
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("Invalid queueItem JSON: %v", err))
		return
	}

	blobName := queueData["blob_name"]
	if blobName == "" {
		WriteError(w, http.StatusBadRequest, "Missing blob_name")
		return
	}

	log.Printf("Processing queue item for blob: %s", blobName)

	csvContent, err := d.Blob.DownloadText(r.Context(), "uploads", blobName)
	if err != nil {
		log.Printf("Failed to download CSV: %v", err)
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to download CSV: %v", err))
		return
	}

	transactions, errors := utils.ParseCSV(csvContent)

	people, err := d.Database.GetAllPeople(r.Context())
	if err != nil {
		log.Printf("Failed to get people: %v", err)
		WriteError(w, http.StatusInternalServerError, "Failed to get people")
		return
	}

	group := &models.Group{
		Members: people,
	}

	if len(errors) > 0 && len(transactions) == 0 {
		log.Printf("CSV Validation Errors: %v", errors)
		recipients := group.GetEmails()
		if err := d.Email.SendErrorEmail(r.Context(), recipients, errors); err != nil {
			log.Printf("Failed to send error email: %v", err)
		}
		// Consume the message so it doesn't retry forever.
		w.WriteHeader(http.StatusOK)
		return
	}

	newTransactions, err := d.Database.SaveTransactions(r.Context(), transactions)
	if err != nil {
		log.Printf("Failed to save transactions: %v", err)
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to save transactions: %v", err))
		return
	}
	log.Printf("Saved %d new transactions", len(newTransactions))

	if len(newTransactions) > 0 {
		cards, err := d.Database.GetCreditCards(r.Context())
		if err != nil {
			log.Printf("Failed to get credit cards: %v", err)
		} else {
			cardMap := make(map[int]models.CreditCard)
			for _, c := range cards {
				cardMap[c.AccountNumber] = c
			}

			cardUpdates := make(map[int]decimal.Decimal)
			for _, t := range newTransactions {
				if card, exists := cardMap[t.AccountNumber]; exists {
					// Skip transactions that predate the last reconciled balance.
					if card.LastReconciled != "" {
						lrDate, err := time.Parse("2006-01-02", card.LastReconciled)
						if err == nil {
							tDate, err := time.Parse("2006-01-02", t.Date)
							if err == nil && tDate.Before(lrDate) {
								log.Printf("Skipping old transaction %s for card %s", t.Date, card.Name)
								continue
							}
						}
					}
				}

				if _, exists := cardUpdates[t.AccountNumber]; !exists {
					cardUpdates[t.AccountNumber] = decimal.Zero
				}
				cardUpdates[t.AccountNumber] = cardUpdates[t.AccountNumber].Add(t.Amount)
			}

			for accNum, delta := range cardUpdates {
				if err := d.Database.UpdateCardBalance(r.Context(), accNum, delta); err != nil {
					log.Printf("Failed to update balance for %d: %v", accNum, err)
				}
			}
		}
	}

	// Use all parsed transactions (not just new ones) for the summary email,
	// matching the Python controller behavior.
	group.AddTransactions(transactions)

	hasTx := false
	for _, m := range group.Members {
		if len(m.Transactions) > 0 {
			hasTx = true
			break
		}
	}

	if !hasTx {
		log.Println("No valid transactions found for configured accounts.")
		w.WriteHeader(http.StatusOK)
		return
	}

	recipients := group.GetEmails()
	if err := d.Email.SendSummaryEmail(r.Context(), recipients, group, errors); err != nil {
		log.Printf("Failed to send summary email: %v", err)
		WriteError(w, http.StatusInternalServerError, "Failed to send summary email")
		return
	}

	log.Println("Processing complete")
	w.WriteHeader(http.StatusOK)
}
