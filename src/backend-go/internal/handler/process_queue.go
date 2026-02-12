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
	slog.Info("PROCESS QUEUE HANDLER INVOKED", "method", r.Method, "path", r.URL.Path)
	var invokeReq invokeRequest
	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		slog.Error("failed to read queue request body", "error", err)
		WriteError(w, http.StatusBadRequest, "Failed to read request body")
		return
	}

	slog.Info("RAW PROCESS QUEUE BODY", "body", string(bodyBytes))

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

	slog.Info("RAW QUEUE ITEM RECEIVED", "value", queueItemVal, "type", fmt.Sprintf("%T", queueItemVal))

	// queueItemVal is interface{}
	var blobName string

	switch v := queueItemVal.(type) {
	case string:
		// Attempt to unmarshal as map. If it's a quoted JSON string, this might fail or return just the string.
		var queueData map[string]interface{}
		if err := json.Unmarshal([]byte(v), &queueData); err != nil {
			// It might be a double-encoded string. Try unmarshaling into a string first.
			var innerStr string
			if err2 := json.Unmarshal([]byte(v), &innerStr); err2 == nil {
				// Now try unmarshaling the inner string into a map
				if err3 := json.Unmarshal([]byte(innerStr), &queueData); err3 == nil {
					slog.Info("successfully unmarshaled double-encoded queueItem")
				} else {
					slog.Error("failed to unmarshal inner queueItem string", "error", err3, "inner_value", innerStr)
					WriteError(w, http.StatusBadRequest, "Invalid inner queueItem JSON")
					return
				}
			} else {
				slog.Error("failed to unmarshal queueItem as string or map", "error", err, "value", v)
				WriteError(w, http.StatusBadRequest, "Invalid queueItem format")
				return
			}
		}
		if name, ok := queueData["blobName"].(string); ok {
			blobName = name
		} else if name, ok := queueData["blob_name"].(string); ok {
			blobName = name
		}
	case map[string]interface{}:
		if name, ok := v["blobName"].(string); ok {
			blobName = name
		} else if name, ok := v["blob_name"].(string); ok {
			blobName = name
		}
	default:
		slog.Error("unexpected type for queueItem", "type", fmt.Sprintf("%T", queueItemVal))
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("queueItem is unexpected type: %T", queueItemVal))
		return
	}

	if blobName == "" {
		slog.Warn("queue message missing blobName or blob_name", "queue_item", queueItemVal)
		WriteError(w, http.StatusBadRequest, "Missing blobName in queue message")
		return
	}

	slog.Info("processing queue item", "blob_name", blobName, "container", "rm-analyzer-data")

	csvContent, err := d.Blob.DownloadText(r.Context(), "rm-analyzer-data", blobName)
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
			cardLastReconciled := make(map[int]string)

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

				// Track the latest transaction date for reconciliation
				if currentLast, exists := cardLastReconciled[t.AccountNumber]; !exists || t.Date > currentLast {
					cardLastReconciled[t.AccountNumber] = t.Date
				}
			}

			for accNum, delta := range cardUpdates {
				lastReconciled := cardLastReconciled[accNum]
				if err := d.Database.UpdateCardBalance(r.Context(), accNum, delta, lastReconciled); err != nil {
					slog.Error("failed to update card balance", "account_number", accNum, "delta", delta.String(), "error", err)
				} else {
					slog.Info("updated card balance", "account_number", accNum, "delta", delta.String(), "last_reconciled", lastReconciled)
				}
			}
		}
	}

	slog.Info("queue processing complete", "blob_name", blobName, "new_transactions_count", len(newTransactions))
	w.WriteHeader(http.StatusOK)
}
