from enum import Enum

class Role(str, Enum):
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice_president"
    GENERAL_SECRETARY = "general_secretary"
    JOINT_SECRETARY = "joint_secretary"
    COMMITTEE_MEMBER = "committee_member"
    ADMIN = "administrator"
    ACCOUNTANT = "accountant"
    ACADEMIC_HEAD = "academic_head"
    IMAM = "imam"
    MUEZZIN = "muezzin"
    TEACHER = "teacher"
    SUPPORT = "support"
    VOLUNTEER = "volunteer"

    @classmethod
    def choices(cls):
        return [
            (cls.PRESIDENT.value, "صدر / متولی"),
            (cls.VICE_PRESIDENT.value, "نائب صدر"),
            (cls.GENERAL_SECRETARY.value, "جنرل سیکرٹری / معتمد"),
            (cls.JOINT_SECRETARY.value, "جوائنٹ سیکرٹری / نائب معتمد"),
            (cls.COMMITTEE_MEMBER.value, "رکن کمیٹی / ممبر شوریٰ"),
            (cls.ADMIN.value, "سسٹم منتظم / Admin"),
            (cls.ACCOUNTANT.value, "خزانچی / ناظم مالیات"),
            (cls.ACADEMIC_HEAD.value, "مہتمم / ناظم تعلیمات"),
            (cls.IMAM.value, "امام / خطیب"),
            (cls.MUEZZIN.value, "مؤذن"),
            (cls.TEACHER.value, "مدرس / استاد"),
            (cls.SUPPORT.value, "خادم / خدمت گار"),
            (cls.VOLUNTEER.value, "رضاکار"),
        ]
