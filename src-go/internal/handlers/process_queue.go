package handlers

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http" // Added back strings just in case, though might not be used if I don't use it.
	"time"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/rocjay1/rm-analyzer/internal/utils"
	"github.com/shopspring/decimal"
)

// invokeRequest represents the payload from Azure Functions Custom Handler
type invokeRequest struct {
	Data     map[string]interface{} `json:"Data"`
	Metadata map[string]interface{} `json:"Metadata"`
}

// ProcessQueue handles the queue trigger for processing uploaded CSVs.
func (d *Dependencies) ProcessQueue(w http.ResponseWriter, r *http.Request) {
	// 1. Parse Request
	var invokeReq invokeRequest
	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}

	if err := json.Unmarshal(bodyBytes, &invokeReq); err != nil {
		http.Error(w, "Failed to unmarshal request", http.StatusBadRequest)
		return
	}

	queueItemVal, ok := invokeReq.Data["queueItem"]
	if !ok {
		// Try lowercase just in case
		queueItemVal, ok = invokeReq.Data["queueitem"]
		if !ok {
			http.Error(w, "Missing queueItem in Data", http.StatusBadRequest)
			return
		}
	}

	// queueItem is a JSON string containing blob_name
	queueItemStr, ok := queueItemVal.(string)
	if !ok {
		// It might be directly map if not stringified?
		// Controller says "message_body = msg.get_body().decode('utf-8')"
		// So it is a string.
		http.Error(w, "queueItem is not a string", http.StatusBadRequest)
		return
	}

	var queueData map[string]string
	if err := json.Unmarshal([]byte(queueItemStr), &queueData); err != nil {
		// It might be raw string if not JSON?
		// Logic: Parse queueItem as JSON.
		fmt.Printf("Error unmarshaling queueItem: %v\n", err)
		http.Error(w, fmt.Sprintf("Invalid queueItem JSON: %v", err), http.StatusBadRequest)
		return
	}

	blobName := queueData["blob_name"]
	if blobName == "" {
		http.Error(w, "Missing blob_name", http.StatusBadRequest)
		return
	}

	fmt.Printf("Processing queue item for blob: %s\n", blobName)

	// 2. Download CSV
	// Assuming "uploads" container as per Python convention
	csvContent, err := d.Blob.DownloadText(r.Context(), "uploads", blobName)
	if err != nil {
		fmt.Printf("Failed to download CSV: %v\n", err)
		http.Error(w, fmt.Sprintf("Failed to download CSV: %v", err), http.StatusInternalServerError)
		return
	}

	// 3. Parse CSV
	transactions, errors := utils.ParseCSV(csvContent)

	// 4. Get People
	people, err := d.Database.GetAllPeople(r.Context())
	if err != nil {
		fmt.Printf("Failed to get people: %v\n", err)
		http.Error(w, "Failed to get people", http.StatusInternalServerError)
		return
	}

	// 5. Build Group
	group := &models.Group{
		Members: people,
	}

	// 6. Handle Validation Errors
	if len(errors) > 0 && len(transactions) == 0 {
		fmt.Printf("CSV Validation Errors: %v\n", errors)
		recipients := group.GetEmails()
		if err := d.Email.SendErrorEmail(r.Context(), recipients, errors); err != nil {
			fmt.Printf("Failed to send error email: %v\n", err)
		}
		// We consider this "success" in terms of handling the message,
		// effectively consuming it so it doesn't retry forever.
		w.WriteHeader(http.StatusOK)
		return
	}

	// 7. Save Transactions
	newTransactions, err := d.Database.SaveTransactions(r.Context(), transactions)
	if err != nil {
		fmt.Printf("Failed to save transactions: %v\n", err)
		http.Error(w, fmt.Sprintf("Failed to save transactions: %v", err), http.StatusInternalServerError)
		return
	}
	fmt.Printf("Saved %d new transactions\n", len(newTransactions))

	// 8. Update Credit Card Balances
	if len(newTransactions) > 0 {
		cards, err := d.Database.GetCreditCards(r.Context())
		if err != nil {
			fmt.Printf("Failed to get credit cards: %v\n", err)
			// Continue or fail? Python: logs error but proceeds to email?
			// Python catches exception for entire block.
		} else {
			cardMap := make(map[int]models.CreditCard)
			for _, c := range cards {
				cardMap[c.AccountNumber] = c
			}

			cardUpdates := make(map[int]decimal.Decimal)
			for _, t := range newTransactions {
				if card, exists := cardMap[t.AccountNumber]; exists {
					// Check Reconciliation
					// Parse LastReconciled (string YYYY-MM-DD or empty)
					if card.LastReconciled != "" {
						lrDate, err := time.Parse("2006-01-02", card.LastReconciled)
						if err == nil {
							// t.Date is string YYYY-MM-DD
							tDate, err := time.Parse("2006-01-02", t.Date)
							if err == nil && tDate.Before(lrDate) {
								fmt.Printf("Skipping old transaction %s for card %s\n", t.Date, card.Name)
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
					fmt.Printf("Failed to update balance for %d: %v\n", accNum, err)
				}
			}
		}
	}

	// 9. Send Summary Email
	// Add transactions to group for calculation
	// Note: We should probably use ALL transactions for the summary email?
	// Python uses 'transactions' (the parsed list), not 'new_transactions'.
	// Checked controller.py: group.add_transactions(transactions)
	// So yes, using full parsed list.
	group.AddTransactions(transactions)

	hasTx := false
	for _, m := range group.Members {
		if len(m.Transactions) > 0 {
			hasTx = true
			break
		}
	}

	if !hasTx {
		fmt.Println("No valid transactions found for configured accounts.")
		w.WriteHeader(http.StatusOK)
		return
	}

	recipients := group.GetEmails()
	if err := d.Email.SendSummaryEmail(r.Context(), recipients, group, errors); err != nil {
		fmt.Printf("Failed to send summary email: %v\n", err)
		http.Error(w, "Failed to send summary email", http.StatusInternalServerError)
		return
	}

	fmt.Println("Processing complete")
	w.WriteHeader(http.StatusOK)
}
