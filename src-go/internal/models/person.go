package models

import (
	"time"

	"github.com/shopspring/decimal"
)

// Person represents a person with accounts and transactions.
type Person struct {
	Name           string        `json:"name"`
	Email          string        `json:"email"`
	AccountNumbers []int         `json:"accountNumbers"`
	Transactions   []Transaction `json:"transactions"`
}

// Group represents a group of people for expense analysis.
type Group struct {
	Members []Person `json:"members"`
}

// GetExpenses calculates total expenses for a person, optionally filtered by category.
func (p *Person) GetExpenses(category Category) decimal.Decimal {
	total := decimal.Zero
	for _, t := range p.Transactions {
		if category != "" && t.Category != category {
			continue
		}
		total = total.Add(t.Amount)
	}
	return total
}

// AddTransaction adds a transaction to the person's list.
func (p *Person) AddTransaction(t Transaction) {
	p.Transactions = append(p.Transactions, t)
}

// GetOldestTransaction returns the date of the oldest transaction.
func (p *Person) GetOldestTransaction() (time.Time, error) {
	if len(p.Transactions) == 0 {
		return time.Time{}, nil
	}
	// TODO: Parse dates properly, assuming ISO8601 strings in Transaction.Date
	// For now, returning zero time as placeholder logic
	return time.Time{}, nil
}

// GetExpenses calculates the total expenses of the group.
// It effectively sums the expenses of all members.
func (g *Group) GetExpenses() decimal.Decimal {
	total := decimal.Zero
	for _, p := range g.Members {
		// p is a copy here if range over slice of values, but GetExpenses is on *Person?
		// Person.GetExpenses uses (p *Person) receiver.
		// If Members is []Person, then p is Person. &p is pointer to copy.
		// Wait, Person struct doesn't have pointer fields that matter much for reading, so copy is fine?
		// Actually, let's use index to get pointer to element in slice to be safe/efficient.
		// Or just value receiver for GetExpenses?
		// Step 706 shows `func (p *Person) GetExpenses`.
		// So we need address.
		// But in range loop `for _, p := range g.Members`, p is a copy.
		// Calling p.GetExpenses() will work (Go auto-takes address of local var), but it's address of copy.
		// This is fine as long as GetExpenses doesn't mutate. It doesn't.
		total = total.Add(p.GetExpenses(""))
	}
	return total
}

// GetExpensesDifference calculates the difference in expenses between two people (p1 - p2).
func (g *Group) GetExpensesDifference(p1, p2 *Person, category Category) decimal.Decimal {
	return p1.GetExpenses(category).Sub(p2.GetExpenses(category))
}

// GetDebt calculates how much p1 owes p2 based on a scale factor (default 0.5).
// Returns positive value if p1 owes p2.
// Math: (total_expenses * scale_factor) - p1_expenses
func (g *Group) GetDebt(p1 *Person, _ *Person, scaleFactor decimal.Decimal) decimal.Decimal {
	// Note: p2 argument is unused in formula but kept for API compatibility/context if needed.
	// Logic: "Share of total" - "Paid by p1"
	// If Share > Paid, p1 owes money (positive).
	// If Paid > Share, p1 is owed money (negative).
	totalExpenses := g.GetExpenses()
	share := totalExpenses.Mul(scaleFactor)
	return share.Sub(p1.GetExpenses(""))
}

// GetEmails returns a list of emails of all members in the group.
func (g *Group) GetEmails() []string {
	var emails []string
	for _, p := range g.Members {
		if p.Email != "" {
			emails = append(emails, p.Email)
		}
	}
	return emails
}

// AddTransactions adds a list of transactions to the group, distributing them to members based on AccountNumber.
func (g *Group) AddTransactions(transactions []Transaction) {
	// Create map of AccountNumber -> *Person for O(1) lookup
	accountMap := make(map[int]*Person)
	for i := range g.Members {
		// We need pointer to member to modify it
		p := &g.Members[i]
		for _, acc := range p.AccountNumbers {
			accountMap[acc] = p
		}
	}

	for _, t := range transactions {
		if p, ok := accountMap[t.AccountNumber]; ok {
			p.AddTransaction(t)
		}
	}
}
