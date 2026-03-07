import os, re

def check_templates():
    template_dir = 'app/templates'
    all_templates = set()
    for r, d, f in os.walk(template_dir):
        for name in f:
            if name.endswith('.html'):
                path = os.path.relpath(os.path.join(r, name), template_dir).replace(os.path.sep, '/')
                all_templates.add(path)

    print('=== Missing Templates in API routes ===')
    api_dir = 'app/api'
    for r, d, f in os.walk(api_dir):
        for name in f:
            if name.endswith('.py'):
                content = open(os.path.join(r, name), encoding='utf-8').read()
                matches = re.findall(r"render\(['\"]([^'\"]+\.html)['\"]", content)
                for t in matches:
                    if t not in all_templates:
                        print(f'  [ERROR] {name} references non-existent template: {t}')

def check_unused_routers():
    print('\n=== Unused API routers ===')
    main_content = open('app/main.py', encoding='utf-8').read()
    for f in os.listdir('app/api'):
        if f.endswith('.py') and f != '__init__.py' and f != 'base_api.py':
            mod = f.replace('.py', '')
            if mod not in main_content:
                print(f'  [WARNING] {f} might not be included in main.py')

def check_unsecured_routes():
    print('\n=== Potentially Unsecured API Routes (Missing Current User) ===')
    for f in os.listdir('app/api'):
        if not f.endswith('.py') or f in ['auth_api.py', 'public_admission_api.py', '__init__.py']:
            continue
        content = open(f'app/api/{f}', encoding='utf-8').read()
        routes = re.split(r'@router\.', content)
        for route in routes[1:]:
            if 'Depends(get_current_user)' not in route and 'get_current_user' not in route:
                name_match = re.search(r'def\s+(\w+)', route)
                path_match = re.search(r'[\"\']([/\w\{\}\-]+)[\"\']', route)
                name = name_match.group(1) if name_match else 'unknown'
                path = path_match.group(1) if path_match else 'unknown'
                print(f'  [WARNING] {f} -> {name} ({path}) might be unsecured')

if __name__ == '__main__':
    check_templates()
    check_unused_routers()
    check_unsecured_routes()
