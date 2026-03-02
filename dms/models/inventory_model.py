from django.db import models
from .foundation_model import Institution
from .people_model import Student, Staff
from .audit_model import AuditModel
from django.utils import timezone

class ItemCategory(AuditModel):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="item_categories")
    name = models.CharField(max_length=100, verbose_name="کیٹیگری کا نام")
    description = models.TextField(blank=True, verbose_name="تفصیل")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "سامان کی قسم"
        verbose_name_plural = "سامان کی اقسام"

class InventoryItem(AuditModel):
    class ItemType(models.TextChoices):
        BOOK = "book", "کتاب (Library)"
        ASSET = "asset", "اثاثہ (Furniture/Electrics)"
        CONSUMABLE = "consumable", "صرف ہونے والا (Stationery/Cleaning)"
        UNIFORM = "uniform", "وردی / لباس"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="inventory_items")
    category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name="نام / ٹائٹل")
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.BOOK, verbose_name="قسم")
    
    # لائبریری کے لیے مخصوص فیلڈز
    author = models.CharField(max_length=255, blank=True, verbose_name="مصنف (برائے کتاب)")
    isbn = models.CharField(max_length=50, blank=True, verbose_name="ISBN / کوڈ")
    
    # اسٹاک مینیجمنٹ
    total_quantity = models.PositiveIntegerField(default=0, verbose_name="کل تعداد")
    available_quantity = models.PositiveIntegerField(default=0, verbose_name="دستیاب تعداد")
    location = models.CharField(max_length=100, blank=True, verbose_name="الماری / جگہ")
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="قیمتِ خرید")

    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"

    class Meta:
        verbose_name = "انوینٹری آئٹم"
        verbose_name_plural = "انوینٹری آئٹمز"

class AssetIssue(AuditModel):
    """کتابوں یا سامان کا اجراء (Issuance)"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="issuances")
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_items")
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_items")
    
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد")
    issue_date = models.DateField(default=timezone.now, verbose_name="تاریخِ اجراء")
    due_date = models.DateField(null=True, blank=True, verbose_name="واپسی کی متوقع تاریخ")
    return_date = models.DateField(null=True, blank=True, verbose_name="اصل واپسی کی تاریخ")
    
    is_returned = models.BooleanField(default=False, verbose_name="واپس ہو گیا؟")
    notes = models.TextField(blank=True, verbose_name="نوٹس")

    def __str__(self):
        receiver = self.student.full_name if self.student else (self.staff.full_name if self.staff else "Unknown")
        return f"{self.item.name} -> {receiver}"

    class Meta:
        verbose_name = "سامان کا اجراء"
        verbose_name_plural = "سامان کا اجراء (ریکارڈ)"
