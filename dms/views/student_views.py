from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - student_list (Line 9) - Directory with search and filters
   - student_detail (Line 30) - Academic profile and actions
   - student_attendance (Line 45) - Daily attendance marking
   - guardian_dashboard (Line 62) - View for parents
   - student_dashboard (Line 72) - Private view for students
   - batch_generate_fees (Line 99) - Trigger automated fee generation
"""
from ..logic.permissions import get_institution_with_access
from ..logic.students import StudentManager
from ..logic.attendance import AttendanceManager
from ..models import Student
from ..forms import StudentCreationForm

@login_required
def student(request, institution_slug):
    """طلبہ کا مرکزی ڈیش بورڈ (خلاصہ، اعداد و شمار اور نیا داخلہ)۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    
    # Redirect Edit Requests to Admission Page
    if request.GET.get('edit'):
        redirect_url = f"{reverse('admission', kwargs={'institution_slug': institution_slug})}?edit={request.GET.get('edit')}"
        return redirect(redirect_url)

    sm = StudentManager(request.user, institution=institution)
    
    form_override = None
    if request.method == "POST":
        # Modifications require management access
        access.enforce_academic_manage()
        success, message, result = sm.handle_student_list_actions(request)
        if success:
            messages.success(request, message)
            return redirect(request.path)
        else:
            if hasattr(result, 'errors'): form_override = result
            messages.error(request, message)
    
    context = sm.get_student_list_context(request, override_form=form_override)
    context['is_academic_admin'] = access.can_manage_academics()
    context['can_view_academics'] = access.can_view_academics()
    
    if request.headers.get("HX-Request"):
        target = request.headers.get("HX-Target")
        if target == "student-dashboard-stats":
            return render(request, "dms/partials/student_stats_partial.html", context)
        elif target in ["student-list-container", "student-list-wrapper"]:
            return render(request, "dms/partials/student_list.html", context)
            
    return render(request, "dms/students.html", context)


@login_required
def student_list_details(request, institution_slug):
    """طلبہ کی تفصیلی فہرست (تلاش، فلٹرز اور صفحہ بندی کے لیے صرف HTMX کا استعمال)۔"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    sm = StudentManager(request.user, institution=institution)
    
    if request.headers.get("HX-Request"):
        context = sm.get_student_list_context(request)
        return render(request, "dms/partials/student_list.html", context)
    
    # اگر براہ راست کوئی اس یو آر ایل پر آئے تو اسے مین ڈیش بورڈ پر بھیج دیں
    return redirect('students', institution_slug=institution_slug)

@login_required
def student_detail(request, institution_slug, student_id):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    sm = StudentManager(request.user, institution=institution)
    
    if request.method == "POST":
        # Determine if the action is academic or finance
        action = request.POST.get("action")
        if action == "add_to_wallet":
            access.enforce_finance_access()
        else:
            access.enforce_academic_manage()

        success, message, _ = sm.handle_detail_actions(request)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect(request.path)

    context = sm.get_student_detail_context(student_id)
    context['is_academic_admin'] = access.can_manage_academics()
    context['can_view_academics'] = access.can_view_academics()
    context['is_finance_admin'] = access.can_manage_finance()
    return render(request, "dms/student_detail.html", context)

@login_required
def student_attendance(request, institution_slug):
    # Teachers/Imams can mark attendance
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    am = AttendanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, message, redirect_to = am.handle_student_attendance_actions(request)
        if success: messages.success(request, message)
        else: messages.error(request, message)
        return redirect(redirect_to)

    context = am.get_student_attendance_context(request)
    if request.headers.get("HX-Request"):
        return render(request, "dms/partials/student_attendance_table.html", context)
    return render(request, "dms/student_attendance.html", context)


@login_required
def guardian_dashboard(request, institution_slug=None):
    from ..logic.guardian import GuardianManager
    institution = None
    if institution_slug:
        institution = get_object_or_404(Institution, slug=institution_slug)
        # Detailed permission check is done in GuardianManager
    
    gm = GuardianManager(request.user, institution=institution)
    return render(request, "dms/guardian_dashboard.html", gm.get_dashboard_context())

@login_required
def student_dashboard(request, student_id, institution_slug=None):
    institution = None
    if institution_slug:
        institution = get_object_or_404(Institution, slug=institution_slug)
    
    # Delegate data fetching and permission checks to StudentManager
    sm = StudentManager(request.user, institution=institution)
    
    # get_student_detail_context performs strict permission checks
    context = sm.get_student_detail_context(student_id)
    
    return render(request, "dms/student_dashboard.html", context)


@login_required
def admission(request, institution_slug):
    # Viewing the form is academic_view, submitting is academic_manage
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='academic_view')
    sm = StudentManager(request.user, institution=institution)
    
    search_name = request.GET.get('name')
    form_override = None
    editing_student = None
    student_obj = None

    if search_name and request.headers.get("HX-Request"):
        import re
        match = re.search(r'^(.*?)\s*\[(.*?)\]$', search_name.strip())
        if match:
            clean_name = match.group(1).strip()
            reg_id = match.group(2).strip()
            student_obj = Student.objects.filter(name__iexact=clean_name, reg_id__iexact=reg_id, institution=institution).first()
        else:
            student_obj = Student.objects.filter(name__iexact=search_name.strip(), institution=institution).first()
        
        if student_obj:
            form_override = StudentCreationForm(instance=student_obj, institution=institution)
            editing_student = student_obj

    if request.method == "POST":
        access.enforce_academic_manage()
        success, message, result = sm.handle_student_list_actions(request)
        if success:
            messages.success(request, message)
            return redirect('students', institution_slug=institution_slug)
        if hasattr(result, 'errors'): form_override = result
        messages.error(request, message)
    
    context = sm.get_student_list_context(request, override_form=form_override)
    context['is_academic_admin'] = access.can_manage_academics()
    context['can_view_academics'] = access.can_view_academics()
    
    if editing_student:
        context['editing_student'] = editing_student
    elif context.get('editing_student'):
        editing_student = context['editing_student']

    if request.headers.get("HX-Request"):
        return render(request, "dms/partials/course_fees_partial.html", context)

    return render(request, "dms/admission.html", context)


@login_required
def batch_generate_fees(request, institution_slug):
    # This is a finance action
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    sm = StudentManager(request.user, institution=institution)
    
    term_students = "ممبران" if institution.type == 'masjid' else "طلبہ"
    term_fees = "چندہ" if institution.type == 'masjid' else "فیس"

    try:
        count = sm.finance().auto_generate_fees()
        if count > 0:
            messages.success(request, f"ماشاءاللہ! {count} {term_students} کے لیے اس مہینے کی {term_fees} کامیابی سے جنریٹ کر دی گئی ہے۔")
        else:
            messages.info(request, f"اس مہینے کی {term_fees} پہلے ہی جنریٹ کی جا چکی ہے یا کوئی فعال داخلہ موجود نہیں ہے۔")
    except Exception as e:
        messages.error(request, f"{term_fees} جنریٹ کرتے وقت مسئلہ پیش آیا: {str(e)}")
        
    return redirect('dashboard', institution_slug=institution_slug)
