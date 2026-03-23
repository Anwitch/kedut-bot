from datetime import date, timedelta
from shared.services.expense_service import get_expenses


def _build_summary(user_id: str, start: date, end: date, label: str) -> str:
    rows = get_expenses(user_id, start, end)
    if not rows:
        return f"Belum ada pengeluaran {label}. 🎉"

    totals: dict[str, dict] = {}
    grand_total = 0.0

    for r in rows:
        cat = r.get("categories") or {}
        cat_name = cat.get("name", "Lainnya")
        icon = cat.get("icon", "📌")
        amount = float(r["amount"])
        grand_total += amount

        if cat_name not in totals:
            totals[cat_name] = {"icon": icon, "total": 0.0}
        totals[cat_name]["total"] += amount

    lines = [f"📊 *Ringkasan {label}*\n"]
    for cat_name, info in sorted(totals.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"{info['icon']} {cat_name}: *Rp {info['total']:,.0f}*")

    lines.append(f"\n💰 *Total: Rp {grand_total:,.0f}*")
    lines.append(f"📅 {start.strftime('%d %b')} – {end.strftime('%d %b %Y')}")
    return "\n".join(lines)


def get_weekly_summary(user_id: str) -> str:
    today = date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    return _build_summary(user_id, start, today, "minggu ini")


def get_monthly_summary(user_id: str) -> str:
    today = date.today()
    start = today.replace(day=1)
    return _build_summary(user_id, start, today, "bulan ini")
