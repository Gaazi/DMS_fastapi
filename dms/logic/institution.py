from django.db import transaction, models
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.core.cache import cache

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: InstitutionManager (Line 15)
   - Dashboard:
     * get_dashboard_data (Line 48) - Core Stats & Overview
     * get_quick_alerts (Line 122) - Defaulters & Capacity
   - Utilities:
     * get_currency_label (Line 146)
"""

class InstitutionManager:
    """Core logic layer for institution-level operations and configurations"""
    
    def __init__(self, user, institution=None):
        """یوزر اور ادارے کے سیاق و سباق (Context) کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        self.institution = institution
        
        # If institution is not provided, try to resolve from user profiles
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'): # For institution owners
                self.institution = user.institution_set.first()

    def _check_access(self):
        """سیکیورٹی چیک: یہ یقینی بنانا کہ یوزر کے پاس ادارے کی مینجمنٹ کی اجازت ہے۔"""
        from django.core.exceptions import PermissionDenied
        
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("Institution context not found.")

        # 1. Check Owner
        if self.user.id == self.institution.user_id:
            return True
            
        # 2. Check Staff
        staff = getattr(self.user, 'staff', None)
        if staff and staff.institution_id == self.institution.id:
            return True
            
        raise PermissionDenied("Access denied: You are not authorized to manage this institution.")
        return True

    def get_dashboard_data(self):
        """ڈیش بورڈ کے لیے تمام اہم معلومات (مالیات، حاضری، سیشنز، الرٹس) اکٹھی کرنا۔"""
        self._check_access()
        from ..models import ClassSession, Income, Expense
        from .finance import FinanceManager
        from .attendance import AttendanceManager
        
        today = timezone.localdate()
        
        # 1. Check Admin / Owner status for Finance visibility
        from .roles import Role
        is_owner = self.institution.user_id == self.user.id
        staff = getattr(self.user, 'staff', None)
        is_admin = self.user.is_superuser or is_owner or (staff and staff.role in [Role.ADMIN.value, Role.ACCOUNTANT.value])
        
        # 1. Financial Overview (Only for Admin/Owner)
        if is_admin:
            fm = FinanceManager(self.user, institution=self.institution)
            finance = fm.institution_summary()
            analytics = fm.analytics()
            chart_data = analytics.get('chart_data', {})
        else:
            finance = {'revenue': {'total': 0}, 'total_expenses': 0, 'balance': 0}
            chart_data = {}
        
        # 2. Attendance Summary
        am = AttendanceManager(self.user, self.institution)
        attendance = am.get_todays_live_summary()
        
        # 3. Class Sessions
        recent_sessions = ClassSession.objects.filter(
            course__institution=self.institution
        ).select_related("course").order_by("-date", "-id")[:5]
        
        upcoming_sessions = ClassSession.objects.filter(
            course__institution=self.institution, 
            date__gte=today
        ).select_related("course").order_by("date", "start_time")[:5]

        # 4. Alerts & Reminders
        alerts = self.get_quick_alerts()

        # 5. Recent Transactions for Detail View (Only for Admin/Owner)
        if is_admin:
            recent_donations = Income.objects.filter(institution=self.institution).select_related('donor').order_by('-date', '-id')
            recent_expenses = Expense.objects.filter(institution=self.institution).order_by('-date', '-id')
            latest_inc = recent_donations.first()
            latest_exp = recent_expenses.first()
            donations_preview = recent_donations[:10]
            expenses_preview = recent_expenses[:10]
        else:
            latest_inc = None
            latest_exp = None
            donations_preview = []
            expenses_preview = []

        # 🚀 Optimization: Cache main stats (Students, Staff, Courses, Facilities)
        stats_cache_key = f"inst_{self.institution.id}_main_stats"
        stats = cache.get(stats_cache_key)
        
        if stats is None:
            from ..models import Student, Staff, Course, Facility
            # FIX: Use direct Manager instead of reverse relation
            student_stats = Student.objects.filter(institution=self.institution).aggregate(
                active=Count('id', filter=Q(is_active=True)),
                new_this_month=Count('id', filter=Q(enrollment_date__month=today.month, enrollment_date__year=today.year))
            )
            stats = {
                'students': student_stats['active'],
                # FIX: Use direct Manager
                'staff': Staff.objects.filter(institution=self.institution, is_active=True).count(),
                'courses': Course.objects.filter(institution=self.institution, is_active=True).count(),
                'facilities': Facility.objects.filter(institution=self.institution).count(),
                'student_details': student_stats # To keep the dictionary structure
            }
            cache.set(stats_cache_key, stats, 60)
        else:
            student_stats = stats['student_details']

        import json
        return {
            'institution': self.institution,
            'is_admin': is_admin,
            'currency_label': self.get_currency_label(self.institution),
            'stats': stats,
            'finance': finance,
            'attendance': attendance,
            'recent_sessions': recent_sessions,
            'upcoming_sessions': upcoming_sessions,
            'alerts': alerts,
            
            # Additional combined fields for dashboard and detail
            'total_donations': finance['revenue']['total'],
            'total_expenses': finance['total_expenses'],
            'balance': finance['balance'],
            'donations': donations_preview,
            'expenses': expenses_preview,
            'latest_donation_amount': latest_inc.amount if latest_inc else 0,
            'latest_donation_date': latest_inc.date if latest_inc else None,
            'latest_expense_amount': latest_exp.amount if latest_exp else 0,
            'latest_expense_date': latest_exp.date if latest_exp else None,
            'today_attendance': attendance.get('present_count', 0),
            'students': student_stats,
            'staff_count': stats['staff'],
            'active_Courses': stats['courses'],
            'today': today,
            'chart_data': {
                'labels': json.dumps(chart_data.get('labels', [])),
                'income': json.dumps(chart_data.get('income', [])),
                'expense': json.dumps(chart_data.get('expense', [])),
            },
        }

    
    # def get_quick_alerts(self):
    #     """سسٹم کے خودکار الرٹس تیار کرنا، جیسے فیس نادہندگان اور بھری ہوئی کلاسیں۔"""
    #     # Note: This is read-only but uses institution context
    #     defaulters = self.institution.students.annotate(
    #         overdue_count=Count('fees', filter=Q(fees__status='overdue'))
    #     ).filter(overdue_count__gte=3).only('name', 'id')[:5]
    #     
    #     full_classes = self.institution.courses.annotate(
    #         enrolled=Count('enrollments')
    #     ).filter(capacity__gt=0, enrolled__gte=F('capacity') * 0.9).only('title', 'capacity')[:5]

    #     return {
    #         'defaulters': defaulters,
    #         'full_classes': full_classes,
    #         'count': defaulters.count() + full_classes.count()
    #     }


    
    def get_quick_alerts(self):
        """سسٹم کے خودکار الرٹس تیار کرنا، جیسے فیس نادہندگان اور بھری ہوئی کلاسیں۔"""
        from ..models import Course

        # 1. فیس نادہندگان
        defaulters_qs = self.institution.student_set.annotate(
            overdue_count=Count('fees', filter=Q(fees__status='overdue'))
        ).filter(overdue_count__gte=3)
        
        # 2. بھری ہوئی کلاسیں (MySQL Error Fix: Evaluate in Python)
        all_active_courses = Course.objects.filter(
            institution=self.institution, 
            is_active=True, 
            capacity__gt=0
        ).annotate(
            enrolled=Count('enrollments', filter=Q(enrollments__status='active'))
        ).only('title', 'capacity')
        
        full_classes = [c for c in all_active_courses if c.enrolled >= (c.capacity * 0.9)][:5]

        return {
            'defaulters': defaulters_qs.only('name', 'id')[:5],
            'full_classes': full_classes,
            # Fix for MySQL HAVING clause error: use len() instead of count()
            'count': defaulters_qs.count() + len(full_classes)
        }

    def get_courses_summary(self):
        """تمام تعلیمی پروگراموں کا خلاصہ، جس میں طلبہ کی تعداد بھی شامل ہو۔"""
        return self.institution.courses.annotate(
            student_count=Count('enrollments')
        ).order_by('title')

    @staticmethod
    def get_currency_label(institution=None):
        """ادارے یا سسٹم کی ڈیفالٹ کرنسی (مثلاً Rs. یا USD) کا لیبل حاصل کرنا۔"""
        from django.conf import settings
        fallback = getattr(settings, "DMS_DEFAULT_CURRENCY_LABEL", "Rs")
        if not institution:
            return fallback

        # Dynamic attribute lookup for various common field names
        for attr in ("currency_label", "currency_code", "currency", "default_currency", "preferred_currency"):
            value = getattr(institution, attr, None)
            if isinstance(value, str):
                value = value.strip()
            if value:
                return str(value)
        return fallback
