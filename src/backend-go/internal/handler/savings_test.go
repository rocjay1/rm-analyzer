package handler

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

func TestHandleSavings_Get_Success(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.GetSavingsFunc = func(ctx context.Context, month string) (*models.SavingsData, error) {
		assert.Equal(t, "2023-01", month)
		return &models.SavingsData{
			StartingBalance: decimal.NewFromFloat(1000.00),
			Items:           []models.SavingsItem{{Name: "Item 1", Cost: decimal.NewFromFloat(100.00)}},
		}, nil
	}

	req := httptest.NewRequest(http.MethodGet, "/savings?month=2023-01", nil)
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
	var resp models.SavingsData
	json.Unmarshal(w.Body.Bytes(), &resp)
	assert.True(t, resp.StartingBalance.Equal(decimal.NewFromFloat(1000.00)))
	assert.Len(t, resp.Items, 1)
}

func TestHandleSavings_Get_MissingMonth(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodGet, "/savings", nil)
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleSavings_Get_DatabaseError(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.GetSavingsFunc = func(ctx context.Context, month string) (*models.SavingsData, error) {
		return nil, errors.New("db error")
	}

	req := httptest.NewRequest(http.MethodGet, "/savings?month=2023-01", nil)
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}

func TestHandleSavings_Post_Success(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.SaveSavingsFunc = func(ctx context.Context, month string, data *models.SavingsData) error {
		assert.Equal(t, "2023-01", month)
		assert.True(t, data.StartingBalance.Equal(decimal.NewFromFloat(1000.00)))
		return nil
	}

	payload := models.SavingsData{
		StartingBalance: decimal.NewFromFloat(1000.00),
		Items:           []models.SavingsItem{{Name: "Item 1", Cost: decimal.NewFromFloat(100.00)}},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/savings?month=2023-01", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusOK, w.Code)
}

func TestHandleSavings_Post_MissingMonth(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodPost, "/savings", nil)
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleSavings_Post_InvalidBody(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodPost, "/savings?month=2023-01", bytes.NewBufferString("invalid json"))
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleSavings_Post_DatabaseError(t *testing.T) {
	mockDb := &MockDatabaseClient{}
	deps := &Dependencies{Database: mockDb}

	mockDb.SaveSavingsFunc = func(ctx context.Context, month string, data *models.SavingsData) error {
		return errors.New("db error")
	}

	payload := models.SavingsData{StartingBalance: decimal.NewFromFloat(1000.00)}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/savings?month=2023-01", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.HandleSavings(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
}
