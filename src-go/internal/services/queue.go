package services

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/storage/azqueue"
)

// QueueService handles interactions with Azure Queue Storage.
type QueueService struct {
	serviceURL string
	client     *azqueue.ServiceClient
}

// NewQueueService creates a new QueueService instance.
func NewQueueService() (*QueueService, error) {
	serviceURL := os.Getenv("QUEUE_SERVICE_URL")
	if serviceURL == "" {
		return nil, fmt.Errorf("QUEUE_SERVICE_URL environment variable is required")
	}

	var client *azqueue.ServiceClient
	var err error

	if strings.HasPrefix(serviceURL, "http") {
		// Dev/Azurite
		var cred *azqueue.SharedKeyCredential
		cred, err = azqueue.NewSharedKeyCredential("devstoreaccount1", "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==")
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		// Using NewServiceClientWithSharedKeyCredential
		client, err = azqueue.NewServiceClientWithSharedKeyCredential(serviceURL, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create queue client: %w", err)
		}
	} else {
		// Prod
		cred, err := azidentity.NewDefaultAzureCredential(nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
		client, err = azqueue.NewServiceClient(serviceURL, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create queue client: %w", err)
		}
	}

	return &QueueService{
		serviceURL: serviceURL,
		client:     client,
	}, nil
}

// EnqueueMessage sends a message to the specified queue.
func (s *QueueService) EnqueueMessage(ctx context.Context, queueName string, message any) error {
	queueClient := s.client.NewQueueClient(queueName)

	// Create queue if not exists (optional, mostly for dev)
	_, err := queueClient.Create(ctx, nil)
	// Ignore if already exists
	if err != nil && !strings.Contains(err.Error(), "QueueAlreadyExists") {
		// Just log or ignore, strictly speaking we should check error code
		// But in prod queue usually exists
	}

	bytes, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	_, err = queueClient.EnqueueMessage(ctx, string(bytes), nil)
	return err
}
