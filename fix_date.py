import os
import re

model_files = [
    'models/people.py', 
    'models/finance.py', 
    'models/exam.py', 
    'models/attendance.py', 
    'models/inventory.py'
]

for file in model_files:
    if not os.path.exists(file): continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Change the import from "from datetime import date, time, datetime" or similar
    # We will just replace all instances of "from datetime import " ... replacing date with dt_date
    # But it's easier to just do:
    content = content.replace("from datetime import date", "from datetime import date as dt_date")
    # if it had "from datetime import date, time, datetime" -> "from datetime import date as dt_date, time, datetime"
    
    # Replace type annotations
    content = re.sub(r':\s*date\s*=', r': dt_date =', content)
    content = re.sub(r'\[date\]', r'[dt_date]', content)
    content = content.replace("date.today", "dt_date.today")

    # In case there's any remaining "from datetime import " that didn't match exactly
    # e.g., "from datetime import time, date"
    # To be safe, let's just do a specific manual replace for the known lines:
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print("Dates fixed.")
