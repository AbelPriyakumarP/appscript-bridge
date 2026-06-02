/* ============================================
   AppScript Bridge — Core JavaScript
   ============================================ */

// ── Theme ──
(function () {
    const saved = localStorage.getItem('asb-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next    = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('asb-theme', next);
    _updateThemeBtn(next);
}

function _updateThemeBtn(theme) {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    if (theme === 'dark') {
        btn.innerHTML = '<i class="bi bi-sun"></i>';
        btn.title = 'Switch to light mode';
    } else {
        btn.innerHTML = '<i class="bi bi-moon-stars-fill"></i>';
        btn.title = 'Switch to dark mode';
    }
}

// ── API Helper ──
const api = {
    async request(method, url, data = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (data) opts.body = JSON.stringify(data);
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || resp.statusText);
        }
        return resp.json();
    },
    get(url)           { return this.request('GET',    url); },
    post(url, data)    { return this.request('POST',   url, data); },
    put(url, data)     { return this.request('PUT',    url, data); },
    delete(url)        { return this.request('DELETE', url); },
};

// ── Toast ──
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const icon = type === 'error' ? 'bi-exclamation-circle' : 'bi-check-circle-fill';
    const toast = document.createElement('div');
    toast.className = `toast-custom ${type}`;
    toast.innerHTML = `<i class="bi ${icon}"></i> ${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.25s ease';
        setTimeout(() => toast.remove(), 260);
    }, 3000);
}

// ── Delete Confirmation ──
let _deleteCallback = null;

function confirmDelete(message, callback) {
    document.getElementById('deleteMessage').textContent = message;
    _deleteCallback = callback;
    new bootstrap.Modal(document.getElementById('deleteModal')).show();
}

// ── Utilities ──
function escapeHtml(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function timeAgo(dateString) {
    if (!dateString) return 'Never';
    const date    = new Date(dateString);
    const seconds = Math.floor((Date.now() - date) / 1000);
    if (seconds < 60)     return 'Just now';
    if (seconds < 3600)   return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400)  return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('show');
}

// ── DOMContentLoaded ──
document.addEventListener('DOMContentLoaded', () => {
    // Sync theme button icon on every page load
    _updateThemeBtn(document.documentElement.getAttribute('data-theme') || 'dark');

    // Delete modal confirm
    const deleteBtn = document.getElementById('deleteConfirmBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            if (_deleteCallback) {
                try { await _deleteCallback(); }
                catch (e) { showToast(e.message, 'error'); }
            }
            bootstrap.Modal.getInstance(document.getElementById('deleteModal'))?.hide();
            _deleteCallback = null;
        });
    }
});
