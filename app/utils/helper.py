from fastapi.responses import RedirectResponse
from typing import Optional

def handle_manager_result(request, success: bool, message: str, redirect_url: Optional[str] = None):
    """مینیجر کے نتیجے پر redirect کرنا۔"""
    target = redirect_url or request.headers.get('referer', '/')
    return RedirectResponse(url=target, status_code=303)

def resolve_currency_label(institution) -> str:
    """ادارے کی کرنسی کا نشان حاصل کرنا۔"""
    if institution:
        for attr in ("currency_label", "currency_code", "currency"):
            value = getattr(institution, attr, None)
            if value:
                return str(value)
    return "Rs."


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
