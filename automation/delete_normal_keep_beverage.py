#!/usr/bin/env python3
"""
Xóa các file hóa đơn BÌNH THƯỜNG trong tax_files, CHỈ GIỮ LẠI các file đã bị thay bằng bia/rượu.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TAX_DIR = BASE_DIR / "tax_files"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from automation.list_beverage_replaced_invoices import is_beverage_only_invoice


def main():
    if not TAX_DIR.exists():
        print("Không tìm thấy thư mục tax_files")
        return 1

    all_xlsx = list(TAX_DIR.glob("*.xlsx"))
    to_keep = []
    to_delete = []

    for f in all_xlsx:
        is_beverage, _ = is_beverage_only_invoice(f)
        if is_beverage:
            to_keep.append(f)
        else:
            to_delete.append(f)

    print("=" * 60)
    print("XÓA HÓA ĐƠN BÌNH THƯỜNG – CHỈ GIỮ LẠI HÓA ĐƠN BIA/RƯỢU")
    print("=" * 60)
    print(f"Giữ lại (bia/rượu): {len(to_keep)} file")
    print(f"Sẽ xóa (bình thường + Grab): {len(to_delete)} file")
    print()

    if not to_delete:
        print("Không có file nào cần xóa.")
        return 0

    for f in sorted(to_delete):
        try:
            f.unlink()
            print(f"  Đã xóa: {f.name}")
        except Exception as e:
            print(f"  ❌ Lỗi xóa {f.name}: {e}")
            return 1

    print()
    print(f"✅ Đã xóa {len(to_delete)} file. Còn lại {len(to_keep)} file (chỉ bia/rượu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
