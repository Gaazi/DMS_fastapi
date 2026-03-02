from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - backup_manager (Line 65) - Backup history
   - create_manual_snapshot (Line 80) - Trigger backup
   - restore_snapshot_ajax (Line 116) - Restore from history
   - download_institution_export_bundle (Line 182) - Full ZIP (JSON+Media)
   - restore_institution_backup (Line 207) - File upload restore
"""
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib import messages
import json
import zipfile
import io
import os

from ..models import Institution, SystemSnapshot
from ..exporting import (
    export_all_institutions_bundle,
    export_institution_to_csv_zip,
    export_institution_to_json,
    export_institutions_bundle,
    export_institution_to_excel,
    import_institution_from_json,
)
from ..logic.permissions import get_institution_with_access

# --- Helper Functions ---

def _handle_zip_restore(file_obj, specific_institution=None):
    """
    ZIP فائل سے ڈیٹا ری اسٹور کرنے کا مشترکہ منطقی فنکشن۔
    اگر specific_institution دیا جائے تو صرف اس ادارے کا ڈیٹا ری اسٹور کرے گا۔
    ورنہ پورے سسٹم (تمام اداروں) کا۔
    """
    restored_count = 0
    errors = []
    
    try:
        with zipfile.ZipFile(file_obj) as z:
            json_files = [f for f in z.namelist() if f.endswith(".json")]
            
            for json_path in json_files:
                slug_candidate = json_path.split('/')[0]
                try:
                    # اگر مخصوص ادارہ دیا گیا ہے، تو صرف اس کے سلگ سے میچ ہونے والی فائل پروسیس کریں
                    if specific_institution and slug_candidate != specific_institution.slug:
                        continue
                        
                    institution = Institution.objects.get(slug=slug_candidate)
                    json_content = z.read(json_path).decode('utf-8')
                    result = import_institution_from_json(institution, json_content)
                    
                    if "error" in result:
                        errors.append(f"{slug_candidate}: {result['error']}")
                    else:
                        restored_count += 1
                        
                except Institution.DoesNotExist:
                    if not specific_institution:
                        errors.append(f"ادارہ '{slug_candidate}' نہیں ملا۔")
        
        return restored_count, errors
    except Exception as e:
        return 0, [str(e)]

# --- Snapshot Management Views ---

@login_required
def backup_manager(request, institution_slug=None):
    """بیک اپ ہسٹری دکھانے کا ویو"""
    if request.user.is_superuser and not institution_slug:
        snapshots = SystemSnapshot.objects.all().order_by('-created_at')
        current_inst = None
    else:
        current_inst, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
        snapshots = SystemSnapshot.objects.filter(institution=current_inst).order_by('-created_at')
    
    return render(request, "dms/backup_manager.html", {
        "snapshots": snapshots,
        "institution": current_inst
    })

@login_required
def create_manual_snapshot(request, institution_slug=None):
    """بیک اپ (اسنیپ شاٹ) بنانے کا ویو"""
    target_slug = institution_slug or request.GET.get('inst_slug')
    label = request.GET.get('label') or f"Manual Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    from django.core.management import call_command
    
    try:
        if target_slug:
            inst, access = get_institution_with_access(target_slug, request=request, access_type='admin')
            call_command('create_snapshot', institution=inst.slug, label=label)
            messages.success(request, f"{inst.name} کا اسنیپ شاٹ کامیابی سے تیار کر لیا گیا ہے۔")
            
            if request.GET.get('download') == '1':
                snapshot = SystemSnapshot.objects.filter(institution=inst).order_by('-created_at').first()
                if snapshot:
                    raw_name = os.path.basename(snapshot.file.name)
                    friendly_name = raw_name.replace('_', ' ')
                    response = FileResponse(snapshot.file.open('rb'), content_type="application/zip")
                    response["Content-Disposition"] = f'attachment; filename="{friendly_name}"'
                    return response
            
            return redirect('backup_manager', institution_slug=inst.slug)
        else:
            if not request.user.is_superuser:
                raise PermissionDenied()
            call_command('create_snapshot', label=label)
            messages.success(request, "پورے سسٹم کا بیک اپ کامیابی سے تیار کر لیا گیا ہے۔")
            return redirect('system_backup_manager')

    except Exception as e:
        messages.error(request, f"بیک اپ میں غلطی: {str(e)}")
        if institution_slug:
            return redirect('backup_manager', institution_slug=institution_slug)
        return redirect('system_backup_manager')

@login_required
def restore_snapshot_ajax(request, snapshot_id, institution_slug=None):
    """بیک اپ ہسٹری سے ڈیٹا ری اسٹور کرنا"""
    if not request.user.is_superuser:
        raise PermissionDenied()
    
    snapshot = get_object_or_404(SystemSnapshot, id=snapshot_id)
    # اگر اسنیپ شاٹ کسی ادارے سے منسلک ہے، تو صرف اسے ری اسٹور کریں
    count, errors = _handle_zip_restore(snapshot.file, specific_institution=snapshot.institution)
    
    if count > 0:
        messages.success(request, f"اسنیپ شاٹ کامیابی سے ری اسٹور ہو گیا! ({count} ادارے)")
    if errors:
        messages.warning(request, f"کچھ مسائل: {', '.join(errors[:3])}")
        
    if institution_slug:
        return redirect('backup_manager', institution_slug=institution_slug)
    return redirect('system_backup_manager')

@login_required
def delete_snapshot(request, snapshot_id, institution_slug=None):
    """بیک اپ ڈیلیٹ کرنا"""
    if not request.user.is_superuser:
        raise PermissionDenied()
    
    snapshot = get_object_or_404(SystemSnapshot, id=snapshot_id)
    snapshot.file.delete()
    snapshot.delete()
    messages.success(request, "اسنیپ شاٹ حذف کر دیا گیا۔")
    
    if institution_slug:
        return redirect('backup_manager', institution_slug=institution_slug)
    return redirect('system_backup_manager')

@login_required
def download_snapshot_file(request, snapshot_id, institution_slug=None):
    """بیک اپ فائل ڈاؤن لوڈ کرنا"""
    snapshot = get_object_or_404(SystemSnapshot, id=snapshot_id)
    if not request.user.is_superuser:
        if not snapshot.institution or snapshot.institution.user != request.user:
            raise PermissionDenied()
            
    try:
        raw_name = os.path.basename(snapshot.file.name)
        friendly_name = raw_name.replace('_', ' ')
        response = FileResponse(snapshot.file.open('rb'), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{friendly_name}"'
        return response
    except Exception as e:
        messages.error(request, f"فایل ڈاؤن لوڈ کرنے میں غلطی: {str(e)}")
        if institution_slug:
            return redirect('backup_manager', institution_slug=institution_slug)
        return redirect('system_backup_manager')

# --- Legacy Manual Export/Import Views (Kept for external file support) ---

@login_required
def download_institution_export(request, institution_slug):
    """JSON فارمیٹ میں ادارے کا ڈیٹا ڈاؤن لوڈ کریں"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    json_payload = export_institution_to_json(institution)
    filename = f"{institution.slug}-backup-{timezone.now().strftime('%Y%m%d')}.json"
    response = HttpResponse(json_payload, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@login_required
def download_institution_export_bundle(request, institution_slug):
    """ZIP فارمیٹ میں مکمل ڈیٹا (Images کے ساتھ) ڈاؤن لوڈ کریں"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    format_param = request.GET.get("format", "combined").lower()
    
    if format_param == "sheet":
        return download_institution_export_sheet(request, institution_slug)
    
    archive = export_institutions_bundle([institution], include_json=True, include_excel=True, include_csv=True)
    filename = f"{institution.slug}-full-bundle-{timezone.now().strftime('%Y%m%d')}.zip"
    response = HttpResponse(archive, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@login_required
def download_institution_export_sheet(request, institution_slug):
    """ایکسل (Excel) فائل ڈائریکٹ ڈاؤن لوڈ کریں"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    excel_bytes = export_institution_to_excel(institution)
    filename = f"{institution.slug}-sheet-{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(excel_bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@login_required
def restore_institution_backup(request, institution_slug):
    """لوکل کمپیوٹر سے فائل اپ لوڈ کر کے ڈیٹا ری اسٹور کریں"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    if request.method == "POST":
        file_obj = request.FILES.get("backup_file")
        if not file_obj:
            messages.error(request, "براہ کرم فائل منتخب کریں۔")
        elif file_obj.name.endswith(".json"):
            json_content = file_obj.read().decode('utf-8')
            results = import_institution_from_json(institution, json_content)
            messages.success(request, "ڈیٹا کامیابی سے اپ لوڈ ہو گیا۔")
        elif file_obj.name.endswith(".zip"):
            count, errors = _handle_zip_restore(file_obj, specific_institution=institution)
            if count > 0: messages.success(request, f"{institution.name} ری اسٹور ہو گیا۔")
            if errors: messages.warning(request, f"مسائل: {errors[0]}")
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def restore_system_backup(request):
    """سپر ایڈمن کے لیے پورے سسٹم کا ری اسٹور (فائل اپ لوڈ)"""
    if not request.user.is_superuser: raise PermissionDenied()
    if request.method == "POST":
        file_obj = request.FILES.get("backup_file")
        if file_obj and file_obj.name.endswith(".zip"):
            count, errors = _handle_zip_restore(file_obj)
            if count > 0: messages.success(request, f"{count} اداروں کا ڈیٹا ری اسٹور ہوا۔")
            if errors: messages.warning(request, f"مسائل: {len(errors)} پائے گئے۔")
    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def download_all_institutions_export(request):
    """سپر ایڈمن کے لیے تمام اداروں کا یکجا بیک اپ"""
    if not request.user.is_superuser: raise PermissionDenied()
    archive = export_all_institutions_bundle()
    response = HttpResponse(archive, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="system-full-backup-{timezone.now().strftime("%Y%m%d")}.zip"'
    return response
