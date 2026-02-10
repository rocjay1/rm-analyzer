package models

// Category represents spending categories for transactions.
type Category string

const (
	CategoryDining        Category = "Dining & Drinks"
	CategoryGroceries     Category = "Groceries"
	CategoryPets          Category = "Pets"
	CategoryBills         Category = "Bills & Utilities"
	CategoryPurchases     Category = "Shared Purchases"
	CategorySubscriptions Category = "Shared Subscriptions"
	CategoryTravel        Category = "Travel & Vacation"
	CategoryOther         Category = "Other"
)
