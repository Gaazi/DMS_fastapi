import os
import re

template_dir = r"d:\Working Project\DMS with Fast API\templates"

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
    
    return content

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
