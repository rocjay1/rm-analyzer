package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/csvparse"
	"github.com/rocjay1/rm-analyzer/internal/models"
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
		slog.Error("failed to read queue request body", "error", err)
		WriteError(w, http.StatusBadRequest, "Failed to read request body")
		return
	}

	if err := json.Unmarshal(bodyBytes, &invokeReq); err != nil {
		slog.Error("failed to unmarshal queue request", "error", err)
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
		slog.Error("failed to unmarshal queueItem", "error", err)
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("Invalid queueItem JSON: %v", err))
		return
	}

	blobName := queueData["blob_name"]
	if blobName == "" {
		slog.Warn("queue message missing blob_name", "queue_data", queueData)
		WriteError(w, http.StatusBadRequest, "Missing blob_name")
		return
	}

	slog.Info("processing queue item", "blob_name", blobName, "container", "uploads")

	csvContent, err := d.Blob.DownloadText(r.Context(), "uploads", blobName)
	if err != nil {
		slog.Error("failed to download CSV from blob", "blob_name", blobName, "container", "uploads", "error", err)
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to download CSV: %v", err))
		return
	}

	transactions, errors := csvparse.ParseCSV(csvContent)
	slog.Info("parsed CSV content", "blob_name", blobName, "transactions_count", len(transactions), "errors_count", len(errors))

	if len(errors) > 0 && len(transactions) == 0 {
		slog.Warn("CSV validation failed with no valid transactions", "blob_name", blobName, "errors_count", len(errors))
		// Consume the message so it doesn't retry forever.
		w.WriteHeader(http.StatusOK)
		return
	}

	newTransactions, err := d.Database.SaveTransactions(r.Context(), transactions)
	if err != nil {
		slog.Error("failed to save transactions", "total_count", len(transactions), "error", err)
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to save transactions: %v", err))
		return
	}
	slog.Info("saved new transactions", "new_count", len(newTransactions), "total_parsed", len(transactions))

	if len(newTransactions) > 0 {
		cards, err := d.Database.GetCreditCards(r.Context())
		if err != nil {
			slog.Error("failed to get credit cards for balance updates", "error", err)
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
								slog.Info("skipping old transaction", "transaction_date", t.Date, "card_name", card.Name, "last_reconciled", card.LastReconciled)
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
					slog.Error("failed to update card balance", "account_number", accNum, "delta", delta.String(), "error", err)
				} else {
					slog.Info("updated card balance", "account_number", accNum, "delta", delta.String())
				}
			}
		}
	}

	slog.Info("queue processing complete", "blob_name", blobName, "new_transactions_count", len(newTransactions))
	w.WriteHeader(http.StatusOK)
}
