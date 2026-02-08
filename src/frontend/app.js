import { renderNavbar } from './navbar.js';

let allCards = [];

// --- API Interactions ---

async function fetchCards() {
    try {
        const response = await fetch('/api/cards');
        if (!response.ok) throw new Error('Failed to fetch cards');
        allCards = await response.json();
        renderCards();
    } catch (error) {
        console.error(error);
        document.getElementById('cards-container').innerHTML = '<div class="error">Failed to load cards.</div>';
    }
}

async function saveCard(cardData) {
    try {
        const response = await fetch('/api/cards', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cardData)
        });
        if (!response.ok) throw new Error('Failed to save card');
        await fetchCards(); // Refresh list
        closeModal('cardModal');
    } catch (error) {
        alert('Error saving card: ' + error.message);
    }
}

// --- Upload Logic ---

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const statusDiv = document.getElementById('status');
    const btn = document.getElementById('uploadBtn');

    if (!fileInput.files.length) {
        statusDiv.innerText = 'Please select a file.';
        return;
    }

    const file = fileInput.files[0];
    btn.disabled = true;
    statusDiv.innerText = 'Uploading...';
    statusDiv.className = 'status-message'; // Reset class

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            statusDiv.innerText = 'Upload accepted! Backend is processing. Balances will update shortly.';
            statusDiv.classList.add('success');
            // Poll for updates or just wait a bit? For now, user can manually refresh.
            setTimeout(fetchCards, 2000);
        } else {
            const errorText = await response.text();
            throw new Error(errorText || 'Upload failed');
        }
    } catch (error) {
        statusDiv.innerText = `Error: ${error.message}`;
        statusDiv.classList.add('error');
    } finally {
        btn.disabled = false;
    }
}

// --- Rendering ---

function renderCards() {
    const container = document.getElementById('cards-container');
    container.innerHTML = '';

    if (allCards.length === 0) {
        container.innerHTML = '<p>No cards configured. Click "Manage Cards" to add one.</p>';
        return;
    }

    allCards.forEach(card => {
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
                <div class="util-bar" style="width: ${Math.min(utilPercent, 100)}%; background-color: ${getColor(card.utilization)}"></div>
            </div>
            <p><strong>Statement Balance:</strong> $${card.statement_balance.toFixed(2)}</p>
            ${paymentNeeded ? `<p style="color: #d35400; font-weight: bold;">Pay $${card.target_payment.toFixed(2)} by Day ${card.due_day}</p>` : '<p style="color: green;">On Track</p>'}
            ${card.last_reconciled ? `<p class="small-text">Reconciled: ${card.last_reconciled}</p>` : ''}
            <button class="btn secondary small edit-btn" data-id="${card.id}">Edit</button>

        `;

        cardEl.querySelector('.edit-btn').addEventListener('click', () => openCardModal(card));
        container.appendChild(cardEl);
    });
}

function getColor(utilization) {
    if (utilization > 0.3) return '#e74c3c';
    if (utilization > 0.1) return '#f1c40f';
    return '#2ecc71';
}

// --- Modals & Forms ---

function openCardModal(card = null) {
    const modal = document.getElementById('cardModal');
    const form = document.getElementById('cardForm');
    const title = document.getElementById('modalTitle');

    form.reset();

    if (card) {
        title.innerText = 'Edit Credit Card';
        document.getElementById('cardId').value = card.id;
        document.getElementById('cardName').value = card.name;
        document.getElementById('accountNumber').value = card.account_number;
        document.getElementById('creditLimit').value = card.credit_limit;
        document.getElementById('dueDay').value = card.due_day;
        document.getElementById('currentBalance').value = card.current_balance;
        document.getElementById('statementBalance').value = card.statement_balance;
    } else {
        title.innerText = 'Add Credit Card';
        document.getElementById('cardId').value = '';
        // Defaults
        document.getElementById('currentBalance').value = 0;
        document.getElementById('statementBalance').value = 0;
    }

    modal.style.display = 'block';
}

function openStatementModal() {
    const modal = document.getElementById('statementModal');
    const container = document.getElementById('statementFields');
    container.innerHTML = '';

    allCards.forEach(card => {
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

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', () => {
    renderNavbar();
    fetchCards();

    // Toolbar Buttons
    document.getElementById('addCardBtn').addEventListener('click', () => openCardModal());
    document.getElementById('updateStatementsBtn').addEventListener('click', openStatementModal);

    // Upload
    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) uploadBtn.addEventListener('click', uploadFile);

    // Close Modals
    document.querySelectorAll('.close').forEach(span => {
        span.addEventListener('click', function () {
            this.closest('.modal').style.display = 'none';
        });
    });

    window.onclick = function (event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    };

    // Card Form Submit
    document.getElementById('cardForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const id = document.getElementById('cardId').value;
        const data = {
            id: id || undefined, // undefined lets backed generate ID if generic, but here we usually use rowkey
            name: document.getElementById('cardName').value,
            account_number: parseInt(document.getElementById('accountNumber').value),
            credit_limit: parseFloat(document.getElementById('creditLimit').value),
            due_day: parseInt(document.getElementById('dueDay').value),
            current_balance: parseFloat(document.getElementById('currentBalance').value),
            statement_balance: parseFloat(document.getElementById('statementBalance').value)
        };
        saveCard(data);
    });

    // Statement Form Submit
    document.getElementById('statementForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const inputs = document.querySelectorAll('.stmt-input');

        // Process sequentially to avoid race conditions or heavy load
        for (const input of inputs) {
            const cardId = input.getAttribute('data-id');
            const newStmt = parseFloat(input.value);
            const card = allCards.find(c => c.id === cardId);

            if (card && card.statement_balance !== newStmt) {
                // Update specific field
                const updatedCard = { ...card, statement_balance: newStmt };
                // Using saveCard logic but manual fetch to avoid full refresh until end
                try {
                    await fetch('/api/cards', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updatedCard)
                    });
                } catch (err) {
                    console.error(`Failed to update ${card.name}`, err);
                }
            }
        }
        await fetchCards();
        closeModal('statementModal');
    });
});
