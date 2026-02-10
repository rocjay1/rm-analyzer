package services

import (
	"fmt"
	"strings"
)

// RenderErrorSection renders the error section HTML.
func RenderErrorSection(errors []string) string {
	if len(errors) == 0 {
		return ""
	}

	var errorItems strings.Builder
	for _, e := range errors {
		errorItems.WriteString(fmt.Sprintf("<li>%s</li>", e))
	}

	return fmt.Sprintf(`
		<div style="background-color: #fff4f4; border-left: 5px solid #d13438; padding: 15px; margin-bottom: 20px;">
			<h3 style="color: #d13438; margin-top: 0; font-size: 18px;">⚠️ Warning: Some transactions were skipped</h3>
			<ul style="margin-bottom: 0; padding-left: 20px;">
				%s
			</ul>
		</div>
	`, errorItems.String())
}

// RenderErrorBody renders the full HTML body for an error email.
func RenderErrorBody(errors []string) string {
	return fmt.Sprintf(`
		<html>
		<body style="font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px;">
			<div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
				<div style="background-color: #d13438; padding: 20px; text-align: center; color: white;">
					<h2 style="margin: 0;">Upload Failed</h2>
				</div>
				<div style="padding: 20px;">
					<p>The uploaded CSV could not be processed due to the following errors:</p>
					%s
				</div>
			</div>
		</body>
		</html>
	`, RenderErrorSection(errors))
}
