package models

import (
	"github.com/shopspring/decimal"
)

// SavingsItem represents a single item in the savings breakdown.
type SavingsItem struct {
	Name string          `json:"name"`
	Cost decimal.Decimal `json:"cost"`
}

// SavingsData represents the savings data for a specific month.
type SavingsData struct {
	StartingBalance decimal.Decimal `json:"startingBalance"`
	Items           []SavingsItem   `json:"items"`
}
