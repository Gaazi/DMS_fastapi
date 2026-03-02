import os
import re

template_dirs = [
    r"d:\Working Project\DMS with Fast API\templates",
    r"d:\Working Project\DMS with Fast API\dms\templates"
]

def transform_template(content):
    # 1. Remove {% load static %}
    content = re.sub(r'\{%\s*load\s+static\s*%\}', '', content)
    
    # 2. Replace {% static 'path' %} with {{ static('path') }}
    content = re.sub(r'\{%\s*static\s+[\'"](.*?)[\'"]\s*%\}', r"{{ static('\1') }}", content)
    
    # 3. Replace {% url 'name' arg1 arg2 %} with {{ url('name', arg1, arg2) }}
    # This is a bit tricky due to spaces. Let's handle common cases.
    def url_replace(match):
        parts = match.group(1).split()
        if not parts: return "{{ url() }}"
        name = parts[0]
        args = ", ".join(parts[1:])
        if args:
            return f"{{{{ url({name}, {args}) }}}}"
        else:
            return f"{{{{ url({name}) }}}}"

    content = re.sub(r'\{%\s*url\s+(.*?)\s*%\}', url_replace, content)
    
    # 4. Replace {% translate '...' %} or {% trans '...' %} with {{ translate('...') }}
    content = re.sub(r'\{%\s*(?:translate|trans)\s+[\'"](.*?)[\'"]\s*%\}', r"{{ translate('\1') }}", content)
    
    # 5. Replace {% csrf_token %} with {{ csrf_token() }}
    content = re.sub(r'\{%\s*csrf_token\s*%\}', r"{{ csrf_token() }}", content)
    
    # 6. Replace {{ block.super }} with {{ super() }}
    content = re.sub(r'\{\{\s*block\.super\s*\}\}', r"{{ super() }}", content)
    
    # 7. Replace {% empty %} with {% else %}
    content = re.sub(r'\{%\s*empty\s*%\}', r"{% else %}", content)
    
    # 8. Replace forloop.counter with loop.index
    content = re.sub(r'forloop\.counter0', 'loop.index0', content)
    content = re.sub(r'forloop\.counter', 'loop.index', content)

    # 9. Remove other Django specific tags that might crash Jinja2
    content = re.sub(r'\{%\s*load\s+.*?\s*%\}', '', content)
    
    # 10. Convert |filter:arg to |filter(arg)
    # Handle single quotes, double quotes, or no quotes
    content = re.sub(r'\|(\w+):([\'"]?)(.*?)\2(\s*[|}]|(?:\s+))', r'|\1(\2\3\2)\4', content)

    # 11. Replace {% comment %} ... {% endcomment %} with {# ... #}
    # This needs to be done carefully for multi-line
    content = re.sub(r'\{%\s*comment\s*%\}(.*?)\{%\s*endcomment\s*%\}', r"{# \1 #}", content, flags=re.DOTALL)
    
    # 12. Remove any other remaining load tags
    content = re.sub(r'\{%\s*load\s+.*?\s*%\}', '', content)

    # 13. Replace common filters that have different names or need simple transformation
    content = content.replace('|floatformat(0)', '|int')
    content = content.replace('|floatformat', '|round')

    # 14. Convert Django 'now' tag to Jinja2 function call
    content = re.sub(r'\{%\s*now\s+[\'"](.*?)[\'"]\s*%\}', r"{{ now('\1') }}", content)
    
    # 15. Convert Django 'url_replace' to Jinja2 function call
    content = re.sub(r'\{%\s*url_replace\s+(.*?)\s*%\}', r"{{ url_replace(\1) }}", content)
    
    # 16. Convert Django allauth 'provider_login_url'
    # Fix previously broken {{ url('auth_google' process="login") }}
    content = re.sub(r"\{\{\s*url\('auth_(\w+)'\s+(\w+)=[\'\"](.*?)[\'\"]\)\s*\}\}", r"{{ url('auth_\1', \2='\3') }}", content)
    
    # And convert original if not converted yet
    content = re.sub(r'\{%\s*provider_login_url\s+[\'"](\w+)[\'"]\s+(\w+)=[\'"](.*?)[\'"]\s*%\}', r"{{ url('auth_\1', \2='\3') }}", content)
    content = re.sub(r'\{%\s*provider_login_url\s+[\'"](\w+)[\'"]\s*%\}', r"{{ url('auth_\1') }}", content)

    # 17. Convert {% widthratio A B C as Var %} to {% set Var = (A/B*C)|round|int %}
    content = re.sub(r'\{%\s*widthratio\s+([\w\.]+)\s+([\w\.]+)\s+(\d+)\s+as\s+(\w+)\s*%\}', r"{% set \4 = (\1 / \2 * \3)|round|int %}", content)

    return content

for template_dir in template_dirs:
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file.endswith(".html"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                new_content = transform_template(content)
                
                if new_content != content:
                    print(f"Updating {path}")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
