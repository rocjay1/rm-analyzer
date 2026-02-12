package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestHandleUpload_Success(t *testing.T) {
	// Setup
	mockBlob := &MockBlobClient{}
	mockQueue := &MockQueueClient{}
	deps := &Dependencies{
		Blob:  mockBlob,
		Queue: mockQueue,
	}

	body := new(bytes.Buffer)
	writer := multipart.NewWriter(body)
	part, _ := writer.CreateFormFile("file", "test.csv")
	part.Write([]byte("content"))
	writer.Close()

	// Mock Blob Upload
	mockBlob.UploadTextFunc = func(ctx context.Context, containerName, blobName, content string) error {
		assert.Equal(t, "rm-analyzer-data", containerName)
		assert.Contains(t, blobName, "uploads/")
		// The filename is modified with a timestamp, so just check suffix
		assert.True(t, strings.HasSuffix(blobName, "-test.csv"))
		assert.Equal(t, "content", content)
		return nil
	}

	// Mock Queue Enqueue
	mockQueue.EnqueueMessageFunc = func(ctx context.Context, queueName string, message any) error {
		assert.Equal(t, "process-queue", queueName)
		msgMap, ok := message.(map[string]string)
		assert.True(t, ok)
		assert.Equal(t, "test.csv", msgMap["filename"])
		assert.Contains(t, msgMap["blobName"], "uploads/")
		return nil
	}

	req := httptest.NewRequest(http.MethodPost, "/upload", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	// Execute
	deps.HandleUpload(w, req)

	// Assert
	assert.Equal(t, http.StatusOK, w.Code)
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	assert.Equal(t, "success", resp["status"])
	assert.NotEmpty(t, resp["blobName"])
}

func TestHandleUpload_MethodNotAllowed(t *testing.T) {
	deps := &Dependencies{}
	req := httptest.NewRequest(http.MethodGet, "/upload", nil)
	w := httptest.NewRecorder()

	deps.HandleUpload(w, req)

	assert.Equal(t, http.StatusMethodNotAllowed, w.Code)
}

func TestHandleUpload_MissingFile(t *testing.T) {
	deps := &Dependencies{}
	body := new(bytes.Buffer)
	writer := multipart.NewWriter(body)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/upload", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	deps.HandleUpload(w, req)

	// FormFile error or ParseMultipartForm error often leads to 400
	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestHandleUpload_UploadError(t *testing.T) {
	mockBlob := &MockBlobClient{}
	deps := &Dependencies{Blob: mockBlob}

	body := new(bytes.Buffer)
	writer := multipart.NewWriter(body)
	part, _ := writer.CreateFormFile("file", "test.csv")
	part.Write([]byte("content"))
	writer.Close()

	mockBlob.UploadTextFunc = func(ctx context.Context, containerName, blobName, content string) error {
		return errors.New("upload failed")
	}

	req := httptest.NewRequest(http.MethodPost, "/upload", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	deps.HandleUpload(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "Failed to upload blob")
}

func TestHandleUpload_EnqueueError(t *testing.T) {
	mockBlob := &MockBlobClient{}
	mockQueue := &MockQueueClient{}
	deps := &Dependencies{Blob: mockBlob, Queue: mockQueue}

	body := new(bytes.Buffer)
	writer := multipart.NewWriter(body)
	part, _ := writer.CreateFormFile("file", "test.csv")
	part.Write([]byte("content"))
	writer.Close()

	mockBlob.UploadTextFunc = func(ctx context.Context, containerName, blobName, content string) error {
		return nil
	}

	mockQueue.EnqueueMessageFunc = func(ctx context.Context, queueName string, message any) error {
		return errors.New("enqueue failed")
	}

	req := httptest.NewRequest(http.MethodPost, "/upload", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	deps.HandleUpload(w, req)

	assert.Equal(t, http.StatusInternalServerError, w.Code)
	assert.Contains(t, w.Body.String(), "Failed to enqueue message")
}
