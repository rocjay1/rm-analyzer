package services

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/storage/azblob"
)

// BlobService handles interactions with Azure Blob Storage.
type BlobService struct {
	serviceURL string
	client     *azblob.Client
}

// NewBlobService creates a new BlobService instance.
func NewBlobService() (*BlobService, error) {
	blobURL := os.Getenv("BLOB_SERVICE_URL")
	if blobURL == "" {
		return nil, fmt.Errorf("BLOB_SERVICE_URL environment variable is required")
	}

	slog.Info("initializing blob service", "blob_url", blobURL)
	var client *azblob.Client

	// Check if running locally with Azurite (http endpoint)
	if isLocal(blobURL) {
		slog.Info("using Azurite shared key credentials for blob service")
		name, key := getAzuriteCredentials()
		cred, err := azblob.NewSharedKeyCredential(name, key)
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		var err2 error
		client, err2 = azblob.NewClientWithSharedKeyCredential(blobURL, cred, nil)
		if err2 != nil {
			return nil, fmt.Errorf("failed to create blob client with shared key: %w", err2)
		}
	} else {
		// Production: Managed Identity
		cred, err := newDefaultAzureCredential()
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
		client, err = azblob.NewClient(blobURL, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create blob client: %w", err)
		}
	}

	slog.Info("blob service initialized successfully")
	return &BlobService{client: client}, nil
}

// UploadText uploads a string to a blob.
func (s *BlobService) UploadText(ctx context.Context, containerName, blobName, text string) error {
	slog.Info("uploading blob", "container", containerName, "blob_name", blobName, "size_bytes", len(text))
	// Create container if not exists (mostly for dev)
	_, err := s.client.CreateContainer(ctx, containerName, nil)
	if err != nil && !strings.Contains(err.Error(), "ContainerAlreadyExists") {
		slog.Warn("failed to create container (may already exist)", "container", containerName, "error", err)
	}

	_, err = s.client.UploadBuffer(ctx, containerName, blobName, []byte(text), nil)
	if err != nil {
		slog.Error("failed to upload blob", "container", containerName, "blob_name", blobName, "error", err)
		return fmt.Errorf("failed to upload blob %s/%s: %w", containerName, blobName, err)
	}
	slog.Info("successfully uploaded blob", "container", containerName, "blob_name", blobName)
	return nil
}

// DownloadText downloads a blob and returns its content as a string.
func (s *BlobService) DownloadText(ctx context.Context, containerName, blobName string) (string, error) {
	slog.Info("downloading blob", "container", containerName, "blob_name", blobName)
	resp, err := s.client.DownloadStream(ctx, containerName, blobName, nil)
	if err != nil {
		slog.Error("failed to download blob", "container", containerName, "blob_name", blobName, "error", err)
		return "", fmt.Errorf("failed to download blob %s/%s: %w", containerName, blobName, err)
	}
	defer resp.Body.Close()

	// Read the entire stream using io.ReadAll
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("failed to read blob content", "container", containerName, "blob_name", blobName, "error", err)
		return "", fmt.Errorf("failed to read blob content: %w", err)
	}

	slog.Info("successfully downloaded blob", "container", containerName, "blob_name", blobName, "size_bytes", len(data))
	return string(data), nil
}
