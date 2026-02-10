package services

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/storage/azqueue"
)

// QueueService handles interactions with Azure Queue Storage.
type QueueService struct {
	serviceClient *azqueue.ServiceClient
}

// NewQueueService creates a new QueueService instance.
func NewQueueService() (*QueueService, error) {
	queueURL := os.Getenv("QUEUE_SERVICE_URL")
	if queueURL == "" {
		return nil, fmt.Errorf("QUEUE_SERVICE_URL environment variable is required")
	}

	slog.Info("initializing queue service", "queue_url", queueURL)
	var client *azqueue.ServiceClient

	if strings.HasPrefix(queueURL, "http") {
		// Check if running locally with Azurite (http endpoint)
		slog.Info("using Azurite shared key credentials for queue service")
		cred, err := azqueue.NewSharedKeyCredential(
			"devstoreaccount1",
			"Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
		)
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		var err2 error
		client, err2 = azqueue.NewServiceClientWithSharedKeyCredential(queueURL, cred, nil)
		if err2 != nil {
			return nil, fmt.Errorf("failed to create queue service client with shared key: %w", err2)
		}
	} else {
		// Production: Managed Identity
		slog.Info("using default Azure credentials for queue service")
		cred, err := azidentity.NewDefaultAzureCredential(nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
		var err2 error
		client, err2 = azqueue.NewServiceClient(queueURL, cred, nil)
		if err2 != nil {
			return nil, fmt.Errorf("failed to create queue service client: %w", err2)
		}
	}

	slog.Info("queue service initialized successfully")
	return &QueueService{serviceClient: client}, nil
}

// EnqueueMessage adds a message to a queue.
func (s *QueueService) EnqueueMessage(ctx context.Context, queueName string, message any) error {
	slog.Info("enqueuing message", "queue", queueName)
	queueClient := s.serviceClient.NewQueueClient(queueName)

	// Create queue if not exists (mostly for dev)
	_, err := queueClient.Create(ctx, nil)
	if err != nil && !strings.Contains(err.Error(), "QueueAlreadyExists") {
		slog.Warn("failed to create queue (may already exist)", "queue", queueName, "error", err)
	}

	// Serialize message
	msgBytes, err := json.Marshal(message)
	if err != nil {
		slog.Error("failed to marshal queue message", "queue", queueName, "error", err)
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	_, err = queueClient.EnqueueMessage(ctx, string(msgBytes), nil)
	if err != nil {
		slog.Error("failed to enqueue message", "queue", queueName, "error", err)
		return fmt.Errorf("failed to enqueue message to %s: %w", queueName, err)
	}

	slog.Info("successfully enqueued message", "queue", queueName)
	return nil
}
