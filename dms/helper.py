from django.shortcuts import redirect
from django.contrib import messages

def handle_manager_result(request, success, message):
    level = messages.SUCCESS if success else messages.ERROR
    messages.add_message(request, level, message)
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

def resolve_currency_label(institution):
    """ادارے کی کرنسی کا نشان حاصل کرنا"""
    try:
        from .logic.institution import InstitutionManager
        return InstitutionManager.get_currency_label(institution)
    except ImportError:
        return "Rs." # Fallback

def number_to_words(n):
    """رقم کو انگلش الفاظ میں تبدیل کرنے کا سادہ فنکشن (Simple Integer Conversion)"""
    try:
        n = int(float(str(n).replace(',', '')))
    except:
        return "Zero"
        
    if n == 0: return "Zero Only"
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert(num):
        if num < 20:
            return units[num]
        elif num < 100:
            return tens[num // 10] + (" " + units[num % 10] if num % 10 != 0 else "")
        elif num < 1000:
            return units[num // 100] + " Hundred" + (" and " + convert(num % 100) if num % 100 != 0 else "")
        elif num < 1000000:
            return convert(num // 1000) + " Thousand" + (" " + convert(num % 1000) if num % 1000 != 0 else "")
        elif num < 1000000000:
            return convert(num // 1000000) + " Million" + (" " + convert(num % 1000000) if num % 1000000 != 0 else "")
        else:
            return str(num)
            
    return convert(n) + " Only"


