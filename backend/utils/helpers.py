# utils/helpers.py
def safe_strip(value):
    """Safely strip a string value, handling None"""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value