from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from ..logic.auth import UserManager

from ..forms.institution_forms import InstitutionCreationForm
from ..models import Institution

@login_required
def no_institution_linked(request):
    """
    View shown when a user is logged in but has no institution assigned.
    Also handles the self-service registration of new institutions.
    """
    # Check if user already has an institution (any role)
    insts = UserManager.get_user_institutions(request.user)
    
    if insts.exists():
        # Check if any of these institutions are approved
        best_inst = insts.filter(is_approved=True).first()
        if best_inst:
            return redirect('dashboard', institution_slug=best_inst.slug)
        else:
            # Show "Pending Approval" state for their first institution
            return render(request, "no_institution_linked.html", {
                "pending": True, 
                "institution": insts.first()
            })

    # Handle New Registration
    if request.method == 'POST':
        form = InstitutionCreationForm(request.POST)
        if form.is_valid():
            inst = form.save(commit=False)
            inst.user = request.user
            inst.is_approved = False  # Explicitly set to False
            inst.save()
            return redirect('no_institution_linked')
    else:
        form = InstitutionCreationForm()

    return render(request, "no_institution_linked.html", {"form": form})

def dms_logout(request, institution_slug=None):
    logout(request)
    return redirect('dms')

def dms_login(request, institution_slug=None):
    if request.user.is_authenticated:
        # Check for default institution preference
        default_inst = Institution.objects.filter(user=request.user, is_default=True).first()
        if default_inst:
            return redirect('dashboard', institution_slug=default_inst.slug)
            
        return redirect(UserManager.get_post_login_redirect(request.user))

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Check for default institution preference
        default_inst = Institution.objects.filter(user=user, is_default=True).first()
        if default_inst:
            return redirect('dashboard', institution_slug=default_inst.slug)

        return redirect(UserManager.get_post_login_redirect(user))

    return render(request, 'login.html', {'form': form})

def signup(request):
    success, message, form = UserManager.handle_signup(request)
    if success:
        return redirect("no_institution_linked")
    return render(request, "signup.html", {"form": form})

@login_required
def set_default_institution(request, institution_slug):
    """Sets the given institution as default for the logged-in user."""
    inst = Institution.objects.get(slug=institution_slug, user=request.user)
    inst.is_default = True
    inst.save()
    
    from django.contrib import messages
    messages.success(request, f"{inst.name} is now your default institution.")
    
    # Redirect back to where the user came from
    return redirect(request.META.get('HTTP_REFERER', 'dms'))

@login_required
def create_portal_account(request, institution_slug, person_type, person_id):
    """
    On-Demand User Provisioning. 
    انتظامیہ کے کلک کرنے پر یہ فنکشن چلے گا اور متعلقہ بندے کا اکاؤنٹ کرئیٹ کرے گا۔
    """
    from ..logic.permissions import get_institution_with_access
    from django.contrib import messages
    from ..models import Staff, Student, Parent
    
    # صرف ایڈمن/صدر وغیرہ ہی اکاؤنٹ بنا سکتے ہیں
    inst, access = get_institution_with_access(institution_slug, request, access_type='admin')
    
    model_map = {
        'staff': Staff,
        'student': Student,
        'parent': Parent
    }
    
    model = model_map.get(person_type)
    if not model:
        messages.error(request, "غلط اکاؤنٹ ٹائپ۔")
        return redirect(request.META.get('HTTP_REFERER', 'dms'))
        
    from django.shortcuts import get_object_or_404
    person = get_object_or_404(model, pk=person_id, institution=inst)
    
    if person.user:
        messages.warning(request, f"{person.name} کا اکاؤنٹ پہلے سے موجود ہے!")
        return redirect(request.META.get('HTTP_REFERER', 'dms'))
        
    try:
        # UserManager.ensure_user خودکار طور پر یزرنیم، پاس ورڈ اور گروپ ہینڈل کرتا ہے
        password = UserManager.ensure_user(person, prefix=person_type)
        if password:
            UserManager.notify_credentials(request, person, password)
            messages.success(request, f"{person.name} کا نیا پورٹل اکاؤنٹ بن گیا ہے!")
    except Exception as e:
        messages.error(request, f"اکاؤنٹ بنانے میں مسئلہ پیش آیا: {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'dms'))
