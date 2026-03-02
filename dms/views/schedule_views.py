from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..logic.schedule import ScheduleManager
from ..logic.permissions import get_institution_with_access

@login_required
def timetable_view(request, institution_slug):
    """پورے ادارے یا کسی مخصوص پروگرام کا ٹائم ٹیبل دیکھنا۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    sm = ScheduleManager(request.user, institution=institution)
    course_id = request.GET.get('course')
    context = sm.get_schedule_context(course_id=course_id)
    return render(request, 'dms/timetable.html', context)
