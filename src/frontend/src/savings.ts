import '../styles.css';
import { renderNavbar } from './navbar';
import { fetchSavings, saveSavings } from './api';
import type { SavingsItem } from './types';

interface SavingsState {
    month: string;
    startingBalance: number;
    items: SavingsItem[];
}

const state: SavingsState = {
    month: '',
    startingBalance: 0,
    items: [],
};

async function init(): Promise<void> {
    await renderNavbar();

    state.month = getCurrentMonth();
    initMonthPicker();

    // Bind global events
    document.getElementById('monthSelect')?.addEventListener('change', handlePickerChange);
    document.getElementById('yearSelect')?.addEventListener('change', handlePickerChange);
    document.getElementById('startingBalance')?.addEventListener('input', handleBalanceChange);
    document.getElementById('addItemBtn')?.addEventListener('click', handleAddItem);
    document.getElementById('saveBtn')?.addEventListener('click', () => void handleSave());

    syncPickerToState();
    await loadData();
}

async function loadData(): Promise<void> {
    updateStatus('Loading data...', true);

    try {
        const data = await fetchSavings(state.month);

        if (data) {
            state.startingBalance = data.startingBalance ?? 0;
            state.items = Array.isArray(data.items) ? data.items : [];
            updateStatus('');
        } else {
            // No data for this month; try previous month
            const prevMonth = getPreviousMonth(state.month);
            try {
                const prevData = await fetchSavings(prevMonth);
                if (prevData) {
                    state.startingBalance = prevData.startingBalance ?? 0;
                    state.items = Array.isArray(prevData.items) ? prevData.items : [];
                    updateStatus('Data copied from previous month.');
                } else {
                    state.startingBalance = 0;
                    state.items = [];
                    updateStatus('');
                }
            } catch {
                state.startingBalance = 0;
                state.items = [];
                updateStatus('');
            }
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus('Network error.');
    }

    render();
}

function render(): void {
    // Sync Starting Balance Input
    const balanceInput = document.getElementById('startingBalance') as HTMLInputElement | null;
    if (balanceInput && document.activeElement !== balanceInput) {
        const newVal = state.startingBalance === 0 ? '' : String(state.startingBalance);
        if (balanceInput.value !== newVal) {
            balanceInput.value = newVal;
        }
    }

    const tbody = document.getElementById('costsBody');
    if (!tbody) return;
    const existingRows = tbody.children;

    // Sync rows
    state.items.forEach((item, index) => {
        let tr = existingRows[index] as HTMLTableRowElement | undefined;

        if (!tr) {
            tr = createRow(index, item);
            tbody.appendChild(tr);
        } else {
            // Update existing row
            const nameInput = tr.querySelector('.item-name') as HTMLInputElement | null;
            if (nameInput && document.activeElement !== nameInput) {
                if (nameInput.value !== item.name) {
                    nameInput.value = item.name || '';
                }
            }
            if (nameInput) {
                nameInput.oninput = (e: Event) =>
                    handleItemChange(index, 'name', (e.target as HTMLInputElement).value);
            }

            const costInput = tr.querySelector('.item-cost') as HTMLInputElement | null;
            if (costInput && document.activeElement !== costInput) {
                const costStr = String(item.cost ?? '');
                if (costInput.value !== costStr) {
                    costInput.value = costStr;
                }
            }
            if (costInput) {
                costInput.oninput = (e: Event) =>
                    handleItemChange(index, 'cost', (e.target as HTMLInputElement).value);
            }

            const btnRemove = tr.querySelector('.btn-danger') as HTMLButtonElement | null;
            if (btnRemove) {
                btnRemove.onclick = () => handleRemoveItem(index);
            }
        }
    });

    // Remove extra rows
    while (existingRows.length > state.items.length) {
        tbody.removeChild(existingRows[existingRows.length - 1]);
    }

    updateCalculations();
}

function createRow(index: number, item: SavingsItem): HTMLTableRowElement {
    const tr = document.createElement('tr');

    // Name Cell
    const tdName = document.createElement('td');
    const inputName = document.createElement('input');
    inputName.type = 'text';
    inputName.className = 'item-name';
    inputName.value = item.name || '';
    inputName.placeholder = 'Expense Name';
    inputName.oninput = (e: Event) =>
        handleItemChange(index, 'name', (e.target as HTMLInputElement).value);
    tdName.appendChild(inputName);

    // Cost Cell
    const tdCost = document.createElement('td');
    const inputCost = document.createElement('input');
    inputCost.type = 'number';
    inputCost.className = 'item-cost';
    inputCost.value = String(item.cost ?? '');
    inputCost.placeholder = '0.00';
    inputCost.step = '0.01';
    inputCost.oninput = (e: Event) =>
        handleItemChange(index, 'cost', (e.target as HTMLInputElement).value);
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

// --- Event Handlers ---

function handlePickerChange(): void {
    const month = (document.getElementById('monthSelect') as HTMLSelectElement).value;
    const year = (document.getElementById('yearSelect') as HTMLSelectElement).value;
    state.month = `${year}-${month}`;
    void loadData();
}

function handleBalanceChange(e: Event): void {
    state.startingBalance = parseFloat((e.target as HTMLInputElement).value) || 0;
    render();
}

function handleAddItem(): void {
    state.items.push({ name: '', cost: '' });
    render();
}

function handleRemoveItem(index: number): void {
    state.items.splice(index, 1);
    render();
}

function handleItemChange(index: number, field: keyof SavingsItem, value: string): void {
    state.items[index][field] = value;
    updateCalculations();
}

async function handleSave(): Promise<void> {
    if (!state.month) {
        updateStatus('Please select a month.');
        return;
    }

    updateStatus('Saving...', true);

    const payload = {
        month: state.month,
        startingBalance: state.startingBalance,
        items: state.items.filter((i) => i.name || i.cost),
    };

    try {
        await saveSavings(payload);
        updateStatus('Changes saved!');
        setTimeout(() => updateStatus(''), 3000);
    } catch {
        updateStatus('Error saving changes.');
    } finally {
        const saveBtn = document.getElementById('saveBtn') as HTMLButtonElement | null;
        if (saveBtn) saveBtn.disabled = false;
    }
}

// --- Helpers ---

function updateCalculations(): void {
    const totalCost = state.items.reduce(
        (sum, item) => sum + (parseFloat(String(item.cost)) || 0),
        0,
    );
    const transfer = state.startingBalance - totalCost;

    const transferEl = document.getElementById('transferAmount');
    if (!transferEl) return;

    transferEl.innerText = `$${transfer.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
    transferEl.style.color = transfer < 0 ? '#d13438' : '#0078d4';
}

function updateStatus(msg: string, disableSave = false): void {
    const statusSpan = document.getElementById('status');
    const saveBtn = document.getElementById('saveBtn') as HTMLButtonElement | null;

    if (statusSpan) statusSpan.innerText = msg;
    if (saveBtn) saveBtn.disabled = disableSave;
}

function getCurrentMonth(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
}

interface MonthOption {
    val: string;
    name: string;
}

function initMonthPicker(): void {
    const monthSelect = document.getElementById('monthSelect') as HTMLSelectElement | null;
    const yearSelect = document.getElementById('yearSelect') as HTMLSelectElement | null;
    if (!monthSelect || !yearSelect) return;

    const months: MonthOption[] = [
        { val: '01', name: 'January' },
        { val: '02', name: 'February' },
        { val: '03', name: 'March' },
        { val: '04', name: 'April' },
        { val: '05', name: 'May' },
        { val: '06', name: 'June' },
        { val: '07', name: 'July' },
        { val: '08', name: 'August' },
        { val: '09', name: 'September' },
        { val: '10', name: 'October' },
        { val: '11', name: 'November' },
        { val: '12', name: 'December' },
    ];

    months.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m.val;
        opt.textContent = m.name;
        monthSelect.appendChild(opt);
    });

    const currentYear = new Date().getFullYear();
    for (let y = currentYear - 5; y <= currentYear + 5; y++) {
        const opt = document.createElement('option');
        opt.value = y.toString();
        opt.textContent = y.toString();
        yearSelect.appendChild(opt);
    }
}

function syncPickerToState(): void {
    if (!state.month) return;
    const [year, month] = state.month.split('-');
    const monthSelect = document.getElementById('monthSelect') as HTMLSelectElement | null;
    const yearSelect = document.getElementById('yearSelect') as HTMLSelectElement | null;
    if (monthSelect) monthSelect.value = month;
    if (yearSelect) yearSelect.value = year;
}

function getPreviousMonth(currentMonth: string): string {
    if (!currentMonth) return '';
    const [yearStr, monthStr] = currentMonth.split('-');
    let year = parseInt(yearStr, 10);
    let month = parseInt(monthStr, 10);

    month -= 1;
    if (month === 0) {
        month = 12;
        year -= 1;
    }

    return `${year}-${String(month).padStart(2, '0')}`;
}

// Start
document.addEventListener('DOMContentLoaded', () => void init());
