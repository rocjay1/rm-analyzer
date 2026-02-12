package csvparse

import (
	"testing"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
)

func TestParseCSV_Valid(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From
2025-08-17,Test,123,42.5,Dining & Drinks,everything
2025-08-18,Test2,123,10.0,Groceries,`

	transactions, errors := ParseCSV(content)

	if len(errors) != 0 {
		t.Fatalf("Expected no errors, got: %v", errors)
	}

	if len(transactions) != 2 {
		t.Fatalf("Expected 2 transactions, got %d", len(transactions))
	}

	t1 := transactions[0]
	if t1.Name != "Test" {
		t.Errorf("Expected Name 'Test', got '%s'", t1.Name)
	}
	if !t1.Amount.Equal(decimal.NewFromFloat(42.5)) {
		t.Errorf("Expected Amount 42.5, got %s", t1.Amount)
	}
	if t1.Category != models.CategoryDining {
		t.Errorf("Expected Category 'Dining & Drinks', got '%s'", t1.Category)
	}
	if t1.Ignore != models.IgnoredFromEverything {
		t.Errorf("Expected Ignore 'everything', got '%s'", t1.Ignore)
	}

	t2 := transactions[1]
	if t2.Ignore != models.IgnoredFromNothing {
		t.Errorf("Expected Ignore '', got '%s'", t2.Ignore)
	}
}

func TestParseCSV_Whitespace(t *testing.T) {
	content := ` Date , Name , Account Number , Amount , Category , Ignored From
 2025-08-17 , Test , 123 , 42.5 , Dining & Drinks , everything `

	transactions, errors := ParseCSV(content)

	if len(errors) != 0 {
		t.Fatalf("Expected no errors, got: %v", errors)
	}

	if len(transactions) != 1 {
		t.Fatalf("Expected 1 transaction, got %d", len(transactions))
	}

	t1 := transactions[0]
	if t1.Name != "Test" {
		t.Errorf("Expected Name 'Test', got '%s'", t1.Name)
	}
	if !t1.Amount.Equal(decimal.NewFromFloat(42.5)) {
		t.Errorf("Expected Amount 42.5, got %s", t1.Amount)
	}
	if t1.Category != models.CategoryDining {
		t.Errorf("Expected Category 'Dining & Drinks', got '%s'", t1.Category)
	}
}

func TestParseCSV_Errors(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From
2025-08-17,Test,123,42.5,Dining & Drinks,everything
bad-date,Bad,123,10.0,Groceries,`

	transactions, errors := ParseCSV(content)

	if len(transactions) != 1 {
		t.Errorf("Expected 1 valid transaction, got %d", len(transactions))
	}

	if len(errors) != 1 {
		t.Fatalf("Expected 1 error, got %d", len(errors))
	}
}

func TestParseCSV_InvalidAmount(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From
2025-08-17,Test,123,bad,Dining & Drinks,everything`

	_, errors := ParseCSV(content)

	if len(errors) == 0 {
		t.Fatal("Expected error for invalid amount")
	}
}

func TestParseCSV_Empty(t *testing.T) {
	transactions, errors := ParseCSV("")

	if len(transactions) != 0 {
		t.Errorf("Expected 0 transactions, got %d", len(transactions))
	}
	if len(errors) != 0 {
		t.Errorf("Expected 0 errors, got %d", len(errors))
	}
}

func TestParseCSV_InvalidAccountNumber(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From
2025-08-17,Test,abc,42.5,Dining & Drinks,everything`

	_, errors := ParseCSV(content)

	if len(errors) == 0 {
		t.Fatal("Expected error for invalid account number")
	}
}

func TestParseCSV_HeaderOnly(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From`

	transactions, errors := ParseCSV(content)

	if len(transactions) != 0 {
		t.Errorf("Expected 0 transactions, got %d", len(transactions))
	}
	if len(errors) != 0 {
		t.Errorf("Expected 0 errors, got %d", len(errors))
	}
}
