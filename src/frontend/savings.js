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
    // Sync Starting Balance Input
    const balanceInput = document.getElementById('startingBalance');
    if (document.activeElement !== balanceInput) {
        // Only update if value implies a change (loose equality might be enough, but strict is safer if types match)
        // Convert to string to compare with input.value
        const newVal = state.startingBalance === 0 ? '' : state.startingBalance;
        if (balanceInput.value != newVal) {
            balanceInput.value = newVal;
        }
    }

    const tbody = document.getElementById('costsBody');
    const existingRows = tbody.children;

    // 1. Sync Rows
    state.items.forEach((item, index) => {
        let tr = existingRows[index];

        if (!tr) {
            // Create new row
            tr = createRow(index, item);
            tbody.appendChild(tr);
        } else {
            // Update existing row
            // Check if we need to update listeners (index might strictly stay same, but if we reorder, helpful to update)
            // But we don't support reordering yet.

            // Name Input
            const nameInput = tr.querySelector('.item-name');
            if (nameInput && document.activeElement !== nameInput) {
                if (nameInput.value !== item.name) {
                    nameInput.value = item.name || '';
                }
            }
            // Ensure onclick handler uses correct index (if we delete from middle, indices shift)
            // Ideally we re-attach handlers or use event delegation. 
            // Re-attaching easiest for now without rewriting everything.
            nameInput.oninput = (e) => handleItemChange(index, 'name', e.target.value);

            // Cost Input
            const costInput = tr.querySelector('.item-cost');
            if (costInput && document.activeElement !== costInput) {
                if (costInput.value !== item.cost) {
                    costInput.value = item.cost || '';
                }
            }
            costInput.oninput = (e) => handleItemChange(index, 'cost', e.target.value);

            // Remove Button
            const btnRemove = tr.querySelector('.btn-danger');
            btnRemove.onclick = () => handleRemoveItem(index);
        }
    });

    // 2. Remove extra rows
    while (existingRows.length > state.items.length) {
        tbody.removeChild(existingRows[existingRows.length - 1]);
    }

    // 3. Update Calculations
    updateCalculations();
}

function createRow(index, item) {
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

    return tr;
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
