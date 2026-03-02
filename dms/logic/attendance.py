from django.db import transaction, models
from django.db.models import Count, Q, F
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from ..constants import ABSENCE_STATUSES, STATUS_CHOICES_URDU

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: AttendanceManager (Line 23)
   - Core Processing:
     * get_prepared_list (Line 99) - UI preparation
     * save_bulk (Line 155) - Save logic
   - Specific Helpers:
     * get_student_attendance_context (Line 231)
     * handle_student_attendance_actions (Line 250)
     * get_staff_attendance_context (Line 270)
   - Analytics & Reports:
     * get_todays_live_summary (Line 306)
     * get_attendance_report (Line 324)
     * get_attendance_report_context (Line 391)
"""

class AttendanceManager:
    """
    ادارے کی تمام حاضریوں (اسٹاف اور طلبہ) کا مرکزی مرکز۔
    یہ کلاس سیکیورٹی، ڈیٹا پروسیسنگ، اور رپورٹس کو یکجا کرتی ہے۔
    """
    
    def __init__(self, user, institution=None):
        """یوزر اور ادارے کی معلومات کے ساتھ حاضری مینیجر کو شروع کرنا۔"""
        self.user = user
        self.institution = institution
        
        # اگر ادارہ فراہم نہیں کیا گیا تو یوزر سے تلاش کریں
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()
        
    def _check_permission(self):
        """چیک کرنا کہ کیا موجودہ یوزر کو حاضری کے ریکارڈز دیکھنے یا تبدیل کرنے کی اجازت ہے۔"""
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("لاگ ان ضروری ہے۔")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("ادارے کی معلومات نہیں مل سکیں۔")

        is_owner = (self.user == self.institution.user)
        is_staff = hasattr(self.user, 'staff') and (self.user.staff.institution == self.institution)
        
        if not (is_owner or is_staff):
            raise PermissionDenied("آپ کو اس ادارے کے ریکارڈز تک رسائی نہیں ہے۔")
        return True

    def _normalize_id(self, val):
        """آئی ڈی (ID) کو درست عددی شکل میں لانا تاکہ ڈیٹا بیس کوئری میں غلطی نہ ہو۔"""
        if not val or str(val).lower() in ["none", "null", ""]:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def get_member_summary(self, member, type='student', limit=15):
        """کسی مخصوص طالب علم یا ملازم کی حالیہ حاضریوں کا مختصر ریکارڈ۔"""
        if type == 'staff':
            return member.daily_attendance.order_by('-date')[:limit]
        return member.session_attendance.select_related('session').order_by('-session__date')[:limit]

    def get_member_metrics(self, member, type='student'):
        """مجموعی حاضری کا فیصد اور حاضر/غیر حاضر دنوں کا تفصیلی حساب۔"""
        from ..models import Attendance, Staff_Attendance
        if type == 'staff':
            records = member.daily_attendance.all()
        else:
            records = member.session_attendance.all()
        
        total = records.count()
        breakdown = records.aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        percentage = round((breakdown['present'] / total * 100), 1) if total > 0 else 0
        
        return {
            'total_daily_records': total,
            'daily_breakdown': breakdown,
            'attendance_percentage': percentage
        }

    # --- Core Processing Logic ---

    def get_prepared_list(self, type='student', target_date=None, course_id=None):
        """فارم کے لیے طلبہ یا اسٹاف کی فہرست تیار کرنا، بشمول ان کی آج کی موجودہ صورتحال۔"""
        self._check_permission()
        from ..models import Attendance, Staff_Attendance, ClassSession
        
        target_date = target_date or timezone.localdate()
        course_id = self._normalize_id(course_id)
        
        # ماڈل اور فیلڈ کا تعین
        if type == 'staff':
            model = Staff_Attendance
            field = 'staff_member'
            members = self.institution.staff_set.filter(is_active=True).order_by("name")
            filters = {"date": target_date, "institution": self.institution}
        else:
            model = Attendance
            field = 'student'
            # صرف اسی ادارے کے طلبہ
            members = self.institution.student_set.filter(is_active=True)
            
            if course_id:
                # 🚨 بگ فکس: صرف ان طلبہ کو دکھائیں جن کا اس کورس میں داخلہ ایکٹیو یا پینڈنگ ہے (Dropped/Completed کو چھپائیں)
                members = members.filter(enrollments__course_id=course_id, enrollments__status__in=['active', 'pending'])
                filters = {
                    "session__date": target_date, 
                    "session__course_id": course_id,
                    "institution": self.institution  # ادارے کی سخت قید
                }
            else:
                filters = {
                    "session__date": target_date, 
                    "institution": self.institution  # ادارے کی سخت قید
                }
            
            members = members.order_by("name").distinct()

        # ڈیٹا میپنگ - یہاں بھی ادارے کی قید لازمی ہے
        records = model.objects.filter(**filters)
        attendance_map = {
            getattr(r, field + "_id"): {'status': r.status, 'remarks': r.remarks, 'is_late': getattr(r, 'is_late', False)}
            for r in records
        }
        
        for m in members:
            data = attendance_map.get(m.id, {'status': 'present', 'remarks': '', 'is_late': False})
            m.current_status = data['status']
            m.current_remarks = data['remarks']
            m.is_late_record = data['is_late']
            
            # Helper booleans for templates (e.g. student_list.html)
            m.is_absent = (data['status'] == 'absent')
            m.is_late = (data['status'] == 'late')
            m.is_excused = (data['status'] == 'excused')
            
        return members, target_date, course_id

    @transaction.atomic
    def save_bulk(self, type, post_data, target_date, course_id=None, fixed_session=None):
        """کئی طلبہ یا ملازمین کی حاضری ایک ساتھ ڈیٹا بیس میں محفوظ کرنا۔"""
        self._check_permission()
        from ..models import Attendance, Staff_Attendance, ClassSession, Enrollment
        
        target_date = target_date or timezone.localdate()
        course_id = self._normalize_id(course_id)
        
        if type == 'staff':
            model = Staff_Attendance
            field = 'staff_member'
            members = self.institution.staff_set.filter(is_active=True)
            session = None
        else:
            model = Attendance
            field = 'student'
            members = self.institution.student_set.filter(is_active=True)
            if course_id:
                # 🚨 بگ فکس: صرف فعال یا پینڈنگ داخلوں پر حاضری لگے (تاکہ ڈراپ آؤٹ طلبہ کے ریکارڈ نہ بنیں)
                members = members.filter(enrollments__course_id=course_id, enrollments__status__in=['active', 'pending'])
            
            # سیشنز کا کیشے (تاکہ بار بار کوئری نہ ہو)
            session_cache = {}

            def get_session_for_course(pid):
                if not pid: return None
                if pid not in session_cache:
                    s, _ = ClassSession.objects.get_or_create(
                        date=target_date, course_id=pid,
                        defaults={'topic': 'Daily Attendance'}
                    )
                    session_cache[pid] = s
                return session_cache[pid]

            # اگر مخصوص پروگرام ہے، تو ایک ہی سیشن استعمال کریں
            if not fixed_session:
                fixed_session = get_session_for_course(course_id) if course_id else None

        # ڈیٹا نکالنا اور محفوظ کرنا
        for m in members:
            status = post_data.get(f"{type}_{m.id}_status") or post_data.get(f"{type}_{m.id}")
            remarks = post_data.get(f"remarks_{m.id}", "")
            
            if status:
                filters = {field + "_id": m.id}
                if type == 'staff':
                    filters["date"] = target_date
                    current_session = None
                else:
                    # طالب علم کے لیے سیشن کا تعین
                    if fixed_session:
                        current_session = fixed_session
                    else:
                        # طالب علم کے پہلے ایکٹو پروگرام کا سیشن استعمال کریں
                        primary_enrollment = m.enrollments.filter(status='active').first() or m.enrollments.first()
                        pid = primary_enrollment.course_id if primary_enrollment else (self.institution.courses.first().id if self.institution.courses.exists() else None)
                        current_session = get_session_for_course(pid)
                    
                    if not current_session: 
                        continue 
                    filters["session"] = current_session
                
                record, created = model.objects.update_or_create(
                    **filters,
                    defaults={'status': status, 'remarks': remarks, 'institution': self.institution}
                )

                # 🚀 الرٹ: اگر طالب علم غیر حاضر ہے تو والدین کو بتائیں
                if type == 'student' and status == 'absent':
                    from .notifications import NotificationService
                    NotificationService.notify_absence(m, target_date)

                if type == 'staff' and status == 'present' and m.shift_start:
                    now_time = timezone.localtime().time()
                    if now_time > m.shift_start:
                        record.is_late = True
                        record.save(update_fields=['is_late'])
        
        return True, "حاضری کامیابی سے محفوظ کر لی گئی ہے۔"

    # --- Specific View Helpers (Thin Wrappers) ---

    def get_student_attendance_context(self, request):
        """طالب علموں کی حاضری والے صفحے کے لیے تمام ضروری ڈیٹا (تاریخ، پروگرام، طلبہ) اکٹھا کرنا۔"""
        from ..forms import DailyAttendanceDateForm
        date_val = request.GET.get("date")
        prog_val = request.GET.get("course")
        
        try: t_date = timezone.datetime.fromisoformat(date_val).date() if date_val else None
        except: t_date = None
        
        members, final_date, final_prog = self.get_prepared_list('student', t_date, prog_val)
        
        return {
            "institution": self.institution,
            "members": members,
            "selected_date": final_date,
            "date_form": DailyAttendanceDateForm(initial={'date': final_date}),
            "all_courses": self.institution.courses.all(),
            "selected_course_id": final_prog
        }

    def handle_student_attendance_actions(self, request):
        """طلبہ کی حاضری کے فارم کو وصول کرنا اور اسے محفوظ کرنے کے عمل کو مکمل کرنا۔"""
        self._check_permission()
        if request.method != "POST":
            return False, "غیر متعلقہ درخواست۔", None
            
        target_date_str = request.POST.get("date")
        course_id = request.POST.get("course")
        
        try: 
            target_date = timezone.datetime.fromisoformat(target_date_str).date() if target_date_str else None
        except (ValueError, TypeError): 
            target_date = None
        
        success, message = self.save_bulk('student', request.POST, target_date, course_id=course_id)
        
        # واپسی کے لیے ری ڈائریکٹ یو آر ایل
        redirect_url = f"{request.path}?date={target_date or ''}&course={course_id or ''}"
        return success, message, redirect_url

    def get_staff_attendance_context(self, request):
        """اسٹاف کی حاضری والے صفحے کے لیے معلومات تیار کرنا۔"""
        from ..forms import DailyAttendanceDateForm
        date_val = request.GET.get("date")
        
        try: t_date = timezone.datetime.fromisoformat(date_val).date() if date_val else None
        except: t_date = None
        
        members, final_date, _ = self.get_prepared_list('staff', t_date)
        
        return {
            "institution": self.institution,
            "members": members,
            "selected_date": final_date,
            "date_form": DailyAttendanceDateForm(initial={'date': final_date}),
        }

    def handle_staff_attendance_actions(self, request):
        """اسٹاف کی حاضری کے فارم کو پراسیس کرنا اور ریکارڈ اپڈیٹ کرنا۔"""
        self._check_permission()
        if request.method != "POST":
            return False, "غیر متعلقہ درخواست۔", None
            
        target_date_str = request.POST.get("date")
        try: 
            target_date = timezone.datetime.fromisoformat(target_date_str).date() if target_date_str else None
        except (ValueError, TypeError): 
            target_date = None
        
        success, message = self.save_bulk('staff', request.POST, target_date)
        
        # واپسی کے لیے ری ڈائریکٹ یو آر ایل (Date parameter کے ساتھ)
        redirect_url = f"{request.path}?date={target_date or ''}"
        return success, message, redirect_url

    # --- Analytics & Reports ---

    def get_todays_live_summary(self):
        """آج کی حاضری کا خلاصہ (کتنے فیصد حاضر ہیں) ڈیش بورڈ پر دکھانے کے لیے۔"""
        if not self.institution: return {'total': 0, 'present_count': 0, 'absent': 0, 'percentage': 0}
        from ..models import Attendance
        today = timezone.localdate()
        total_students = self.institution.student_set.filter(is_active=True).count()
        present_count = Attendance.objects.filter(
            session__course__institution=self.institution,
            session__date=today, status='present'
        ).values('student').distinct().count()
        
        return {
            'total': total_students,
            'present_count': present_count,
            'absent': max(0, total_students - present_count),
            'percentage': round((present_count / total_students * 100), 1) if total_students > 0 else 0
        }

    def get_attendance_report(self, start_date, end_date):
        """مخصوص دورانیے کے لیے اسٹاف اور طلبہ کی حاضری کا مکمل تجزیہ اور رپورٹ۔"""
        self._check_permission()
        from ..models import Attendance, Staff_Attendance, Student, Staff
        
        # ریکارڈز فلٹر کرنا
        staff_records = Staff_Attendance.objects.filter(institution=self.institution, date__range=[start_date, end_date])
        student_records = Attendance.objects.filter(session__course__institution=self.institution, session__date__range=[start_date, end_date])

        # جنرل ڈیٹا
        staff_active = Staff.objects.filter(institution=self.institution, is_active=True).count()
        student_active = Student.objects.filter(institution=self.institution, is_active=True).count()
        
        def process_stats(records, total_possible):
            total_rec = records.count()
            stats = records.aggregate(
                p=Count('id', filter=Q(status='present')),
                a=Count('id', filter=Q(status='absent')),
                l=Count('id', filter=Q(status='late')),
                e=Count('id', filter=Q(status='excused'))
            )
            calc = lambda x: (x / total_rec * 100) if total_rec > 0 else 0
            return [
                {'label': 'حاضر', 'count': stats['p'], 'percentage': calc(stats['p'])},
                {'label': 'غیر حاضر', 'count': stats['a'], 'percentage': calc(stats['a'])},
                {'label': 'لیٹ', 'count': stats['l'], 'percentage': calc(stats['l'])},
                {'label': 'رخصت', 'count': stats['e'], 'percentage': calc(stats['e'])},
            ], total_rec

        staff_summary, staff_total = process_stats(staff_records, staff_active)
        student_summary, student_total = process_stats(student_records, student_active)

        # اضافی ڈیٹا (جو ٹیمپلیٹ میں درکار ہے)
        staff_unique = staff_records.values('staff_member').distinct().count()
        student_unique = student_records.values('student').distinct().count()
        
        staff_days = staff_records.values('date').distinct().count()
        student_days = student_records.values('session__date').distinct().count()

        # غیر حاضریوں کی تفصیل
        staff_absences = staff_records.filter(status='absent').values(
            name=F('staff_member__name')
        ).annotate(count=Count('id')).order_by('-count')[:10]

        student_absences = student_records.filter(status='absent').values(
            name=F('student__name')
        ).annotate(count=Count('id')).order_by('-count')[:10]

        return {
            'staff_active_count': staff_active, 
            'staff_total_records': staff_total, 
            'staff_summary': staff_summary,
            'staff_unique_members': staff_unique,
            'staff_days_recorded': staff_days,
            'staff_absences': staff_absences,

            'student_active_count': student_active, 
            'student_total_records': student_total, 
            'student_summary': student_summary,
            'student_unique_members': student_unique,
            'student_days_recorded': student_days,
            'student_absences': student_absences,

            'day_span': (end_date - start_date).days + 1,
            'no_records': not (staff_records.exists() or student_records.exists())
        }

    def get_attendance_report_context(self, request):
        """حاضری رپورٹ کے صفحے کے لیے تاریخوں اور رپورٹ کے ڈیٹا کا مجموعہ۔"""
        self._check_permission()
        from ..forms import AttendanceReportForm
        
        today = timezone.localdate()
        form = AttendanceReportForm(request.GET or None, initial={
            'start_date': (today - timezone.timedelta(days=30)),
            'end_date': today
        })
        
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
        else:
            start_date = today - timezone.timedelta(days=30)
            end_date = today

        report_data = self.get_attendance_report(start_date, end_date)
        
        return {
            "institution": self.institution,
            "start_date": start_date,
            "end_date": end_date,
            "form": form,
            **report_data 
        }

    def get_session_attendance_context(self, session_id):
        """کسی مخصوص تعلیمی سیشن کی حاضری لگانے کے لیے ضروری ڈیٹا فراہم کرنا۔"""
        self._check_permission()
        from ..models import ClassSession, Attendance
        from django.shortcuts import get_object_or_404
        session = get_object_or_404(ClassSession.objects.select_related("course"), pk=session_id, course__institution=self.institution)
        course = session.course
        
        enrollments, _, _ = self.get_prepared_list('student', target_date=session.date, course_id=course.id)

        return {
            "institution": self.institution,
            "course": course,
            "session": session,
            "enrollments": enrollments,
            "attendance_choices": Attendance.Status.choices,
        }

    def handle_session_attendance_actions(self, request, session_id):
        """سیشن کی حاضری کے فارم کو وصول کر کے ریکارڈ کو اپڈیٹ کرنا۔"""
        self._check_permission()
        from ..models import ClassSession
        from django.shortcuts import get_object_or_404
        session = get_object_or_404(ClassSession.objects.select_related("course"), pk=session_id, course__institution=self.institution)
        course = session.course
        
        success, message = self.save_bulk('student', request.POST, session.date, course_id=course.id, fixed_session=session)
        
        from django.urls import reverse
        redirect_url = reverse("dms_course_detail", kwargs={
            'institution_slug': self.institution.slug, 
            'course_id': course.id
        })
        
        return success, message, redirect_url