from ..models import TimetableItem, Course, Staff, Facility

class ScheduleManager:
    """ٹائم ٹیبل اور ہفتہ وار شیڈول مینیج کرنے کی لاجک۔"""

    def __init__(self, user, institution=None):
        self.user = user
        self.institution = institution
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def get_weekly_matrix(self, course_id=None, staff_id=None):
        """ہفتہ وار ٹائم ٹیبل کو ایک گرڈ (Grid) کی شکل میں تیار کرنا۔"""
        filters = {"institution": self.institution, "is_active": True}
        if course_id:
            filters["course_id"] = course_id
        if staff_id:
            filters["teacher_id"] = staff_id
            
        items = TimetableItem.objects.filter(**filters).order_by('start_time')
        
        # ہفتے کے سات دنوں کے لیے خالی ڈکشنری
        matrix = {day: [] for day, label in TimetableItem.DayOfWeek.choices}
        
        for item in items:
            matrix[item.day_of_week].append(item)
            
        return matrix

    def check_conflict(self, day, start, end, teacher_id=None, facility_id=None):
        """چیک کرنا کہ کیا اس وقت استاد یا کلاس روم پہلے سے مصروف تو نہیں (Conflict Check)۔"""
        conflicts = TimetableItem.objects.filter(
            institution=self.institution,
            day_of_week=day,
            is_active=True,
            start_time__lt=end,
            end_time__gt=start
        )
        
        if teacher_id:
            if conflicts.filter(teacher_id=teacher_id).exists():
                return True, "استاد اس وقت پہلے ہی کسی اور کلاس میں مصروف ہیں۔"
        
        if facility_id:
            if conflicts.filter(facility_id=facility_id).exists():
                return True, "یہ کمرہ/ہال اس وقت پہلے ہی استعمال میں ہے۔"
                
        return False, None

    def get_schedule_context(self, course_id=None):
        """ٹائم ٹیبل کے صفحے کے لیے ڈیٹا۔"""
        matrix = self.get_weekly_matrix(course_id=course_id)
        courses = Course.objects.filter(institution=self.institution, is_active=True)
        staff = Staff.objects.filter(institution=self.institution, is_active=True)
        
        return {
            "matrix": matrix,
            "courses": courses,
            "staff_members": staff,
            "days": TimetableItem.DayOfWeek.choices,
            "selected_course": course_id
        }
