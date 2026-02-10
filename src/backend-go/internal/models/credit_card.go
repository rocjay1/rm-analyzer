package models

import (
	"github.com/shopspring/decimal"
)

// Account represents a financial account synced from external sources.
type Account struct {
	ID             string          `json:"id"`
	Name           string          `json:"name"`
	Mask           string          `json:"mask"`
	Institution    string          `json:"institution"`
	CurrentBalance decimal.Decimal `json:"current_balance"`
	CreditLimit    decimal.Decimal `json:"credit_limit"`
	Type           string          `json:"type"`
}

// CreditCard represents a managed credit card with tracking for utilization.
type CreditCard struct {
	ID               string          `json:"id"` // RowKey
	Name             string          `json:"name"`
	AccountNumber    int             `json:"account_number"` // Last 4 digits
	CreditLimit      decimal.Decimal `json:"credit_limit"`
	DueDay           int             `json:"due_day"`
	StatementBalance decimal.Decimal `json:"statement_balance"`
	CurrentBalance   decimal.Decimal `json:"current_balance"`
	LastReconciled   string          `json:"last_reconciled,omitempty"` // ISO 8601 date string
	Utilization      float64         `json:"utilization"`               // Calculated
	TargetPayment    float64         `json:"target_payment"`            // Calculated
}

// CalculateUtilization calculates current utilization ratio.
func (c *CreditCard) CalculateUtilization() decimal.Decimal {
	if c.CreditLimit.IsZero() {
		return decimal.Zero
	}
	return c.CurrentBalance.Div(c.CreditLimit)
}

// CalculateTargetPayment calculates amount to pay to reach 10% utilization.
func (c *CreditCard) CalculateTargetPayment() decimal.Decimal {
	// target = limit * 0.1
	// payment = current - statement - target
	targetBalance := c.CreditLimit.Mul(decimal.NewFromFloat(0.1))
	return c.CurrentBalance.Sub(c.StatementBalance).Sub(targetBalance)
}

// PopulateCalculatedFields populates the float64 fields for JSON output.
func (c *CreditCard) PopulateCalculatedFields() {
	c.Utilization = c.CalculateUtilization().InexactFloat64()
	c.TargetPayment = c.CalculateTargetPayment().InexactFloat64()
}
