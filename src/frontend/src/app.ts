import '../styles.css';
import { renderNavbar } from './navbar';
import { fetchCards as apiFetchCards, saveCard as apiSaveCard, deleteCard as apiDeleteCard, uploadFile as apiUploadFile } from './api';
import type { CreditCard, CreditCardPayload } from './types';

let allCards: CreditCard[] = [];

// --- Data Loading ---

async function fetchCards(): Promise<void> {
    try {
        allCards = await apiFetchCards();
        renderCards();
    } catch (error) {
        console.error(error);
        const container = document.getElementById('cards-container');
        if (container) {
            container.innerHTML = '<div class="error">Failed to load cards.</div>';
        }
    }
}

// --- Upload Logic ---

async function handleUpload(): Promise<void> {
    const fileInput = document.getElementById('fileInput') as HTMLInputElement;
    const statusDiv = document.getElementById('status') as HTMLElement;
    const btn = document.getElementById('uploadBtn') as HTMLButtonElement;

    if (!fileInput.files?.length) {
        statusDiv.innerText = 'Please select a file.';
        return;
    }

    const file = fileInput.files[0];
    btn.disabled = true;
    statusDiv.innerText = 'Uploading...';
    statusDiv.className = 'status-message';

    try {
        await apiUploadFile(file);
        statusDiv.innerText = 'Upload accepted! Backend is processing. Balances will update shortly.';
        statusDiv.classList.add('success');
        setTimeout(() => void fetchCards(), 2000);
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        statusDiv.innerText = `Error: ${message}`;
        statusDiv.classList.add('error');
    } finally {
        btn.disabled = false;
    }
}

// --- Rendering ---

function renderCards(): void {
    const container = document.getElementById('cards-container');
    if (!container) return;
    container.innerHTML = '';

    if (allCards.length === 0) {
        container.innerHTML = '<p>No cards configured. Click "Manage Cards" to add one.</p>';
        return;
    }

    allCards.forEach((card) => {
        const utilPercent = (card.utilization * 100).toFixed(1);
        let statusClass = 'low-utilization';
        if (card.utilization > 0.3) statusClass = 'high-utilization';
        else if (card.utilization > 0.1) statusClass = 'medium-utilization';

        const paymentNeeded = card.target_payment > 0;

        const cardEl = document.createElement('div');
        cardEl.className = `card-item ${statusClass}`;
        cardEl.innerHTML = `
            <h3>${card.name} (${card.account_number})</h3>
            <p><strong>Current Balance:</strong> $${card.current_balance.toFixed(2)}</p>
            <p><strong>Limit:</strong> $${card.credit_limit.toFixed(2)}</p>
            <p><strong>Utilization:</strong> ${utilPercent}%</p>
            <div class="util-bar-container">
                <div class="util-bar" style="width: ${Math.min(parseFloat(utilPercent), 100)}%; background-color: ${getColor(card.utilization)}"></div>
            </div>
            <p><strong>Statement Balance:</strong> $${card.statement_balance.toFixed(2)}</p>
            ${paymentNeeded ? `<p style="color: #d35400; font-weight: bold;">Pay $${card.target_payment.toFixed(2)} by Day ${card.due_day}</p>` : '<p style="color: green;">On Track</p>'}
            ${card.last_reconciled ? `<p class="small-text">Reconciled: ${card.last_reconciled}</p>` : ''}
            <button class="btn secondary small edit-btn" data-id="${card.id}">Edit</button>
        `;

        const editBtn = cardEl.querySelector('.edit-btn');
        if (editBtn) {
            editBtn.addEventListener('click', () => openCardModal(card));
        }
        container.appendChild(cardEl);
    });
}

function getColor(utilization: number): string {
    if (utilization > 0.3) return '#e74c3c';
    if (utilization > 0.1) return '#f1c40f';
    return '#2ecc71';
}

// --- Modals & Forms ---

function openCardModal(card: CreditCard | null = null): void {
    const modal = document.getElementById('cardModal') as HTMLElement;
    const form = document.getElementById('cardForm') as HTMLFormElement;
    const title = document.getElementById('modalTitle') as HTMLElement;
    const deleteBtn = document.getElementById('deleteCardBtn') as HTMLButtonElement | null;

    form.reset();

    if (card) {
        title.innerText = 'Edit Credit Card';
        (document.getElementById('cardId') as HTMLInputElement).value = card.id;
        (document.getElementById('cardName') as HTMLInputElement).value = card.name;
        (document.getElementById('accountNumber') as HTMLInputElement).value = String(card.account_number);
        (document.getElementById('creditLimit') as HTMLInputElement).value = String(card.credit_limit);
        (document.getElementById('dueDay') as HTMLInputElement).value = String(card.due_day);
        (document.getElementById('currentBalance') as HTMLInputElement).value = String(card.current_balance);
        (document.getElementById('statementBalance') as HTMLInputElement).value = String(card.statement_balance);

        if (deleteBtn) {
            deleteBtn.style.display = 'inline-block';
            deleteBtn.dataset.id = card.id;
        }
    } else {
        title.innerText = 'Add Credit Card';
        (document.getElementById('cardId') as HTMLInputElement).value = '';
        (document.getElementById('currentBalance') as HTMLInputElement).value = '0';
        (document.getElementById('statementBalance') as HTMLInputElement).value = '0';

        if (deleteBtn) {
            deleteBtn.style.display = 'none';
        }
    }

    modal.style.display = 'block';
}

function openStatementModal(): void {
    const modal = document.getElementById('statementModal') as HTMLElement;
    const container = document.getElementById('statementFields') as HTMLElement;
    container.innerHTML = '';

    allCards.forEach((card) => {
        const div = document.createElement('div');
        div.className = 'form-group';
        div.innerHTML = `
            <label>${card.name} (Current Stmt: $${card.statement_balance.toFixed(2)})</label>
            <input type="number" step="0.01" class="stmt-input" data-id="${card.id}" value="${card.statement_balance}">
        `;
        container.appendChild(div);
    });

    modal.style.display = 'block';
}

function closeModal(modalId: string): void {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    void renderNavbar();
    void fetchCards();

    // Toolbar Buttons
    document.getElementById('addCardBtn')?.addEventListener('click', () => openCardModal());
    document.getElementById('updateStatementsBtn')?.addEventListener('click', openStatementModal);

    // Upload
    document.getElementById('uploadBtn')?.addEventListener('click', () => void handleUpload());

    // Close Modals
    document.querySelectorAll('.close').forEach((span) => {
        span.addEventListener('click', function (this: HTMLElement) {
            const modal = this.closest('.modal') as HTMLElement | null;
            if (modal) modal.style.display = 'none';
        });
    });

    window.onclick = function (event: MouseEvent) {
        const target = event.target as HTMLElement;
        if (target.classList.contains('modal')) {
            target.style.display = 'none';
        }
    };

    // Card Form Submit
    document.getElementById('cardForm')?.addEventListener('submit', (e: Event) => {
        e.preventDefault();
        const id = (document.getElementById('cardId') as HTMLInputElement).value;
        const data: CreditCardPayload = {
            id: id || undefined,
            name: (document.getElementById('cardName') as HTMLInputElement).value,
            account_number: parseInt((document.getElementById('accountNumber') as HTMLInputElement).value),
            credit_limit: parseFloat((document.getElementById('creditLimit') as HTMLInputElement).value),
            due_day: parseInt((document.getElementById('dueDay') as HTMLInputElement).value),
            current_balance: parseFloat((document.getElementById('currentBalance') as HTMLInputElement).value),
            statement_balance: parseFloat((document.getElementById('statementBalance') as HTMLInputElement).value),
        };
        void apiSaveCard(data).then(() => {
            void fetchCards();
            closeModal('cardModal');
        }).catch((err: unknown) => {
            const message = err instanceof Error ? err.message : 'Unknown error';
            alert('Error saving card: ' + message);
        });
    });

    // Delete Card Button
    const deleteBtn = document.getElementById('deleteCardBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async (e: Event) => {
            const targetBtn = e.currentTarget as HTMLButtonElement;
            const id = targetBtn.dataset.id;

            if (!id) {
                return;
            }

            if (confirm('Are you sure you want to delete this card? This action cannot be undone.')) {
                try {
                    await apiDeleteCard(id);
                    await fetchCards();
                    closeModal('cardModal');
                } catch (err: unknown) {
                    const message = err instanceof Error ? err.message : 'Unknown error';
                    alert('Error deleting card: ' + message);
                }
            }
        });
    }

    // Statement Form Submit
    document.getElementById('statementForm')?.addEventListener('submit', (e: Event) => {
        e.preventDefault();
        void handleStatementSubmit();
    });
});

async function handleStatementSubmit(): Promise<void> {
    const inputs = document.querySelectorAll<HTMLInputElement>('.stmt-input');

    for (const input of inputs) {
        const cardId = input.getAttribute('data-id');
        const newStmt = parseFloat(input.value);
        const card = allCards.find((c) => c.id === cardId);

        if (card && card.statement_balance !== newStmt) {
            try {
                const payload: CreditCardPayload = {
                    id: card.id,
                    name: card.name,
                    account_number: card.account_number,
                    credit_limit: card.credit_limit,
                    due_day: card.due_day,
                    current_balance: card.current_balance,
                    statement_balance: newStmt,
                };
                await apiSaveCard(payload);
            } catch (err) {
                console.error(`Failed to update ${card.name}`, err);
            }
        }
    }
    await fetchCards();
    closeModal('statementModal');
}
