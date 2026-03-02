# from django import template

# register = template.Library()

# @register.filter(name='split')
# def split(value, arg):
#     return value.split(arg)

# @register.filter(name='dict_key')
# def dict_key(d, k):
#     """ڈکشنری سے ڈائنامک کی (Key) کے ذریعے ویلیو حاصل کرنا۔"""
#     return d.get(k)

# @register.simple_tag(takes_context=True)
# def url_replace(context, **kwargs):
#     """
#     Return an encoded string of query parameters, replacing existing ones with kwargs.
#     Usage: {% url_replace page=page_obj.next_page_number %}
#     """
#     request = context.get('request')
#     if request:
#         query = request.GET.copy()
#     else:
#         # Fallback if request context processor is not enabled
#         from django.http import QueryDict
#         query = QueryDict(mutable=True)
        
#     for key, value in kwargs.items():
#         query[key] = value
        
# @register.filter(name='get_field')
# def get_field(form, field_name):
#     """Returns a form field by name."""
#     try:
#         return form[field_name]
#     except KeyError:
#         return None
# #




# dms_tags.py
from django import template
from django.http import QueryDict

register = template.Library()

@register.filter(name='split')
def split(value, arg):
    """اسٹرنگ کو دیئے گئے نشان سے توڑنا"""
    return value.split(arg)

@register.filter(name='dict_key')
def dict_key(d, k):
    """ڈکشنری سے کی (Key) کے ذریعے ویلیو حاصل کرنا"""
    try:
        return d.get(k)
    except (AttributeError, TypeError):
        return None

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """یو آر ایل کے پیرامیٹرز کو بدلنا (Pagination کے لیے)"""
    request = context.get('request')
    if request:
        query = request.GET.copy()
    else:
        query = QueryDict(mutable=True)
        
    for key, value in kwargs.items():
        query[key] = value
    
    return query.urlencode() # یہ لائن بہت ضروری ہے

@register.filter(name='get_field')
def get_field(form, field_name):
    """فارم سے مخصوص فیلڈ حاصل کرنا"""
    try:
        return form[field_name]
    except (KeyError, TypeError):
        return None

@register.filter(name='short_id')
def short_id(reg_id):
    """رجسٹریشن آئی ڈی کو مزید چھوٹا کرنا (مثلاً MKT-001-S-001 سے صرف 001)"""
    if not reg_id:
        return ""
    parts = str(reg_id).split('-')
    if parts:
        return parts[-1]
    return reg_id