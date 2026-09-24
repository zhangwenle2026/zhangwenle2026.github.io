#!/usr/bin/env python3
"""
共享常量模块，供 alert.py 和 render_card.py 共同使用。
避免两个文件中重复定义 REGION_TZ、REGION_TZ_NAMES、_slot_range。
"""

from datetime import timezone, timedelta


REGION_TZ = {
    "SA": timezone(timedelta(hours=3)),
    "AE": timezone(timedelta(hours=4)),
    "QA": timezone(timedelta(hours=3)),
    "KW": timezone(timedelta(hours=3)),
    "BH": timezone(timedelta(hours=3)),
    "HK": timezone(timedelta(hours=8)),
    "BR": timezone(timedelta(hours=-3)),
}

REGION_TZ_NAMES = {
    "SA": "Asia/Riyadh", "AE": "Asia/Dubai", "QA": "Asia/Qatar",
    "KW": "Asia/Kuwait", "BH": "Asia/Bahrain",
    "HK": "Asia/Hong_Kong", "BR": "America/Sao_Paulo",
}


def _slot_range(slot_str, interval_min=10):
    """将 slot 起点 'HH:MM' 转换为区间 'HH:MM-HH:MM'（如 '17:00' → '17:00-17:10'）"""
    try:
        h, m = map(int, slot_str.split(":"))
        total = h * 60 + m + interval_min
        if total >= 1440:
            total -= 1440
        eh, em = divmod(total, 60)
        return f"{slot_str}-{eh:02d}:{em:02d}"
    except Exception:
        return slot_str
