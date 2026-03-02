from typing import Any, Tuple
from django.db import transaction
from django.db.models import Sum, Avg, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from ..models import Income, Donor

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: DonationManager (Line 20)
   - Analytics:
     * get_detailed_summary (Line 52)
     * get_donor_analytics (Line 102)
     * get_top_donors (Line 114)
   - Management:
     * get_donation_list_context (Line 78)
     * record_donation (Line 121)
     * get_donation_dashboard_context (Line 133)
"""

class DonationManager:
    """Business logic for managing institution income and donors"""
    
    def __init__(self, user, institution=None):
        """یوزر اور ادارے کی معلومات کے ساتھ ڈونیشن مینیجر کو شروع کرنا۔"""
        self.user = user
        self.institution = institution
        
        # Resolve institution from user profile if not provided
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def _check_access(self):
        """سیکیورٹی چیک: آمدنی کے ریکارڈز تک رسائی کے حقوق کی تصدیق۔"""
        from django.core.exceptions import PermissionDenied
        
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("Institution context not found.")

        is_owner = (self.user == self.institution.user)
        if not is_owner:
             raise PermissionDenied("Access denied to donation records.")
        return True

    def get_detailed_summary(self):
        """آمدنی کا تفصیلی خلاصہ، بشمول کل رقم اور ماہانہ رجحان۔"""
        stats = Income.objects.filter(institution=self.institution).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            avg=Avg('amount')
        )
        
        latest = Income.objects.filter(institution=self.institution).order_by('-date', '-id').first()
        
        monthly = (
            Income.objects.filter(institution=self.institution)
            .annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('-month')[:6]
        )

        return {
            'total_amount': stats['total'] or 0,
            'donation_count': stats['count'] or 0,
            'average_amount': stats['avg'] or 0,
            'latest_donation': latest,
            'monthly_totals': monthly
        }

    def get_donation_list_context(self, page=1, page_size=20):
        """عطیات کی فہرست والے صفحے کے لیے ڈیٹا اور صفحہ بندی (Pagination) تیار کرنا۔"""
        self._check_access()
        from django.core.paginator import Paginator
        from ..logic.institution import InstitutionManager
        
        income_qs = Income.objects.filter(institution=self.institution).select_related("donor").order_by("-date", "-id")
        
        stats = income_qs.aggregate(
            total=Sum('amount'),
            avg=Avg('amount'),
            count=Count('id')
        )
        
        paginator = Paginator(income_qs, page_size)
        page_obj = paginator.get_page(page)
        
        return {
            "donations": page_obj,
            "total_donations": stats['total'] or 0,
            "average_donation": stats['avg'] or 0,
            "donation_count": stats['count'] or 0,
            "donors": self.institution.donors.all(),
            "institution": self.institution,
            "currency_label": InstitutionManager.get_currency_label(self.institution)
        }

    def get_donor_analytics(self, donor):
        """کسی مخصوص ڈونر کی طرف سے دی گئی کل رقم اور اس کی تاریخ کا تجزیہ۔"""
        self._check_access()
        donations = donor.donations.all().order_by("-date")
        total = donations.aggregate(s=Sum("amount"))["s"] or 0
        
        return {
            "donor": donor,
            "donations": donations,
            "total_donated": total
        }

    def get_top_donors(self, limit=5):
        """سب سے زیادہ مالی تعاون کرنے والے نمایاں ڈونرز کی فہرست۔"""
        return Donor.objects.filter(institution=self.institution).annotate(
            total=Sum('donations__amount'),
            count=Count('donations')
        ).filter(total__gt=0).order_by('-total')[:limit]

    def record_donation(self, donor, amount, date=None, source="Donation", description=""):
        """نئے عطیہ یا آمدنی کی ٹرانزیکشن کا اندراج کرنا۔"""
        self._check_access()
        return Income.objects.create(
            institution=self.institution,
            donor=donor,
            amount=amount,
            date=date or timezone.now().date(),
            source=source,
            description=description
        )

    def get_donation_dashboard_context(self):
        """آمدنی کے ڈیش بورڈ کے لیے مکمل مالیاتی اعداد و شمار اکٹھے کرنا۔"""
        self._check_access()
        context = self.get_detailed_summary()
        context["top_donors"] = self.get_top_donors()
        context["institution"] = self.institution
        context["donations"] = self.institution.incomes.all().order_by("-date", "-id")[:20]
        from ..logic.institution import InstitutionManager
        context["currency_label"] = InstitutionManager.get_currency_label(self.institution)
        return context

    def get_donor_list_context(self, page=1, page_size=50):
        """ادارے کے تمام عطیہ دہندگان (Donors) کی فہرست اور ان کا خلاصہ۔"""
        self._check_access()
        from django.core.paginator import Paginator
        
        donors_qs = Donor.objects.filter(institution=self.institution).annotate(
            total=Sum('donations__amount'),
            count=Count('donations')
        ).order_by('-total')

        overall_total = donors_qs.aggregate(sum=Sum('total'))['sum'] or 0
        
        paginator = Paginator(donors_qs, page_size)
        page_obj = paginator.get_page(page)
        
        from ..logic.institution import InstitutionManager
        return {
            "donors": page_obj,
            "institution": self.institution,
            "total_count": donors_qs.count(),
            "overall_total": overall_total,
            "currency_label": InstitutionManager.get_currency_label(self.institution)
        }
    @transaction.atomic
    def get_or_create_donor(self, name: str, phone: str = "", email: str = "", address: str = "") -> Tuple[Donor, bool]:
        """نام اور فون کی بنیاد پر ڈونر تلاش کرنا یا نیا بنانا۔"""
        self._check_access()
        if not name:
            raise ValueError("ڈونر کا نام ضروری ہے")
            
        donor = Donor.objects.filter(institution=self.institution, name=name, phone=phone).first()
        created = False
        if not donor:
            donor = Donor.objects.create(
                institution=self.institution,
                name=name,
                phone=phone,
                email=email,
                address=address
            )
            created = True
        return donor, created

    def handle_donor_action(self, request, action="list") -> Tuple[bool, str, Any]:
        """ویوز (Views) سے آنے والے ڈونر سے متعلق ایکشنز کو ہینڈل کرنا۔"""
        self._check_access()
        
        if request.method == "POST":
            name = request.POST.get('new_donor_name')
            phone = request.POST.get('new_donor_phone', '')
            email = request.POST.get('new_donor_email', '')
            address = request.POST.get('new_donor_address', '')
            
            try:
                donor, created = self.get_or_create_donor(name, phone, email, address)
                msg = f"{donor.name} محفوظ ہو گیا!" if created else f"{donor.name} کا ریکارڈ مل گیا"
                return True, msg, donor
            except Exception as e:
                return False, str(e), None
        
        # Default: List context
        return True, "", self.get_donor_list_context(page=request.GET.get("page"))

    @transaction.atomic
    def handle_public_donation(self, request) -> Tuple[bool, str, Any]:
        """عوامی (Public) عطیہ کو محفوظ کرنا۔"""
        from ..forms import PublicSupportForm
        form = PublicSupportForm(request.POST)
        
        if form.is_valid():
            name = form.cleaned_data['donor_name']
            phone = form.cleaned_data['donor_phone']
            amount = form.cleaned_data['amount']
            desc = form.cleaned_data['description']
            
            # Use local helper to find or create donor
            donor = Donor.objects.filter(institution=self.institution, phone=phone).first()
            if not donor:
                donor = Donor.objects.create(institution=self.institution, name=name, phone=phone)
            
            # Record Income (Atomic)
            Income.objects.create(
                institution=self.institution,
                donor=donor,
                amount=amount,
                source=Income.Source.DONATION,
                description=f"Public Donation: {desc}"
            )
            return True, f"شکریہ {name}! آپ کا {amount} کا عطیہ موصول ہو گیا ہے۔", form
            
        return False, "فارم میں غلطی ہے، براہ کرم درست کریں۔", form
