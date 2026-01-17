import { renderNavbar } from './navbar.js';

const state = {
    month: '',
    startingBalance: 0,
    items: []
};

async function init() {
    await renderNavbar();

    // Initialize state
    state.month = getCurrentMonth();

    // Bind global events
    document.getElementById('monthPicker').addEventListener('change', handleMonthChange);
    document.getElementById('startingBalance').addEventListener('input', handleBalanceChange);
    document.getElementById('addItemBtn').addEventListener('click', handleAddItem);
    document.getElementById('saveBtn').addEventListener('click', handleSave);

    // Initial UI sync
    document.getElementById('monthPicker').value = state.month;

    // Load data
    await loadData();
}

async function loadData() {
    updateStatus('Loading data...', true);

    try {
        const response = await fetch(`/api/savings?month=${state.month}`);
        if (response.ok) {
            const data = await response.json();
            // Merge into state
            state.startingBalance = data.startingBalance !== undefined ? data.startingBalance : 0;
            state.items = Array.isArray(data.items) ? data.items : [];
            updateStatus('');
        } else if (response.status === 404) {
            // Reset for new month
            state.startingBalance = 0;
            state.items = [];
            updateStatus('');
        } else {
            console.error('Failed to load data', response.statusText);
            updateStatus('Error loading data.');
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus('Network error.');
    }

    render();
}

function render() {
    // Update inputs if they aren't the active element (to avoid cursor jumping)
    const balanceInput = document.getElementById('startingBalance');
    if (document.activeElement !== balanceInput) {
        balanceInput.value = state.startingBalance || '';
    }

    // Render Table
    const tbody = document.getElementById('costsBody');
    tbody.innerHTML = '';

    state.items.forEach((item, index) => {
        const tr = document.createElement('tr');

        // Name Cell
        const tdName = document.createElement('td');
        const inputName = document.createElement('input');
        inputName.type = 'text';
        inputName.className = 'item-name';
        inputName.value = item.name || '';
        inputName.placeholder = 'Expense Name';
        inputName.oninput = (e) => handleItemChange(index, 'name', e.target.value);
        tdName.appendChild(inputName);

        // Cost Cell
        const tdCost = document.createElement('td');
        const inputCost = document.createElement('input');
        inputCost.type = 'number';
        inputCost.className = 'item-cost';
        inputCost.value = item.cost || '';
        inputCost.placeholder = '0.00';
        inputCost.step = '0.01';
        inputCost.oninput = (e) => handleItemChange(index, 'cost', e.target.value);
        tdCost.appendChild(inputCost);

        // Action Cell
        const tdAction = document.createElement('td');
        const btnRemove = document.createElement('button');
        btnRemove.className = 'btn btn-danger';
        btnRemove.innerText = 'Remove';
        btnRemove.onclick = () => handleRemoveItem(index);
        tdAction.appendChild(btnRemove);

        tr.appendChild(tdName);
        tr.appendChild(tdCost);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
    });

    // Calculations
    const totalCost = state.items.reduce((sum, item) => sum + (parseFloat(item.cost) || 0), 0);
    const transfer = state.startingBalance - totalCost;

    const transferEl = document.getElementById('transferAmount');
    transferEl.innerText = `$${transfer.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    if (transfer < 0) {
        transferEl.style.color = '#d13438';
    } else {
        transferEl.style.color = '#0078d4';
    }
}

// Event Handlers

function handleMonthChange(e) {
    state.month = e.target.value;
    loadData();
}

function handleBalanceChange(e) {
    state.startingBalance = parseFloat(e.target.value) || 0;
    render(); // Re-render to update calculations
}

function handleAddItem() {
    state.items.push({ name: '', cost: '' });
    render();
}

function handleRemoveItem(index) {
    state.items.splice(index, 1);
    render();
}

function handleItemChange(index, field, value) {
    state.items[index][field] = value;
    // We don't call render() here to avoid losing focus/cursor position
    // But we do need to update calculations
    updateCalculations();
}

async function handleSave() {
    if (!state.month) {
        updateStatus('Please select a month.');
        return;
    }

    updateStatus('Saving...', true);

    // Filter out empty rows
    const payload = {
        month: state.month,
        startingBalance: state.startingBalance,
        items: state.items.filter(i => i.name || i.cost)
    };

    try {
        const response = await fetch('/api/savings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            updateStatus('Changes saved!');
            setTimeout(() => updateStatus(''), 3000);
        } else {
            const text = await response.text();
            updateStatus('Save failed: ' + text);
        }
    } catch (error) {
        updateStatus('Error saving changes.');
    } finally {
        document.getElementById('saveBtn').disabled = false;
    }
}

// Helpers

function updateCalculations() {
    const totalCost = state.items.reduce((sum, item) => sum + (parseFloat(item.cost) || 0), 0);
    const transfer = state.startingBalance - totalCost;

    const transferEl = document.getElementById('transferAmount');
    transferEl.innerText = `$${transfer.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (transfer < 0) {
        transferEl.style.color = '#d13438';
    } else {
        transferEl.style.color = '#0078d4';
    }
}

function updateStatus(msg, disableSave = false) {
    const statusSpan = document.getElementById('status');
    const saveBtn = document.getElementById('saveBtn');

    statusSpan.innerText = msg;
    saveBtn.disabled = disableSave;
}

function getCurrentMonth() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
}

// Start
document.addEventListener('DOMContentLoaded', init);
