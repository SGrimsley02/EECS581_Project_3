def nextMonth(year: int, month: int) -> tuple[int, int]:
    """Returns the year and month of the next month."""
    if month == 12:
        return year + 1, 1
    return year, month + 1

def prevMonth(year: int, month: int) -> tuple[int, int]:
    """Returns the year and month of the previous month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1