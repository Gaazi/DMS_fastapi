from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - staff (Line 10) - Directory of employees
   - staff_create_edit (Line 32)
   - staff_attendance (Line 62) - Daily staff clocking
   - process_monthly_payroll (Line 90) - Salary calculations
"""
from django.http import HttpResponse
from ..logic.permissions import get_institution_with_access
from ..logic.staff import StaffManager
from ..logic.attendance import AttendanceManager

@login_required
def staff(request, institution_slug):
    # Staff viewing requires 'staff_view' (Owner/Admin/Accountant) access
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='staff_view')
        
    sm = StaffManager(request.user, institution=institution)
    
    # Handle deletion via HTMX
    if request.method == "POST" and request.POST.get("action") == "delete":
        success, message, _ = sm.handle_staff_actions(request)
        if success: messages.success(request, message)
        else: messages.error(request, message)
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect(request.path)

    context = sm.get_staff_context(request)
    
    # If HTMX is just asking for the table
    if request.headers.get("HX-Request") and request.method == "GET":
        return render(request, "dms/partials/staff_table_partial.html", context)

    return render(request, "dms/staff.html", context)

@login_required
def staff_create_edit(request, institution_slug, staff_id=None):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
        
    sm = StaffManager(request.user, institution=institution)
    
    # If editing, get the staff object
    from ..models import Staff
    from ..forms import StaffForm
    editing_staff = None
    if staff_id:
        editing_staff = get_object_or_404(Staff, pk=staff_id, institution=institution)
    
    if request.method == "POST":
        form = StaffForm(request.POST, instance=editing_staff)
        if form.is_valid():
            success, message, _ = sm.save_staff(form, request=request)
            if success:
                messages.success(request, message)
                return redirect("dms_staff", institution_slug=institution.slug)
            else:
                messages.error(request, message)
    else:
        form = StaffForm(instance=editing_staff)
    
    return render(request, "dms/staff_form_page.html", {
        "institution": institution,
        "form": form,
        "editing_staff": editing_staff
    })

@login_required
def staff_attendance(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    am = AttendanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, message, redirect_to = am.handle_staff_attendance_actions(request)
        if success: messages.success(request, message)
        else: messages.error(request, message)
        return redirect(redirect_to)

    context = am.get_staff_attendance_context(request)
    if request.headers.get("HX-Request"):
        return render(request, "dms/partials/staff_attendance_rows.html", context)

    return render(request, "dms/staff_attendance.html", context)

@login_required
def staff_detail(request, institution_slug, staff_id):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='staff_view')
    
    from ..models import Staff
    staff_member = get_object_or_404(Staff, pk=staff_id, institution=institution)
    
    return render(request, "dms/staff_detail.html", {
        "institution": institution,
        "member": staff_member,
    })

@login_required
def process_monthly_payroll(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    # Payroll might be manageable by Accountant as well, so using 'finance'
        
    sm = StaffManager(request.user, institution=institution)
    
    if request.method == "POST":
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        
        if request.POST.get('action') == 'bulk_pay':
             success, message, count = sm.execute_bulk_payroll(month, year)
             if success: messages.success(request, message)
             else: messages.error(request, message)
             return redirect(f"{request.path}?month={month}&year={year}")
             
    return render(request, "dms/payroll_report.html", sm.get_payroll_context(request))

@login_required
def promote_to_staff(request, institution_slug, student_id):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    
    from ..models import Student, Staff
    from ..logic.roles import Role
    from django.utils import timezone
    
    student = get_object_or_404(Student, pk=student_id, institution=institution)
    
    if request.method == "POST":
        # چیک کریں کہ کیا اس موبائل نمبر یا نام سے پہلے ہی کوئی اسٹاف موجود ہے؟
        existing_staff = None
        if student.mobile:
            existing_staff = Staff.objects.filter(institution=institution, mobile=student.mobile).first()
        if not existing_staff:
            existing_staff = Staff.objects.filter(institution=institution, name=student.name).first()
            
        if existing_staff:
            messages.warning(request, f"یہ شخص ({existing_staff.name}) پہلے ہی اسٹاف کی لسٹ میں موجود ہے۔ آپ یہیں سے اپڈیٹ کر سکتے ہیں۔")
            return redirect("dms_staff_edit", institution_slug=institution.slug, staff_id=existing_staff.pk)

        # نیا پروفائل (ون کلک کاپی)
        new_staff = Staff.objects.create(
            institution=institution,
            name=student.name,
            mobile=student.mobile,
            email=student.email,
            address=student.address,
            role=Role.VOLUNTEER,  # بائی ڈیفالٹ رضاکار (کوئی خاص عہدہ نہیں)
            base_salary=0,
            hire_date=timezone.now().date()
        )
        
        messages.success(request, f"زبردست! {student.name} کو عملے (Staff) میں شامل کر دیا گیا ہے۔ اب ان کا عہدہ (Role) سلیکٹ کریں!")
        return redirect("dms_staff_edit", institution_slug=institution.slug, staff_id=new_staff.pk)
    
    if institution.type == 'masjid':
        return redirect("musalleen_detail", institution_slug=institution.slug, student_id=student.id)
    return redirect("student_detail", institution_slug=institution.slug, student_id=student.id)
