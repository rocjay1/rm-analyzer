
async function loadData() {
    const statusSpan = document.getElementById('status');
    const saveBtn = document.getElementById('saveBtn');

    // Get selected month or default to current
    const monthPicker = document.getElementById('monthPicker');
    if (!monthPicker.value) {
        // Set to current month by default
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0'); // January is 0!
        monthPicker.value = `${year}-${month}`;
    }
    const selectedMonth = monthPicker.value;

    // Disable save while loading
    saveBtn.disabled = true;
    statusSpan.innerText = 'Loading data...';

    try {
        const response = await fetch(`/api/savings?month=${selectedMonth}`);
        if (response.ok) {
            const data = await response.json();
            populateForm(data);
            recalculate();
            statusSpan.innerText = '';
        } else {
            console.error('Failed to load data', response.statusText);
            statusSpan.innerText = 'Error loading data.';
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        statusSpan.innerText = 'Network error.';
    } finally {
        saveBtn.disabled = false;
    }
}

function populateForm(data) {
    if (data.startingBalance !== undefined) {
        document.getElementById('startingBalance').value = data.startingBalance;
    } else {
        document.getElementById('startingBalance').value = "";
    }

    const tbody = document.getElementById('costsBody');
    tbody.innerHTML = ''; // Clear existing

    if (data.items && Array.isArray(data.items)) {
        data.items.forEach(item => addRow(item.name, item.cost));
    }
}

function addRow(name = '', cost = '') {
    const tbody = document.getElementById('costsBody');
    const tr = document.createElement('tr');

    tr.innerHTML = `
        <td><input type="text" class="item-name" value="${name}" placeholder="Expense Name" oninput="recalculate()"></td>
        <td><input type="number" class="item-cost" value="${cost}" placeholder="0.00" step="0.01" oninput="recalculate()"></td>
        <td><button class="btn btn-danger" onclick="removeRow(this)">Remove</button></td>
    `;
    tbody.appendChild(tr);
    recalculate();
}

function removeRow(btn) {
    const row = btn.closest('tr');
    row.remove();
    recalculate();
}

function recalculate() {
    const startingBalanceCheck = parseFloat(document.getElementById('startingBalance').value);
    const startingBalance = isNaN(startingBalanceCheck) ? 0 : startingBalanceCheck;

    const costs = document.querySelectorAll('.item-cost');
    let totalCost = 0;
    costs.forEach(input => {
        const val = parseFloat(input.value);
        if (!isNaN(val)) {
            totalCost += val;
        }
    });

    const transfer = startingBalance - totalCost;

    const transferEl = document.getElementById('transferAmount');
    transferEl.innerText = `$${transfer.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    // Visual cue
    if (transfer < 0) {
        transferEl.style.color = '#d13438'; // Red if negative
    } else {
        transferEl.style.color = '#0078d4'; // Blue default
    }
}

async function saveData() {
    const statusSpan = document.getElementById('status');
    const saveBtn = document.getElementById('saveBtn');
    const monthPicker = document.getElementById('monthPicker');

    if (!monthPicker.value) {
        statusSpan.innerText = 'Please select a month.';
        return;
    }

    saveBtn.disabled = true;
    statusSpan.innerText = 'Saving...';

    const startingBalance = parseFloat(document.getElementById('startingBalance').value) || 0;
    const items = [];

    document.querySelectorAll('#costsBody tr').forEach(row => {
        const name = row.querySelector('.item-name').value;
        const cost = parseFloat(row.querySelector('.item-cost').value) || 0;
        if (name || cost) { // Only save non-empty rows
            items.push({ name, cost });
        }
    });

    const payload = {
        month: monthPicker.value,
        startingBalance,
        items
    };

    try {
        const response = await fetch('/api/savings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            statusSpan.innerText = 'Changes saved!';
            setTimeout(() => { statusSpan.innerText = ''; }, 3000);
        } else {
            const text = await response.text();
            statusSpan.innerText = 'Save failed: ' + text;
        }
    } catch (error) {
        statusSpan.innerText = 'Error saving changes.';
    } finally {
        saveBtn.disabled = false;
    }
}

// Global listener for starting balance changes
document.getElementById('startingBalance').addEventListener('input', recalculate);
// Listener for month changes
document.getElementById('monthPicker').addEventListener('change', loadData);

// Load on start
loadData();
