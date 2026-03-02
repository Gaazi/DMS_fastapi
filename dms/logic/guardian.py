from django.db.models import Sum
from ..models import Student, Attendance, Fee

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: GuardianManager (Line 14)
   - Dashboard:
     * get_dashboard_context (Line 26) - Aggregated data for parents
"""

class GuardianManager:
    """Business logic and security for the Guardian/Parent dashboard"""
    
    def __init__(self, user, institution=None):
        """یوزر اور اس کے سرپرست (Guardian) پروفائل کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        self.parent = getattr(user, "parent", None)
        self.institution = institution
        
        # Fallback resolution
        if not self.institution and self.parent:
            self.institution = self.parent.institution

    def get_dashboard_context(self):
        """والدین کے ڈیش بورڈ کے لیے ان کے بچوں کی حاضری اور فیس کا مکمل ڈیٹا اکٹھا کرنا۔"""
        from ..models import Student, Attendance, Fee
        from django.db.models import Sum
        from django.core.exceptions import PermissionDenied
        from django.http import Http404
        
        # 1. Security & Institution Resolution
        if self.institution:
            # Check if parent is allowed to access this specific institution slug
            if self.parent and self.parent.institution_id != self.institution.id and not self.user.is_superuser:
                raise PermissionDenied("You do not have access to this institution.")
        elif self.parent:
            # Fallback to parent's home institution
            self.institution = self.parent.institution

        # 2. Final security check (Must be a parent, superuser, or institution owner)
        if not self.parent and not (self.user.is_superuser or (self.institution and self.user == self.institution.user)):
            raise Http404("No guardian profile linked to this account.")

        # 3. Data Query Logic
        if self.parent:
            students_qs = self.parent.students.all()
            if self.institution:
                students_qs = students_qs.filter(institution=self.institution)
        else:
            # Admin view of guardian context (if any)
            students_qs = Student.objects.filter(institution=self.institution)

        students = students_qs.select_related("institution")
        
        # Latest attendance (Last 10 records)
        attendance = Attendance.objects.filter(student__in=students).select_related("student", "session").order_by("-session__date")[:10]
        
        # Fee Records
        fees = Fee.objects.filter(student__in=students).select_related("student").order_by("-due_date")[:10]
        
        # Aggregate totals for the overview tab
        totals = Fee.objects.filter(student__in=students).aggregate(
            due=Sum('amount_due'),
            paid=Sum('amount_paid')
        )
        
        return {
            "parent": self.parent,
            "institution": self.institution,
            "students": students,
            "attendance": attendance,
            "fees": fees,
            "total_due": totals['due'] or 0,
            "total_paid": totals['paid'] or 0,
        }
