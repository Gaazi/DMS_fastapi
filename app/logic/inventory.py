from sqlmodel import Session, select
from datetime import datetime, date
from typing import Optional, List
from fastapi import HTTPException

# Internal Imports
# Internal Imports
from ..models import InventoryItem, AssetIssue, ItemCategory, Student, Staff, Institution, User
from .audit import AuditManager

class InventoryManager:
    """انوینٹری، لائبریری اور اثاثہ جات مینیج کرنے کی لاجک (SQLModel Version)۔"""
    
    def __init__(self, session: Session, user: User, institution: Optional[Institution] = None):
        self.user = user
        self.session = session
        self.institution = institution
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = session.get(Institution, user.staff.inst_id)
            elif user:
                self.institution = session.exec(select(Institution).where(Institution.user_id == user.id)).first()

    def _check_access(self):
        """سیکیورٹی چیک۔"""
        if not self.user: raise HTTPException(status_code=401, detail="Authentication required.")
        return True

    def save_item(self, data: dict):
        """نیا سامان یا کتاب شامل کرنا یا موجودہ کو اپڈیٹ کرنا۔"""
        self._check_access()
        item_id = data.get('id')
        if item_id:
            item = self.session.get(InventoryItem, item_id)
            if not item: raise HTTPException(status_code=404, detail="Item not found")
            for k, v in data.items(): 
                if hasattr(item, k): setattr(item, k, v)
            action = "update"
        else:
            item = InventoryItem(**data)
            item.inst_id = self.institution.id
            item.available_quantity = item.total_quantity
            self.session.add(item)
            action = "create"
            
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, action, 'InventoryItem', item.id or 0, item.name, data)
        self.session.commit()
        self.session.refresh(item)
        return True, "Inventory information saved successfully.", item

    def issue_item(self, item_id: int, student_id: Optional[int] = None, staff_id: Optional[int] = None, quantity: int = 1, due_date: Optional[date] = None):
        """سامان یا کتاب جاری کرنا۔"""
        self._check_access()
        item = self.session.get(InventoryItem, item_id)
        if not item or item.inst_id != self.institution.id:
            return False, "Item not found."
        
        if item.available_quantity < int(quantity):
            return False, "Not enough stock available."
        
        issue = AssetIssue(
            item_id=item.id,
            student_id=student_id,
            staff_id=staff_id,
            quantity=int(quantity),
            issue_date=date.today(),
            due_date=due_date
        )
        
        item.available_quantity -= int(quantity)
        self.session.add(issue)
        self.session.add(item)
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'issue_item', 'InventoryItem', item.id, f"Issued {quantity} of {item.name}", {})
        self.session.commit()
        return True, "Item issued successfully.", issue

    def return_item(self, issue_id: int):
        """جاری شدہ سامان کی واپسی درج کرنا اور اسٹاک بحال کرنا۔"""
        self._check_access()
        issue = self.session.get(AssetIssue, issue_id)
        if not issue or not issue.item_id: return False, "Record not found."
        
        item = self.session.get(InventoryItem, issue.item_id)
        if not item or item.inst_id != self.institution.id:
            return False, "Unauthorized access or record missing."
        
        if issue.is_returned: return False, "Already returned."
        
        issue.return_date = date.today()
        issue.is_returned = True
        item.available_quantity += issue.quantity
        
        self.session.add(issue)
        self.session.add(item)
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'return_item', 'InventoryItem', item.id, f"Returned {item.name}", {})
        self.session.commit()
        return True, "Return recorded successfully.", issue



    def get_inventory_context(self):
        """انوینٹری کے صفحے کے لیے ڈیٹا تیار کرنا۔"""
        # Note: Using select().where() instead of filter()
        items = self.session.exec(select(InventoryItem).where(InventoryItem.inst_id == self.institution.id)).all()
        categories = self.session.exec(select(ItemCategory).where(ItemCategory.inst_id == self.institution.id)).all()
        
        # Complex join for pending returns
        pending_returns = self.session.exec(
            select(AssetIssue).join(InventoryItem).where(InventoryItem.inst_id == self.institution.id, AssetIssue.is_returned == False)
        ).all()
        
        students = self.session.exec(select(Student).where(Student.inst_id == self.institution.id, Student.is_active == True)).all()
        staff = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True)).all()
        
        return {
            "items": items,
            "categories": categories,
            "pending_returns": pending_returns,
            "students": students,
            "staff": staff,
            "institution": self.institution
        }
