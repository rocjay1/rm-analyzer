package utils

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
	reader.TrimLeadingSpace = true // Handle leading whitespace in fields

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
		rowNum := i + 2 // 1-based index, skipping header
		// Ensure record has enough fields (simple check)
		if len(record) < len(headers) {
			errors = append(errors, fmt.Sprintf("Row %d: Not enough fields", rowNum))
			continue
		}

		// Map row to map based on headers
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
	// 1. Date
	dateStr := row["Date"]
	if dateStr == "" {
		return nil, fmt.Errorf("missing Date")
	}
	// Validate date format (YYYY-MM-DD)
	if _, err := time.Parse("2006-01-02", dateStr); err != nil {
		return nil, fmt.Errorf("invalid Date format: %s", dateStr)
	}

	// 2. Name
	name := row["Name"]
	if name == "" {
		return nil, fmt.Errorf("missing Name")
	}

	// 3. Account Number
	accNumStr := row["Account Number"]
	// Handle "Account Number" vs "Account" if needed? Python code uses "Account Number"
	if accNumStr == "" {
		return nil, fmt.Errorf("missing Account Number")
	}
	// Python: int(row['Account Number'])
	// But in Go we might need to handle parsing
	// Use fmt.Sscanf or strconv.Atoi?
	// NOTE: models.Transaction uses `AccountNumber int`
	var accNum int
	if _, err := fmt.Sscanf(accNumStr, "%d", &accNum); err != nil {
		return nil, fmt.Errorf("invalid Account Number: %s", accNumStr)
	}

	// 4. Amount
	amountStr := row["Amount"]
	if amountStr == "" {
		return nil, fmt.Errorf("missing Amount")
	}
	amount, err := decimal.NewFromString(amountStr)
	if err != nil {
		return nil, fmt.Errorf("invalid Amount: %s", amountStr)
	}

	// 5. Category
	catStr := row["Category"]
	category := models.Category(catStr)
	// Python uses Enum(value). Go doesn't inherently validate string conversion to type unless we check.
	// We should probably check against known categories if strict validation is required.
	// For now, simple cast.

	// 6. Ignored From
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
		// Python: IgnoredFrom(row['Ignored From']) would raise ValueError if invalid
		// We should error if it's not empty and not matching
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
