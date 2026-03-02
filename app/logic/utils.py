import string
import random
import secrets

def get_random_string(length=12):
    """رینڈم سٹرنگ (پاس ورڈ یا ٹوکن کے لیے) حاصل کرنا۔"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_slug(text):
    """ٹیکسٹ سے سلگ بنانا (Simple Slugify)۔"""
    text = text.lower().strip()
    text = ''.join(c if c.isalnum() else '-' for c in text)
    while '--' in text: text = text.replace('--', '-')
    return text.strip('-')
