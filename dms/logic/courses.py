from django.db import transaction
from django.shortcuts import get_object_or_404
from ..models import Enrollment, ClassSession, Attendance

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: CourseManager (Line 19)
   - Course Management:
     * save_Course (Line 63)
     * delete_Course (Line 76)
   - Student Enrollments:
     * enroll_student_form (Line 89)
     * update_enrollment (Line 121)
     * delete_enrollment (Line 133)
   - Class Sessions:
     * save_session_form (Line 101)
     * delete_session (Line 143)
   - View Logic:
     * handle_detail_actions (Line 155)
     * get_detail_context (Line 192)
"""

class CourseManager:
    """Business logic for courses, enrollments, and class sessions"""
    
    def __init__(self, user, target=None, institution=None):
        """یوزر، ادارے یا کسی مخصوص تعلیمی پروگرام (Course) کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        from ..models import Institution, Course
        
        if isinstance(target, Institution):
             self.institution = target
             self.course = None
        elif isinstance(target, Course):
             self.course = target
             self.institution = target.institution
        else:
             self.course = None
             self.institution = institution
             
        # Resolve institution from user profile if not provided
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def _check_access(self):
        """سیکیورٹی چیک: پروگرام اور داخلوں کی مینجمنٹ کے حقوق کی تصدیق۔"""
        from django.core.exceptions import PermissionDenied
        
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("Institution context missing.")

        is_owner = (self.user == self.institution.user)
        is_staff = hasattr(self.user, 'staff') and (self.user.staff.institution == self.institution)
        
        if not (is_owner or is_staff):
            raise PermissionDenied("Access denied to Course management.")
        return True

    @transaction.atomic
    def save_course(self, form):
        """نئے تعلیمی پروگرام (Course) کا اندراج کرنا یا پرانے کو اپڈیٹ کرنا۔"""
        self._check_access()
        try:
            course = form.save(commit=False)
            course.institution = self.institution
            course.save()
            form.save_m2m()
            term = "Program" if self.institution.type == 'masjid' else "Course"
            return True, f"{term} information has been saved successfully.", course
        except Exception as e:
            return False, f"Error saving course: {str(e)}", None

    def delete_course(self, course_id):
        """کسی پروگرام اور اس سے جڑے تمام ریکارڈز (داخلے، سیشنز) کو حذف کرنا۔"""
        self._check_access()
        try:
            from ..models import Course
            course = get_object_or_404(Course, pk=course_id, institution=self.institution)
            name = course.title
            course.delete()
            term = "Program" if self.institution.type == 'masjid' else "Course"
            return True, f"{term} '{name}' has been deleted.", None
        except Exception as e:
            return False, f"Error deleting course: {str(e)}", None

    @transaction.atomic
    def enroll_student_form(self, form):
        """کسی طالب علم کو مخصوص پروگرام میں داخل (Enroll) کرنے کی لاجک۔"""
        self._check_access()
        try:
            enrollment = form.save(commit=False)
            enrollment.course = self.course
            enrollment.save()
            return True, "Student enrollment has been completed.", enrollment
        except Exception as e:
            return False, f"Enrollment error: {str(e)}", None

    @transaction.atomic
    def save_session_form(self, form):
        """تعلیمی پروگرام کے تحت ایک انفرادی کلاس سیشن کا شیڈول بنانا۔"""
        self._check_access()
        try:
            session = form.save(commit=False)
            session.course = self.course
            session.save()
            return True, "Class session scheduled successfully.", session
        except Exception as e:
            return False, f"Scheduling error: {str(e)}", None

    def get_stats(self):
        """موجودہ پروگرام کے کل طلبہ اور سیشنز کا مجموعی خلاصہ (Stats)۔"""
        if not self.course: return {}
        return {
            'total_students': self.course.enrollments.count(),
            'active_students': self.course.enrollments.filter(status='active').count(),
            'total_sessions': self.course.sessions.count()
        }

    def update_enrollment(self, enrollment_id, status=None, notes=None):
        """کسی طالب علم کے داخلے کی معلومات یا اسٹیٹس (Active/Completed) اپڈیٹ کرنا۔"""
        self._check_access()
        try:
            enrollment = get_object_or_404(Enrollment, pk=enrollment_id, course=self.course)
            if status: enrollment.status = status
            if notes: enrollment.notes = notes
            enrollment.save()
            return True, "Enrollment updated successfully.", enrollment
        except Exception as e:
            return False, f"Update failed: {str(e)}", None

    def delete_enrollment(self, enrollment_id):
        """کسی طالب علم کے داخلے کا ریکارڈ پروگرام سے ختم کرنا۔"""
        self._check_access()
        try:
            enrollment = get_object_or_404(Enrollment, pk=enrollment_id, course=self.course)
            enrollment.delete()
            return True, "Enrollment removed.", None
        except Exception as e:
            return False, f"Deletion failed: {str(e)}", None

    def delete_session(self, session_id):
        """کسی مخصوص کلاس سیشن کا ریکارڈ ڈیلیٹ کرنا۔"""
        self._check_access()
        try:
            session = get_object_or_404(ClassSession, pk=session_id, course=self.course)
            session.delete()
            return True, "Session deleted.", None
        except Exception as e:
            return False, f"Session deletion failed: {str(e)}", None

        # return False, "Validation errors in form.", form  <-- This line looked orphaned in original, removing/fixing logic flow if needed but sticking to direct replacement.

    def handle_detail_actions(self, request):
        """کورس کی تفصیلات والے صفحے سے ہونے والے مختلف کاموں (داخلہ، سیشن) کو ہینڈل کرنا۔"""
        self._check_access()
        from ..forms import EnrollmentForm, ClassSessionForm
        
        action = request.POST.get("action")
        success, message = False, "نامعلوم ایکشن کی درخواست کی گئی ہے۔"
        
        if action == "enroll":
            form = EnrollmentForm(request.POST, institution=self.institution, course=self.course, prefix="enrollment")
            if form.is_valid():
                success, message, _ = self.enroll_student_form(form)
            else:
                message = "فارم میں غلطی ہے، براہ کرم چیک کریں۔"
                
        elif action == "enrollment_update":
            success, message, _ = self.update_enrollment(
                request.POST.get("enrollment_id"), 
                status=request.POST.get("status"), 
                notes=request.POST.get("notes")
            )
            
        elif action == "enrollment_delete":
            success, message, _ = self.delete_enrollment(request.POST.get("enrollment_id"))
            
        elif action == "session":
            form = ClassSessionForm(request.POST, prefix="session")
            if form.is_valid():
                success, message, _ = self.save_session_form(form)
            else:
                message = "سیشن فارم میں غلطی ہے۔"
                
        elif action == "session_delete":
            success, message, _ = self.delete_session(request.POST.get("session_id"))

        return success, message

    def get_detail_context(self):
        """کورس کے پروفائل صفحے کے لیے تمام داخلے، سیشنز اور فارمز کا ڈیٹا تیار کرنا۔"""
        from dms.forms import EnrollmentForm, ClassSessionForm
        return {
            "institution": self.institution,
            "course": self.course,
            "enrollments": self.course.enrollments.select_related("student").order_by("-enrollment_date"),
            "sessions": self.course.sessions.order_by("-date", "-id"),
            "enrollment_form": EnrollmentForm(institution=self.institution, course=self.course, prefix="enrollment"),
            "session_form": ClassSessionForm(prefix="session"),
            "stats": self.get_stats()
        }

    @transaction.atomic
    def handle_course_actions(self, request):
        """کورسز کی فہرست والے صفحے سے آنے والے POST ایکشنز (محفوظ/حذف) کو مینیج کرنا۔"""
        self._check_access()
        from ..forms import CourseForm
        
        if "delete_course_id" in request.POST:
            return self.delete_course(request.POST.get("delete_course_id"))
            
        # Default is Save/Update
        course_id = request.POST.get("course_id")
        editing_course = None
        if course_id:
            from ..models import Course
            editing_course = get_object_or_404(Course, pk=course_id, institution=self.institution)
            
        form = CourseForm(request.POST, instance=editing_course, institution=self.institution)
        
        if form.is_valid():
            return self.save_course(form)
        
        return False, "فارم میں غلطیاں ہیں، براہ کرم درست کریں۔", form

    def get_list_context(self, request, override_form=None):
        """تمام تعلیمی پروگراموں کی فہرست اور نئے پروگرام کے لیے فارم تیار کرنا۔"""
        self._check_access()
        from ..models import Course
        from ..forms import CourseForm
        from .institution import InstitutionManager
        
        im = InstitutionManager(self.user, self.institution)
        
        edit_id = request.GET.get("edit")
        editing_course = None
        if edit_id:
            editing_course = get_object_or_404(Course, pk=edit_id, institution=self.institution)
        
        form = override_form or CourseForm(instance=editing_course, institution=self.institution)
        
        return {
            "institution": self.institution,
            "courses": im.get_courses_summary(), 
            "form": form,
            "editing_course": editing_course,
        }
