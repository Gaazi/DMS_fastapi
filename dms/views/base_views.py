from django.shortcuts import render, redirect, get_object_or_404, resolve_url
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib import messages

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - dms (Line 12) - Public landing page
   - redirect_institution_slug (Line 29) - Smart role-based redirection
   - institution_overview (Line 58) - SuperAdmin global report
   - dashboard (Line 68) - Main institution dashboard
   - service_worker/manifest (Line 88-96) - PWA support
"""
from django.http import Http404

from ..models import Institution
from ..constants import VALID_TYPES
from ..logic.institution import InstitutionManager
from ..logic.permissions import get_institution_with_access, InstitutionAccess

def dms(request):
    from ..models import Institution, Income, Expense
    from django.db.models import Sum
    from django.core.cache import cache
    
    # Attempt to get stats from cache to speed up the public/home page
    stats = cache.get('dms_global_stats')
    if not stats:
        total_inst = Institution.objects.count()
        income_sum = Income.objects.aggregate(s=Sum('amount'))['s'] or 0
        expense_sum = Expense.objects.aggregate(s=Sum('amount'))['s'] or 0
        stats = {
            "total_institutions": total_inst,
            "total_income": income_sum,
            "total_expense": expense_sum,
            "total_balance": income_sum - expense_sum,
        }
    # --- GLOBAL ZERO-TOUCH AUTOMATION FALLBACK ---
    # Even if an institution admin NEVER logs in, this background trap will trigger 
    # if ANYONE (even a Google Bot or Uptime Monitor) visits the main website.
    from django.utils import timezone
    import threading
    
    # We only trigger this global event on or AFTER the 15th of the month!
    now = timezone.localtime()
    if now.day >= 15:
        current_month_global = f"global_fees_{now.month}_{now.year}"
        # ATOMIC LOCK: cache.add only returns True if the key didn't exist. Prevention from Thread Bombing.
        if cache.add(current_month_global, 'processing', timeout=86400):
            # We spawn a background thread so the user doesn't wait for 100+ institutions to process
            def background_global_auto_generation():
                from django.core.management import call_command
                try:
                    call_command('generate_monthly_fees')
                    # Cache for exactly one month (in seconds) indicating success
                    cache.set(current_month_global, 'completed', timeout=2592000)
                except Exception as e:
                    # Silent fail in background, but release the lock early (1 hour) to allow retry
                    cache.set(current_month_global, 'failed', timeout=3600)
                    
            t = threading.Thread(target=background_global_auto_generation)
            t.daemon = True
            t.start()
    # ---------------------------------------------
    
    context = {
        **stats,
        "currency_label": "PKR"
    }
    
    return render(request, "dms/dms.html", context)

@login_required
def share_target(request):
    text = request.GET.get('text', '')
    title = request.GET.get('title', '')
    url = request.GET.get('url', '')
    
    # Logic to find default institution
    from ..logic.auth import UserManager
    insts = UserManager.get_user_institutions(request.user)
    if insts.exists():
        # Show shared content as a message
        content = f"{title} {text} {url}".strip()
        if content:
             messages.info(request, f"Shared Content: {content}")
        
        from django.urls import reverse
        return redirect('dashboard', institution_slug=insts.first().slug)
        
    return redirect('dms')

@login_required
def smart_shortcut(request, action):
    """
    Redirects PWA shortcuts to the user's primary institution context.
    Action can be 'in' (Income) or 'out' (Expense).
    """
    from ..logic.auth import UserManager
    insts = UserManager.get_user_institutions(request.user)
    
    if not insts.exists():
        messages.error(request, "No institution linked to your account.")
        return redirect('dms')
        
    slug = insts.first().slug
    
    redirect_map = {
        'in': 'income',
        'out': 'expense',
        'admission': 'admission',
        'students': 'student_list'
    }
    
    view_name = redirect_map.get(action, 'dashboard')
    return redirect(view_name, institution_slug=slug)

@login_required
def redirect_institution_slug(request, institution_slug):
    # Graceful handling for Pending Institutions (Redirect Owner)
    temp_inst = Institution.objects.filter(slug=institution_slug).only('is_approved', 'user').first()
    if temp_inst:
        if temp_inst.is_approved:
             return redirect('dashboard', institution_slug=institution_slug)
             
        if not temp_inst.is_approved and temp_inst.user_id == request.user.id:
            return redirect('no_institution_linked')

    institution = get_object_or_404(Institution, slug=institution_slug)
    access = InstitutionAccess(request.user, institution)
    
    # 1. Staff or Owner -> Main Dashboard
    if access.can_view_academics() or access.can_manage_finance():
        return redirect("dashboard", institution_slug=institution.slug)
    
    # 2. Student -> Self Dashboard
    student = getattr(request.user, 'student', None)
    if student and student.institution_id == institution.id:
        return redirect("student_dashboard_scoped", institution_slug=institution.slug, student_id=student.id)
        
    # 3. Parent -> Guardian Dashboard
    parent = getattr(request.user, 'parent', None)
    if parent and parent.institution_id == institution.id:
        return redirect("guardian_dashboard_scoped", institution_slug=institution.slug)
        
    return redirect("dashboard", institution_slug=institution.slug)

@login_required(login_url="dms_login")
def institution_overview(request):
    from ..logic.global_logic import GlobalManager
    gm = GlobalManager(request.user)
    return render(request, "dms/institution_overview.html", gm.get_global_overview())

# @login_required
# def institution_type_list(request, institution_type):
#     # --- Auto-Redirect for Regular Users ---
#     if not request.user.is_superuser:
#         from ..logic.auth import UserManager
#         unique_insts = UserManager.get_user_institutions(request.user)
#             
#         # اگر صرف ایک ادارہ ہے، تو ڈائریکٹ جائیں۔ اگر زیادہ ہیں تو لسٹ دکھائیں۔
#         if unique_insts.count() == 1:
#             return redirect('dashboard', institution_slug=unique_insts.first().slug)

#     from ..logic.global_logic import GlobalManager
#     gm = GlobalManager(request.user)
#     return render(request, "dms/institution_type_list.html", gm.get_type_list_context(institution_type))

def dashboard(request, institution_slug):
    institution = get_object_or_404(Institution, slug=institution_slug)
    access = InstitutionAccess(request.user, institution)

    # Graceful handling for Pending Institutions
    if not institution.is_approved and not access.is_superuser:
        if access.is_owner:
            return redirect('no_institution_linked')
        raise PermissionDenied("Institution Pending Approval")

    if request.user.is_authenticated:
        # 1. Staff or Owner -> Main Dashboard
        if access.can_view_academics() or access.can_manage_finance():
            # --- Improved Background Automation (Runs in background on dashboard view) ---
            from django.core.cache import cache
            from django.utils import timezone
            now = timezone.localtime() # Get exact local time
            
            # مہینے اور سال کا ایک منفرد نشان (e.g. "3_2026")
            current_month_token = f"{now.month}_{now.year}"
            
            # UNIQUE KEYS PER MONTH
            cleanup_key = f"auto_cleanup_month_{institution.id}_{current_month_token}"
            fee_key = f"auto_fee_month_{institution.id}_{current_month_token}"
            
            # --- 1. Robotic Auto-Cleanup of Dead Accounts (Runs ONLY once per month) ---
            # ATOMIC LOCK (cache.add) prevents Race Conditions
            if cache.add(cleanup_key, 'done', timeout=2592000): # 30 Days expiry
                from dms.logic.auth import UserManager
                suspended_count, deleted_count = UserManager.run_smart_auto_cleanup(institution)
                
                # Feedback Logs
                if suspended_count > 0 or deleted_count > 0:
                    msg = f"🤖 ماہانہ روبوٹک کلین اپ: سسٹم نے {suspended_count} اکاؤنٹس کو معطل"
                    if deleted_count > 0:
                        msg += f" اور {deleted_count} لاوارث اکاؤنٹس کو ڈیلیٹ"
                    msg += " کر دیا ہے۔"
                    messages.info(request, msg)

            # --- 2. FULLY AUTOMATIC ZERO-CLICK FEE GENERATION (Runs on or after the 15th) ---
            # ATOMIC LOCK (cache.add) prevents Double Duplicate Fees!
            if now.day >= 15 and cache.add(fee_key, 'done', timeout=2592000): # 30 Days expiry
                from dms.logic.finance import FinanceManager
                fm = FinanceManager(request.user, institution=institution)
                auto_fees_count = fm.auto_generate_fees()
                
                if auto_fees_count > 0:
                    messages.success(request, f"🚀 آٹو-فیس الرٹ: سسٹم نے شیڈول کے مطابق خودکار طور پر {auto_fees_count} فیسیں کامیابی سے جاری کر دی ہیں۔")
            # -------------------------------------------------------------------------
            im = InstitutionManager(request.user, institution)
            return render(request, "dms/dashboard.html", im.get_dashboard_data())
        
        # 2. Student Dashboard
        student = getattr(request.user, 'student', None)
        if student and student.institution_id == institution.id:
            return redirect("student_dashboard_scoped", institution_slug=institution.slug, student_id=student.id)
            
        # 3. Parent -> Guardian Dashboard
        parent = getattr(request.user, 'parent', None)
        if parent and parent.institution_id == institution.id:
            return redirect("guardian_dashboard_scoped", institution_slug=institution.slug)

    # Otherwise (unauthenticated or unlinked user) show the Public Home Page
    return render(request, "dms/public_home.html", {"institution": institution})

@login_required
def institution_detail(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request)
    is_admin = access.can_manage_institution()

    if request.method == "POST":
        if not is_admin:
            raise PermissionDenied("You do not have permission to edit settings.")
            
        institution.name = request.POST.get('name', institution.name)
        institution.type = request.POST.get('institution_type', institution.type)
        institution.phone = request.POST.get('phone', institution.phone)
        institution.email = request.POST.get('email', institution.email)
        institution.address = request.POST.get('address', institution.address)
        
        if 'logo' in request.FILES:
            institution.logo = request.FILES['logo']
            
        institution.save()
        messages.success(request, "Settings updated successfully.")
        return redirect('institution_detail', institution_slug=institution.slug)

    im = InstitutionManager(request.user, institution)
    context = im.get_dashboard_data()
    context['is_admin'] = is_admin
    
    if request.headers.get("HX-Request"):
        return render(request, "dms/partials/institution_detail_partial.html", context)
        
    return render(request, "dms/institution_settings.html", context)

@login_required
def admin_tools_view(request, institution_slug):
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    return render(request, "dms/tools.html", {"institution": institution})

@login_required
def manage_accounts(request, institution_slug):
    """
    یوزر اکاؤنٹس کو منظم کرنے (Active/Inactive) اور ڈیلیٹ کرنے کا کنٹرول پینل۔
    یہاں صرف ادارے سے منسلک یوزرز نظر آئیں گے۔
    """
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='admin')
    
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    
    # صرف اسی ادارے کے یوزرز تلاش کریں
    inst_users = User.objects.filter(
        Q(staff__institution=institution) | 
        Q(student__institution=institution) | 
        Q(parent__institution=institution)
    ).distinct()

    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")
        
        target_user = inst_users.filter(id=user_id).first()
        if target_user and not target_user.is_superuser:
            # 🚨 انتہاٸی اہم سیفٹی چیک: کسی بھی ادارے کے مالک (Owner) کو ہاتھ نہ لگانے دیں
            from dms.models.foundation_model import Institution as FoundationInstitution
            is_any_owner = FoundationInstitution.objects.filter(user=target_user).exists()
            
            if target_user == institution.user or is_any_owner:
                messages.error(request, "سسٹم الرٹ: اس اکاؤنٹ کو ڈیلیٹ یا معطل نہیں کیا جا سکتا کیونکہ یہ ماسٹر اونر ہے!")
                return redirect('manage_accounts', institution_slug=institution.slug)

            # BUGFIX: Mutli-Tenant Account Suspension 
            # We must verify if the user is linked to another institution before suspending globally. 
            from dms.models import Staff, Student, Parent
            has_other_links = (
                Staff.objects.filter(user=target_user).exclude(institution=institution).exists() or
                Student.objects.filter(user=target_user).exclude(institution=institution).exists() or
                Parent.objects.filter(user=target_user).exclude(institution=institution).exists()
            )

            if action == "deactivate":
                if has_other_links:
                    # Only suspend local profiles
                    Staff.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    Student.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    Parent.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    messages.warning(request, f"یوزر '{target_user.username}' کی اس ادارے تک رسائی معطل کر دی گئی ہے۔ (یہ کسی اور ادارے سے منسلک تھا اس لیے پورٹل اکاؤنٹ بند نہیں کیا گیا)")
                else:
                    # User is only connected here, suspend globally
                    target_user.is_active = False
                    target_user.save(update_fields=['is_active'])
                    # Also suspend their local profiles for consistency
                    Staff.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    Student.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    Parent.objects.filter(user=target_user, institution=institution).update(is_active=False)
                    messages.warning(request, f"یوزر '{target_user.username}' کا اکاؤنٹ مکمل طور پر غیر فعال (Suspended) کر دیا گیا ہے۔")
                    
            elif action == "activate":
                # Always activate global user account to guarantee login fixes
                target_user.is_active = True
                target_user.save(update_fields=['is_active'])
                # Also activate their local profiles
                Staff.objects.filter(user=target_user, institution=institution).update(is_active=True)
                Student.objects.filter(user=target_user, institution=institution).update(is_active=True)
                Parent.objects.filter(user=target_user, institution=institution).update(is_active=True)
                messages.success(request, f"یوزر '{target_user.username}' کا اکاؤنٹ اور پروفائلز فعال کر دیے گئے ہیں۔")
            elif action == "delete":
                username = target_user.username
                
                # BUGFIX: Preventing Multi-Tenant Data Loss!
                # If the user is linked to OTHER institutions, do NOT delete their global User object.
                # Just unlink them from this specific institution's profiles.
                from django.db.models import Prefetch
                from dms.models import Staff, Student, Parent
                
                has_other_links = (
                    Staff.objects.filter(user=target_user).exclude(institution=institution).exists() or
                    Student.objects.filter(user=target_user).exclude(institution=institution).exists() or
                    Parent.objects.filter(user=target_user).exclude(institution=institution).exists()
                )
                
                if has_other_links:
                    # Sirf is idaray se un-link karo (Safe Disconnect)
                    Staff.objects.filter(user=target_user, institution=institution).update(user=None)
                    Student.objects.filter(user=target_user, institution=institution).update(user=None)
                    Parent.objects.filter(user=target_user, institution=institution).update(user=None)
                    messages.warning(request, f"یوزر '{username}' کا تعلق آپ کے ادارے سے ختم کر دیا گیا ہے۔ (یہ کسی اور ادارے سے منسلک تھا اس لیے اکاؤنٹ مکمل ڈیلیٹ نہیں کیا گیا)")
                else:
                    # Agar kisi aur idaray se link nahi hai to pora account hamesha k liye delete kar do
                    target_user.delete() # یہ اصل پروفائل کو نہیں (SET_NULL) کرے گا، صرف لاگ ان ڈیلیٹ کرے گا۔
                    messages.error(request, f"پورٹل اکاؤنٹ '{username}' کو ہمیشہ کے لیے ڈیلیٹ کر دیا گیا ہے۔")
        
        # --- Monthly Auto Cleanup Feature ---
        if action == "auto_cleanup":
            from dms.logic.auth import UserManager
            suspended_count, deleted_count = UserManager.run_smart_auto_cleanup(institution)
            
            if suspended_count > 0 or deleted_count > 0:
                msg = f"زبردست! سسٹم نے {suspended_count} اکاؤنٹس کو معطل"
                if deleted_count > 0:
                    msg += f" اور {deleted_count} (18 ماہ پرانے) اکاؤنٹس کو جڑ سے ڈیلیٹ"
                msg += " کر دیا ہے۔"
                messages.success(request, msg)
            else:
                messages.info(request, "سسٹم بالکل صاف ہے۔ اس مہینے کوئی بھی پرانا یا لاوارث اکاؤنٹ موجود نہیں ملا۔")
            
        return redirect('manage_accounts', institution_slug=institution.slug)

    context = {
        "institution": institution,
        "active_users": inst_users.filter(is_active=True).order_by('-date_joined'),
        "inactive_users": inst_users.filter(is_active=False).order_by('-date_joined'),
        "total": inst_users.count()
    }
    return render(request, "dms/manage_accounts.html", context)

import os
from django.http import HttpResponse
from django.conf import settings

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'service-worker.js')
    try:
        with open(sw_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="application/javascript")
    except FileNotFoundError:
        return HttpResponse("Service worker not found", status=404)

def manifest(request):
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    try:
        with open(manifest_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="application/json")
    except FileNotFoundError:
        return HttpResponse("Manifest not found", status=404)



@login_required
def all_notifications(request, institution_slug):
    """
    Shows a comprehensive list of all notifications.
    """
    from ..context_processors import HeaderContextBuilder
    from ..logic.institution import InstitutionManager
    
    builder = HeaderContextBuilder(request)
    if not builder.institution:
        return redirect("dms")
        
    currency = InstitutionManager.get_currency_label(builder.institution)
    
    # Get un-cached, larger limit notifications
    notifications = builder._build_notifications(currency, limit=50, use_cache=False, model_limit=20)
    
    return render(request, "dms/all_notifications.html", {
        "notifications": notifications,
        "currency_label": currency,
        "institution": builder.institution,
    })
