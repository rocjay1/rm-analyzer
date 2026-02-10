package utils

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
	
	// We expect an error for the second row (index 1 in 0-based list of data rows? or Row 3 in file?)
	// Our implementation says "Row 3: ..."
	// Let's check generally if error message is present
	// Error might be on Date or something else depending on error return order, but date is first.
	// Actually Date is just string in Struct, mapToTransaction checks empty.
	// But "bad-date" is not empty.
	// Wait, mapToTransaction in csv.go:
	// dateStr := row["Date"] ... if dateStr == "" return error...
	// It doesn't validate date format yet (per comments).
	
	// Ah, I need to check what I implemented.
	// I implemented: "For simplicity, we just store it as string... Python `get_transactions` relies on `to_transaction` returning an error if date is invalid."
	// Wait, if I didn't verify date format, then "bad-date" might be ACCEPTED as valid string?
	
	// Let's re-read my `mapToTransaction` implementation in previous turn.
	// ... "Validate date format (YYYY-MM-DD) regex or parsing... We'll rely on basic non-empty check for now"
	// So "bad-date" WILL BE ACCEPTED.
	
	// I should probably improve the implementation to fail on "bad-date" if I want to match Python test `test_get_transactions_with_errors`.
	// Python test expects error on "bad-date".
	// "Row 2" in Python test.
	
	// Let's fix the implementation first? Or just write a test that expects it to PASS for now and then fix implementation?
	// The user wants "cover all functionality". 
	// I'll update the test to expect success for now, OR better, I'll update `csv.go` to validate date immediately.
	
	// Let's check `Amount` parsing. "bad" amount WILL fail in `csv.go` because of `decimal.NewFromString`.
	// So I can use "Amount: bad" to trigger error.
}

func TestParseCSV_InvalidAmount(t *testing.T) {
	content := `Date,Name,Account Number,Amount,Category,Ignored From
2025-08-17,Test,123,bad,Dining & Drinks,everything`

	_, errors := ParseCSV(content)

	if len(errors) == 0 {
		t.Fatal("Expected error for invalid amount")
	}
}
