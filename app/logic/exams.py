from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, delete, and_
from decimal import Decimal

# Models
from ..models import Exam, ExamResult, Student, Course, Institution
from .audit import AuditManager

class ExamManager:
    """امتحانات، پوزیشنز اور رزلٹ کارڈ مینیج کرنے کی ایڈوانس سروس کلاس (FastAPI/SQLModel Version)"""
    
    def __init__(self, session: Session, user: Any, exam: Exam):
        """امتحان کے مخصوص آبجیکٹ اور سیشن کے ساتھ امتحان مینیجر کو شروع کرنا۔"""
        self.exam = exam
        self.session = session
        self.user = user
        self.institution = self.session.get(Institution, exam.inst_id)

    def record_marks(self, marks_data: List[Dict]):
        """طلبہ کے حاصل کردہ نمبروں کو بلک میں محفوظ کرنا، پرانے ریکارڈز کو اپڈیٹ کرتے ہوئے۔"""
        student_ids = [int(entry['student_id']) for entry in marks_data]
        
        # 1. پرانے ریکارڈز حذف کریں (اگر اسی امتحان اور طالب علموں کے لیے ہوں)
        stmt = delete(ExamResult).where(
            ExamResult.exam_id == self.exam.id,
            ExamResult.student_id.in_(student_ids)
        )
        self.session.exec(stmt)
        
        # 2. نئے ریکارڈز شامل کریں
        count = 0
        for entry in marks_data:
            res = ExamResult(
                exam_id=self.exam.id,
                student_id=entry['student_id'],
                course_id=entry['course_id'],
                obtained_marks=int(entry['obtained']),
                total_marks=int(entry.get('total', 100)),
                teacher_remarks=entry.get('remarks', "")
            )
            self.session.add(res)
            count += 1
            
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'record_marks', 'Exam', self.exam.id, f"Marks for {count} students", marks_data)
        self.session.commit()
        return True, f"{count} records saved successfully.", count


    def get_student_report(self, student_id: int):
        """کسی مخصوص طالب علم کا رزلٹ کارڈ تیار کرنا۔"""
        stmt = select(ExamResult).where(ExamResult.exam_id == self.exam.id, ExamResult.student_id == student_id)
        results = self.session.exec(stmt).all()
        
        subject_list = []
        total_obtained = 0
        total_max = 0
        has_failed = False

        for r in results:
            total_obtained += r.obtained_marks
            total_max += r.total_marks
            
            # حاصل کردہ نمبروں کا تناسب
            p = (r.obtained_marks / r.total_marks * 100) if r.total_marks > 0 else 0
            is_pass = p >= 40
            if not is_pass: has_failed = True
            
            course = self.session.get(Course, r.course_id)
            course_name = course.title if course else f"Course #{r.course_id}"

            subject_list.append({
                'name': course_name,
                'max': r.total_marks,
                'got': r.obtained_marks,
                'status': 'Pass' if is_pass else 'Fail',
                'percentage': round(p, 1)
            })

        final_p = (total_obtained / total_max * 100) if total_max > 0 else 0
        status = "Fail" if (has_failed or final_p < 40) else "Pass"

        return {
            'subjects': subject_list,
            'total_got': total_obtained,
            'total_max': total_max,
            'percentage': round(final_p, 2),
            'status': status
        }