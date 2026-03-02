from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..logic.facilities import FacilityManager
from ..logic.permissions import get_institution_with_access

@login_required
def facility_list(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    fm = FacilityManager(request.user, institution)
    
    form_override = None
    if request.method == "POST":
        success, message, result = fm.handle_facility_actions(request)
        if success:
            if request.headers.get('HX-Request') and request.POST.get('action') == 'delete':
                from django.http import HttpResponse
                return HttpResponse("")
            messages.success(request, message)
            return redirect(request.path)
        else:
            if hasattr(result, 'errors'): form_override = result
            messages.error(request, message)

    return render(request, "dms/facility_list.html", fm.get_list_context(request, override_form=form_override))

