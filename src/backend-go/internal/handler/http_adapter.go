package handler

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
)

// HTTPTriggerRequest represents the structure of the JSON payload for HTTP triggers.
type HTTPTriggerRequest struct {
	Data struct {
		Req struct {
			URL             string              `json:"Url"`
			Method          string              `json:"Method"`
			Query           map[string]string   `json:"Query"`
			Headers         map[string][]string `json:"Headers"`
			Params          map[string]string   `json:"Params"`
			Body            string              `json:"Body"`
			IsBase64Encoded bool                `json:"isBase64Encoded"`
		} `json:"req"`
	} `json:"Data"`
	Metadata map[string]any `json:"Metadata"`
}

// HTTPTriggerResponse represents the structure of the JSON response for HTTP triggers.
type HTTPTriggerResponse struct {
	Outputs struct {
		Res struct {
			StatusCode int               `json:"statusCode"`
			Headers    map[string]string `json:"headers"`
			Body       string            `json:"body"`
		} `json:"res"`
	} `json:"Outputs"`
	Logs        []string `json:"Logs,omitempty"`
	ReturnValue any      `json:"ReturnValue,omitempty"`
}

// HandleHttpTrigger adapts the Azure Functions JSON POST request to a standard HTTP request/response.
// It wraps the provided Next handler (usually the ServeMux).
func (d *Dependencies) HandleHttpTrigger(next http.Handler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		slog.Info("HTTP TRIGGER ADAPTER INVOKED")

		var invokeReq HTTPTriggerRequest
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			slog.Error("failed to read HTTP trigger body", "error", err)
			http.Error(w, "Failed to read request body", http.StatusBadRequest)
			return
		}

		slog.Info("RAW HTTP ADAPTER BODY", "body", string(bodyBytes))

		if err := json.Unmarshal(bodyBytes, &invokeReq); err != nil {
			slog.Error("failed to unmarshal HTTP trigger request", "error", err)
			http.Error(w, "Failed to unmarshal request", http.StatusBadRequest)
			return
		}

		reqData := invokeReq.Data.Req
		slog.Info("processing wrapped HTTP request", "method", reqData.Method, "url", reqData.URL)

		// Create a new HTTP request from the JSON data
		// The URL in the payload is absolute (e.g. http://localhost:7071/api/cards).
		// We need to parse it to get the path relative to our internal router if needed.
		// However, standard http.NewRequest accepts absolute URLs.

		// Handle body: it might be base64 encoded.
		// Some hosts don't set isBase64Encoded flag but send base64 anyway.
		var bodyReader io.Reader
		if reqData.Body != "" {
			bodyBytes := []byte(reqData.Body)
			// Try decoding as base64
			if decoded, err := base64.StdEncoding.DecodeString(reqData.Body); err == nil {
				bodyBytes = decoded
				slog.Info("successfully decoded body as base64", "original_len", len(reqData.Body), "decoded_len", len(bodyBytes))
			} else {
				slog.Debug("body is not base64 or decoding failed, using raw", "error", err)
			}
			bodyReader = bytes.NewReader(bodyBytes)
		} else {
			bodyReader = http.NoBody
		}

		newReq, err := http.NewRequest(reqData.Method, reqData.URL, bodyReader)
		if err != nil {
			slog.Error("failed to create internal request", "error", err)
			http.Error(w, "Failed to create internal request", http.StatusInternalServerError)
			return
		}

		// Copy headers
		slog.Info("copying headers to internal request", "count", len(reqData.Headers))
		for k, v := range reqData.Headers {
			for _, val := range v {
				newReq.Header.Add(k, val)
				slog.Debug("adding header", "key", k, "value", val)
			}
		}

		slog.Info("internal request prepared",
			"method", newReq.Method,
			"path", newReq.URL.Path,
			"content_type", newReq.Header.Get("Content-Type"),
			"content_length", newReq.ContentLength,
		)

		// Use httptest.ResponseRecorder to capture the response
		recorder := httptest.NewRecorder()

		// Call the internal handler (ServeMux)
		next.ServeHTTP(recorder, newReq)

		// Construct the JSON response
		respResult := recorder.Result()
		respBodyBytes, _ := io.ReadAll(respResult.Body)
		respResult.Body.Close()

		respHeaders := make(map[string]string)
		for k, v := range respResult.Header {
			respHeaders[k] = v[0] // Simplified header handling
		}

		jsonResp := HTTPTriggerResponse{}
		jsonResp.Outputs.Res.StatusCode = respResult.StatusCode
		jsonResp.Outputs.Res.Headers = respHeaders
		jsonResp.Outputs.Res.Body = string(respBodyBytes)

		// Write the JSON response back to the Host
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(jsonResp); err != nil {
			slog.Error("failed to encode HTTP trigger response", "error", err)
		}
	}
}
