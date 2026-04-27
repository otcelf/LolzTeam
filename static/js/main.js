// ===== SIDEBAR TOGGLE =====
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('active');
}

// ===== AUTO-HIDE ALERTS =====
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
});

// ===== COPY TO CLIPBOARD =====
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('Скопировано в буфер обмена!', 'success');
        }).catch(err => {
            console.error('Ошибка копирования:', err);
            fallbackCopyToClipboard(text);
        });
    } else {
        fallbackCopyToClipboard(text);
    }
}

function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showNotification('Скопировано в буфер обмена!', 'success');
    } catch (err) {
        console.error('Ошибка копирования:', err);
        showNotification('Не удалось скопировать', 'error');
    }
    
    document.body.removeChild(textArea);
}

// ===== NOTIFICATIONS =====
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.style.animation = 'slideInRight 0.3s ease-out';
    
    const icon = type === 'success' ? 'check-circle' : 
                 type === 'error' ? 'exclamation-circle' : 'info-circle';
    
    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        ${message}
        <button class="close-alert" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// ===== CONFIRM DIALOG =====
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// ===== LOADING SPINNER =====
function showLoading() {
    const loader = document.createElement('div');
    loader.id = 'loading-overlay';
    loader.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 99999;
    `;
    loader.innerHTML = `
        <div style="background: white; padding: 30px; border-radius: 15px; text-align: center;">
            <i class="fas fa-spinner fa-spin" style="font-size: 48px; color: #667eea;"></i>
            <p style="margin-top: 15px; color: #374151; font-weight: 600;">Загрузка...</p>
        </div>
    `;
    document.body.appendChild(loader);
}

function hideLoading() {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
        loader.remove();
    }
}

// ===== TABLE SORTING =====
function sortTable(table, column, asc = true) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aText = a.children[column].textContent.trim();
        const bText = b.children[column].textContent.trim();
        
        return asc ? aText.localeCompare(bText) : bText.localeCompare(aText);
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// ===== SEARCH HIGHLIGHT =====
function highlightSearchResults(searchTerm) {
    if (!searchTerm) return;
    
    const tables = document.querySelectorAll('.table tbody');
    tables.forEach(tbody => {
        const cells = tbody.querySelectorAll('td');
        cells.forEach(cell => {
            const text = cell.textContent;
            if (text.toLowerCase().includes(searchTerm.toLowerCase())) {
                cell.style.backgroundColor = '#fef3c7';
            }
        });
    });
}

// ===== EXPORT TABLE TO CSV =====
function exportTableToCSV(tableId, filename = 'export.csv') {
    const table = document.getElementById(tableId) || document.querySelector('.table');
    if (!table) return;
    
    const rows = table.querySelectorAll('tr');
    const csv = [];
    
    rows.forEach(row => {
        const cols = row.querySelectorAll('td, th');
        const rowData = Array.from(cols).map(col => {
            return '"' + col.textContent.trim().replace(/"/g, '""') + '"';
        });
        csv.push(rowData.join(','));
    });
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ===== REAL-TIME SEARCH =====
function setupRealtimeSearch(inputSelector, tableSelector) {
    const input = document.querySelector(inputSelector);
    const table = document.querySelector(tableSelector);
    
    if (!input || !table) return;
    
    input.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(searchTerm) ? '' : 'none';
        });
    });
}

// ===== STATISTICS COUNTER ANIMATION =====
function animateCounter(element, target, duration = 1000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = Math.round(target);
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, 16);
}

// ===== AUTO-REFRESH DATA =====
let autoRefreshInterval = null;

function startAutoRefresh(interval = 30000) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        location.reload();
    }, interval);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// ===== KEYBOARD SHORTCUTS =====
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K: Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('.search-input');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape: Close modals/alerts
    if (e.key === 'Escape') {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => alert.remove());
    }
});

// ===== FORM VALIDATION =====
function validateForm(formSelector) {
    const form = document.querySelector(formSelector);
    if (!form) return true;
    
    const inputs = form.querySelectorAll('input[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = '#ef4444';
            isValid = false;
        } else {
            input.style.borderColor = '#e5e7eb';
        }
    });
    
    return isValid;
}

// ===== INITIALIZE ON PAGE LOAD =====
document.addEventListener('DOMContentLoaded', function() {
    // Setup realtime search if search input exists
    setupRealtimeSearch('.search-input', '.table');
    
    // Animate counters on statistics page
    const statNumbers = document.querySelectorAll('.stat-info h3');
    statNumbers.forEach(stat => {
        const target = parseInt(stat.textContent.replace(/[^0-9]/g, ''));
        if (!isNaN(target) && target > 0) {
            stat.textContent = '0';
            animateCounter(stat, target);
        }
    });
    
    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
    
    // Close sidebar on mobile when clicking outside
    document.addEventListener('click', function(e) {
        const sidebar = document.querySelector('.sidebar');
        const toggle = document.querySelector('.sidebar-toggle');
        
        if (window.innerWidth <= 1024 && 
            sidebar && 
            sidebar.classList.contains('active') && 
            !sidebar.contains(e.target) && 
            !toggle.contains(e.target)) {
            sidebar.classList.remove('active');
        }
    });
});

// ===== UTILITY FUNCTIONS =====
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

function formatCurrency(amount, currency = 'RUB') {
    const symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'TON': ' TON'
    };
    
    return formatNumber(amount) + (symbols[currency] || ' ' + currency);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    const intervals = {
        'год': 31536000,
        'месяц': 2592000,
        'день': 86400,
        'час': 3600,
        'минута': 60,
        'секунда': 1
    };
    
    for (const [name, value] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / value);
        if (interval >= 1) {
            return `${interval} ${name}${interval > 1 ? (name === 'час' ? 'а' : name === 'день' ? 'я' : 'ы') : ''} назад`;
        }
    }
    
    return 'только что';
}

// ===== EXPORT FUNCTIONS FOR GLOBAL USE =====
window.copyToClipboard = copyToClipboard;
window.showNotification = showNotification;
window.confirmAction = confirmAction;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.exportTableToCSV = exportTableToCSV;
window.formatNumber = formatNumber;
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.timeAgo = timeAgo;
window.toggleSidebar = toggleSidebar;
