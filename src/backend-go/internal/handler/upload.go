package handler

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"path/filepath"
	"time"
)

// HandleUpload handles CSV file uploads.
func (d *Dependencies) HandleUpload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		slog.Warn("upload attempt with invalid method", "method", r.Method, "path", r.URL.Path)
		WriteError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// 10MB limit
	if err := r.ParseMultipartForm(10 << 20); err != nil {
		slog.Warn("failed to parse multipart form", "error", err, "max_size_mb", 10)
		WriteError(w, http.StatusBadRequest, "File too large or invalid form")
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		slog.Warn("failed to get file from form", "error", err)
		WriteError(w, http.StatusBadRequest, "Failed to get file")
		return
	}
	defer file.Close()

	// Read file content
	bytes, err := io.ReadAll(file)
	if err != nil {
		slog.Error("failed to read uploaded file", "filename", header.Filename, "error", err)
		WriteError(w, http.StatusInternalServerError, "Failed to read file")
		return
	}
	content := string(bytes)
	slog.Info("received file upload", "filename", header.Filename, "size_bytes", len(bytes))

	// Blob Name
	timestamp := time.Now().Format("20060102-150405")
	filename := filepath.Base(header.Filename)
	blobName := fmt.Sprintf("uploads/%s-%s", timestamp, filename)

	// Upload to Blob
	if err := d.Blob.UploadText(r.Context(), "rm-analyzer-data", blobName, content); err != nil {
		slog.Error("failed to upload blob", "blob_name", blobName, "container", "rm-analyzer-data", "error", err)
		WriteError(w, http.StatusInternalServerError, "Failed to upload blob: "+err.Error())
		return
	}
	slog.Info("successfully uploaded blob", "blob_name", blobName, "container", "rm-analyzer-data")

	// Queue Message
	msg := map[string]string{
		"blobName": blobName,
		"filename": filename,
	}

	if err := d.Queue.EnqueueMessage(r.Context(), "process-queue", msg); err != nil {
		slog.Error("failed to enqueue message", "queue", "process-queue", "filename", filename, "blob_name", blobName, "error", err)
		WriteError(w, http.StatusInternalServerError, "Failed to enqueue message: "+err.Error())
		return
	}
	slog.Info("successfully enqueued message", "queue", "process-queue", "filename", filename, "blob_name", blobName)

	WriteJSON(w, http.StatusOK, map[string]string{
		"status":   "success",
		"blobName": blobName,
	})
}
