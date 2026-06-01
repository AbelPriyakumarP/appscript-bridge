/* ============================================
   EventBridge — Core JavaScript
   ============================================ */

// ── API Helper ──
const api = {
    async request(method, url, data = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (data) opts.body = JSON.stringify(data);
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: resp.statusText }));
            throw new Error(err.error || resp.statusText);
        }
        return resp.json();
    },
    get(url) { return this.request('GET', url); },
    post(url, data) { return this.request('POST', url, data); },
    put(url, data) { return this.request('PUT', url, data); },
    delete(url) { return this.request('DELETE', url); },
};

// ── Toast Notifications ──
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const icon = type === 'error' ? 'bi-exclamation-circle' : 'bi-check-circle';
    const toast = document.createElement('div');
    toast.className = `toast-custom ${type}`;
    toast.innerHTML = `<i class="bi ${icon}"></i> ${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Delete Confirmation ──
let _deleteCallback = null;

function confirmDelete(message, callback) {
    document.getElementById('deleteMessage').textContent = message;
    _deleteCallback = callback;
    new bootstrap.Modal(document.getElementById('deleteModal')).show();
}

document.addEventListener('DOMContentLoaded', () => {
    const deleteBtn = document.getElementById('deleteConfirmBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            if (_deleteCallback) {
                try {
                    await _deleteCallback();
                } catch (e) {
                    showToast(e.message, 'error');
                }
            }
            bootstrap.Modal.getInstance(document.getElementById('deleteModal'))?.hide();
            _deleteCallback = null;
        });
    }
});

// ── Utilities ──
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function timeAgo(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    return date.toLocaleDateString();
}

// ── Sidebar Toggle (Mobile) ──
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('show');
}
