import type { CreditCard, CreditCardPayload, SavingsData, SavingsPayload, AuthPayload } from './types';

/** Fetch all credit cards. */
export async function fetchCards(): Promise<CreditCard[]> {
    const response = await fetch('/api/cards');
    if (!response.ok) {
        throw new Error('Failed to fetch cards');
    }
    return response.json() as Promise<CreditCard[]>;
}

/** Create or update a credit card. */
export async function saveCard(cardData: CreditCardPayload): Promise<void> {
    const response = await fetch('/api/cards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cardData),
    });
    if (!response.ok) {
        throw new Error('Failed to save card');
    }
}

/** Delete a credit card. */
export async function deleteCard(id: string): Promise<void> {
    const response = await fetch(`/api/cards?id=${encodeURIComponent(id)}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete card');
    }
}

/** Upload a CSV file for processing. */
export async function uploadFile(file: File): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Upload failed');
    }
}

/** Fetch savings data for a given month (YYYY-MM format). */
export async function fetchSavings(month: string): Promise<SavingsData | null> {
    const response = await fetch(`/api/savings?month=${month}`);
    if (response.ok) {
        return response.json() as Promise<SavingsData>;
    }
    if (response.status === 404) {
        return null;
    }
    throw new Error(`Failed to load savings: ${response.statusText}`);
}

/** Save savings data for a given month. */
export async function saveSavings(payload: SavingsPayload): Promise<void> {
    const response = await fetch(`/api/savings?month=${payload.month}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Save failed');
    }
}

/** Fetch the current authenticated user info from SWA auth. */
export async function fetchAuthInfo(): Promise<AuthPayload | null> {
    try {
        const response = await fetch('/.auth/me');
        if (response.ok) {
            return response.json() as Promise<AuthPayload>;
        }
    } catch {
        // Auth endpoint not available (local dev without SWA emulator)
    }
    return null;
}
