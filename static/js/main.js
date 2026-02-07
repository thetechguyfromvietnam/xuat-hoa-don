// API endpoints
const API_BASE = '';

// State
let statusInterval = null;
let logInterval = null;
let fetchInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    refreshStatus();
    startPolling();
    // Tự động load và hiển thị kết quả kiểm tra hóa đơn
    loadCheckResults();
    // Tự động load và hiển thị hóa đơn bia/rượu
    loadBeverageInvoices();
    // Tự động refresh hóa đơn bia/rượu mỗi 10 giây
    setInterval(loadBeverageInvoices, 10000);
});

// Start polling for status and logs
function startPolling() {
    if (!statusInterval) {
        statusInterval = setInterval(() => {
            refreshStatus();
        }, 2000);
    }
    if (!logInterval) {
        logInterval = setInterval(() => {
            updateLogs();
        }, 1000);
    }
    // Update immediately
    refreshStatus();
    updateLogs();
}

// Stop polling
function stopPolling() {
    if (statusInterval) {
        clearInterval(statusInterval);
        statusInterval = null;
    }
    if (logInterval) {
        clearInterval(logInterval);
        logInterval = null;
    }
}

// Refresh status
async function refreshStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();
        
        document.getElementById('data-files-count').textContent = data.data_files || 0;
        document.getElementById('tax-files-count').textContent = data.tax_files || 0;
        
        // Update script status
        const statusEl = document.getElementById('script-status');
        const btnStart = document.getElementById('btn-start');
        
        if (data.running) {
            statusEl.textContent = 'Đang chạy';
            statusEl.style.color = '#10b981';
            statusEl.style.fontSize = '1.2rem';
            btnStart.disabled = true;
            const activityEl = document.getElementById('activity');
            if (activityEl && data.current) {
                activityEl.textContent = '📌 ' + data.current;
            }
        } else {
            statusEl.textContent = 'Đang dừng';
            statusEl.style.color = '#ef4444';
            statusEl.style.fontSize = '1.2rem';
            btnStart.disabled = false;
            const activityEl = document.getElementById('activity');
            if (activityEl) {
                activityEl.textContent = '';
            }
        }
    } catch (error) {
        console.error('Error refreshing status:', error);
    }
}

// Update logs
function updateLogs() {
    fetch(`${API_BASE}/api/logs`)
        .then(res => res.json())
        .then(data => {
            const logPanel = document.getElementById('log-panel');
            if (data.logs && data.logs.length > 0) {
                logPanel.innerHTML = data.logs.map(log => 
                    `<div class="log-entry">${escapeHtml(log)}</div>`
                ).join('');
                logPanel.scrollTop = logPanel.scrollHeight;
            }
        })
        .catch(err => console.error('Error updating logs:', err));
}

// Start script
async function startScript() {
    const btn = document.getElementById('btn-start');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang khởi động...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/start`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            startPolling();
        } else {
            alert('❌ Lỗi: ' + (data.error || 'Unknown error'));
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">▶️</span><span class="btn-text">Bắt đầu Upload</span>';
        }
    } catch (error) {
        alert('❌ Lỗi kết nối: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">▶️</span><span class="btn-text">Bắt đầu Upload</span>';
    }
}

// Reset software
async function resetSoftware() {
    if (!confirm('⚠️ Bạn có chắc chắn muốn reset lại phần mềm?\n\nĐiều này sẽ:\n- Dừng tất cả các quá trình đang chạy\n- Xóa tất cả logs\n- Reset trạng thái về ban đầu')) {
        return;
    }
    
    const btn = document.getElementById('btn-reset');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang reset...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/reset`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            // Clear log panel
            const logPanel = document.getElementById('log-panel');
            logPanel.innerHTML = '<div class="log-entry">✅ Đã reset lại phần mềm thành công</div>';
            
            // Refresh status
            refreshStatus();
            
            // Stop polling and restart
            stopPolling();
            setTimeout(() => {
                startPolling();
            }, 500);
            
            alert('✅ Đã reset lại phần mềm thành công!');
        } else {
            alert('❌ Lỗi: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('❌ Lỗi kết nối: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🔄</span><span class="btn-text">Reset lại phần mềm</span>';
    }
}

// Process default
async function processDefault() {
    const btn = document.getElementById('btn-process');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang xử lý...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/process-default`, { method: 'POST' });
        const data = await response.json();
        
        const logPanel = document.getElementById('log-panel');
        if (data.success) {
            const files = (data.files || []).map(f => `- ${f}`).join('\n');
            const msg = `✅ Đã tạo ${data.created} file trong tax_files\n${files}`;
            const logs = (data.logs || []).join('\n');
            logPanel.innerHTML = `<div class="log-entry">${escapeHtml(msg)}</div>` +
                (logs ? `<div class="log-entry">${escapeHtml(logs)}</div>` : '');
            logPanel.scrollTop = logPanel.scrollHeight;
            refreshStatus();
            
            // Hiển thị loading trong phần hóa đơn bia/rượu
            const beverageDisplay = document.getElementById('beverage-invoices-display');
            if (beverageDisplay) {
                beverageDisplay.innerHTML = '<div class="loading">🔄 Đang cập nhật thông tin hóa đơn bia/rượu...</div>';
            }
            
            // Tự động cập nhật phần hiển thị hóa đơn bia/rượu
            setTimeout(() => {
                loadBeverageInvoices();
            }, 1500);
        } else {
            logPanel.innerHTML = `<div class="log-entry">❌ Lỗi: ${escapeHtml(data.error || 'Unknown')}</div>`;
        }
    } catch (error) {
        alert('❌ Lỗi xử lý: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Fetch data
async function fetchData() {
    if (fetchInterval) {
        alert('⚠️ Đang chạy lấy dữ liệu, vui lòng chờ.');
        return;
    }

    const btn = document.getElementById('btn-fetch');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang khởi động...</span>';

    try {
        const response = await fetch(`${API_BASE}/api/fetch-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ headless: false })
        });
        
        const data = await response.json();
        
        if (data.success) {
            startFetchPolling();
        } else {
            alert('❌ Lỗi: ' + (data.error || 'Unknown error'));
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (error) {
        alert('❌ Lỗi kết nối: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

function startFetchPolling() {
    if (fetchInterval) {
        return;
    }
    updateFetchStatus();
    fetchInterval = setInterval(updateFetchStatus, 1000);
    const btn = document.getElementById('btn-fetch');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang lấy dữ liệu...</span>';
}

function stopFetchPolling() {
    if (fetchInterval) {
        clearInterval(fetchInterval);
        fetchInterval = null;
    }
}

function updateFetchStatus() {
    fetch(`${API_BASE}/api/fetch-status`)
        .then(res => res.json())
        .then(data => {
            const logPanel = document.getElementById('log-panel');
            if (data.logs && data.logs.length) {
                logPanel.innerHTML = data.logs.map(line => 
                    `<div class="log-entry">${escapeHtml(line)}</div>`
                ).join('');
                logPanel.scrollTop = logPanel.scrollHeight;
            }

            if (!data.running) {
                stopFetchPolling();
                const btn = document.getElementById('btn-fetch');
                btn.disabled = false;
                btn.innerHTML = '<span class="btn-icon">📥</span><span class="btn-text">Lấy dữ liệu Fabi</span>';
                if (typeof data.exit_code !== 'undefined' && data.exit_code !== null) {
                    if (data.exit_code === 0) {
                        alert('✅ Đã tải dữ liệu Fabi xong!');
                    } else {
                        alert('⚠️ Fetch kết thúc với mã lỗi ' + data.exit_code);
                    }
                }
            }
        })
        .catch(err => {
            console.error('Error updating fetch status:', err);
        });
}

// Clear files
async function clearFiles() {
    if (!confirm('⚠️ Bạn có chắc muốn xóa TẤT CẢ files .xlsx trong tax_files/?\n\nHành động này không thể hoàn tác!')) {
        return;
    }
    
    const btn = document.getElementById('btn-clear-files');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang xóa...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/clear-files`, { method: 'POST' });
        const data = await response.json();
        
        const logPanel = document.getElementById('log-panel');
        if (data.success) {
            const filesList = (data.files || []).map(f => `- ${f}`).join('\n');
            const message = `✅ Đã xóa ${data.deleted_count} file(s):\n${filesList}`;
            logPanel.innerHTML = `<div class="log-entry">${escapeHtml(message)}</div>`;
            logPanel.scrollTop = logPanel.scrollHeight;
            refreshStatus();
        } else {
            logPanel.innerHTML = `<div class="log-entry">❌ Lỗi: ${escapeHtml(data.error || 'Unknown error')}</div>`;
        }
    } catch (error) {
        alert('❌ Lỗi kết nối: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🗑️</span><span class="btn-text">Xóa files đã tạo</span>';
    }
}

// Clear data files
async function clearDataFiles() {
    if (!confirm('⚠️ Bạn có chắc muốn xóa TẤT CẢ files trong thư mục data/?\n\nHành động này không thể hoàn tác!')) {
        return;
    }
    
    const btn = document.getElementById('btn-clear-data');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang xóa...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/clear-data-files`, { method: 'POST' });
        const data = await response.json();
        
        const logPanel = document.getElementById('log-panel');
        if (data.success) {
            const filesList = (data.files || []).map(f => `- ${f}`).join('\n');
            const message = `✅ Đã xóa ${data.deleted_count} file(s) trong data/:\n${filesList}`;
            logPanel.innerHTML = `<div class="log-entry">${escapeHtml(message)}</div>`;
            logPanel.scrollTop = logPanel.scrollHeight;
            refreshStatus();
        } else {
            logPanel.innerHTML = `<div class="log-entry">❌ Lỗi: ${escapeHtml(data.error || 'Unknown error')}</div>`;
        }
    } catch (error) {
        alert('❌ Lỗi kết nối: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🗑️</span><span class="btn-text">Xóa files trong data</span>';
    }
}

// Thay 5 hóa đơn bia/rượu (Sapporo, Tiger, Coke) – tổng 10% = tổng gốc 8%, chỉ chỉnh món cuối
async function runBeverageReplace() {
    const btn = document.getElementById('btn-beverage-replace');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang thay thế...</span>';

    try {
        const response = await fetch(`${API_BASE}/api/beverage-replace`, { method: 'POST' });
        const data = await response.json();
        const logPanel = document.getElementById('log-panel');

        if (data.success) {
            const entries = (data.log_lines || []).map(l => `<div class="log-entry">${escapeHtml(l)}</div>`).join('');
            logPanel.innerHTML = `<div class="log-entry">🍺 Đã thay 5 hóa đơn bia/rượu</div>${entries}`;
            logPanel.scrollTop = logPanel.scrollHeight;
            refreshStatus();
            if (data.replaced && data.replaced.length) {
                setTimeout(() => loadBeverageInvoices(), 1500);
            }
        } else {
            logPanel.innerHTML = `<div class="log-entry">❌ ${escapeHtml(data.error || 'Lỗi')}</div>`;
        }
    } catch (error) {
        const logPanel = document.getElementById('log-panel');
        logPanel.innerHTML = `<div class="log-entry">❌ Lỗi: ${escapeHtml(error.message)}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Check invoices
async function checkInvoices() {
    const btn = document.getElementById('btn-check');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang kiểm tra...</span>';
    
    try {
        const response = await fetch(`${API_BASE}/api/check-invoices`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Lỗi khi kiểm tra hóa đơn');
        }
        
        // Hiển thị kết quả
        displayCheckResults(data.results);
        
        // Cập nhật section luôn hiển thị
        if (data.results && data.results.invoices_with_beverages) {
            displayBeverageInvoices(data.results.invoices_with_beverages);
        }
        
        // Tự động scroll đến phần kết quả
        const section = document.getElementById('check-results-section');
        if (section) {
            setTimeout(() => {
                section.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
        }
        
    } catch (error) {
        alert('❌ Lỗi: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🔍</span><span class="btn-text">Kiểm Tra Hóa Đơn</span>';
    }
}

// Display check results
function displayCheckResults(results) {
    const section = document.getElementById('check-results-section');
    section.style.display = 'block';
    
    // Hiển thị hóa đơn chưa format
    const unformattedDiv = document.getElementById('unformatted-invoices');
    if (results.invoices_without_format && results.invoices_without_format.length > 0) {
        unformattedDiv.innerHTML = `
            <div style="margin-bottom: 10px; color: #666;">
                Tổng cộng: <strong>${results.invoices_without_format.length}</strong> hóa đơn
            </div>
            ${results.invoices_without_format.map(inv => `
                <div class="invoice-item">
                    <div class="invoice-number">Hóa đơn: ${inv}</div>
                </div>
            `).join('')}
        `;
    } else {
        unformattedDiv.innerHTML = '<div class="empty">✅ Không có hóa đơn nào có món chưa format</div>';
    }
    
    // Không hiển thị hóa đơn bia/rượu ở đây nữa - đã có phần luôn hiển thị ở trên
    // Chỉ cập nhật phần luôn hiển thị
    if (results.invoices_with_beverages) {
        displayBeverageInvoices(results.invoices_with_beverages);
    }
    
    // Scroll to results
    section.scrollIntoView({ behavior: 'smooth' });
}

// Load check results on page load
async function loadCheckResults() {
    try {
        const response = await fetch(`${API_BASE}/api/check-results`);
        if (response.ok) {
            const results = await response.json();
            // Chỉ hiển thị nếu có kết quả
            if (results && (results.invoices_with_beverages?.length > 0 || results.invoices_without_format?.length > 0)) {
                displayCheckResults(results);
            }
        }
    } catch (error) {
        // Ignore if no results file exists
    }
}

// Load and display beverage invoices (always visible section)
async function loadBeverageInvoices() {
    try {
        // Gọi API check-results (sẽ tự động chạy check mới, không đọc file)
        const response = await fetch(`${API_BASE}/api/check-results`);
        if (response.ok) {
            const results = await response.json();
            if (results && results.invoices_with_beverages) {
                displayBeverageInvoices(results.invoices_with_beverages);
            } else {
                displayBeverageInvoices([]);
            }
        } else {
            // Nếu lỗi, hiển thị empty
            displayBeverageInvoices([]);
        }
    } catch (error) {
        console.error('Error loading beverage invoices:', error);
        displayBeverageInvoices([]);
    }
}


// Display beverage invoices in the always-visible section
function displayBeverageInvoices(beverageInvoices) {
    const displayDiv = document.getElementById('beverage-invoices-display');
    
    if (!beverageInvoices || beverageInvoices.length === 0) {
        displayDiv.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #28a745; font-size: 1.1rem;">
                ✅ Không có hóa đơn nào có bia/rượu đã được thay thế
            </div>
        `;
        return;
    }
    
    // Tính tổng số món đã thay thế
    const totalReplacements = beverageInvoices.reduce((sum, item) => sum + item.replacements.length, 0);
    
    displayDiv.innerHTML = `
        <div style="margin-bottom: 15px; color: #666; font-size: 1.1rem;">
            <strong style="color: #fda085; font-size: 1.3rem;">${beverageInvoices.length}</strong> hóa đơn có bia/rượu đã được thay thế 
            (<strong>${totalReplacements}</strong> món đã thay thế)
        </div>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <thead>
                    <tr style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); color: white;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0;">Hóa Đơn</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0;">Món Bia/Rượu Gốc</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0;">Món Đã Thay Thế</th>
                        <th style="padding: 12px; text-align: right; border-bottom: 2px solid #e0e0e0;">Giá Thay Thế</th>
                    </tr>
                </thead>
                <tbody>
                    ${beverageInvoices.map(item => 
                        item.replacements.map((rep, idx) => `
                            <tr style="border-bottom: 1px solid #f0f0f0; ${idx === 0 ? 'border-top: 2px solid #fda085;' : ''}">
                                ${idx === 0 ? `
                                    <td style="padding: 12px; font-weight: 600; color: #667eea;" rowspan="${item.replacements.length}">
                                        <div style="font-size: 1.1rem;">${item.invoice_number}</div>
                                        <div style="font-size: 0.85rem; color: #999; font-weight: normal; margin-top: 4px;">${item.file}</div>
                                    </td>
                                ` : ''}
                                <td style="padding: 12px;">
                                    <div style="color: #dc3545; font-weight: 500;">${escapeHtml(rep.original_beverage_name || 'Bia/Rượu/Coke')}</div>
                                    ${rep.original_beverage_price ? `
                                        <div style="font-size: 0.85rem; color: #999; margin-top: 4px;">
                                            Giá gốc: ${rep.original_beverage_price.toLocaleString('vi-VN')}đ
                                        </div>
                                        <div style="font-size: 0.85rem; color: #dc3545; margin-top: 4px; font-weight: 500;">
                                            Giá bia + 10%: ${(rep.original_beverage_price * 1.10).toLocaleString('vi-VN')}đ
                                        </div>
                                        ${rep.item_type ? `
                                            <div style="font-size: 0.75rem; color: #667eea; margin-top: 4px; font-style: italic;">
                                                ${rep.item_type}
                                            </div>
                                        ` : ''}
                                    ` : ''}
                                </td>
                                <td style="padding: 12px;">
                                    <div style="color: #28a745; font-weight: 500;">${escapeHtml(rep.product)}</div>
                                    <div style="font-size: 0.85rem; color: #666; margin-top: 4px;">
                                        (Món thay thế)
                                    </div>
                                </td>
                                <td style="padding: 12px; text-align: right;">
                                    <div style="color: #333; font-weight: 600; font-size: 1.1rem;">${typeof rep.price === 'number' ? rep.price.toLocaleString('vi-VN') : rep.price}đ</div>
                                    ${rep.original_beverage_price ? `
                                        <div style="font-size: 0.85rem; color: #28a745; margin-top: 4px;">
                                            Sau thuế 8%: ${(rep.price * 1.08).toLocaleString('vi-VN')}đ
                                        </div>
                                        <div style="font-size: 0.75rem; color: #999; margin-top: 2px; font-style: italic;">
                                            = Giá bia + 10%
                                        </div>
                                    ` : ''}
                                </td>
                            </tr>
                        `).join('')
                    ).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// Generate Grab Invoice
async function generateGrabInvoice() {
    const totalInput = document.getElementById('grab-total');
    const menuSelect = document.getElementById('grab-menu');
    const totalAmount = parseFloat(totalInput.value);
    const menuSelection = menuSelect.value;
    
    if (!totalAmount || totalAmount <= 0) {
        alert('⚠️ Vui lòng nhập tổng tiền hợp lệ');
        return;
    }
    
    const btn = document.getElementById('btn-generate-grab');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Đang tạo...</span>';
    
    const resultDiv = document.getElementById('grab-result');
    const resultContent = document.getElementById('grab-result-content');
    resultContent.innerHTML = '<div class="loading">Đang tạo hóa đơn...</div>';
    resultDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_BASE}/api/grab-invoice`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                menu: menuSelection,
                total_with_tax: totalAmount
            })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Lỗi khi tạo hóa đơn');
        }
        
        // Hiển thị kết quả
        resultContent.innerHTML = `
            <div class="grab-result-summary">
                <div>📄 File: <strong>${data.output}</strong></div>
                <div>Menu: <strong>${data.menu === 'taco' ? 'Taco Place' : 'Simple Place'}</strong></div>
                <div>Tổng files mới: <strong>${data.created_count}</strong></div>
            </div>
        `;
        
        // Refresh status
        refreshStatus();
        
        // Scroll to result
        resultDiv.scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        resultContent.innerHTML = `<div style="color: #dc3545;">❌ Lỗi: ${error.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">🎲</span><span class="btn-text">Tạo Hóa Đơn Grab</span>';
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load check results on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCheckResults();
});
