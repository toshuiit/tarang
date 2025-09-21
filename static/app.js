// JavaScript for Tarang Web Application - Optimized for Performance

// Initialize Socket.IO connection with optimized settings
let socket;
let currentProcessId = null;

// Initialize socket connection only when needed
function initializeSocket() {
    if (!socket) {
        socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            rememberUpgrade: true
        });
        setupSocketHandlers();
    }
    return socket;
}

// Setup socket event handlers
function setupSocketHandlers() {
    // Connection event handlers
    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus(true);
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });

    // Simulation event handlers
    socket.on('simulation_output', function(data) {
        if (data.process_id === currentProcessId) {
            appendOutput(data.output);
        }
    });

    socket.on('simulation_complete', function(data) {
        if (data.process_id === currentProcessId) {
            updateStatus('completed', 'Simulation completed successfully!');
            enableStartButton();
            showNotification('Simulation completed!', 'success');
        }
    });

    socket.on('simulation_error', function(data) {
        if (data.process_id === currentProcessId) {
            updateStatus('error', 'Simulation error: ' + data.error);
            enableStartButton();
            showNotification('Simulation error: ' + data.error, 'error');
        }
    });
}

// Utility functions
function updateConnectionStatus(connected) {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
        statusElement.className = connected ? 'text-success' : 'text-danger';
        statusElement.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

function updateStatus(status, message) {
    const statusElement = document.getElementById('status');
    if (statusElement) {
        statusElement.className = 'status-' + status;
        statusElement.textContent = message;
    }
}

function clearOutput() {
    const outputDiv = document.getElementById('output-content');
    if (outputDiv) {
        outputDiv.innerHTML = '';
    }
}

// Optimized output appending with batching for better performance
let outputBuffer = [];
let outputTimeout = null;

function appendOutput(text) {
    outputBuffer.push(text);
    
    // Batch DOM updates for better performance
    if (outputTimeout) {
        clearTimeout(outputTimeout);
    }
    
    outputTimeout = setTimeout(() => {
        flushOutputBuffer();
    }, 16); // ~60fps
}

function flushOutputBuffer() {
    const outputDiv = document.getElementById('output-content');
    if (outputDiv && outputBuffer.length > 0) {
        const fragment = document.createDocumentFragment();
        
        outputBuffer.forEach(text => {
            const line = document.createElement('div');
            line.textContent = text;
            fragment.appendChild(line);
        });
        
        outputDiv.appendChild(fragment);
        outputDiv.scrollTop = outputDiv.scrollHeight;
        outputBuffer = [];
    }
}

function enableStartButton() {
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
}

function disableStartButton() {
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;
}

function showNotification(message, type = 'info') {
    const alertClass = type === 'success' ? 'alert-success' : 
                      type === 'error' ? 'alert-danger' : 'alert-info';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Optimized simulation control functions
function startSimulation() {
    // Initialize socket connection if needed
    initializeSocket();
    
    // Use AbortController for request cancellation
    const controller = new AbortController();
    
    fetch('/start_simulation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        signal: controller.signal
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            currentProcessId = data.process_id;
            updateStatus('running', 'Simulation started...');
            clearOutput();
            appendOutput('Starting simulation with Process ID: ' + data.process_id);
            appendOutput('='.repeat(50));
            disableStartButton();
            showNotification('Simulation started successfully!', 'success');
        } else {
            updateStatus('error', 'Failed to start simulation: ' + data.error);
            showNotification('Failed to start simulation: ' + data.error, 'error');
        }
    })
    .catch(error => {
        if (error.name !== 'AbortError') {
            updateStatus('error', 'Error: ' + error.message);
            showNotification('Network error: ' + error.message, 'error');
        }
    });
}

function stopSimulation() {
    if (currentProcessId) {
        fetch('/kill_process/' + currentProcessId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatus('stopped', 'Simulation stopped by user');
                enableStartButton();
                showNotification('Simulation stopped successfully', 'info');
            } else {
                showNotification('Failed to stop simulation: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Stop simulation error:', error);
            showNotification('Connection error while stopping simulation. Please try again.', 'error');
        });
    }
}

// Form validation and enhancement
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;
    
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Grid dimension handlers
function updateGridFields() {
    const dimension = document.getElementById('dimension');
    if (!dimension) return;
    
    const nx = document.getElementById('nx');
    const ny = document.getElementById('ny');
    const nz = document.getElementById('nz');
    
    if (!nx || !ny || !nz) return;
    
    const dimValue = dimension.value;
    
    if (dimValue === '1') {
        nx.value = '1';
        ny.value = '1';
        nx.disabled = true;
        ny.disabled = true;
        nz.disabled = false;
    } else if (dimValue === '2') {
        nx.value = '64';
        ny.value = '1';
        nx.disabled = false;
        ny.disabled = true;
        nz.disabled = false;
    } else {
        nx.value = '64';
        ny.value = '64';
        nx.disabled = false;
        ny.disabled = false;
        nz.disabled = false;
    }
}

// File browser simulation (for demo purposes)
function browseFiles(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    // Simulate file browser
    const path = prompt('Enter path (or leave empty for default):');
    if (path !== null) {
        input.value = path || '/tmp/simulation_data';
    }
}

// Progress tracking
function updateProgress(percentage) {
    const progressBar = document.getElementById('progress-bar');
    if (progressBar) {
        progressBar.style.width = percentage + '%';
        progressBar.setAttribute('aria-valuenow', percentage);
        progressBar.textContent = Math.round(percentage) + '%';
    }
}

// Optimized page initialization
document.addEventListener('DOMContentLoaded', function() {
    // Use requestAnimationFrame for better performance
    requestAnimationFrame(() => {
        initializePageElements();
    });
});

function initializePageElements() {
    // Add fade-in class to cards immediately (no animation delays)
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.classList.add('fade-in');
    });
    
    // Initialize tooltips only if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipTriggerList.forEach(tooltipTriggerEl => {
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Add optimized form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });
    
    // Initialize dimension change handler
    const dimensionSelect = document.getElementById('dimension');
    if (dimensionSelect) {
        dimensionSelect.addEventListener('change', updateGridFields);
        updateGridFields(); // Initialize on load
    }
}

function handleFormSubmit(e) {
    const form = e.target;
    if (!form.checkValidity()) {
        e.preventDefault();
        e.stopPropagation();
    }
    form.classList.add('was-validated');
}

// Export functions for global access
window.startSimulation = startSimulation;
window.stopSimulation = stopSimulation;
window.updateGridFields = updateGridFields;
window.browseFiles = browseFiles;
