package handlers

import (
	"fmt"
	"io"
	"net/http"
	"path/filepath"
	"time"
)

// HandleUpload handles CSV file uploads.
func (d *Dependencies) HandleUpload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		WriteError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// 10MB limit
	if err := r.ParseMultipartForm(10 << 20); err != nil {
		WriteError(w, http.StatusBadRequest, "File too large or invalid form")
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		WriteError(w, http.StatusBadRequest, "Failed to get file")
		return
	}
	defer file.Close()

	// Read file content
	bytes, err := io.ReadAll(file)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to read file")
		return
	}
	content := string(bytes)

	// Blob Name
	timestamp := time.Now().Format("20060102-150405")
	filename := filepath.Base(header.Filename)
	blobName := fmt.Sprintf("uploads/%s-%s", timestamp, filename)

	// Upload to Blob
	if err := d.Blob.UploadText(r.Context(), "rm-analyzer-data", blobName, content); err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to upload blob: "+err.Error())
		return
	}

	// Queue Message
	msg := map[string]string{
		"blobName": blobName,
		"filename": filename,
	}

	if err := d.Queue.EnqueueMessage(r.Context(), "process-queue", msg); err != nil {
		WriteError(w, http.StatusInternalServerError, "Failed to enqueue message: "+err.Error())
		return
	}

	WriteJSON(w, http.StatusOK, map[string]string{
		"status":   "success",
		"blobName": blobName,
	})
}
