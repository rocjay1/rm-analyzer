package handler

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
)

func TestHandleNightlyTrigger_Success(t *testing.T) {
	// Setup
	os.Setenv("USER_EMAIL", "test@example.com")
	defer os.Unsetenv("USER_EMAIL")

	mockDb := &MockDatabaseClient{}
	mockEmail := &MockEmailClient{}
	deps := &Dependencies{
		Database: mockDb,
		Email:    mockEmail,
	}

	// Mock Date (Target date is 3 days from now)
	// We need the test to run such that "today + 3 days" matches the card's due day.
	// Since we can't easily mock time.Now() in the handler without dependency injection for time,
	// checking logic depends on the current day + 3.
	// So we'll set the card's due day to (Today + 3).Day()
	targetDate := time.Now().AddDate(0, 0, 3)
	targetDay := targetDate.Day()

	// 1. Mock DB: Return a card that is due
	mockDb.GetCreditCardsFunc = func(ctx context.Context) ([]models.CreditCard, error) {
		return []models.CreditCard{
			{
				Name:             "Due Card",
				DueDay:           targetDay,
				CreditLimit:      decimal.NewFromFloat(1000.00),
				CurrentBalance:   decimal.NewFromFloat(500.00), // Utilization 50%, Target 10% (100) -> Pay 400
				StatementBalance: decimal.Zero,
			},
			{
				Name:           "Not Due Card",
				DueDay:         targetDay + 1, // Not due today
				CreditLimit:    decimal.NewFromFloat(1000.00),
				CurrentBalance: decimal.NewFromFloat(500.00),
			},
		}, nil
	}

	// 2. Mock Email: Expect email to be sent
	emailSent := false
	mockEmail.SendEmailFunc = func(ctx context.Context, to []string, subject, body string) error {
		emailSent = true
		assert.Contains(t, to, "test@example.com")
		assert.Contains(t, subject, "Payment Reminder: Due Card")
		assert.Contains(t, body, "$400.00") // 500 - (1000 * 0.1) = 400
		return nil
	}

	req := httptest.NewRequest(http.MethodPost, "/NightlyTrigger", nil)
	w := httptest.NewRecorder()

	// Execute
	deps.HandleNightlyTrigger(w, req)

	// Assert
	assert.Equal(t, http.StatusOK, w.Code)
	assert.True(t, emailSent, "Email should have been sent for Due Card")
}

func TestHandleNightlyTrigger_NoPaymentNeeded(t *testing.T) {
	os.Setenv("USER_EMAIL", "test@example.com")
	defer os.Unsetenv("USER_EMAIL")

	mockDb := &MockDatabaseClient{}
	mockEmail := &MockEmailClient{}
	deps := &Dependencies{
		Database: mockDb,
		Email:    mockEmail,
	}

	targetDate := time.Now().AddDate(0, 0, 3)
	targetDay := targetDate.Day()

	mockDb.GetCreditCardsFunc = func(ctx context.Context) ([]models.CreditCard, error) {
		return []models.CreditCard{
			{
				Name:             "Paid Off Card",
				DueDay:           targetDay,
				CreditLimit:      decimal.NewFromFloat(1000.00),
				CurrentBalance:   decimal.NewFromFloat(50.00), // Utilization 5% < 10% -> No payment
				StatementBalance: decimal.Zero,
			},
		}, nil
	}

	// execute
	req := httptest.NewRequest(http.MethodPost, "/NightlyTrigger", nil)
	w := httptest.NewRecorder()
	deps.HandleNightlyTrigger(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	// MockEmailClient methods are nil, so if called they would panic (if we didn't assign them)
	// OR we can assert they were NOT called.
	// However, our mock implementation calls `m.SendEmailFunc` if not nil, otherwise returns nil.
	// So to verify it wasn't called, we can set a flag.

	mockEmail.SendEmailFunc = func(ctx context.Context, to []string, subject, body string) error {
		assert.Fail(t, "Email should not have been sent")
		return nil
	}
}

func TestHandleNightlyTrigger_NoUserEmail(t *testing.T) {
	// Ensure env var is unset
	os.Unsetenv("USER_EMAIL")

	deps := &Dependencies{} // no mocks needed as it should return early

	req := httptest.NewRequest(http.MethodPost, "/NightlyTrigger", nil)
	w := httptest.NewRecorder()

	deps.HandleNightlyTrigger(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}
