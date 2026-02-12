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

func TestProcessQueue_Success(t *testing.T) {
	// Setup
	mockDb := &MockDatabaseClient{}
	mockBlob := &MockBlobClient{}
	mockEmail := &MockEmailClient{}
	deps := &Dependencies{
		Database: mockDb,
		Blob:     mockBlob,
		Email:    mockEmail,
	}

	// Mock Blob Download
	blobContent := "Date,Description,Amount,AccountNumber\n2023-01-01,Test Transaction,100.50,12345"
	mockBlob.DownloadTextFunc = func(ctx context.Context, containerName, blobName string) (string, error) {
		assert.Equal(t, "uploads", containerName)
		assert.Equal(t, "test-blob.csv", blobName)
		return blobContent, nil
	}

	// Mock Database SaveTransactions
	mockDb.SaveTransactionsFunc = func(ctx context.Context, transactions []models.Transaction) ([]models.Transaction, error) {
		assert.Len(t, transactions, 1)
		return transactions, nil
	}

	// Mock Database GetCreditCards
	mockDb.GetCreditCardsFunc = func(ctx context.Context) ([]models.CreditCard, error) {
		return []models.CreditCard{
			{Name: "Test Card", AccountNumber: 12345, CurrentBalance: decimal.NewFromFloat(500.00)},
		}, nil
	}

	// Mock Database UpdateCardBalance
	mockDb.UpdateCardBalanceFunc = func(ctx context.Context, accountNumber int, delta decimal.Decimal) error {
		assert.Equal(t, 12345, accountNumber)
		assert.True(t, delta.Equal(decimal.NewFromFloat(100.50)))
		return nil
	}

	// Request Payload
	reqPayload := map[string]any{
		"Data": map[string]any{
			"queueItem": `{"blob_name": "test-blob.csv"}`,
		},
	}
	body, _ := json.Marshal(reqPayload)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	// Execute
	deps.ProcessQueue(w, req)

	// Assert
	assert.Equal(t, http.StatusOK, w.Code)
}

func TestProcessQueue_DownloadError(t *testing.T) {
	// Setup
	mockBlob := &MockBlobClient{}
	deps := &Dependencies{
		Blob: mockBlob,
	}

	mockBlob.DownloadTextFunc = func(ctx context.Context, containerName, blobName string) (string, error) {
		return "", errors.New("download failed")
	}

	reqPayload := map[string]any{
		"Data": map[string]any{
			"queueItem": `{"blob_name": "test-blob.csv"}`,
		},
	}
	body, _ := json.Marshal(reqPayload)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.ProcessQueue(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "Failed to download CSV")
}

func TestProcessQueue_ValidationError(t *testing.T) {
	// Setup
	mockDb := &MockDatabaseClient{}
	mockBlob := &MockBlobClient{}
	mockEmail := &MockEmailClient{}
	deps := &Dependencies{
		Database: mockDb,
		Blob:     mockBlob,
		Email:    mockEmail,
	}

	// Invalid CSV
	mockBlob.DownloadTextFunc = func(ctx context.Context, containerName, blobName string) (string, error) {
		return "Invalid CSV Content", nil
	}

	reqPayload := map[string]any{
		"Data": map[string]any{
			"queueItem": `{"blob_name": "test-blob.csv"}`,
		},
	}
	body, _ := json.Marshal(reqPayload)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.ProcessQueue(w, req)

	// Should return OK because we consumed the message and sent error email
	assert.Equal(t, http.StatusOK, w.Code)
}

func TestProcessQueue_InvalidBody(t *testing.T) {
	deps := &Dependencies{}

	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBufferString("not json"))
	w := httptest.NewRecorder()

	deps.ProcessQueue(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestProcessQueue_MissingBlobName(t *testing.T) {
	deps := &Dependencies{}

	reqPayload := map[string]any{
		"Data": map[string]any{
			"queueItem": `{}`,
		},
	}
	body, _ := json.Marshal(reqPayload)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewBuffer(body))
	w := httptest.NewRecorder()

	deps.ProcessQueue(w, req)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}
