from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from .audit_model import AuditModel # یقینی بنائیں کہ یہ فائل موجود ہے

"""
INDEX / TABLE OF CONTENTS:
--------------------------
1. Class: Fee - فیس کے واجبات کا ریکارڈ
2. Class: Fee_Payment - وصولی اور رسیدیں
3. Class: WalletTransaction - بٹوے کی تفصیلات
4. Class: Donor - عطیہ دہندہ (Donation Contacts)
5. Class: Income - آمدنی (Unified: Fees + Donations)
6. Class: Expense - ادارے کے اخراجات
"""


class Fee(AuditModel):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        PARTIAL = "Partial", "قسط"
        PAID = "Paid", "Paid"
        OVERDUE = "Overdue", "Overdue"
        WAIVED = "Waived", "معاف شدہ"

    class FeeType(models.TextChoices):
        MONTHLY = "monthly", "ماہانہ فیس"
        ADMISSION = "admission", "داخلہ فیس"
        COURSE = "fixed", "مکمل کورس فیس"
        INSTALLMENT = "installment", "قسط"
        EXAM = "exam", "امتحانی فیس"
        STATIONERY = "stationery", "کتب و اسٹیشنری"
        TRANSPORT = "transport", "ٹرانسپورٹ فیس"
        OTHER = "other", "دیگر"

    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="student_fees")
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="fees")
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, null=True, blank=True, related_name="fees", verbose_name="پروگرام/کلاس")
    enrollment = models.ForeignKey('Enrollment', on_delete=models.SET_NULL, null=True, blank=True, related_name="fees", verbose_name="داخلہ ریکارڈ")
    
    fee_type = models.CharField(max_length=20, choices=FeeType.choices, default=FeeType.MONTHLY, verbose_name="فیس کی قسم")
    title = models.CharField(max_length=200, blank=True, verbose_name="فیس کا عنوان")
    month = models.DateField(null=True, blank=True, verbose_name="بابت مہینہ/سال")
    
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="اصل فیس")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="ادا شدہ رقم")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="رعایت")
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="جرمانہ")
    
    due_date = models.DateField(null=True, blank=True, verbose_name="آخری تاریخ")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'dms'
        verbose_name = "Fee"
        verbose_name_plural = "Fees"
        indexes = [models.Index(fields=['institution', 'status']),]

    def __str__(self):
        return f"{self.student.full_name if self.student else 'Unknown'} - {self.title}"

    @property
    def total_payable(self):
        return (self.amount_due + self.late_fee) - self.discount

    @property
    def balance(self):
        return max(Decimal("0.00"), self.total_payable - self.amount_paid)

    def update_status_logic(self):
        """اسٹیٹس کو رقم کے حساب سے اپڈیٹ کرنا"""
        if self.status == self.Status.WAIVED: return
        paid, total = self.amount_paid, self.total_payable
        
        # 1. Fully Paid
        if paid >= total and total > 0: 
            self.status = self.Status.PAID
            
        # 2. Overdue (if date passed and not fully paid)
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = self.Status.OVERDUE
            
        # 3. Partial (if paid something but not full, and not overdue yet)
        elif paid > 0: 
            self.status = self.Status.PARTIAL
            
        # 4. Pending (default)
        else: 
            self.status = self.Status.PENDING

    def update_amount_paid(self):
        """فیس کی تمام ادائیگیوں کو دوبارہ جمع کر کے اپڈیٹ کرنا"""
        total = self.payments.aggregate(total=models.Sum('amount'))['total'] or 0
        self.amount_paid = total
        self.update_status_logic()
        self.save(update_fields=['amount_paid', 'status'])

    def save(self, *args, **kwargs):
        if not self.title:
            month_label = f" ({self.month.strftime('%b %Y')})" if self.month else ""
            course_label = f" - {self.course.title}" if self.course else ""
            self.title = f"{self.get_fee_type_display()}{course_label}{month_label}"
        
        self.update_status_logic()
        super().save(*args, **kwargs)


class Fee_Payment(AuditModel):
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="fee_payments")
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="payments")
    fee = models.ForeignKey('Fee', on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(default=timezone.now)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    payment_method = models.CharField(max_length=50, default="Cash")

    class Meta:
        app_label = 'dms'
        verbose_name = "Fee Payment"
        verbose_name_plural = "Fee Payments"
        indexes = [models.Index(fields=['institution', 'payment_date']),]

    def __str__(self):
        return f"REC: {self.receipt_number} - {self.amount}"

    def save(self, *args, **kwargs):
        # اگر پیمنٹ ڈائریکٹ فیس سے جڑی ہے تو اسٹوڈنٹ اور انسٹی ٹیوشن خود اٹھا لے
        if self.fee:
            if not self.student: self.student = self.fee.student
            if not self.institution: self.institution = self.fee.institution

        if not self.receipt_number:
            from dms.logic.payments import generate_transaction_id
            self.receipt_number = generate_transaction_id(self.institution, "FEE", reference_user=self.student)
            
        super().save(*args, **kwargs)


class WalletTransaction(AuditModel):
    class TransactionType(models.TextChoices):
        CREDIT = "credit", "رقم جمع ہوئی (Deposit)"
        DEBIT = "debit", "رقم نکالی گئی (Usage)"

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="wallet_transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    payment_ref = models.ForeignKey('Fee_Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_entries")
    description = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'dms'
        ordering = ("-date",)

    def __str__(self):
        return f"{self.student.full_name} - {self.transaction_type} - {self.amount}"


class Donor(AuditModel):
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="donors")
    name = models.CharField(max_length=200, verbose_name="نام")
    phone = models.CharField(max_length=20, blank=True, verbose_name="فون نمبر")
    email = models.EmailField(blank=True, verbose_name="ای میل")
    address = models.TextField(blank=True, verbose_name="پتہ")

    class Meta:
        ordering = ("name",)
        verbose_name = "عطیہ دہندہ"
        verbose_name_plural = "عطیہ دہندگان"

    def __str__(self):
        return self.name


class Income(AuditModel):
    class Source(models.TextChoices):
        DONATION = "Donation", "عطیہ"
        ZAKAT = "Zakat", "زکوٰۃ"
        SADAQAH = "Sadaqah", "صدقہ"
        FITRA = "Fitra", "فطرانہ"
        ZAKAT_AL_FITR = "Zakat-ul-Fitr", "صدقہ فطر"
        HIDE = "Hide", "کھالیں"
        QURBANI = "Qurbani", "قربانی"
        PUBLICATION = "Publication", "اشاعت/کتب"
        RENT = "Rent", "کرایہ"
        EVENT = "Event", "تقریب"
        GOVT_GRANT = "Govt Grant", "سرکاری گرانٹ"
        FEE = "Fee", "فیس"
        OTHER = "Other", "دیگر"

    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="incomes")
    payment_record = models.OneToOneField('Fee_Payment', on_delete=models.CASCADE, null=True, blank=True, related_name="income_entry")
    donor = models.ForeignKey('Donor', on_delete=models.SET_NULL, null=True, blank=True, related_name="donations")
    source = models.CharField(max_length=50, choices=Source.choices, default=Source.DONATION, verbose_name="ذریعہ")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="رقم")
    date = models.DateField(default=timezone.now, verbose_name="تاریخ")
    description = models.TextField(blank=True, verbose_name="تفصیل")
    receipt_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="رسید نمبر")

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "آمدنی"
        verbose_name_plural = "آمدنی کے اندراجات"
        indexes = [models.Index(fields=['institution', 'date']),]

    def __str__(self):
        source_name = "N/A"
        if self.donor:
            source_name = self.donor.name
        elif self.payment_record and self.payment_record.student:
            source_name = self.payment_record.student.name
        
        return f"{source_name} {self.get_source_display()}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            from dms.logic.payments import generate_transaction_id
            # Try to find a user (Donor or Linked Student)
            ref_user = self.donor
            if not ref_user and self.payment_record:
                ref_user = self.payment_record.student
            
            self.receipt_number = generate_transaction_id(self.institution, "IN", reference_user=ref_user)
            
        super().save(*args, **kwargs)


class Expense(AuditModel):
    class Category(models.TextChoices):
        SALARY = "salary", "تنخواہ"
        FOOD = "food", "خوراک/راشن"
        BOOKS = "books", "کتب و اسٹیشنری"
        UTILITIES = "electricity", "بجلی و برقی اشیاء"
        MAINTENANCE = "maintenance", "مرمت و تعمیرات"
        KHIDMAT = "khidmat", "خدمت خلق"
        OTHER = "other", "دیگر"

    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="expenses")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="رقم")
    category = models.CharField(max_length=50, choices=Category.choices, verbose_name="مد")
    description = models.TextField(blank=True, verbose_name="تفصیل")
    date = models.DateField(default=timezone.now, verbose_name="تاریخ")
    receipt_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="واؤچر نمبر")

    class Meta:
        ordering = ("-date", "-id")
        verbose_name = "خرچ"
        verbose_name_plural = "اخراجات"
        indexes = [models.Index(fields=['institution', 'date']),]

    def __str__(self):
        return f"{self.receipt_number} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            from dms.logic.payments import generate_transaction_id
            self.receipt_number = generate_transaction_id(self.institution, "OUT")
            
        super().save(*args, **kwargs)

