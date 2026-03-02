from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - audit_logs (Line 8) - Activity logs overview
   - recycle_bin (Line 18) - SafeDelete restore/purge
"""
from ..logic.permissions import get_institution_with_access
from ..logic.audit import AuditManager

@login_required
def audit_logs(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    am = AuditManager(request.user, institution)
    
    return render(request, "dms/audit_logs.html", {
        "institution": institution,
        "logs": am.get_logs()
    })

@login_required
def recycle_bin(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    am = AuditManager(request.user, institution)
    
    if request.method == "POST":
        action = request.POST.get("action")
        model_path = request.POST.get("model_path")
        obj_id = request.POST.get("object_id")
        
        if action == "restore":
            success, message = am.restore_item(model_path, obj_id)
            messages.success(request, message)
        elif action == "delete_permanent":
            success, message = am.permanent_delete(model_path, obj_id)
            messages.warning(request, message)
            
        return redirect(request.path)

    return render(request, "dms/recycle_bin.html", {
        "institution": institution,
        "trash_items": am.get_trash_items()
    })
