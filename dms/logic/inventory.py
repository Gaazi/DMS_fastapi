from django.db import transaction
from django.utils import timezone
from ..models import InventoryItem, AssetIssue, ItemCategory

class InventoryManager:
    """انوینٹری، لائبریری اور اثاثہ جات مینیج کرنے کی لاجک۔"""
    
    def __init__(self, user, institution=None):
        self.user = user
        self.institution = institution
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def _check_access(self):
        """سیکیورٹی چیک۔"""
        from django.core.exceptions import PermissionDenied
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
        return True

    @transaction.atomic
    def create_new_item(self, request_data):
        """نیا سامان یا کتاب شامل کرنا"""
        self._check_access()
        name = request_data.get('name')
        if not name:
            return False, "نام فراہم کرنا لازمی ہے۔", None
            
        quantity = int(request_data.get('total_quantity', 0))
        
        category_id = request_data.get('category_id')
        category = ItemCategory.objects.get(pk=category_id, institution=self.institution) if category_id else None

        item = InventoryItem.objects.create(
            institution=self.institution,
            name=name,
            item_type=request_data.get('item_type', InventoryItem.ItemType.BOOK),
            category=category,
            total_quantity=quantity,
            available_quantity=quantity, # نیا سامان جتنا آئے گا, اتنا دستیاب بھی ہوگا
            location=request_data.get('location', ''),
            author=request_data.get('author', ''),
            isbn=request_data.get('isbn', ''),
            price=request_data.get('price', 0)
        )
        return True, "نیا سامان کامیابی سے شامل کر لیا گیا ہے۔", item

    @transaction.atomic
    def add_stock(self, item_id, quantity):
        """موجودہ سامان کے اسٹاک میں اضافہ کرنا۔"""
        self._check_access()
        item = InventoryItem.objects.get(pk=item_id, institution=self.institution)
        item.total_quantity += int(quantity)
        item.available_quantity += int(quantity)
        item.save()
        return item

    @transaction.atomic
    def add_item(self, data):
        """نیا سامان یا کتاب شامل کرنا۔"""
        self._check_access()
        item = InventoryItem.objects.create(
            institution=self.institution,
            name=data.get('name'),
            item_type=data.get('item_type', 'book'),
            author=data.get('author', ''),
            isbn=data.get('isbn', ''),
            total_quantity=int(data.get('quantity', 0)),
            available_quantity=int(data.get('quantity', 0)),
            location=data.get('location', ''),
            price=float(data.get('price', 0.0))
        )
        return True, f"'{item.name}' کامیابی سے شامل کر دیا گیا۔", item

    @transaction.atomic
    def issue_item(self, item_id, student_id=None, staff_id=None, quantity=1, due_date=None):
        """سامان یا کتاب جاری کرنا۔"""
        self._check_access()
        item = InventoryItem.objects.get(pk=item_id, institution=self.institution)
        
        if item.available_quantity < int(quantity):
            return False, "اسٹاک میں اتنی مقدار دستیاب نہیں ہے۔"
        
        issue = AssetIssue.objects.create(
            item=item,
            student_id=student_id,
            staff_id=staff_id,
            quantity=quantity,
            issue_date=timezone.now().date(),
            due_date=due_date
        )
        
        # اسٹاک اپ ڈیٹ کریں
        item.available_quantity -= int(quantity)
        item.save()
        
        return True, "سامان کامیابی سے جاری کر دیا گیا ہے۔", issue

    @transaction.atomic
    def return_item(self, issue_id):
        """جاری شدہ سامان کی واپسی درج کرنا اور اسٹاک بحال کرنا۔"""
        self._check_access()
        issue = AssetIssue.objects.get(pk=issue_id, item__institution=self.institution)
        
        if issue.is_returned:
            return False, "یہ سامان پہلے ہی واپس ہو چکا ہے۔"
        
        issue.return_date = timezone.now().date()
        issue.is_returned = True
        issue.save()
        
        # اسٹاک واپس بڑھائیں
        item = issue.item
        item.available_quantity += issue.quantity
        item.save()
        
        return True, "سامان کی واپسی کامیابی سے ریکارڈ کر لی گئی ہے۔", issue

    def get_inventory_context(self):
        """انوینٹری کے صفحے کے لیے ڈیٹا تیار کرنا۔"""
        from ..models import Student, Staff
        items = InventoryItem.objects.filter(institution=self.institution)
        categories = ItemCategory.objects.filter(institution=self.institution)
        pending_returns = AssetIssue.objects.filter(item__institution=self.institution, is_returned=False)
        students = Student.objects.filter(institution=self.institution, status='active')
        staff = Staff.objects.filter(institution=self.institution, status='active')
        
        return {
            "items": items,
            "categories": categories,
            "pending_returns": pending_returns,
            "students": students,
            "staff": staff,
            "institution": self.institution
        }
