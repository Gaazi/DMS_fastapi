from sqlmodel import SQLModel, Field

class CourseStaffLink(SQLModel, table=True):
    __tablename__ = "dms_course_instructors"
    course_id: int = Field(foreign_key="dms_course.id", primary_key=True)
    staff_id: int = Field(foreign_key="dms_staff.id", primary_key=True)

class StudentParentLink(SQLModel, table=True):
    __tablename__ = "dms_student_parents"
    student_id: int = Field(foreign_key="dms_student.id", primary_key=True)
    parent_id: int = Field(foreign_key="dms_parent.id", primary_key=True)

class AnnouncementTargetParentLink(SQLModel, table=True):
    __tablename__ = "dms_announcement_target_parents"
    announcement_id: int = Field(foreign_key="dms_announcement.id", primary_key=True)
    parent_id: int = Field(foreign_key="dms_parent.id", primary_key=True)
