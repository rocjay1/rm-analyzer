/** Represents a credit card with tracking for utilization. Matches Go CreditCard model. */
export interface CreditCard {
    id: string;
    name: string;
    account_number: number;
    credit_limit: number;
    due_day: number;
    statement_balance: number;
    current_balance: number;
    last_reconciled?: string;
    utilization: number;
    target_payment: number;
}

/** Represents spending categories for transactions. Matches Go Category model. */
export enum Category {
    Dining = "Dining & Drinks",
    Groceries = "Groceries",
    Pets = "Pets",
    Bills = "Bills & Utilities",
    Purchases = "Shared Purchases",
    Subscriptions = "Shared Subscriptions",
    Travel = "Travel & Vacation",
    Payment = "Credit Card Payment",
    Donations = "Charitable Donations",
    Loans = "Loan Payment",
    Miscellaneous = "Miscellaneous",
    Rocco = "Rocco’s Bucket",
    Tori = "Tori's Bucket",
    Other = "Other"
}

/** Payload for creating/updating a credit card. */
export interface CreditCardPayload {
    id?: string;
    name: string;
    account_number: number;
    credit_limit: number;
    due_day: number;
    current_balance: number;
    statement_balance: number;
}

/** A single line item in the savings breakdown. Matches Go SavingsItem model. */
export interface SavingsItem {
    name: string;
    cost: string | number;
}

/** Savings data for a specific month. Matches Go SavingsData model. */
export interface SavingsData {
    startingBalance: number;
    items: SavingsItem[];
}

/** Payload for saving savings data (includes month). */
export interface SavingsPayload extends SavingsData {
    month: string;
}

/** Azure Static Web Apps auth payload from /.auth/me. */
export interface AuthPayload {
    clientPrincipal: {
        userDetails: string;
        userRoles: string[];
    } | null;
}
