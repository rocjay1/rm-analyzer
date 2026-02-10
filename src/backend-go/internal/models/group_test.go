package models

import (
	"testing"

	"github.com/shopspring/decimal"
)

func TestPerson_GetExpenses(t *testing.T) {
	p := Person{
		Name: "Alice",
		Transactions: []Transaction{
			{Amount: decimal.NewFromFloat(10.0), Category: CategoryGroceries},
			{Amount: decimal.NewFromFloat(20.0), Category: CategoryDining},
			{Amount: decimal.NewFromFloat(5.0), Category: CategoryGroceries},
		},
	}

	// Test total expenses (empty category)
	total := p.GetExpenses("")
	expectedTotal := decimal.NewFromFloat(35.0)
	if !total.Equal(expectedTotal) {
		t.Errorf("Expected total 35.0, got %s", total)
	}

	// Test filtered expenses
	groceries := p.GetExpenses(CategoryGroceries)
	expectedGroceries := decimal.NewFromFloat(15.0)
	if !groceries.Equal(expectedGroceries) {
		t.Errorf("Expected groceries 15.0, got %s", groceries)
	}

	dining := p.GetExpenses(CategoryDining)
	expectedDining := decimal.NewFromFloat(20.0)
	if !dining.Equal(expectedDining) {
		t.Errorf("Expected dining 20.0, got %s", dining)
	}
}

func TestGroup_GetExpenses(t *testing.T) {
	alice := Person{
		Name: "Alice",
		Transactions: []Transaction{
			{Amount: decimal.NewFromFloat(100.0)},
		},
	}
	bob := Person{
		Name: "Bob",
		Transactions: []Transaction{
			{Amount: decimal.NewFromFloat(50.0)},
			{Amount: decimal.NewFromFloat(25.0)},
		},
	}

	g := Group{Members: []Person{alice, bob}}

	total := g.GetExpenses()
	expected := decimal.NewFromFloat(175.0) // 100 + 50 + 25
	if !total.Equal(expected) {
		t.Errorf("Expected total 175.0, got %s", total)
	}
}

func TestGroup_GetExpensesDifference(t *testing.T) {
	alice := Person{Name: "Alice", Transactions: []Transaction{{Amount: decimal.NewFromFloat(100.0)}}}
	bob := Person{Name: "Bob", Transactions: []Transaction{{Amount: decimal.NewFromFloat(60.0)}}}

	g := Group{Members: []Person{alice, bob}}

	// Alice - Bob = 100 - 60 = 40
	diff := g.GetExpensesDifference(&alice, &bob, "")
	if !diff.Equal(decimal.NewFromFloat(40.0)) {
		t.Errorf("Expected diff 40.0, got %s", diff)
	}

	// Bob - Alice = 60 - 100 = -40
	diff = g.GetExpensesDifference(&bob, &alice, "")
	if !diff.Equal(decimal.NewFromFloat(-40.0)) {
		t.Errorf("Expected diff -40.0, got %s", diff)
	}
}

func TestGroup_GetDebt(t *testing.T) {
	// Scenario: Total expenses 200. Split 50/50 means each should pay 100.
	// Alice paid 150. Bob paid 50.
	alice := Person{Name: "Alice", Transactions: []Transaction{{Amount: decimal.NewFromFloat(150.0)}}}
	bob := Person{Name: "Bob", Transactions: []Transaction{{Amount: decimal.NewFromFloat(50.0)}}}

	g := Group{Members: []Person{alice, bob}}
	
	// Total = 200.
	// Alice target share = 100.
	// Alice debt = Target - Paid = 100 - 150 = -50. (She is OWED 50)
	debtAlice := g.GetDebt(&alice, &bob, decimal.NewFromFloat(0.5))
	if !debtAlice.Equal(decimal.NewFromFloat(-50.0)) {
		t.Errorf("Expected Alice debt -50.0, got %s", debtAlice)
	}

	// Bob target share = 100.
	// Bob debt = Target - Paid = 100 - 50 = 50. (He OWES 50)
	debtBob := g.GetDebt(&bob, &alice, decimal.NewFromFloat(0.5))
	if !debtBob.Equal(decimal.NewFromFloat(50.0)) {
		t.Errorf("Expected Bob debt 50.0, got %s", debtBob)
	}
}
