package models

import (
	"github.com/shopspring/decimal"
)

// IgnoredFrom represents flags for ignoring transactions from certain calculations.
type IgnoredFrom string

const (
	IgnoredFromBudget     IgnoredFrom = "budget"
	IgnoredFromEverything IgnoredFrom = "everything"
	IgnoredFromNothing    IgnoredFrom = ""
)

// Transaction represents a single financial transaction.
type Transaction struct {
	Date          string          `json:"date"`
	Name          string          `json:"name"`
	AccountNumber int             `json:"accountNumber"`
	Amount        decimal.Decimal `json:"amount"`
	Category      Category        `json:"category"`
	Ignore        IgnoredFrom     `json:"ignore"`
}
