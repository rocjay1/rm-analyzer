package services

import (
	"log/slog"
	"strings"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
)

const (
	// Standard Azurite account name and key
	azuriteAccountName = "devstoreaccount1"
	azuriteAccountKey  = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)

// isLocal checks if the service URL indicates a local environment (starts with http).
func isLocal(serviceURL string) bool {
	return strings.HasPrefix(serviceURL, "http")
}

// getAzuriteCredentials returns the hardcoded Azurite account name and key.
func getAzuriteCredentials() (string, string) {
	return azuriteAccountName, azuriteAccountKey
}

// newDefaultAzureCredential creates a new DefaultAzureCredential.
func newDefaultAzureCredential() (azcore.TokenCredential, error) {
	slog.Info("using default Azure credentials")
	return azidentity.NewDefaultAzureCredential(nil)
}
