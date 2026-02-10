package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"

	"github.com/stretchr/testify/assert"
)

func TestHandleCreditCards_Success(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.GetCreditCardsFunc = func(ctx context.Context) ([]models.CreditCard, error) {
		return []models.CreditCard{
			{Name: "Card 1", AccountNumber: 1234, CurrentBalance: decimal.NewFromFloat(500.00)},
		}, nil
	}

	req := httptest.NewRequest(http.MethodGet, "/cards", nil)
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	var resp []models.CreditCard
	json.Unmarshal(w.Body.Bytes(), &resp)
	assert.Len(t, resp, 1)
	assert.Equal(t, "Card 1", resp[0].Name)
}

func TestHandleCreditCards_MethodNotAllowed(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodPost, "/cards", nil)
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
}

func TestHandleCreditCards_DatabaseError(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.GetCreditCardsFunc = func(ctx context.Context) ([]models.CreditCard, error) {
		return nil, errors.New("db error")
	}

	req := httptest.NewRequest(http.MethodGet, "/cards", nil)
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}
