package handlers

import (
	"context"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
)

// MockDatabaseClient is a mock implementation of DatabaseClient
type MockDatabaseClient struct {
	GetSavingsFunc        func(ctx context.Context, month string) (*models.SavingsData, error)
	SaveSavingsFunc       func(ctx context.Context, month string, data *models.SavingsData) error
	GetCreditCardsFunc    func(ctx context.Context) ([]models.CreditCard, error)
	SaveCreditCardFunc    func(ctx context.Context, card models.CreditCard) error
	UpdateCardBalanceFunc func(ctx context.Context, accountNumber int, delta decimal.Decimal) error
	GetAllPeopleFunc      func(ctx context.Context) ([]models.Person, error)
	SaveTransactionsFunc  func(ctx context.Context, transactions []models.Transaction) ([]models.Transaction, error)
}

func (m *MockDatabaseClient) GetSavings(ctx context.Context, month string) (*models.SavingsData, error) {
	if m.GetSavingsFunc != nil {
		return m.GetSavingsFunc(ctx, month)
	}
	return nil, nil
}

func (m *MockDatabaseClient) SaveSavings(ctx context.Context, month string, data *models.SavingsData) error {
	if m.SaveSavingsFunc != nil {
		return m.SaveSavingsFunc(ctx, month, data)
	}
	return nil
}

func (m *MockDatabaseClient) GetCreditCards(ctx context.Context) ([]models.CreditCard, error) {
	if m.GetCreditCardsFunc != nil {
		return m.GetCreditCardsFunc(ctx)
	}
	return nil, nil
}

func (m *MockDatabaseClient) SaveCreditCard(ctx context.Context, card models.CreditCard) error {
	if m.SaveCreditCardFunc != nil {
		return m.SaveCreditCardFunc(ctx, card)
	}
	return nil
}

func (m *MockDatabaseClient) UpdateCardBalance(ctx context.Context, accountNumber int, delta decimal.Decimal) error {
	if m.UpdateCardBalanceFunc != nil {
		return m.UpdateCardBalanceFunc(ctx, accountNumber, delta)
	}
	return nil
}

func (m *MockDatabaseClient) GetAllPeople(ctx context.Context) ([]models.Person, error) {
	if m.GetAllPeopleFunc != nil {
		return m.GetAllPeopleFunc(ctx)
	}
	return nil, nil
}

func (m *MockDatabaseClient) SaveTransactions(ctx context.Context, transactions []models.Transaction) ([]models.Transaction, error) {
	if m.SaveTransactionsFunc != nil {
		return m.SaveTransactionsFunc(ctx, transactions)
	}
	return nil, nil
}

// MockBlobClient is a mock implementation of BlobClient
type MockBlobClient struct {
	UploadTextFunc   func(ctx context.Context, containerName, blobName, content string) error
	DownloadTextFunc func(ctx context.Context, containerName, blobName string) (string, error)
}

func (m *MockBlobClient) UploadText(ctx context.Context, containerName, blobName, content string) error {
	if m.UploadTextFunc != nil {
		return m.UploadTextFunc(ctx, containerName, blobName, content)
	}
	return nil
}

func (m *MockBlobClient) DownloadText(ctx context.Context, containerName, blobName string) (string, error) {
	if m.DownloadTextFunc != nil {
		return m.DownloadTextFunc(ctx, containerName, blobName)
	}
	return "", nil
}

// MockQueueClient is a mock implementation of QueueClient
type MockQueueClient struct {
	EnqueueMessageFunc func(ctx context.Context, queueName string, message interface{}) error
}

func (m *MockQueueClient) EnqueueMessage(ctx context.Context, queueName string, message interface{}) error {
	if m.EnqueueMessageFunc != nil {
		return m.EnqueueMessageFunc(ctx, queueName, message)
	}
	return nil
}

// MockEmailClient is a mock implementation of EmailClient
type MockEmailClient struct {
	SendErrorEmailFunc   func(ctx context.Context, recipients []string, errors []string) error
	SendSummaryEmailFunc func(ctx context.Context, recipients []string, group *models.Group, errors []string) error
}

func (m *MockEmailClient) SendErrorEmail(ctx context.Context, recipients []string, errors []string) error {
	if m.SendErrorEmailFunc != nil {
		return m.SendErrorEmailFunc(ctx, recipients, errors)
	}
	return nil
}

func (m *MockEmailClient) SendSummaryEmail(ctx context.Context, recipients []string, group *models.Group, errors []string) error {
	if m.SendSummaryEmailFunc != nil {
		return m.SendSummaryEmailFunc(ctx, recipients, group, errors)
	}
	return nil
}
