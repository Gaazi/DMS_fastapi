from decimal import Decimal
from django.db.models import Sum, F, Window
from django.db.models.functions import Rank
from django.db import transaction

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: ExamManager (Line 16)
   - Result Management:
     * record_marks (Line 23) - Bulk save student results
     * get_student_report (Line 54) - Student result card
"""

class ExamManager:
    """امتحانات، پوزیشنز اور رزلٹ کارڈ مینیج کرنے کی ایڈوانس سروس کلاس"""

    def __init__(self, exam_obj):
        """امتحان کے مخصوص آبجیکٹ کے ساتھ امتحان مینیجر کو شروع کرنا۔"""
        self.exam = exam_obj

    @transaction.atomic
    def record_marks(self, marks_data):
        """طلبہ کے حاصل کردہ نمبروں کو بلک میں محفوظ کرنا، پرانے ریکارڈز کو اپڈیٹ کرتے ہوئے۔"""
        from ..models import ExamResult
        
        # 1. پہلے سے موجود ریکارڈز کو ڈھونڈنا (تاکہ ڈبلنگ نہ ہو)
        student_ids = [entry['student_id'] for entry in marks_data]
        Course_ids = [entry['Course_id'] for entry in marks_data]
        
        # اس امتحان کے موجودہ ریکارڈز کو ایک ہی بار میں ڈیلیٹ کر دیں
        ExamResult.objects.filter(
            exam=self.exam,
            student_id__in=student_ids,
            Course_id__in=Course_ids
        ).delete()

        # 2. نئے ریکارڈز کی لسٹ تیار کرنا
        results_to_create = [
            ExamResult(
                exam=self.exam,
                student_id=entry['student_id'],
                Course_id=entry['Course_id'],
                obtained_marks=int(entry['obtained']),
                total_marks=int(entry.get('total', 100))
            )
            for entry in marks_data
        ]

        # 3. بلک کریٹ
        ExamResult.objects.bulk_create(results_to_create)
        
        return True, f"{len(results_to_create)} ریکارڈز کامیابی سے محفوظ ہو گئے۔"

    def get_student_report(self, student):
        """کسی مخصوص طالب علم کا رزلٹ کارڈ تیار کرنا، بشمول فیصد اور پاس/فیل اسٹیٹس۔"""
        results = student.exam_results.filter(exam=self.exam).select_related('Course')
        
        subject_list = []
        total_obtained = 0
        total_max = 0
        has_failed = False

        for r in results:
            total_obtained += r.obtained_marks
            total_max += r.total_marks
            
            p = r.percentage
            is_pass = p >= 40
            if not is_pass: has_failed = True

            subject_list.append({
                'name': r.Course.title,
                'max': r.total_marks,
                'got': r.obtained_marks,
                'status': 'پاس' if is_pass else 'فیل',
                'grade': r.grade
            })

        percentage = (total_obtained / total_max * 100) if total_max > 0 else 0
        final_status = "ناکام" if (has_failed or percentage < 40) else "کامیاب"

        return {
            'subjects': subject_list,
            'grand_total': total_obtained,
            'max_total': total_max,
            'percentage': round(percentage, 2),
            'status': final_status
        }