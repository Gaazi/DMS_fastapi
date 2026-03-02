from sqladmin import ModelView
from app.models.foundation import Institution, Course, Facility
from app.models.schedule import TimetableItem
from app.models.attendance import ClassSession

class InstitutionAdmin(ModelView, model=Institution):
    column_list = [Institution.id, Institution.name, Institution.slug, Institution.reg_id]
    column_searchable_list = [Institution.name, Institution.reg_id]
    category = "Core"
    icon = "fa-solid fa-hotel"

class CourseAdmin(ModelView, model=Course):
    column_list = [Course.id, Course.title, Course.category, Course.admission_fee, Course.course_fee, Course.inst_id]
    column_searchable_list = [Course.title, Course.category]
    category = "Core"
    icon = "fa-solid fa-graduation-cap"

class FacilityAdmin(ModelView, model=Facility):
    column_list = [Facility.id, Facility.name, Facility.facility_type, Facility.inst_id]
    category = "Core"
    icon = "fa-solid fa-building"

class TimetableAdmin(ModelView, model=TimetableItem):
    column_list = [TimetableItem.id, TimetableItem.course_id, TimetableItem.day_of_week, TimetableItem.start_time, TimetableItem.end_time]
    category = "Schedule"
    icon = "fa-solid fa-calendar-days"

class ClassSessionAdmin(ModelView, model=ClassSession):
    column_list = [ClassSession.id, ClassSession.course_id, ClassSession.date, ClassSession.start_time, ClassSession.end_time]
    category = "Schedule"
    icon = "fa-solid fa-clock"
