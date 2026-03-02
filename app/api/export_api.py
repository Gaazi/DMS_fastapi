from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, desc
from typing import Optional, List
import json
import zipfile
import io
import os
from datetime import datetime

# Internal Imports
from ..db.session import get_session
from ..models import Institution, SystemSnapshot, User
from ..logic.auth import get_current_user
from ..logic.permissions import get_institution_with_access
from ..helper.exporting import (
    export_all_institutions_bundle,
    export_institution_to_csv_zip,
    export_institution_to_json,
    export_institutions_bundle,
    export_institution_to_excel,
    import_institution_from_json,
)

router = APIRouter()
from fastapi import Response
from ..helper.context import TemplateResponse
from ..logic.auth import get_current_user

# --- 1. ZIP Restore Logic ---
def _handle_zip_restore(session: Session, file_obj, specific_institution: Optional[Institution] = None):
    """ZIP فائل سے ڈیٹا کی بحالی کا منطقی فنکشن۔"""
    restored_count = 0
    errors = []
    try:
        wrap_file = io.BytesIO(file_obj) if isinstance(file_obj, bytes) else file_obj
        with zipfile.ZipFile(wrap_file) as z:
            json_files = [f for f in z.namelist() if f.endswith(".json")]
            for json_path in json_files:
                slug_candidate = json_path.split('/')[0]
                if specific_institution and slug_candidate != specific_institution.slug:
                    continue
                institution = session.exec(select(Institution).where(Institution.slug == slug_candidate)).first()
                if institution:
                    json_content = z.read(json_path).decode('utf-8')
                    result = import_institution_from_json(institution, session, json_content)
                    if "error" in result: errors.append(f"{slug_candidate}: {result['error']}")
                    else: restored_count += 1
        return restored_count, errors
    except Exception as e:
        return 0, [str(e)]

# --- 2. Backup Manager ---
@router.get("/backups/", response_class=HTMLResponse, name="backup_manager")
@router.get("/{institution_slug}/backups/", response_class=HTMLResponse, name="institution_backup_manager")
async def backup_manager(request: Request, institution_slug: Optional[str] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.is_superuser and not institution_slug:
        snapshots = session.exec(select(SystemSnapshot).order_by(desc(SystemSnapshot.created_at))).all()
        current_inst = None
    else:
        current_inst, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
        snapshots = session.exec(select(SystemSnapshot).where(SystemSnapshot.inst_id == current_inst.id).order_by(desc(SystemSnapshot.created_at))).all()
    
    return await TemplateResponse.render("dms/backup_manager.html", request, session, {
        "snapshots": snapshots, 
        "institution": current_inst
    })

# --- 3. Snapshot Actions ---
@router.get("/backups/create/", name="create_manual_snapshot")
@router.get("/{institution_slug}/backups/create/", name="create_institution_snapshot")
async def create_manual_snapshot(request: Request, institution_slug: Optional[str] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    target_slug = institution_slug or request.query_params.get('inst_slug')
    # Logic to create snapshot should be here or in logic layer
    return RedirectResponse(url=f"/{target_slug}/backups" if target_slug else "/backups", status_code=303)

@router.post("/backups/restore/{snapshot_id}/", name="restore_snapshot")
async def restore_snapshot(snapshot_id: int, institution_slug: Optional[str] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    # Restore logic
    return RedirectResponse(url=f"/{institution_slug}/backups" if institution_slug else "/backups", status_code=303)

@router.post("/backups/delete/{snapshot_id}/", name="delete_snapshot")
async def delete_snapshot_route(snapshot_id: int, institution_slug: Optional[str] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    snapshot = session.get(SystemSnapshot, snapshot_id)
    if snapshot:
        session.delete(snapshot)
        session.commit()
    return RedirectResponse(url=f"/{institution_slug}/backups" if institution_slug else "/backups", status_code=303)

@router.get("/backups/download/{snapshot_id}/", name="download_snapshot")
async def download_snapshot_file(snapshot_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    snapshot = session.get(SystemSnapshot, snapshot_id)
    if not snapshot: raise HTTPException(status_code=404)
    if not current_user.is_superuser and snapshot.inst_id:
        inst = session.get(Institution, snapshot.inst_id)
        if inst.user_id != current_user.id: raise HTTPException(status_code=403)
    return FileResponse(snapshot.file_path, filename=os.path.basename(snapshot.file_path))

# --- 4. Exports ---
@router.get("/{institution_slug}/export/json/", name="export_institution_json")
async def download_institution_export_json_route(institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    json_payload = export_institution_to_json(institution, session)
    return Response(content=json_payload, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{institution.slug}.json"'})

@router.get("/{institution_slug}/export/bundle/", name="export_institution_bundle")
async def download_institution_export_bundle_route(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    if request.query_params.get("format") == "sheet":
        excel_bytes = export_institution_to_excel(institution, session)
        return Response(content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{institution.slug}.xlsx"'})
    archive = export_institutions_bundle([institution], session)
    return Response(content=archive, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{institution.slug}-bundle.zip"'})

@router.get("/{institution_slug}/export/sheet/", name="export_institution_sheet")
async def download_institution_export_sheet_route(institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    excel_bytes = export_institution_to_excel(institution, session)
    return Response(content=excel_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{institution.slug}.xlsx"'})

# --- 5. Restores ---
@router.post("/{institution_slug}/restore/", name="restore_institution")
async def restore_institution_backup(institution_slug: str, backup_file: UploadFile = File(...), session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    content = await backup_file.read()
    if backup_file.filename.endswith(".json"):
        import_institution_from_json(institution, session, content.decode('utf-8'))
    elif backup_file.filename.endswith(".zip"):
        _handle_zip_restore(session, content, specific_institution=institution)
    return RedirectResponse(url=f"/{institution_slug}/settings", status_code=303)

@router.post("/system/restore/", name="restore_system")
async def restore_system_backup(backup_file: UploadFile = File(...), session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    content = await backup_file.read()
    if backup_file.filename.endswith(".zip"):
        _handle_zip_restore(session, content)
    return RedirectResponse(url="/backups", status_code=303)

@router.get("/system/export/all/", name="export_all_institutions")
async def download_all_institutions_export_route(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    archive = export_all_institutions_bundle(session)
    return Response(content=archive, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="system-full-backup.zip"'})

