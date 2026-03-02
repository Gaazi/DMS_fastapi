from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - attendance_report (Line 8) - Institutional reporting
   - session_attendance (Line 14) - Session-specific marking
"""
from ..logic.attendance import AttendanceManager
from ..logic.permissions import get_institution_with_access

@login_required
def attendance_report(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    am = AttendanceManager(request.user, institution=institution)
    return render(request, "dms/attendance_report.html", am.get_attendance_report_context(request))

@login_required
def session_attendance(request, institution_slug, session_id):
    # Teachers need to mark attendance, so academic_view is appropriate here
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    am = AttendanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, message, redirect_url = am.handle_session_attendance_actions(request, session_id)
        if success: messages.success(request, message)
        else: messages.error(request, message)
        return redirect(redirect_url)

    return render(request, "dms/attendance_manage.html", am.get_session_attendance_context(session_id))
