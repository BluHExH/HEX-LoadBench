/**
 * HEX-LoadBench Frontend Application
 * Handles the dashboard UI, API communication, and real-time updates
 */

// Configuration
const CONFIG = {
    API_BASE_URL: process.env.API_URL || 'http://localhost:8000',
    AUTH_BASE_URL: process.env.AUTH_URL || 'http://localhost:8080',
    WS_URL: process.env.WS_URL || 'ws://localhost:9000',
    REFRESH_INTERVAL: 30000, // 30 seconds
    CHART_COLORS: {
        primary: '#2563eb',
        success: '#22c55e',
        danger: '#ef4444',
        warning: '#f59e0b',
        info: '#06b6d4'
    }
};

// Application State
class AppState {
    constructor() {
        this.currentUser = null;
        this.token = localStorage.getItem('hex_token');
        this.tests = [];
        this.results = [];
        this.activeExecutions = [];
        this.currentPage = 'dashboard';
        this.chart = null;
        this.socket = null;
    }

    isAuthenticated() {
        return this.token !== null;
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('hex_token', token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('hex_token');
    }
}

const app = new AppState();

// API Client
class ApiClient {
    constructor() {
        this.baseUrl = CONFIG.API_BASE_URL;
        this.token = app.token;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}/api/v1${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (this.token) {
            config.headers.Authorization = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, config);
            
            if (response.status === 401) {
                app.clearToken();
                window.location.reload();
                return;
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || data.message || 'API request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

const api = new ApiClient();

// UI Utilities
class UI {
    static showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div class="text-center" style="padding: 2rem;">
                    <div class="spinner" style="margin: 0 auto 1rem;"></div>
                    <p style="color: var(--gray-500);">Loading...</p>
                </div>
            `;
        }
    }

    static showAlert(message, type = 'info') {
        const alertHtml = `
            <div class="alert alert-${type}">
                <i class="fas fa-${this.getAlertIcon(type)}"></i>
                <span>${message}</span>
                <button class="btn btn-ghost btn-sm" onclick="this.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        const container = document.querySelector('.main-content .container');
        container.insertAdjacentHTML('afterbegin', alertHtml);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) alert.remove();
        }, 5000);
    }

    static getAlertIcon(type) {
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    static formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    static formatDuration(seconds) {
        if (seconds < 60) {
            return `${seconds}s`;
        }
        if (seconds < 3600) {
            return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        }
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    static formatDate(dateString) {
        return new Date(dateString).toLocaleString();
    }
}

// Chart Management
class ChartManager {
    static initializePerformanceChart() {
        const ctx = document.getElementById('performanceChart');
        if (!ctx) return;

        app.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Response Time (ms)',
                        data: [],
                        borderColor: CONFIG.CHART_COLORS.primary,
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'RPS',
                        data: [],
                        borderColor: CONFIG.CHART_COLORS.success,
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Response Time (ms)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'RPS'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    static updatePerformanceChart(data) {
        if (!app.chart) return;

        const labels = data.map((_, index) => `${index}`);
        const responseTimes = data.map(d => d.response_time_avg || 0);
        const rpsValues = data.map(d => d.requests_per_second || 0);

        app.chart.data.labels = labels;
        app.chart.data.datasets[0].data = responseTimes;
        app.chart.data.datasets[1].data = rpsValues;
        app.chart.update();
    }
}

// Page Navigation
function navigateTo(pageName) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.style.display = 'none';
    });

    // Show selected page
    const selectedPage = document.getElementById(`${pageName}-page`);
    if (selectedPage) {
        selectedPage.style.display = 'block';
    }

    // Update navigation
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-page="${pageName}"]`).classList.add('active');

    app.currentPage = pageName;

    // Load page-specific data
    loadPageData(pageName);
}

// Load page-specific data
async function loadPageData(pageName) {
    try {
        switch (pageName) {
            case 'dashboard':
                await loadDashboardData();
                break;
            case 'tests':
                await loadTests();
                break;
            case 'results':
                await loadResults();
                break;
            case 'settings':
                await loadSettings();
                break;
        }
    } catch (error) {
        UI.showAlert(`Failed to load ${pageName} data: ${error.message}`, 'danger');
    }
}

// Dashboard Functions
async function loadDashboardData() {
    try {
        // Load dashboard stats
        const tests = await api.get('/tests');
        const stats = calculateTestStats(tests);

        // Update stats cards
        document.getElementById('totalTests').textContent = UI.formatNumber(stats.total);
        document.getElementById('runningTests').textContent = UI.formatNumber(stats.running);
        document.getElementById('failedTests').textContent = UI.formatNumber(stats.failed);
        document.getElementById('currentRPS').textContent = UI.formatNumber(stats.currentRPS);

        // Load recent tests
        loadRecentTests(tests);

        // Initialize performance chart
        ChartManager.initializePerformanceChart();

    } catch (error) {
        console.error('Dashboard load error:', error);
    }
}

function calculateTestStats(tests) {
    const stats = {
        total: tests.length,
        running: tests.filter(t => t.status === 'running').length,
        failed: tests.filter(t => t.status === 'failed').length,
        currentRPS: 0 // This would come from real-time metrics
    };

    return stats;
}

function loadRecentTests(tests) {
    const container = document.getElementById('recentTestsList');
    const recentTests = tests.slice(0, 5);

    if (recentTests.length === 0) {
        container.innerHTML = '<p style="color: var(--gray-500); text-align: center; padding: 2rem;">No recent tests</p>';
        return;
    }

    const testsHtml = recentTests.map(test => `
        <div class="test-card status-${test.status}" style="margin-bottom: 1rem;">
            <div class="test-card-header">
                <h4 class="test-card-title">${test.name}</h4>
                <span class="badge badge-${getStatusBadgeClass(test.status)}">${test.status}</span>
            </div>
            <div class="test-card-body">
                <p style="margin: 0; font-size: 0.875rem;">${test.description || 'No description'}</p>
            </div>
            <div class="test-card-footer">
                <div class="test-card-meta">
                    <span><i class="fas fa-clock"></i> ${UI.formatDate(test.created_at)}</span>
                    <span><i class="fas fa-users"></i> ${test.max_concurrent_users} users</span>
                </div>
                <div class="test-card-actions">
                    ${getTestActionButtons(test)}
                </div>
            </div>
        </div>
    `).join('');

    container.innerHTML = testsHtml;
}

function getStatusBadgeClass(status) {
    const statusMap = {
        'running': 'success',
        'completed': 'primary',
        'failed': 'danger',
        'draft': 'gray',
        'scheduled': 'info'
    };
    return statusMap[status] || 'gray';
}

function getTestActionButtons(test) {
    if (test.status === 'running') {
        return `
            <button class="btn btn-sm btn-danger" onclick="stopTest(${test.id})">
                <i class="fas fa-stop"></i> Stop
            </button>
        `;
    } else if (test.status === 'draft' || test.status === 'failed' || test.status === 'completed') {
        return `
            <button class="btn btn-sm btn-primary" onclick="startTest(${test.id})">
                <i class="fas fa-play"></i> Start
            </button>
            <button class="btn btn-sm btn-outline" onclick="viewTestResults(${test.id})">
                <i class="fas fa-chart-line"></i> Results
            </button>
        `;
    }
    return '';
}

// Tests Management
async function loadTests() {
    UI.showLoading('testsList');

    try {
        const tests = await api.get('/tests');
        app.tests = tests;
        renderTestsList(tests);
    } catch (error) {
        document.getElementById('testsList').innerHTML = `
            <div class="text-center" style="padding: 2rem;">
                <i class="fas fa-exclamation-triangle" style="color: var(--danger-color); font-size: 2rem; margin-bottom: 1rem;"></i>
                <p style="color: var(--gray-500);">Failed to load tests: ${error.message}</p>
            </div>
        `;
    }
}

function renderTestsList(tests) {
    const container = document.getElementById('testsList');

    if (tests.length === 0) {
        container.innerHTML = `
            <div class="text-center" style="padding: 3rem;">
                <i class="fas fa-flask" style="color: var(--gray-400); font-size: 3rem; margin-bottom: 1rem;"></i>
                <h3 style="color: var(--gray-600); margin-bottom: 0.5rem;">No Tests Found</h3>
                <p style="color: var(--gray-500);">Create your first load test to get started</p>
                <button class="btn btn-primary" onclick="showCreateTestModal()">
                    <i class="fas fa-plus"></i> Create Test
                </button>
            </div>
        `;
        return;
    }

    const testsHtml = tests.map(test => `
        <div class="test-card status-${test.status}" style="margin-bottom: 1rem;">
            <div class="test-card-header">
                <h4 class="test-card-title">${test.name}</h4>
                <span class="badge badge-${getStatusBadgeClass(test.status)}">${test.status}</span>
            </div>
            <div class="test-card-body">
                <p style="margin: 0; color: var(--gray-600); font-size: 0.875rem;">${test.description || 'No description'}</p>
                <div class="test-card-meta" style="margin-top: 0.5rem;">
                    <span><i class="fas fa-globe"></i> ${test.target_url}</span>
                    <span><i class="fas fa-users"></i> ${test.max_concurrent_users} users</span>
                    <span><i class="fas fa-clock"></i> ${UI.formatDuration(test.duration)}</span>
                    <span><i class="fas fa-tachometer-alt"></i> ${test.rps_limit} RPS</span>
                </div>
            </div>
            <div class="test-card-footer">
                <span style="font-size: 0.75rem; color: var(--gray-500);">
                    Created ${UI.formatDate(test.created_at)}
                </span>
                <div class="test-card-actions">
                    ${getTestActionButtons(test)}
                    <button class="btn btn-sm btn-outline" onclick="editTest(${test.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="deleteTest(${test.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    container.innerHTML = testsHtml;
}

// Test Actions
async function startTest(testId) {
    try {
        await api.post(`/tests/${testId}/start`);
        UI.showAlert('Test started successfully', 'success');
        loadDashboardData();
        if (app.currentPage === 'tests') {
            loadTests();
        }
    } catch (error) {
        UI.showAlert(`Failed to start test: ${error.message}`, 'danger');
    }
}

async function stopTest(testId) {
    try {
        await api.post(`/tests/${testId}/stop`, { reason: 'Manual stop' });
        UI.showAlert('Test stopped successfully', 'success');
        loadDashboardData();
        if (app.currentPage === 'tests') {
            loadTests();
        }
    } catch (error) {
        UI.showAlert(`Failed to stop test: ${error.message}`, 'danger');
    }
}

// Modal Functions
function showCreateTestModal() {
    const modal = document.getElementById('createTestModal');
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('show'), 10);
}

function hideCreateTestModal() {
    const modal = document.getElementById('createTestModal');
    modal.classList.remove('show');
    setTimeout(() => modal.style.display = 'none', 300);
}

// Create Test
async function createTest() {
    const form = document.getElementById('createTestForm');
    const formData = new FormData(form);
    
    const testData = {
        name: formData.get('name'),
        description: formData.get('description'),
        target_url: formData.get('target_url'),
        method: formData.get('method'),
        load_profile_type: formData.get('load_profile_type'),
        load_profile_config: getDefaultProfileConfig(formData.get('load_profile_type')),
        max_concurrent_users: parseInt(formData.get('max_concurrent_users')),
        duration: parseInt(formData.get('duration')),
        rps_limit: parseInt(formData.get('rps_limit')),
        region: formData.get('region')
    };

    try {
        await api.post('/tests', testData);
        UI.showAlert('Test created successfully', 'success');
        hideCreateTestModal();
        form.reset();
        navigateTo('tests');
    } catch (error) {
        UI.showAlert(`Failed to create test: ${error.message}`, 'danger');
    }
}

function getDefaultProfileConfig(profileType) {
    const configs = {
        'ramp_up': {
            initial_users: 1,
            target_users: 100,
            ramp_duration: 300,
            hold_duration: 600
        },
        'steady_state': {
            concurrent_users: 100,
            duration: 600
        },
        'spike': {
            baseline_users: 10,
            spike_users: 1000,
            spike_duration: 60,
            baseline_duration: 300
        },
        'soak': {
            concurrent_users: 50,
            duration: 86400
        }
    };
    return configs[profileType] || {};
}

// Results Management
async function loadResults() {
    UI.showLoading('resultsContent');
    // Implementation would load test results
}

async function loadSettings() {
    try {
        const user = await api.get('/users/me');
        app.currentUser = user;
        
        // Update user info in UI
        document.getElementById('userName').textContent = user.full_name || user.username;
        document.getElementById('fullName').value = user.full_name || '';
        document.getElementById('email').value = user.email;
        
        // Load API keys
        loadApiKeys();
    } catch (error) {
        console.error('Settings load error:', error);
    }
}

async function loadApiKeys() {
    try {
        const apiKeys = await api.get('/users/api-keys');
        renderApiKeysList(apiKeys);
    } catch (error) {
        document.getElementById('apiKeysList').innerHTML = 
            '<p style="color: var(--gray-500); text-align: center;">Failed to load API keys</p>';
    }
}

function renderApiKeysList(apiKeys) {
    const container = document.getElementById('apiKeysList');
    
    if (apiKeys.length === 0) {
        container.innerHTML = '<p style="color: var(--gray-500); text-align: center;">No API keys</p>';
        return;
    }

    const keysHtml = apiKeys.map(key => `
        <div style="padding: 0.75rem; border: 1px solid var(--gray-200); border-radius: var(--radius-md); margin-bottom: 0.5rem;">
            <div class="flex justify-between items-center">
                <div>
                    <div style="font-weight: 500; color: var(--gray-900);">${key.name}</div>
                    <div style="font-size: 0.75rem; color: var(--gray-500);">Created ${UI.formatDate(key.created_at)}</div>
                    <div style="font-size: 0.75rem; color: var(--gray-500);">Last used ${key.last_used ? UI.formatDate(key.last_used) : 'Never'}</div>
                </div>
                <button class="btn btn-sm btn-outline" onclick="deleteApiKey('${key.key_id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');

    container.innerHTML = keysHtml;
}

// Authentication
async function authenticate() {
    if (!app.token) {
        // Redirect to login or show login modal
        return;
    }

    try {
        const user = await api.get('/users/me');
        app.currentUser = user;
        document.getElementById('userName').textContent = user.full_name || user.username;
    } catch (error) {
        console.error('Authentication error:', error);
        app.clearToken();
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize navigation
    document.querySelectorAll('.nav-link[data-page]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo(this.dataset.page);
        });
    });

    // Form submissions
    document.getElementById('createTestForm')?.addEventListener('submit', function(e) {
        e.preventDefault();
        createTest();
    });

    document.getElementById('accountSettingsForm')?.addEventListener('submit', function(e) {
        e.preventDefault();
        // Handle account settings update
    });

    // Initialize application
    initializeApp();
});

async function initializeApp() {
    try {
        // Authenticate user
        await authenticate();
        
        // Load initial page
        navigateTo('dashboard');
        
        // Set up periodic updates
        setInterval(() => {
            if (app.currentPage === 'dashboard') {
                loadDashboardData();
            }
        }, CONFIG.REFRESH_INTERVAL);
        
    } catch (error) {
        console.error('App initialization error:', error);
        UI.showAlert('Failed to initialize application', 'danger');
    }
}

// Export for global access
window.navigateTo = navigateTo;
window.showCreateTestModal = showCreateTestModal;
window.hideCreateTestModal = hideCreateTestModal;
window.createTest = createTest;
window.startTest = startTest;
window.stopTest = stopTest;