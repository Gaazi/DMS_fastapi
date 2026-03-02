from django.shortcuts import render, get_object_or_404
from django.contrib import messages

def public_admission(request, institution_slug):
    """
    عوام کے لیے اوپن داخلہ فارم (بغیر لاگ ان)
    """
    from ..models import Institution, Enrollment
    from ..forms import PublicAdmissionForm
    
    institution = get_object_or_404(Institution, slug=institution_slug)
    
    if request.method == "POST":
        form = PublicAdmissionForm(request.POST, request.FILES, institution=institution)
        if form.is_valid():
            try:
                # 1. طالب علم بنائیں
                student = form.save(commit=False)
                student.institution = institution
                student.is_active = False # ابھی منظوری باقی ہے
                student.save()
                
                # 2. انمولمنٹ (Enrollment) بنائیں
                course = form.cleaned_data.get('course')
                if course:
                    Enrollment.objects.create(
                        student=student, 
                        course=course,
                        status=Enrollment.Status.PENDING,
                    )
                
                # کامیابی کا پیغام
                messages.success(request, "آپ کی درخواست کامیابی سے موصول ہو گئی ہے۔")
                return render(request, "dms/public_admission_success.html", {"institution": institution})
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f"مسئلہ: {str(e)}")
    else:
        form = PublicAdmissionForm(institution=institution)
    
    return render(request, "dms/public_admission.html", {
        "institution": institution,
        "form": form
    })
