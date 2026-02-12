package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azcore/policy"
)

// EmailService handles sending emails via Azure Communication Services REST API.
type EmailService struct {
	endpoint   string
	sender     string
	cred       azcore.TokenCredential
	httpClient *http.Client
}

// NewEmailService creates a new EmailService instance.
// If cred is nil, it defaults to using DefaultAzureCredential.
func NewEmailService(cred azcore.TokenCredential) (*EmailService, error) {
	endpoint := os.Getenv("COMMUNICATION_SERVICES_ENDPOINT")
	if endpoint == "" {
		return nil, fmt.Errorf("COMMUNICATION_SERVICES_ENDPOINT environment variable is required")
	}

	sender := os.Getenv("SENDER_EMAIL")
	if sender == "" {
		return nil, fmt.Errorf("SENDER_EMAIL environment variable is required")
	}

	if cred == nil {
		var err error
		cred, err = newDefaultAzureCredential()
		if err != nil {
			return nil, fmt.Errorf("failed to create default azure credential: %w", err)
		}
	}

	return &EmailService{
		endpoint:   endpoint,
		sender:     sender,
		cred:       cred,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}, nil
}

type emailAddress struct {
	Address string `json:"address"`
}

type emailRecipients struct {
	To []emailAddress `json:"to"`
}

type emailContent struct {
	Subject string `json:"subject"`
	HTML    string `json:"html"`
}

type emailRequest struct {
	SenderAddress string          `json:"senderAddress"`
	Content       emailContent    `json:"content"`
	Recipients    emailRecipients `json:"recipients"`
}

// SendEmail sends an email to the specified recipients using the REST API.
func (s *EmailService) SendEmail(ctx context.Context, to []string, subject, body string) error {
	// Get access token
	token, err := s.cred.GetToken(ctx, policy.TokenRequestOptions{
		Scopes: []string{"https://communication.azure.com//.default"},
	})
	if err != nil {
		return fmt.Errorf("failed to get access token: %w", err)
	}

	// Construct request body
	recipients := make([]emailAddress, len(to))
	for i, email := range to {
		recipients[i] = emailAddress{Address: email}
	}

	reqBody := emailRequest{
		SenderAddress: s.sender,
		Content: emailContent{
			Subject: subject,
			HTML:    body,
		},
		Recipients: emailRecipients{
			To: recipients,
		},
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal email request: %w", err)
	}

	// Construct HTTP request
	url := fmt.Sprintf("%s/emails:send?api-version=2023-03-31", s.endpoint)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonBody))
	if err != nil {
		return fmt.Errorf("failed to create http request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token.Token)

	// Send request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send email request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusAccepted {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("email request failed with status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	slog.Info("email sent successfully", "recipients", to)
	return nil
}

// SendErrorEmail sends an email with validation errors.
func (s *EmailService) SendErrorEmail(ctx context.Context, recipients []string, errors []string) error {
	subject := "RMAnalyzer - Upload Failed"
	body := RenderErrorBody(errors)
	return s.SendEmail(ctx, recipients, subject, body)
}
