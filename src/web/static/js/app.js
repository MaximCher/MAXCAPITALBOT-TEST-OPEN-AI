// MAXCAPITAL Bot Admin Panel - Frontend JavaScript

const API_BASE = '/api';

// State
let currentFilters = {
    user_id: null,
    start_date: null,
    end_date: null,
    role: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initLogin();
    initFilters();
    checkAuth();
});

// Login
function initLogin() {
    const loginForm = document.getElementById('login-form');
    const passwordInput = document.getElementById('password-input');
    
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = passwordInput.value.trim();
        
        if (!password) {
            showError('Введите пароль');
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            
            if (response.ok) {
                showAdminPanel();
                passwordInput.value = '';
                document.getElementById('login-error').textContent = '';
                // Load data after successful login (wait for DOM to update)
                setTimeout(() => {
                    loadDialogs();
                    loadUsers();
                    loadStatistics();
                }, 200);
            } else {
                const data = await response.json();
                showError(data.detail || 'Неверный пароль');
            }
        } catch (error) {
            showError('Ошибка подключения');
            console.error('Login error:', error);
        }
    });
}

// Logout
document.getElementById('logout-btn')?.addEventListener('click', async () => {
    try {
        await fetch(`${API_BASE}/logout`, { method: 'POST' });
        showLoginScreen();
    } catch (error) {
        console.error('Logout error:', error);
    }
});

// Check authentication
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/dialogs?limit=1`);
        if (response.ok) {
            showAdminPanel();
            loadDialogs();
            loadUsers();
            loadStatistics();
        } else {
            showLoginScreen();
        }
    } catch (error) {
        showLoginScreen();
    }
}

// UI State
function showLoginScreen() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('admin-panel').classList.add('hidden');
}

function showAdminPanel() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('admin-panel').classList.remove('hidden');
}

function showError(message) {
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = message;
    setTimeout(() => {
        errorEl.textContent = '';
    }, 5000);
}

// Filters
function initFilters() {
    document.getElementById('apply-filters').addEventListener('click', () => {
        applyFilters();
    });
    
    document.getElementById('reset-filters').addEventListener('click', () => {
        resetFilters();
    });
}

function applyFilters() {
    const userFilter = document.getElementById('user-filter');
    const startDate = document.getElementById('start-date');
    const endDate = document.getElementById('end-date');
    const roleFilter = document.getElementById('role-filter');
    
    currentFilters = {
        user_id: userFilter.value ? parseInt(userFilter.value) : null,
        start_date: startDate.value || null,
        end_date: endDate.value || null,
        role: roleFilter.value || null
    };
    
    loadDialogs();
}

function resetFilters() {
    document.getElementById('user-filter').value = '';
    document.getElementById('start-date').value = '';
    document.getElementById('end-date').value = '';
    document.getElementById('role-filter').value = '';
    
    currentFilters = {
        user_id: null,
        start_date: null,
        end_date: null,
        role: null
    };
    
    loadDialogs();
}

// Load users for filter
async function loadUsers() {
    try {
        const response = await fetch(`${API_BASE}/users`);
        if (!response.ok) throw new Error('Failed to load users');
        
        const data = await response.json();
        const userFilter = document.getElementById('user-filter');
        
        // Clear existing options except "All"
        userFilter.innerHTML = '<option value="">Все клиенты</option>';
        
        data.users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.user_id;
            const label = user.full_name || user.phone || user.username || `User ${user.user_id}`;
            option.textContent = `${label} (${user.message_count} сообщений)`;
            userFilter.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

// Load dialogs
async function loadDialogs() {
    const dialogsList = document.getElementById('dialogs-list');
    const loading = document.getElementById('loading');
    const emptyState = document.getElementById('empty-state');
    
    dialogsList.innerHTML = '';
    loading.classList.remove('hidden');
    emptyState.classList.add('hidden');
    
    try {
        const params = new URLSearchParams();
        if (currentFilters.user_id) params.append('user_id', currentFilters.user_id);
        if (currentFilters.start_date) params.append('start_date', currentFilters.start_date);
        if (currentFilters.end_date) params.append('end_date', currentFilters.end_date);
        params.append('limit', '100');
        params.append('offset', '0');
        
        const response = await fetch(`${API_BASE}/dialogs?${params}`);
        if (!response.ok) throw new Error('Failed to load dialogs');
        
        const data = await response.json();
        
        loading.classList.add('hidden');
        
        if (data.messages.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }
        
        // Filter by role if needed
        let messages = data.messages;
        if (currentFilters.role) {
            messages = messages.filter(m => m.role === currentFilters.role);
        }
        
        messages.forEach(message => {
            const messageEl = createMessageElement(message);
            dialogsList.appendChild(messageEl);
        });
    } catch (error) {
        console.error('Error loading dialogs:', error);
        loading.classList.add('hidden');
        emptyState.classList.remove('hidden');
        emptyState.textContent = 'Ошибка загрузки сообщений';
    }
}

// Create message element
function createMessageElement(message) {
    const div = document.createElement('div');
    div.className = `dialog-message ${message.role}`;
    
    const userInfo = message.full_name || message.phone || message.username || `User ${message.user_id}`;
    const roleLabel = message.role === 'user' ? 'Клиент' : 'Бот';
    // Parse UTC datetime and convert to user's local timezone
    const date = new Date(message.created_at);
    // Format in user's local timezone
    const timeStr = date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short' // Shows timezone abbreviation
    });
    
    div.innerHTML = `
        <div class="message-header">
            <div class="message-user-info">
                <strong>${escapeHtml(userInfo)}</strong>
                <span class="message-role ${message.role}">${roleLabel}</span>
            </div>
            <span class="message-time">${timeStr}</span>
        </div>
        <div class="message-text">${escapeHtml(message.message_text)}</div>
    `;
    
    return div;
}

// Load statistics
async function loadStatistics() {
    // Check if elements exist
    const dialogsTodayEl = document.getElementById('stat-dialogs-today');
    const dialogsTotalEl = document.getElementById('stat-dialogs-total');
    const leadsTodayEl = document.getElementById('stat-leads-today');
    const leadsTotalEl = document.getElementById('stat-leads-total');
    
    if (!dialogsTodayEl || !dialogsTotalEl || !leadsTodayEl || !leadsTotalEl) {
        console.warn('Statistics elements not found, skipping load');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/statistics`);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Statistics API error:', response.status, errorText);
            // Set to 0 on error
            dialogsTodayEl.textContent = '0';
            dialogsTotalEl.textContent = '0';
            leadsTodayEl.textContent = '0';
            leadsTotalEl.textContent = '0';
            return;
        }
        
        const data = await response.json();
        console.log('Statistics loaded:', data);
        
        dialogsTodayEl.textContent = data.dialogs_today ?? 0;
        dialogsTotalEl.textContent = data.dialogs_total ?? 0;
        leadsTodayEl.textContent = data.leads_today ?? 0;
        leadsTotalEl.textContent = data.leads_total ?? 0;
    } catch (error) {
        console.error('Error loading statistics:', error);
        // Set to 0 on error
        dialogsTodayEl.textContent = '0';
        dialogsTotalEl.textContent = '0';
        leadsTodayEl.textContent = '0';
        leadsTotalEl.textContent = '0';
    }
}

// Refresh statistics periodically
setInterval(loadStatistics, 60000); // Every minute

// Utility
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


