package handlers

import (
	"bytes"
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
	req := httptest.NewRequest(http.MethodDelete, "/cards", nil)
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

func TestHandleCreditCards_PostSuccess(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	var savedCard models.CreditCard
	mockDb.SaveCreditCardFunc = func(ctx context.Context, card models.CreditCard) error {
		savedCard = card
		return nil
	}

	card := models.CreditCard{
		Name:           "Test Card",
		AccountNumber:  5678,
		CurrentBalance: decimal.NewFromFloat(250.00),
	}
	body, _ := json.Marshal(card)
	req := httptest.NewRequest(http.MethodPost, "/cards", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "Test Card", savedCard.Name)
	assert.Equal(t, 5678, savedCard.AccountNumber)
}

func TestHandleCreditCards_PostInvalidBody(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodPost, "/cards", bytes.NewBufferString("invalid json"))
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleCreditCards_PostDatabaseError(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.SaveCreditCardFunc = func(ctx context.Context, card models.CreditCard) error {
		return errors.New("save failed")
	}

	card := models.CreditCard{Name: "Test Card", AccountNumber: 1234}
	body, _ := json.Marshal(card)
	req := httptest.NewRequest(http.MethodPost, "/cards", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.HandleCreditCards(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "Failed to save credit card")
}
