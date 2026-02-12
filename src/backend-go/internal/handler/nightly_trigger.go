package handler

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/shopspring/decimal"
)

// HandleNightlyTrigger processes the nightly trigger to check credit card payments.
func (d *Dependencies) HandleNightlyTrigger(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	slog.Info("Starting nightly trigger processing")

	// 1. Get User Email
	userEmail := os.Getenv("USER_EMAIL")
	if userEmail == "" {
		slog.Warn("USER_EMAIL environment variable is not set; skipping email notifications")
		w.WriteHeader(http.StatusOK)
		return
	}

	// 2. Get Credit Cards
	cards, err := d.Database.GetCreditCards(ctx)
	if err != nil {
		slog.Error("Failed to fetching credit cards", "error", err)
		http.Error(w, "Failed to fetch credit cards", http.StatusInternalServerError)
		return
	}

	// 3. Determine dates
	now := time.Now()
	targetDate := now.AddDate(0, 0, 3) // 3 days from now
	targetDay := targetDate.Day()

	slog.Info("Checking cards for upcoming due date", "target_date", targetDate.Format("2006-01-02"), "target_day", targetDay)

	// 4. Iterate and Check
	for _, card := range cards {
		// Calculate derived fields first
		card.PopulateCalculatedFields()

		// Check if due day matches
		// Note: This simple check assumes due day is just the day of month.
		// It might need more robust handling for end-of-month logic, but this is a good start.
		if card.DueDay == targetDay {
			paymentNeeded := card.CalculateTargetPayment()

			if paymentNeeded.GreaterThan(decimal.Zero) {
				slog.Info("Card payment needed",
					"card", card.Name,
					"due_in_days", 3,
					"amount", paymentNeeded.StringFixed(2))

				// Send Email
				subject := fmt.Sprintf("Payment Reminder: %s", card.Name)
				body := fmt.Sprintf(`
					<h3>Payment Reminder</h3>
					<p>Your <b>%s</b> card is due in 3 days (on day %d).</p>
					<p>To keep utilization at 10%%, you need to make an additional payment of:</p>
					<h2>$%s</h2>
					<p>Current Balance: $%s</p>
					<p>Credit Limit: $%s</p>
					<p>Target (10%%): $%s</p>
				`,
					card.Name,
					card.DueDay,
					paymentNeeded.StringFixed(2),
					card.CurrentBalance.StringFixed(2),
					card.CreditLimit.StringFixed(2),
					card.CreditLimit.Mul(decimal.NewFromFloat(0.1)).StringFixed(2),
				)

				if err := d.Email.SendEmail(ctx, []string{userEmail}, subject, body); err != nil {
					slog.Error("Failed to send payment reminder email",
						"card", card.Name,
						"email", userEmail,
						"error", err)
					// Continue to next card even if email fails
				} else {
					slog.Info("Payment reminder email sent", "card", card.Name, "email", userEmail)
				}
			} else {
				slog.Info("Card due soon but no payment needed",
					"card", card.Name,
					"current_balance", card.CurrentBalance.StringFixed(2),
					"target_payment", paymentNeeded.StringFixed(2))
			}
		}
	}

	slog.Info("Nightly trigger processing complete")
	w.WriteHeader(http.StatusOK)
}
