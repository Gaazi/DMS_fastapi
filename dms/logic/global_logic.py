from django.db.models import Count, Sum
from django.core.exceptions import PermissionDenied
from ..models import Institution, Income, Expense, Student, Staff, Course
from ..constants import TYPE_LABELS, VALID_TYPES
from .institution import InstitutionManager
from .auth import UserManager

class GlobalManager:
    """Central manager for global reporting and multi-institution logic."""

    def __init__(self, user):
        self.user = user
        self._check_access()

    def _check_access(self):
        """Ensure only authenticated users can access global logic."""
        if not self.user or not self.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

    def get_global_overview(self):
        """تمام اقسام کے اداروں کا مجموعی مالیاتی اور انتظامی خلاصہ تیار کرنا۔"""
        institution_ids = UserManager.get_user_institutions(self.user).values_list('id', flat=True)
        
        summary = {
            key: {
                "meta": TYPE_LABELS[key],
                "institution_count": 0,
                "total_income": 0,
                "total_expense": 0,
                "balance": 0,
                "student_count": 0,
                "staff_count": 0,
                "course_count": 0,
            }
            for key in VALID_TYPES
        }

        # Count institutions per type (Scoped)
        qs_inst = Institution.objects.filter(id__in=institution_ids)
        for row in qs_inst.values("type").annotate(count=Count("id")):
            summary[row["type"]]["institution_count"] = row["count"]

        # Aggregate Income (Scoped)
        qs_income = Income.objects.filter(institution_id__in=institution_ids)
        for row in qs_income.values("institution__type").annotate(total=Sum("amount")):
            summary[row["institution__type"]]["total_income"] = row["total"] or 0

        # Aggregate Expenses (Scoped)
        qs_expense = Expense.objects.filter(institution_id__in=institution_ids)
        for row in qs_expense.values("institution__type").annotate(total=Sum("amount")):
            summary[row["institution__type"]]["total_expense"] = row["total"] or 0

        # Aggregate Students, Staff, and Courses (Scoped)
        qs_students = Student.objects.filter(institution_id__in=institution_ids)
        for row in qs_students.values("institution__type").annotate(count=Count("id")):
            summary[row["institution__type"]]["student_count"] = row["count"]
        
        qs_staff = Staff.objects.filter(institution_id__in=institution_ids)
        for row in qs_staff.values("institution__type").annotate(count=Count("id")):
            summary[row["institution__type"]]["staff_count"] = row["count"]

        qs_courses = Course.objects.filter(institution_id__in=institution_ids)
        for row in qs_courses.values("institution__type").annotate(count=Count("id")):
            summary[row["institution__type"]]["course_count"] = row["count"]

        # Final calculations and global totals
        total_metrics = {
            "institutions": 0, "income": 0, "expense": 0, "balance": 0, 
            "students": 0, "staff": 0, "courses": 0
        }

        for key, data in summary.items():
            data["balance"] = data["total_income"] - data["total_expense"]
            total_metrics["institutions"] += data["institution_count"]
            total_metrics["income"] += data["total_income"]
            total_metrics["expense"] += data["total_expense"]
            total_metrics["students"] += data["student_count"]
            total_metrics["staff"] += data["staff_count"]
            total_metrics["courses"] += data["course_count"]
            data["currency_label"] = InstitutionManager.get_currency_label()

        total_metrics["balance"] = total_metrics["income"] - total_metrics["expense"]
        total_metrics["currency_label"] = InstitutionManager.get_currency_label()

        return {
            "type_summary": summary,
            "totals": total_metrics,
            "type_choices": TYPE_LABELS,
            "institutions": qs_inst.annotate(
                income_total=Sum("incomes__amount"),
                expense_total=Sum("expenses__amount")
            ).order_by("name")
        }

    def get_institutions_by_type(self, inst_type):
        """کسی مخصوص قسم کے تمام متعلقہ اداروں کی فہرست حاصل کرنا۔"""
        institution_ids = UserManager.get_user_institutions(self.user).values_list('id', flat=True)
        
        return Institution.objects.filter(
            id__in=institution_ids, 
            type=inst_type
        ).annotate(
            student_count=Count("student", distinct=True),
            staff_count=Count("staff", distinct=True),
            course_count=Count("courses", distinct=True),
            total_income=Sum("incomes__amount"),
            total_expense=Sum("expenses__amount"),
        ).order_by("name")

    def get_type_list_context(self, inst_type):
        """مخصوص قسم کے اداروں والے صفحے کے لیے تمام ضروری ڈیٹا اکٹھا کرنا۔"""
        from django.http import Http404

        if inst_type not in VALID_TYPES:
            raise Http404("Unknown institution type.")

        # 1. صرف وہ ادارے لائیں جو یوزر کے ہیں
        institutions = self.get_institutions_by_type(inst_type)
        
        # 2. صرف وہ "Types" (بٹن) دکھائیں جن میں یوزر کا کوئی ادارہ موجود ہے
        user_inst_ids = UserManager.get_user_institutions(self.user).values_list('id', flat=True)
        user_inst_types = Institution.objects.filter(id__in=user_inst_ids).values_list('type', flat=True).distinct()
        
        scoped_type_choices = {
            k: v for k, v in TYPE_LABELS.items() 
            if k in user_inst_types
        }
            
        return {
            "institutions": institutions,
            "institution_type": inst_type,
            "type_meta": TYPE_LABELS[inst_type],
            "type_choices": scoped_type_choices,
            "currency_label": InstitutionManager.get_currency_label()
        }
