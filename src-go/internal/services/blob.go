package services

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/storage/azblob"
)

// BlobService handles interactions with Azure Blob Storage.
type BlobService struct {
	serviceURL string
	client     *azblob.Client
}

// NewBlobService creates a new BlobService instance.
func NewBlobService() (*BlobService, error) {
	serviceURL := os.Getenv("BLOB_SERVICE_URL")
	if serviceURL == "" {
		return nil, fmt.Errorf("BLOB_SERVICE_URL environment variable is required")
	}

	var client *azblob.Client
	var err error

	if strings.HasPrefix(serviceURL, "http") {
		// Dev/Azurite
		var cred *azblob.SharedKeyCredential
		cred, err = azblob.NewSharedKeyCredential("devstoreaccount1", "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==")
		if err != nil {
			return nil, fmt.Errorf("failed to create shared key credential: %w", err)
		}
		// In newer SDKs, shared key is passed to NewClientWithSharedKeyCredential
		client, err = azblob.NewClientWithSharedKeyCredential(serviceURL, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create blob client: %w", err)
		}
	} else {
		// Prod
		cred, err := azidentity.NewDefaultAzureCredential(nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
		client, err = azblob.NewClient(serviceURL, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create blob client: %w", err)
		}
	}

	return &BlobService{
		serviceURL: serviceURL,
		client:     client,
	}, nil
}

// UploadText uploads a string to a blob.
func (s *BlobService) UploadText(ctx context.Context, containerName, blobName, text string) error {
	_, err := s.client.UploadBuffer(ctx, containerName, blobName, []byte(text), nil)
	return err
}

// DownloadText downloads a blob as a string.
func (s *BlobService) DownloadText(ctx context.Context, containerName, blobName string) (string, error) {
	resp, err := s.client.DownloadStream(ctx, containerName, blobName, nil)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	// Read everything
	// In a real optimized app we might stream, but for text config/logs it's fine
	// Max size check recommended in production
	b := make([]byte, 0)
	buf := make([]byte, 1024)
	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			b = append(b, buf[:n]...)
		}
		if err != nil {
			break
		}
	}
	
	return string(b), nil
}
