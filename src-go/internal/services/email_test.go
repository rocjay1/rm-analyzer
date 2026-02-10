package services

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azcore/policy"
)

// MockCredential implements azcore.TokenCredential for testing.
type MockCredential struct{}

func (m *MockCredential) GetToken(ctx context.Context, options policy.TokenRequestOptions) (azcore.AccessToken, error) {
	return azcore.AccessToken{
		Token:     "mock-token",
		ExpiresOn: time.Now().Add(1 * time.Hour),
	}, nil
}

func TestEmailService_SendEmail(t *testing.T) {
	// Setup Mock Server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify URL
		if r.URL.Path != "/emails:send" {
			t.Errorf("Expected path /emails:send, got %s", r.URL.Path)
		}

		// Verify Headers
		if r.Header.Get("Authorization") != "Bearer mock-token" {
			t.Errorf("Expected Authorization header 'Bearer mock-token', got %s", r.Header.Get("Authorization"))
		}

		// Verify Body
		body, _ := io.ReadAll(r.Body)
		var req emailRequest
		if err := json.Unmarshal(body, &req); err != nil {
			t.Errorf("Failed to unmarshal request body: %v", err)
		}

		if req.SenderAddress != "sender@test.com" {
			t.Errorf("Expected sender 'sender@test.com', got %s", req.SenderAddress)
		}
		if len(req.Recipients.To) != 1 || req.Recipients.To[0].Address != "recipient@test.com" {
			t.Errorf("Expected recipient 'recipient@test.com', got %v", req.Recipients.To)
		}
		if req.Content.Subject != "Test Subject" {
			t.Errorf("Expected subject 'Test Subject', got %s", req.Content.Subject)
		}

		// Respond success
		w.WriteHeader(http.StatusAccepted)
	}))
	defer server.Close()

	// Setup Env
	os.Setenv("COMMUNICATION_SERVICES_ENDPOINT", server.URL)
	os.Setenv("SENDER_EMAIL", "sender@test.com")
	defer os.Unsetenv("COMMUNICATION_SERVICES_ENDPOINT")
	defer os.Unsetenv("SENDER_EMAIL")

	// Init Service with Mock Cred
	service, err := NewEmailService(&MockCredential{})
	if err != nil {
		t.Fatalf("Failed to create service: %v", err)
	}

	// Test SendEmail
	err = service.SendEmail(context.Background(), []string{"recipient@test.com"}, "Test Subject", "Test Body")
	if err != nil {
		t.Errorf("SendEmail failed: %v", err)
	}
}

func TestEmailService_SendEmail_Error(t *testing.T) {
	// Setup Mock Server returning error
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Error"))
	}))
	defer server.Close()

	os.Setenv("COMMUNICATION_SERVICES_ENDPOINT", server.URL)
	os.Setenv("SENDER_EMAIL", "sender@test.com")
	defer os.Unsetenv("COMMUNICATION_SERVICES_ENDPOINT")
	defer os.Unsetenv("SENDER_EMAIL")

	service, _ := NewEmailService(&MockCredential{})

	err := service.SendEmail(context.Background(), []string{"recipient@test.com"}, "Sub", "Body")
	if err == nil {
		t.Error("Expected error, got nil")
	}
}
