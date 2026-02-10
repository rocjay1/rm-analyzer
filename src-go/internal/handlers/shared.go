package handlers

import (
	"encoding/json"
	"net/http"
)

// Dependencies holds the services required by the handlers.
type Dependencies struct {
	Database DatabaseClient
	Blob     BlobClient
	Queue    QueueClient
	Email    EmailClient
}

// WriteJSON writes a JSON response with the given status code.
func WriteJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if data != nil {
		json.NewEncoder(w).Encode(data)
	}
}

// WriteError writes an error response.
func WriteError(w http.ResponseWriter, status int, message string) {
	WriteJSON(w, status, map[string]string{"error": message})
}
