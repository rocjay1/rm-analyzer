package csvparse

import (
	"encoding/csv"
	"fmt"
	"strings"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
)

// ParseCSV parses transactions from a CSV string.
// It returns a list of transactions and a list of error messages for invalid rows.
func ParseCSV(content string) ([]models.Transaction, []string) {
	reader := csv.NewReader(strings.NewReader(content))
	reader.TrimLeadingSpace = true

	// Read all records
	records, err := reader.ReadAll()
	if err != nil {
		return nil, []string{fmt.Sprintf("Failed to read CSV: %v", err)}
	}

	if len(records) < 2 {
		return []models.Transaction{}, nil // Empty or header-only
	}

	headers := parseHeaders(records[0])
	var transactions []models.Transaction
	var errors []string

	for i, record := range records[1:] {
		rowNum := i + 2
		if len(record) < len(headers) {
			errors = append(errors, fmt.Sprintf("Row %d: Not enough fields", rowNum))
			continue
		}

		rowMap := make(map[string]string)
		for j, header := range headers {
			if j < len(record) {
				rowMap[header] = strings.TrimSpace(record[j])
			}
		}

		t, err := mapToTransaction(rowMap)
		if err != nil {
			errors = append(errors, fmt.Sprintf("Row %d: %v", rowNum, err))
			continue
		}
		transactions = append(transactions, *t)
	}

	return transactions, errors
}

func parseHeaders(row []string) []string {
	headers := make([]string, len(row))
	for i, h := range row {
		headers[i] = strings.TrimSpace(h)
	}
	return headers
}

func mapToTransaction(row map[string]string) (*models.Transaction, error) {
	dateStr := row["Date"]
	if dateStr == "" {
		return nil, fmt.Errorf("missing Date")
	}

	if _, err := time.Parse("2006-01-02", dateStr); err != nil {
		return nil, fmt.Errorf("invalid Date format: %s", dateStr)
	}

	name := row["Name"]
	if name == "" {
		return nil, fmt.Errorf("missing Name")
	}

	accNumStr := row["Account Number"]
	if accNumStr == "" {
		return nil, fmt.Errorf("missing Account Number")
	}
	var accNum int
	if _, err := fmt.Sscanf(accNumStr, "%d", &accNum); err != nil {
		return nil, fmt.Errorf("invalid Account Number: %s", accNumStr)
	}

	amountStr := row["Amount"]
	if amountStr == "" {
		return nil, fmt.Errorf("missing Amount")
	}
	amount, err := decimal.NewFromString(amountStr)
	if err != nil {
		return nil, fmt.Errorf("invalid Amount: %s", amountStr)
	}

	catStr := row["Category"]
	category := models.Category(catStr)

	ignoreStr := row["Ignored From"]
	var ignore models.IgnoredFrom
	switch strings.ToLower(ignoreStr) {
	case "budget":
		ignore = models.IgnoredFromBudget
	case "everything":
		ignore = models.IgnoredFromEverything
	case "":
		ignore = models.IgnoredFromNothing
	default:

		return nil, fmt.Errorf("invalid Ignored From: %s", ignoreStr)
	}

	return &models.Transaction{
		Date:          dateStr,
		Name:          name,
		AccountNumber: accNum,
		Amount:        amount,
		Category:      category,
		Ignore:        ignore,
	}, nil
}
