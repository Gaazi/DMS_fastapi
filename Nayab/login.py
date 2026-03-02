from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse

from masjid.models import MasjidInstitution
from madrasa.models import MadrasaInstitution
from maktab.models import MaktabInstitution


GROUP_TO_INSTITUTION = {
    "Masjid": ("masjid:dashboard", MasjidInstitution),
    "Madrasa": ("madrasa:dashboard", MadrasaInstitution),
    "Maktab": ("maktab:dashboard", MaktabInstitution),
}


def _institution_dashboard_url_for_user(user, group_name):
    mapping = GROUP_TO_INSTITUTION.get(group_name)
    if not mapping:
        return None

    url_name, model_cls = mapping
    institution = model_cls.objects.filter(user=user).first()
    if not institution:
        return None
    return reverse(url_name, args=[institution.slug])


def login(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)

            if user.groups.filter(name="First_Year").exists():
                return redirect("first_year")
            if user.groups.filter(name="Second_Year").exists():
                return redirect("second_year")
            if user.groups.filter(name="Third_Year").exists():
                return redirect("third_year")

            for group_name in GROUP_TO_INSTITUTION.keys():
                if user.groups.filter(name=group_name).exists():
                    dashboard_url = _institution_dashboard_url_for_user(
                        user, group_name
                    )
                    if dashboard_url:
                        return redirect(dashboard_url)
                    messages.warning(
                        request,
                        "متعلقہ ادارے کی معلومات نہیں مل سکیں، براہ کرم ایڈمن سے رابطہ کریں۔",
                    )
                    break

            return redirect("student")

        messages.error(request, "غلط صارف نام یا پاس ورڈ۔")

    return render(request, "login.html", {"form": form})


@login_required
def logout(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')
