from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, delete, desc
from datetime import date as dt_date

from app.models import Exam, ExamResult, Student, Course, Institution
from app.logic.audit import AuditLogic


class ExamLogic:
    """امتحانات، نمبر اور رزلٹ کارڈ مینیج کرنا (FastAPI/SQLModel)"""

    def __init__(self, session: Session, user: Any,
                 exam: Optional[Exam] = None,
                 institution: Optional[Institution] = None):
        self.session = session
        self.user = user
        self.exam = exam

        if exam:
            self.institution = institution or self.session.get(Institution, exam.inst_id)
        else:
            self.institution = institution

    # ── Context helpers ──────────────────────────────────────────────────────

    def get_list_context(self) -> dict:
        """امتحانات کی فہرست کا context۔"""
        exams = self.session.exec(
            select(Exam).where(Exam.inst_id == self.institution.id)
            .order_by(desc(Exam.date), desc(Exam.id))
        ).all()
        return {"exams": exams}

    def get_record_marks_context(self, exam_id: int) -> Optional[dict]:
        """نمبر درج کرنے کے صفحے کا context۔"""
        exam = self.session.get(Exam, exam_id)
        if not exam or exam.inst_id != self.institution.id:
            return None
        self.exam = exam
        students = self.session.exec(
            select(Student).where(Student.inst_id == self.institution.id, Student.is_active == True)
        ).all()
        courses = self.session.exec(
            select(Course).where(Course.inst_id == self.institution.id, Course.is_active == True)
        ).all()
        students_data = [{"id": s.id, "name": s.name, "reg_id": s.reg_id or "-"} for s in students]
        courses_data = [{"id": c.id, "title": c.title} for c in courses]
        import json
        return {
            "exam": exam, 
            "students": students, 
            "courses": courses,
            "students_json": json.dumps(students_data),
            "courses_json": json.dumps(courses_data)
        }

    def get_report_card_context(self, exam_id: int, student_id: int) -> Optional[dict]:
        """رزلٹ کارڈ کا context۔"""
        exam = self.session.get(Exam, exam_id)
        student = self.session.get(Student, student_id)
        if not exam or not student:
            return None
        self.exam = exam
        report = self.get_student_report(student_id)
        return {"exam": exam, "student": student, "report": report}

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save_exam(self, data: dict):
        """امتحان محفوظ کریں یا اپڈیٹ کریں۔"""
        exam_id = data.get("id")
        if exam_id:
            exam = self.session.get(Exam, int(exam_id))
            if not exam or exam.inst_id != self.institution.id:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Exam not found")
            for k, v in data.items():
                if hasattr(exam, k): setattr(exam, k, v)
        else:
            exam = Exam(
                inst_id=self.institution.id,
                title=data.get("title"),
                date=data.get("date"),
                is_active=True,
            )
            self.session.add(exam)
        self.session.commit()
        return True, "Exam saved.", exam

    def record_marks(self, marks_data: List[Dict], exam_id: int = None):
        """طلبہ کے نمبر بلک میں محفوظ کریں۔"""
        exam = self.exam or (self.session.get(Exam, exam_id) if exam_id else None)
        if not exam:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Exam context required.")

        student_ids = [int(e["student_id"]) for e in marks_data]
        self.session.exec(
            delete(ExamResult).where(
                ExamResult.exam_id == exam.id,
                ExamResult.student_id.in_(student_ids),
            )
        )
        count = 0
        for entry in marks_data:
            self.session.add(ExamResult(
                exam_id=exam.id,
                student_id=entry["student_id"],
                course_id=entry["course_id"],
                obtained_marks=int(entry["obtained"]),
                total_marks=int(entry.get("total", 100)),
                teacher_remarks=entry.get("remarks", ""),
            ))
            count += 1

        AuditLogic.log_activity(
            self.session, self.institution.id, self.user.id,
            "record_marks", "Exam", exam.id,
            f"Marks for {count} students", marks_data,
        )
        self.session.commit()
        return True, f"{count} records saved.", count

    def get_student_report(self, student_id: int) -> dict:
        """ایک طالب علم کا مکمل رزلٹ کارڈ۔"""
        results = self.session.exec(
            select(ExamResult).where(
                ExamResult.exam_id == self.exam.id,
                ExamResult.student_id == student_id,
            )
        ).all()

        subjects, total_got, total_max, has_failed = [], 0, 0, False
        for r in results:
            total_got += r.obtained_marks
            total_max += r.total_marks
            p = (r.obtained_marks / r.total_marks * 100) if r.total_marks > 0 else 0
            passed = p >= 40
            if not passed: has_failed = True
            course = self.session.get(Course, r.course_id)
            subjects.append({
                "name": course.title if course else f"Course #{r.course_id}",
                "max": r.total_marks, "got": r.obtained_marks,
                "status": "Pass" if passed else "Fail",
                "percentage": round(p, 1),
            })

        final_p = (total_got / total_max * 100) if total_max > 0 else 0
        return {
            "subjects": subjects,
            "total_got": total_got, "total_max": total_max,
            "percentage": round(final_p, 2),
            "status": "Fail" if (has_failed or final_p < 40) else "Pass",
        }