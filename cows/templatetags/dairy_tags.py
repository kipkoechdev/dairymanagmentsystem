from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter
def sub(value, arg):
    """Subtract arg from value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply value by arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
