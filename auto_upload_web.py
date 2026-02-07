#!/usr/bin/env python3
"""
WEB INTERFACE FOR AUTO UPLOAD
==============================
Web interface để điều khiển auto_upload_simple.py từ trình duyệt
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import threading
import subprocess
import sys
from pathlib import Path
import json
from datetime import datetime
import io
import contextlib

# Project structure helpers
BASE_DIR = Path(__file__).resolve().parent
AUTOMATION_DIR = BASE_DIR / "automation"

# Ensure automation package remains importable when running as a script
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from automation.process_invoices import (
    process_sale_by_payment_method,
    load_menus,
    combine_files,
    parse_invoices_from_html,
    _process_and_save_invoices,
    create_grab_invoice,
    SERVICE_FEE_ENABLED,
    SERVICE_FEE_PERCENTAGE,
    SERVICE_FEE_NAME,
    SERVICE_FEE_UNIT,
)

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Global state
script_process = None
script_status = {
    "running": False,
    "pid": None,
    "start_time": None,
    "logs": [],
    "current": None,
}

fetch_process = None
fetch_status = {
    "running": False,
    "pid": None,
    "start_time": None,
    "logs": [],
    "exit_code": None,
}

SCRIPT_PATH = AUTOMATION_DIR / "auto_upload_simple.py"
FETCH_SCRIPT_PATH = AUTOMATION_DIR / "auto_fetch_fabi.py"
DATA_DIR = BASE_DIR / "data"
TAX_DIR = BASE_DIR / "tax_files"

@app.route('/')
def index():
    """Trang chủ"""
    return render_template('auto_upload_control.html')


@app.route('/api/start', methods=['POST'])
def start_script():
    """Start script"""
    global script_process, script_status
    
    if script_status["running"]:
        return jsonify({"error": "Script đang chạy rồi"}), 400
    
    try:
        # Chạy script trong background
        script_process = subprocess.Popen(
            [sys.executable, str(SCRIPT_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        script_status["running"] = True
        script_status["pid"] = script_process.pid
        script_status["start_time"] = datetime.now().isoformat()
        script_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Script đã được khởi động")
        
        # Thread để đọc output
        def read_output():
            for line in iter(script_process.stdout.readline, ''):
                if line:
                    log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] {line.strip()}"
                    script_status["logs"].append(log_entry)
                    low = line.strip().lower()
                    if ("uploading:" in low) or ("processing..." in low) or ("thành công" in low) or ("thất bại" in low):
                        script_status["current"] = line.strip()
                    # Giới hạn log để tránh quá nhiều
                    if len(script_status["logs"]) > 1000:
                        script_status["logs"] = script_status["logs"][-500:]
            
            # Script đã kết thúc
            script_process.wait()
            script_status["running"] = False
            script_status["current"] = None
            script_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Script đã kết thúc (exit code: {script_process.returncode})")
            script_process = None
        
        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()
        
        return jsonify({"success": True, "pid": script_process.pid})
    
    except Exception as e:
        script_status["running"] = False
        return jsonify({"error": str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_script():
    """Stop script"""
    global script_process, script_status
    
    if not script_status["running"]:
        return jsonify({"error": "Script không đang chạy"}), 400
    
    try:
        if script_process:
            script_process.terminate()
            script_status["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Đang dừng script...")
            return jsonify({"success": True})
        else:
            script_status["running"] = False
            return jsonify({"success": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_software():
    """Reset lại phần mềm: dừng script, clear logs, reset status"""
    global script_process, script_status, fetch_process, fetch_status
    
    try:
        # Dừng script nếu đang chạy
        if script_status["running"] and script_process:
            try:
                script_process.terminate()
            except:
                pass
        
        # Dừng fetch nếu đang chạy
        if fetch_status["running"] and fetch_process:
            try:
                fetch_process.terminate()
            except:
                pass
        
        # Reset script status
        script_status = {
            "running": False,
            "pid": None,
            "start_time": None,
            "logs": [],
            "current": None,
        }
        
        # Reset fetch status
        fetch_status = {
            "running": False,
            "pid": None,
            "start_time": None,
            "logs": [],
            "exit_code": None,
        }
        
        script_process = None
        fetch_process = None
        
        return jsonify({
            "success": True,
            "message": "Đã reset lại phần mềm thành công"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Lấy logs"""
    return jsonify({
        "logs": script_status["logs"],
        "count": len(script_status["logs"])
    })

@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    """Xóa logs"""
    script_status["logs"] = []
    return jsonify({"success": True})

@app.route('/api/clear-files', methods=['POST'])
def clear_files():
    """Xóa tất cả files .xlsx trong tax_files/"""
    try:
        if not TAX_DIR.exists():
            return jsonify({"success": False, "error": "Thư mục tax_files không tồn tại"}), 400
        
        files_deleted = []
        for file_path in TAX_DIR.glob("*.xlsx"):
            try:
                file_path.unlink()
                files_deleted.append(file_path.name)
            except Exception as e:
                return jsonify({"success": False, "error": f"Lỗi khi xóa {file_path.name}: {str(e)}"}), 500
        
        return jsonify({
            "success": True,
            "deleted_count": len(files_deleted),
            "files": files_deleted
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/clear-data-files', methods=['POST'])
def clear_data_files():
    """Xóa tất cả files trong data/"""
    try:
        if not DATA_DIR.exists():
            return jsonify({"success": False, "error": "Thư mục data không tồn tại"}), 400
        
        files_deleted = []
        for file_path in DATA_DIR.glob("*"):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    files_deleted.append(file_path.name)
                except Exception as e:
                    return jsonify({"success": False, "error": f"Lỗi khi xóa {file_path.name}: {str(e)}"}), 500
        
        return jsonify({
            "success": True,
            "deleted_count": len(files_deleted),
            "files": files_deleted
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/fetch-data', methods=['POST'])
def fetch_data():
    """Chạy script auto_fetch_fabi.py để tải dữ liệu báo cáo."""
    global fetch_process, fetch_status

    if not FETCH_SCRIPT_PATH.exists():
        return jsonify({"success": False, "error": "auto_fetch_fabi.py không tồn tại"}), 404

    if fetch_status["running"]:
        return jsonify({"success": False, "error": "Fetch đang chạy"}), 400

    payload = request.get_json(silent=True) or {}

    args = [sys.executable, str(FETCH_SCRIPT_PATH)]
    if payload.get("headless", True):
        args.append("--headless")
    if payload.get("no_click_transfer", False):
        args.append("--no-click-transfer")
    if "wait" in payload:
        args.extend(["--wait", str(payload["wait"])])

    try:
        fetch_process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=str(BASE_DIR),
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500

    fetch_status.update({
        "running": True,
        "pid": fetch_process.pid,
        "start_time": datetime.now().isoformat(),
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] Fetch script started"],
        "exit_code": None,
    })

    def read_output():
        global fetch_process, fetch_status
        for line in iter(fetch_process.stdout.readline, ''):
            if line:
                entry = f"[{datetime.now().strftime('%H:%M:%S')}] {line.strip()}"
                fetch_status["logs"].append(entry)
                if len(fetch_status["logs"]) > 500:
                    fetch_status["logs"] = fetch_status["logs"][-250:]
        fetch_process.wait()
        fetch_status["running"] = False
        fetch_status["exit_code"] = fetch_process.returncode
        fetch_status["logs"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Fetch script finished (exit code: {fetch_process.returncode})"
        )
        if len(fetch_status["logs"]) > 500:
            fetch_status["logs"] = fetch_status["logs"][-250:]
        fetch_process = None

    threading.Thread(target=read_output, daemon=True).start()

    return jsonify({"success": True, "pid": fetch_process.pid})

@app.route('/api/fetch-status')
def get_fetch_status():
    """Trả về trạng thái hiện tại của fetch script."""
    return jsonify({
        "running": fetch_status["running"],
        "pid": fetch_status["pid"],
        "start_time": fetch_status["start_time"],
        "logs": fetch_status["logs"][-200:],
        "exit_code": fetch_status["exit_code"],
    })

@app.route('/api/process-default', methods=['POST'])
def process_default():
    """Process invoices from data/ if present; otherwise fallback to defaults."""
    TAX_DIR.mkdir(exist_ok=True)
    before = set(p.name for p in TAX_DIR.glob('*.xlsx'))
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            # Prefer processing from data/ folder
            if DATA_DIR.exists():
                file_combined_1 = DATA_DIR / 'sale_by_payment_method.xls'
                file_combined_2 = DATA_DIR / 'sale_by_payment_method (1).xls'
                data_files = sorted([p for p in DATA_DIR.glob('*') if p.is_file()])

                if file_combined_1.exists() and file_combined_2.exists():
                    # Combined processing path
                    print(f"\n📂 Using data/: {file_combined_1.name} + {file_combined_2.name}")
                    content, _ = combine_files(str(file_combined_1), str(file_combined_2))
                    all_menu_items, name_mapping, price_to_items = load_menus()
                    invoices, alcohol_items_found = parse_invoices_from_html(content, all_menu_items, name_mapping, price_to_items, True)
                    _process_and_save_invoices(invoices, 'combined', alcohol_items_found)
                else:
                    # Single file path: pick the first .xls/.html-like file
                    preferred_exts = ['.xls', '.xlsx', '.html', '.htm']
                    candidates = [p for p in data_files if p.suffix.lower() in preferred_exts]
                    if not candidates and data_files:
                        candidates = data_files[:1]
                    if not candidates:
                        print("❌ No input files found in data/ folder")
                    else:
                        input_path = candidates[0]
                        print(f"\n📂 Using data/: {input_path.name}")
                        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        all_menu_items, name_mapping, price_to_items = load_menus()
                        is_combined = 'sale_by_payment_method' in input_path.name.lower()
                        invoices, alcohol_items_found = parse_invoices_from_html(content, all_menu_items, name_mapping, price_to_items, is_combined)
                        # Detect source type from filename
                        name_lower = input_path.name.lower()
                        if 'atm' in name_lower:
                            source_type = 'atm'
                        elif 'transfer' in name_lower:
                            source_type = 'transfer'
                        else:
                            source_type = input_path.stem
                        _process_and_save_invoices(invoices, source_type, alcohol_items_found)
            else:
                # Fallback to original default behavior (root files)
                print("ℹ️ data/ not found, using default files in project root")
                process_sale_by_payment_method()

        logs = buf.getvalue().splitlines()[-400:]
        after = set(p.name for p in TAX_DIR.glob('*.xlsx'))
        new_files = sorted(list(after - before))
        return jsonify({
            "success": True,
            "created": len(new_files),
            "files": new_files,
            "logs": logs,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "logs": buf.getvalue().splitlines()[-400:]}), 500

@app.route('/api/service-fee-status')
def get_service_fee_status():
    """Lấy trạng thái phí dịch vụ"""
    return jsonify({
        "enabled": SERVICE_FEE_ENABLED,
        "percentage": SERVICE_FEE_PERCENTAGE,
        "percentage_display": f"{SERVICE_FEE_PERCENTAGE * 100:.0f}%",
        "name": SERVICE_FEE_NAME,
        "unit": SERVICE_FEE_UNIT,
    })

@app.route('/api/grab-invoice', methods=['POST'])
def api_grab_invoice():
    """Create a Grab invoice by menu and total amount (with VAT)."""
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        menu_choice = (data.get('menu') or 'simple').strip().lower()
        total_with_tax = data.get('total_with_tax')
        date_str = data.get('date')
        invoice_number = data.get('invoice_number')

        if total_with_tax is None:
            return jsonify({"success": False, "error": "total_with_tax is required"}), 400
        try:
            total_with_tax = float(str(total_with_tax).replace(',', '').replace('.', '').strip())
        except Exception:
            return jsonify({"success": False, "error": "total_with_tax must be a number"}), 400

        all_menu_items, _, _ = load_menus()
        simple_menu_items = []
        taco_menu_items = []
        for item in all_menu_items:
            src = item.get('menu_source', 'simple')
            (taco_menu_items if src == 'taco' else simple_menu_items).append(item)

        if menu_choice in ['taco', 'grab_taco', 'taco place']:
            menu_items = taco_menu_items
            used_menu = 'taco'
        else:
            menu_items = simple_menu_items
            used_menu = 'simple'

        TAX_DIR.mkdir(exist_ok=True)
        before = set(p.name for p in TAX_DIR.glob('*.xlsx'))
        out_file = create_grab_invoice(total_with_tax, menu_items, date_str, invoice_number)
        after = set(p.name for p in TAX_DIR.glob('*.xlsx'))
        new_files = sorted(list(after - before))

        if not out_file:
            return jsonify({"success": False, "error": "Failed to create Grab invoice"}), 500

        return jsonify({
            "success": True,
            "menu": used_menu,
            "output": out_file,
            "created_count": len(new_files),
            "files": new_files,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/beverage-replace', methods=['POST'])
def api_beverage_replace():
    """Thay 5 hóa đơn ngẫu nhiên trong tax_files bằng hóa đơn bia/rượu (Sapporo, Tiger Draught, Coke)."""
    try:
        from automation.daily_beverage_invoices import run_beverage_replacement
        result = run_beverage_replacement()
        if not result.get('success'):
            return jsonify({"success": False, "error": result.get("error", "Lỗi không xác định")}), 400
        return jsonify({
            "success": True,
            "replaced": result.get("replaced", []),
            "log_lines": result.get("log_lines", []),
            "log_file": result.get("log_file", ""),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/check-invoices', methods=['POST'])
def check_invoices():
    """Chạy script kiểm tra hóa đơn - so sánh với menu gốc, không lưu file, chỉ trả về kết quả"""
    try:
        from check_invoices import check_invoices as check_invoices_func
        results = check_invoices_func()
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-results')
def get_check_results():
    """Lấy kết quả kiểm tra - chạy check mới (so sánh với menu gốc) thay vì đọc file"""
    try:
        from check_invoices import check_invoices as check_invoices_func
        results = check_invoices_func()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500

@app.route('/api/status')
def get_status():
    """Lấy trạng thái script và file counts"""
    data_files_count = len(list(DATA_DIR.glob("*"))) if DATA_DIR.exists() else 0
    tax_files_count = len(list(TAX_DIR.glob("*.xlsx"))) if TAX_DIR.exists() else 0
    
    return jsonify({
        "running": script_status["running"],
        "pid": script_status["pid"],
        "start_time": script_status["start_time"],
        "current": script_status.get("current"),
        "logs": script_status["logs"][-50:],  # Chỉ lấy 50 log cuối
        "data_files": data_files_count,
        "tax_files": tax_files_count,
    })

if __name__ == '__main__':
    print("="*70)
    print("🌐 AUTO UPLOAD WEB CONTROL")
    print("="*70)
    
    url = "http://localhost:5001"
    
    print(f"🚀 Server starting at: {url}")
    print(f"📁 Mở trình duyệt và truy cập: {url}")
    print("="*70)
    
    # Tự động mở trình duyệt 1 lần khi server start
    def _open():
        import time, webbrowser
        time.sleep(1.2)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)