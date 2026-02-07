#!/usr/bin/env python3
"""
Mỗi ngày tạo 5 hóa đơn bia/rượu (Sapporo, Tiger Draught, Coke).
5 hóa đơn này thay thế NGẪU NHIÊN 5 hóa đơn trong tax_files.
Tổng tiền bia/rượu (thuế 10%) = chính xác tổng tiền ban đầu (thuế 8%).
Chỉ điều chỉnh 1 món cuối cùng (ví dụ 35.000 → 35.426) để khớp tổng.

Chạy từ thư mục gốc dự án:
    python automation/daily_beverage_invoices.py
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path

# Project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.process_invoices import create_invoice_file, OUTPUT_DIR

# ============================================================================
# CẤU HÌNH MÓN BIA/RƯỢU/COKE
# ============================================================================
# Bia/rượu tính thuế 10%. Tổng sau thuế 10% = tổng gốc (8%) của hóa đơn bị thay.
# Chỉ điều chỉnh giá món cuối (vd 35.000 → 35.426) để khớp chính xác.

BEVERAGE_ITEMS = [
    {
        'name': 'Sapporo / Sapporo',
        'unit': 'Ly',
        'price': 55_000,
    },
    {
        'name': 'Tiger Draught / Tiger Draught',
        'unit': 'Ly',
        'price': 45_000,
    },
    {
        'name': 'Coke / Coke',
        'unit': 'Ly',
        'price': 25_000,
    },
]


def parse_total_from_stem(total_str):
    """'500.000đ' hoặc '1.234.567đ' -> 500000, 1234567."""
    s = (total_str or "").strip().replace("đ", "").replace(".", "").replace(",", "")
    try:
        return int(s)
    except ValueError:
        return None


def beverage_invoice_items_for_target(original_final_total):
    """
    Tạo danh sách món bia/rượu/Coke sao cho: sum(items) * 1.10 = original_final_total.
    Chỉ điều chỉnh 1 món cuối (vd 35.000 -> 35.426) để khớp chính xác.
    """
    # Tổng trước thuế 10% cần đạt để sau thuế 10% = original_final_total
    target_before_tax = original_final_total / 1.10

    # Món đầu: 1–2 món cố định (giá chuẩn), tổng luôn < target để món cuối điều chỉnh
    items = []
    sum_so_far = 0
    reserve_for_last = random.randint(25_000, 60_000)  # chừa cho món cuối (vd 35.426)
    max_fixed = target_before_tax - reserve_for_last
    if max_fixed < 25_000:
        max_fixed = target_before_tax * 0.5  # fallback
    n_fixed = random.randint(1, 2)
    for _ in range(n_fixed):
        choice = random.choice(BEVERAGE_ITEMS)
        remaining = max_fixed - sum_so_far
        if remaining < choice['price']:
            break
        max_qty = min(3, int(remaining // choice['price']))
        if max_qty < 1:
            break
        qty = random.randint(1, max_qty)
        amount = choice['price'] * qty
        items.append({
            'name': choice['name'],
            'unit': choice['unit'],
            'quantity': qty,
            'price': choice['price'],
        })
        sum_so_far += amount

    # Món cuối duy nhất: điều chỉnh đơn giá để tổng = target_before_tax (vd 35.000 -> 35.426)
    gap = target_before_tax - sum_so_far
    last_qty = 1
    last_price = max(1, round(gap))
    last_choice = random.choice(BEVERAGE_ITEMS)
    items.append({
        'name': last_choice['name'],
        'unit': last_choice['unit'],
        'quantity': last_qty,
        'price': last_price,
    })
    return items


def build_beverage_invoice(invoice_id, payment_method, original_final_total, date_str=None):
    """
    Tạo hóa đơn bia/rượu có tổng sau thuế 10% = original_final_total (tổng 8% ban đầu).
    Chỉ điều chỉnh món cuối (vd 35.000 -> 35.426). Không thêm phí dịch vụ để tổng khớp chính xác.
    """
    if date_str is None:
        date_str = datetime.now().strftime('%d/%m/%Y')
    items = beverage_invoice_items_for_target(original_final_total)
    invoice = {
        'invoice_id': invoice_id,
        'date': date_str,
        'payment_method': payment_method,
        'discount': 0,
        'payment_discount': 0,
        'items': items,
        'final_total': 0,
    }
    # Không gọi add_service_fee_to_invoice để: tổng = sum(items) * 1.10 = original_final_total
    return invoice


def parse_tax_filename(filepath):
    """
    Parse tên file tax: "123456 - atm - 500.000đ.xlsx"
    Returns (invoice_id, payment_method, original_final_total) hoặc None.
    """
    stem = filepath.stem
    parts = stem.split(' - ')
    if len(parts) < 3:
        return None
    inv_id = parts[0].strip()
    payment = parts[1].strip().lower()
    if payment not in ('atm', 'transfer'):
        payment = 'atm'
    original_total = parse_total_from_stem(parts[2].strip())
    if original_total is None:
        return None
    return inv_id, payment, original_total


STATE_FILE = PROJECT_ROOT / "beverage_replacement_state.json"
MAX_REPLACEMENTS_PER_DAY = 5


def _read_replacement_state():
    """Đọc trạng thái: đã thay bao nhiêu hóa đơn bia/rượu hôm nay."""
    if not STATE_FILE.exists():
        return {"date": None, "count": 0}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {"date": data.get("date"), "count": data.get("count", 0)}
    except Exception:
        return {"date": None, "count": 0}


def _write_replacement_state(today: str, count: int):
    STATE_FILE.write_text(json.dumps({"date": today, "count": count}, ensure_ascii=False), encoding="utf-8")


def run_beverage_replacement():
    """
    Chạy thay thế 5 hóa đơn ngẫu nhiên bằng hóa đơn bia/rượu.
    Tối đa 5 hóa đơn bia/rượu mỗi ngày – bấm nhiều lần cũng không thay thêm.
    Trả về dict: success, error, replaced (list), log_lines, log_file.
    Dùng cho gọi từ web (auto_upload_web.py).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    state = _read_replacement_state()
    if state["date"] == today and state["count"] >= MAX_REPLACEMENTS_PER_DAY:
        return {
            "success": False,
            "error": f"Đã thay đủ {MAX_REPLACEMENTS_PER_DAY} hóa đơn bia/rượu hôm nay. Không thay thêm. (Chỉ 5 HĐ/ngày)",
        }

    tax_dir = PROJECT_ROOT / OUTPUT_DIR
    if not tax_dir.exists():
        tax_dir.mkdir(parents=True, exist_ok=True)
    if not tax_dir.exists():
        return {"success": False, "error": f"Không tìm thấy thư mục {OUTPUT_DIR}"}

    all_files = list(tax_dir.glob("*.xlsx"))
    all_files = [f for f in all_files if not f.name.startswith("Grab - ")]
    if len(all_files) < 5:
        return {
            "success": False,
            "error": f"Trong {OUTPUT_DIR} có {len(all_files)} file. Cần ít nhất 5 file để thay thế.",
        }

    to_replace = random.sample(all_files, 5)
    date_str = datetime.now().strftime('%d/%m/%Y')
    log_lines = [
        f"LOG THAY THẾ HÓA ĐƠN BIA/RƯỢU/COKE - {date_str}",
        "Tổng bia/rượu (thuế 10%) = đúng tổng ban đầu (thuế 8%). Chỉ điều chỉnh 1 món cuối.",
        "",
    ]
    replaced = []

    for i, filepath in enumerate(to_replace, 1):
        parsed = parse_tax_filename(filepath)
        if not parsed:
            log_lines.append(f"  {i}. Bỏ qua (không parse được): {filepath.name}")
            continue
        invoice_id, payment_method, original_final = parsed
        invoice = build_beverage_invoice(invoice_id, payment_method, original_final, date_str)
        total_str = f"{original_final:,}".replace(',', '.')
        output_path = tax_dir / f"{invoice_id} - {payment_method} - {total_str}đ.xlsx"
        create_invoice_file(invoice, str(output_path))
        if output_path != filepath and filepath.exists():
            filepath.unlink()

        last_item = invoice['items'][-1]
        old_name = filepath.name
        log_lines.append(f"  {i}. Hóa đơn bị thay thế: {old_name}")
        log_lines.append(f"     → HĐ {invoice_id}, {payment_method.upper()}, tổng {original_final:,}đ. Món cuối: {last_item['price']:,}đ")
        replaced.append({
            "old_name": old_name,
            "invoice_id": invoice_id,
            "payment_method": payment_method,
            "total": original_final,
            "last_item_price": last_item["price"],
        })

    log_file = PROJECT_ROOT / f"beverage_replacement_log_{datetime.now().strftime('%Y-%m-%d')}.txt"
    log_file.write_text("\n".join(log_lines), encoding="utf-8")
    # Ghi trạng thái: hôm nay đã thay đủ 5, không cho thay thêm nữa trong ngày
    _write_replacement_state(today, MAX_REPLACEMENTS_PER_DAY)
    return {
        "success": True,
        "replaced": replaced,
        "log_lines": log_lines,
        "log_file": str(log_file.name),
    }


def main():
    result = run_beverage_replacement()
    if not result.get("success"):
        print(f"❌ {result.get('error', 'Lỗi')}")
        return 1
    for line in result.get("log_lines", []):
        print(line)
    print(f"\n📄 Log đã ghi: {result.get('log_file', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
