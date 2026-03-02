import json
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.core.cache import cache  # Redis/Cache کے لیے

from .models import Announcement, Expense, Income, Institution, Fee, Enrollment
from .logic.permissions import InstitutionAccess 
from .logic.auth import UserManager
from .logic.institution import InstitutionManager

class HeaderContextBuilder:
    """
    یہ کلاس ہر پیج پر ہیڈر، نوٹیفکیشن اور پرمیشنز کا ڈیٹا تیار کرتی ہے۔
    Senior Level Architecture with Redis Caching & Query Optimization.
    """
    def __init__(self, request):
        self.request = request
        self.user = request.user
        self.now = timezone.now()
        
        # 1. ادارہ اور پرمیشنز کو صرف ایک بار لوڈ کریں
        self.institution = self._resolve_institution()
        self.access = InstitutionAccess(self.user, self.institution) if self.institution else None

    # ==========================================
    # 1. Core Resolvers
    # ==========================================
    def _resolve_institution(self) -> Optional[Institution]:
        match = getattr(self.request, "resolver_match", None)
        if match and (slug := match.kwargs.get("institution_slug")):
            return Institution.objects.only("id", "name", "slug", "type", "logo").filter(slug=slug).first()

        if self.user.is_authenticated:
            return Institution.objects.filter(user=self.user).first()
        return None

    def _safe_reverse(self, name: str) -> str:
        if not self.institution: return "#"
        try: return reverse(name, args=[self.institution.slug])
        except NoReverseMatch: return "#"

    # ==========================================
    # 2. User & Format Helpers
    # ==========================================
    def _get_user_payload(self) -> Dict[str, str]:
        if not self.user.is_authenticated:
            return {"name": "مہمان", "email": "", "role": "", "initials": ""}

        name = self.user.get_full_name() or self.user.get_username() or "یوزر"
        
        # بہتر طریقہ: ادارے کے لحاظ سے رول دکھائیں
        role = ""
        if self.user.is_superuser: 
            role = "سپر ایڈمن / مالک"
        elif self.access and self.access.staff_member:
            # یہ Role Choice کی اردو والی string اٹھا کر لے آئے گا (مثلاً "مہتمم / ناظم تعلیمات")
            role = self.access.staff_member.get_role_display() 
        elif self.user.groups.exists():
            role = self.user.groups.values_list("name", flat=True).first() or ""

        initials = "".join(part[0] for part in name.split() if part)[:2].upper()
        return {"name": name, "email": self.user.email or "", "role": role, "initials": initials}

    def _format_notification(self, type_str, obj, title, desc, amount, icon, color, url, date_field="date"):
        dt = getattr(obj, date_field)
        if type(dt) is not datetime: 
            dt = timezone.make_aware(datetime.combine(dt, time.min))
            
        return {
            "id": f"{type_str}-{obj.id}",
            "timestamp": dt,
            "type": type_str,
            "title": title,
            "description": desc or "",
            "amount": amount,
            "icon": icon,
            "color": color,
            "time": "ابھی" if not (delta := timesince(dt, self.now)) or delta == "0 minutes" else f"{delta} پہلے",
            "time_iso": dt.isoformat(),
            "url": url,
            "is_read": False,
        }

    # ==========================================
    # 3. Notification Engine (with REDIS CACHE)
    # ==========================================
    def _build_notifications(self, currency, limit=8, use_cache=True, model_limit=3) -> List[Dict]:
        """صرف متعلقہ نوٹیفکیشن لائیں، Caching کے ساتھ تاکہ DB پر بوجھ نہ پڑے"""
        
        if not self.institution or (self.access and not self.access.is_linked_user()):
            return []

        # 🚀 CACHE LOGIC START
        cache_key = f"header_notifs_usr_{self.user.id}_inst_{self.institution.id}_limit_{limit}"
        if use_cache:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data  # اگر ڈیٹا Redis میں ہے، تو Database کو مت چھیڑیں!

        entries = []
        
        # A. Finance Notifications (صرف ایڈمن/اکاؤنٹنٹ کے لیے)
        if self.access.can_manage_finance():
            # Incomes (.only() استعمال کر کے میموری بچائی گئی ہے)
            for inc in Income.objects.filter(institution=self.institution).select_related("donor").only('id', 'amount', 'date', 'description', 'source', 'donor', 'donor__name').order_by("-date", "-id")[:model_limit]:
                donor_name = inc.donor.name if hasattr(inc, 'donor') and inc.donor else inc.get_source_display()
                entries.append(self._format_notification(
                    "income", inc, f"{donor_name} سے آمدنی", inc.description, 
                    f"{inc.amount} {currency}", "fa-donate", "green", self._safe_reverse("income")
                ))
                
            # Expenses
            for exp in Expense.objects.filter(institution=self.institution).only('id', 'amount', 'date', 'description', 'category').order_by("-date", "-id")[:model_limit]:
                entries.append(self._format_notification(
                    "expense", exp, f"خرچ: {exp.get_category_display()}", exp.description,
                    f"{exp.amount} {currency}", "fa-receipt", "red", self._safe_reverse("expense")
                ))

            # Fees
            pending_fees = Fee.objects.filter(
                institution=self.institution, 
                status__in=[Fee.Status.PENDING, Fee.Status.PARTIAL, Fee.Status.OVERDUE]
            ).select_related("student").only('id', 'amount_due', 'amount_paid', 'late_fee', 'discount', 'due_date', 'status', 'student__name', 'student', 'title').order_by("due_date")[:model_limit]
            
            for fee in pending_fees:
                amt = f"{getattr(fee, 'balance', fee.amount_due)} {currency}"
                entries.append(self._format_notification(
                    "fee", fee, f"{fee.student.name} - {fee.title}", fee.status,
                    amt, "fa-wallet", "amber", self._safe_reverse("balance"), date_field="due_date"
                ))

        # B. Announcements (سب کے لیے)
        for ann in Announcement.objects.filter(institution=self.institution, is_published=True).only('id', 'title', 'content', 'created_at').order_by("-created_at")[:model_limit]:
            entries.append(self._format_notification(
                "announcement", ann, ann.title, (ann.content or "")[:120],
                "", "fa-bullhorn", "indigo", self._safe_reverse("dashboard"), date_field="created_at"
            ))

        entries.sort(key=lambda x: x["timestamp"], reverse=True)
        final_entries = entries[:limit] if limit else entries

        # 🚀 CACHE DATA FOR 60 SECONDS (1 Minute)
        if use_cache:
            cache.set(cache_key, final_entries, timeout=60)
        
        return final_entries

    # ==========================================
    # 4. Final Output Builder
    # ==========================================
    def get_context(self) -> Dict[str, Any]:
        """فائنل ڈکشنری جو ٹیمپلیٹ کو بھیجی جائے گی"""
        currency = InstitutionManager.get_currency_label(self.institution)
        
        # نوٹیفکیشنز پروسیسنگ (Cache سے یا DB سے)
        raw_notifications = self._build_notifications(currency)
        serializable_notifs =[{k: v for k, v in n.items() if k != "timestamp"} for n in raw_notifications]
        
        # Pending Students Count (صرف اکیڈمک ایڈمن کے لیے)
        pending_students = 0
        if self.institution and self.access and self.access.can_manage_academics():
            pending_students = Enrollment.objects.filter(
                student__institution=self.institution, student__is_active=False, status='pending'
            ).count()

        return {
            "dms_header": {
                "notifications_json": json.dumps(serializable_notifs, ensure_ascii=False),
                "unread_count": sum(1 for n in serializable_notifs if not n.get("is_read")),
                "user": self._get_user_payload(),
                "notifications_url": self._safe_reverse("all_notifications"),
                "all_institutions": UserManager.get_user_institutions(self.user).only("id", "name", "slug", "type") if self.user.is_authenticated else[],
            },
            "currency_label": currency,
            "current_institution": self.institution,
            
            # 🚀 پرمیشنز - Hardcoding کی بجائے Access کلاس کا استعمال
            "is_dms_admin": self.access.can_manage_finance() if self.access else False,
            "is_academic_admin": self.access.can_manage_academics() if self.access else False,
            "can_view_academics": self.access.can_view_academics() if self.access else False,
            "is_staff_admin": self.access.can_view_staff() if self.access else False,
            "can_edit_staff": self.access.can_manage_institution() if self.access else False,
            
            "is_dms_staff": bool(getattr(self.user, 'staff', None)),
            "is_dms_parent": bool(getattr(self.user, 'parent', None)),
            "is_dms_student": bool(getattr(self.user, 'student', None)),
            
            "pending_students_count": pending_students,
        }

# ==========================================
# ACTUAL CONTEXT PROCESSOR FUNCTION
# ==========================================
def header_payload(request) -> Dict[str, Any]:
    """
    Django Settings.py کے Context Processors میں یہی فنکشن کال ہوگا۔
    """
    builder = HeaderContextBuilder(request)
    return builder.get_context()

