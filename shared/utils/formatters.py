def format_currency(amount: float) -> str:
    """Format float to Indonesian Rupiah string. e.g. 35000 → 'Rp 35.000'"""
    return f"Rp {amount:,.0f}".replace(",", ".")


def format_expense_confirmation(amount: float, category: str, note: str, icon: str = "✅") -> str:
    return (
        f"{icon} Tercatat!\n"
        f"💰 {format_currency(amount)}\n"
        f"🏷️ {category}\n"
        f"📝 {note}"
    )
