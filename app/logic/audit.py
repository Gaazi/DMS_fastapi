from typing import List, Optional, Tuple, Any, Dict, Type
from sqlmodel import Session, select, desc
from fastapi import HTTPException
from datetime import datetime
from sqlalchemy.orm import selectinload
import json

# تمام ماڈلز کو ایک ساتھ امپورٹ کرنا تاکہ میپنگ مکمل ہو
from ..models import (
    Student, Staff, Course, Fee, Income, Expense, Institution, 
    Facility, Admission, Donor, Parent, StaffAdvance, Attendance,
    Exam, Announcement, InventoryItem, ActivityLog
)

class AuditManager:
    """لاگز اور ریسائیکل بن کی مینجمنٹ (Hyper-Refined Version)"""

    # 🚀 جینگو کی 'apps.get_model' کا مکمل نعم البدل
    MODEL_MAP: Dict[str, Type[Any]] = {
        'Student': Student,
        'Staff': Staff,
        'Course': Course,
        'Fee': Fee,
        'Income': Income,
        'Expense': Expense,
        'Institution': Institution,
        'Facility': Facility,
        'Admission': Admission,
        'Donor': Donor,
        'Parent': Parent,
        'StaffAdvance': StaffAdvance,
        'Attendance': Attendance,
        'Exam': Exam,
        'Announcement': Announcement,
        'InventoryItem': InventoryItem
    }

    def __init__(self, user, session: Session, institution: Optional[Institution] = None):
        """یوزر اور ڈیٹا بیس سیشن کے ساتھ آڈٹ کو سنبھالنا۔"""
        self.user = user
        self.session = session
        self.institution = institution

    @staticmethod
    def log_activity(session: Session, inst_id: int, user_id: Optional[int], 
                     action: str, model_name: str, object_id: int, 
                     object_repr: str, changes: Optional[dict] = None):
        """جینگو کی خودکار ہسٹری کی طرح ایونٹس کو ریکارڈ کرنا۔"""
        try:
            # ماڈل کا نام صاف کریں
            clean_model_name = model_name.split('.')[-1].capitalize()
            
            # اگر repr موجود نہ ہو تو ایک ڈیفالٹ بنائیں
            safe_repr = object_repr or f"{clean_model_name} #{object_id or 'New'}"
            if len(safe_repr) > 250: safe_repr = safe_repr[:247] + "..."
    
            log = ActivityLog(
                inst_id=inst_id,
                user_id=user_id,
                action=action.lower(),
                model_name=clean_model_name,
                object_id=object_id or 0,
                object_repr=safe_repr,
                changes=json.dumps(changes) if changes else None
            )
            session.add(log)
            session.flush() # Ensure it's part of the transaction
        except Exception as e:
            # آڈٹ لاگنگ کی وجہ سے مین آپریشن نہیں رکنا چاہیے
            print(f"Audit log failed: {e}")
            session.rollback()


    def get_logs(self, limit: int = 100) -> List[dict]:
        """سسٹم کی ہسٹری رپورٹس۔"""
        statement = select(ActivityLog).options(selectinload(ActivityLog.user))
        
        if self.institution:
            statement = statement.where(ActivityLog.inst_id == self.institution.id)
        
        statement = statement.order_by(desc(ActivityLog.timestamp)).limit(limit)
        logs = self.session.exec(statement).all()
        
        return [{
            'timestamp': l.timestamp,
            'user': l.user, 
            'action': l.action,
            'model_name': l.model_name,
            'object_repr': l.object_repr,
            'changes': json.loads(l.changes) if l.changes else None
        } for l in logs]

    def get_trash_items(self) -> List[dict]:
        """ریسائیکل بن سے تمام حذف شدہ ڈیٹا نکالنا۔"""
        trash = []
        
        for name, model in self.MODEL_MAP.items():
            # صرف وہ ماڈلز چیک کریں جن میں deleted_at موجود ہے
            if not hasattr(model, 'deleted_at'):
                continue
                
            statement = select(model).where(model.deleted_at != None)
            
            if self.institution:
                # لاجک: inst_id یا institution_id میں سے جو ملے اسے فلٹر کریں
                if hasattr(model, 'inst_id'):
                    statement = statement.where(model.inst_id == self.institution.id)
                elif hasattr(model, 'institution_id'):
                    statement = statement.where(model.institution_id == self.institution.id)
                else:
                    continue # سیکیورٹی رسک سے بچنے کے لیے اسکپ کریں
                
            items = self.session.exec(statement).all()
                
            for item in items:
                trash.append({
                    'id': item.id,
                    'repr': str(item) or f"{name} #{item.id}",
                    'name': name,
                    'deleted_at': item.deleted_at,
                    'model_path': f"dms.{name}"
                })
        
        # جدید ترین ڈیلیٹڈ ڈیٹا اوپر دکھائیں
        trash.sort(key=lambda x: x['deleted_at'] if x['deleted_at'] else datetime.min, reverse=True)
        return trash

    def restore_item(self, model_path: str, object_id: int):
        """حذف شدہ ریکارڈ کو واپس لانا۔"""
        item, model_name = self._get_item_with_security(model_path, object_id)
        repr_str = str(item)
        
        item.deleted_at = None
        self.session.add(item)
        
        # لاگنگ
        self.log_activity(
            self.session, self.institution.id, self.user.id, 
            'restore', model_name, object_id, repr_str
        )
        
        self.session.commit()
        return True, f"'{repr_str}' کو کامیابی سے بحال کر دیا گیا ہے۔"

    def permanent_delete(self, model_path: str, object_id: int):
        """مستقل حذف کرنا ( ناقابل واپسی)۔"""
        item, model_name = self._get_item_with_security(model_path, object_id)
        repr_str = str(item)
        
        self.session.delete(item)
        
        self.log_activity(
            self.session, self.institution.id, self.user.id, 
            'hard_delete', model_name, object_id, repr_str
        )
        
        self.session.commit()
        return True, f"'{repr_str}' کو مکمل طور پر حذف کر دیا گیا۔"

    def _get_item_with_security(self, model_path: str, object_id: int):
        """سیکیورٹی لیئر: یہ چیک کرتا ہے کہ ابجیکٹ موجود ہے اور یوزر کو حق حاصل ہے۔"""
        model_name = model_path.split('.')[-1].capitalize()
        model = self.MODEL_MAP.get(model_name)
        
        if not model:
            raise HTTPException(status_code=404, detail="Requested model not found.")
        
        statement = select(model).where(model.id == object_id).where(model.deleted_at != None)
        item = self.session.exec(statement).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="The record does not exist or is not in trash.")

        # انسٹی ٹیوشن سیکیورٹی چیک
        if self.institution:
            item_inst_id = getattr(item, 'inst_id', getattr(item, 'institution_id', None))
            if item_inst_id is None or item_inst_id != self.institution.id:
                raise HTTPException(status_code=403, detail="Permission Denied for this institution.")
            
        return item, model_name
