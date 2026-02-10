package handlers

import (
	"context"

	"github.com/rocjay1/rm-analyzer/internal/models"
	"github.com/shopspring/decimal"
)

// DatabaseClient defines the interface for database operations used by handlers.
type DatabaseClient interface {
	GetSavings(ctx context.Context, month string) (*models.SavingsData, error)
	SaveSavings(ctx context.Context, month string, data *models.SavingsData) error
	GetCreditCards(ctx context.Context) ([]models.CreditCard, error)
	SaveCreditCard(ctx context.Context, card models.CreditCard) error
	UpdateCardBalance(ctx context.Context, accountNumber int, delta decimal.Decimal) error
	GetAllPeople(ctx context.Context) ([]models.Person, error)
	SaveTransactions(ctx context.Context, transactions []models.Transaction) ([]models.Transaction, error)
}

// BlobClient defines the interface for blob storage operations used by handlers.
type BlobClient interface {
	UploadText(ctx context.Context, containerName, blobName, content string) error
	DownloadText(ctx context.Context, containerName, blobName string) (string, error)
}

// QueueClient defines the interface for queue operations used by handlers.
type QueueClient interface {
	EnqueueMessage(ctx context.Context, queueName string, message interface{}) error
}

// EmailClient defines the interface for email operations used by handlers.
type EmailClient interface {
	SendErrorEmail(ctx context.Context, recipients []string, errors []string) error
	SendSummaryEmail(ctx context.Context, recipients []string, group *models.Group, errors []string) error
}
