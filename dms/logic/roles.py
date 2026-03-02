from django.db import models

class Role(models.TextChoices):
    PRESIDENT = "president", "صدر / متولی"
    VICE_PRESIDENT = "vice_president", "نائب صدر"
    GENERAL_SECRETARY = "general_secretary", "جنرل سیکرٹری / معتمد"
    JOINT_SECRETARY = "joint_secretary", "جوائنٹ سیکرٹری / نائب معتمد"
    COMMITTEE_MEMBER = "committee_member", "رکن کمیٹی / ممبر شوریٰ"
    ADMIN = "administrator", "سسٹم منتظم / Admin"
    ACCOUNTANT = "accountant", "خزانچی / ناظم مالیات"
    ACADEMIC_HEAD = "academic_head", "مہتمم / ناظم تعلیمات"
    IMAM = "imam", "امام / خطیب"
    MUEZZIN = "muezzin", "مؤذن"
    TEACHER = "teacher", "مدرس / استاد"
    SUPPORT = "support", "خادم / خدمت گار"
    VOLUNTEER = "volunteer", "رضاکار"
