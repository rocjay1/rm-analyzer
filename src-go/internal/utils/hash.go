package utils

import (
	"crypto/sha256"
	"encoding/hex"
)

// GenerateSHA256Hash returns the SHA-256 hash of the input string as a hex string.
func GenerateSHA256Hash(input string) string {
	hash := sha256.Sum256([]byte(input))
	return hex.EncodeToString(hash[:])
}
