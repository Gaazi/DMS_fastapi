from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..logic.courses import CourseManager
from ..models import Course
from ..logic.permissions import get_institution_with_access

@login_required
def course(request, institution_slug):
    # This automatically enforces 'academic_view' access (Teacher/Imam/Admin)
    institution, access = get_institution_with_access(institution_slug, request, access_type='academic_view')
        
    pm = CourseManager(request.user, institution=institution)
    
    form_override = None
    if request.method == "POST":
        # Enforce 'academic_manage' (Admin/Academic Head) for modifications
        access.enforce_academic_manage()
            
        success, message, result = pm.handle_course_actions(request)
        if success:
            messages.success(request, message)
            return redirect(request.path)
        else:
            if hasattr(result, 'errors'): form_override = result
            messages.error(request, message)

    context = pm.get_list_context(request, override_form=form_override)
    context['is_academic_admin'] = access.can_manage_academics() # For template UI
    context['can_view_academics'] = access.can_view_academics()
    return render(request, "dms/course.html", context)

@login_required
def course_detail(request, institution_slug, course_id):
    institution, access = get_institution_with_access(institution_slug, request, access_type='academic_view')
        
    course_obj = get_object_or_404(Course, pk=course_id, institution=institution)
    pm = CourseManager(request.user, target=course_obj)
    
    if request.method == "POST":
        access.enforce_academic_manage()
            
        success, message = pm.handle_detail_actions(request)
        if success: messages.success(request, message)
        else: messages.error(request, message)
        return redirect(request.path)

    context = pm.get_detail_context()
    context['is_academic_admin'] = access.can_manage_academics() # For template UI
    context['can_view_academics'] = access.can_view_academics()
    return render(request, "dms/course_detail.html", context)
