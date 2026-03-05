"""
INDEX / TABLE OF CONTENTS:
--------------------------
Variables:
   - VALID_TYPES (Line 11) - Allowed institution types
   - TYPE_LABELS (Line 13) - Metadata for dashboards
   - STATUS_CHOICES_URDU (Line 31) - Attendance display names
"""

VALID_TYPES = {"masjid", "madrasa", "maktab"}

TYPE_LABELS = {
    "masjid": {
        "title": "Masjid Management",
        "description": "Track donations, Courses, and staff for your masjid.",
        "cta": "View masjid dashboard",
    },
    "madrasa": {
        "title": "Madrasa Operations",
        "description": "Monitor students, classes, and finances for your madrasa.",
        "cta": "View madrasa dashboard",
    },
    "maktab": {
        "title": "Maktab Oversight",
        "description": "Oversee maktab classes, attendance, and community support.",
        "cta": "View maktab dashboard",
    },
}

STATUS_CHOICES_URDU = [
    ("present", "حاضر"),
    ("absent", "غیر حاضر"),
    ("late", "دیر سے"),
    ("excused", "معذور"),
]

ABSENCE_STATUSES = ("absent", "late", "excused")
