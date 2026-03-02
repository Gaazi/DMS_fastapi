from django.shortcuts import get_object_or_404
from ..models import Facility

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: FacilityManager (Line 14)
   - Management:
     * get_all (Line 48)
     * save_facility (Line 53)
     * delete_facility (Line 76)
   - View Logic:
     * handle_facility_actions (Line 86)
     * get_list_context (Line 111)
"""

class FacilityManager:
    """Business logic for managing institution facilities and assets"""
    
    def __init__(self, user, institution=None):
        """یوزر اور ادارے کی معلومات کے ساتھ سہولیات (Facilities) مینیجر کو شروع کرنا۔"""
        self.user = user
        self.institution = institution
        
        # Resolve institution from user profile if not provided
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def _check_access(self):
        """سیکیورٹی چیک: سہولیات کے ریکارڈز تک رسائی کے حقوق کی تصدیق۔"""
        from django.core.exceptions import PermissionDenied
        
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("Institution context missing.")

        is_owner = (self.user == self.institution.user)
        is_staff = hasattr(self.user, 'staff') and (self.user.staff.institution == self.institution)
        
        if not (is_owner or is_staff):
            raise PermissionDenied("Access denied to facility management.")
        return True

    def get_all(self):
        """ادارے کی تمام دستیاب سہولیات (کمرے، لائبریری وغیرہ) کی فہرست حاصل کرنا۔"""
        if not self.institution: return []
        return self.institution.facilities.order_by('name')

    def save_facility(self, name, facility_type, is_available=True, facility_id=None):
        """نئی سہولت کا اندراج کرنا یا پہلے سے موجود ریکارڈ میں تبدیلی کرنا۔"""
        self._check_access()
        try:
            if facility_id:
                facility = get_object_or_404(Facility, pk=facility_id, institution=self.institution)
                facility.name = name
                facility.facility_type = facility_type
                facility.is_available = is_available
                facility.save()
                message = f"Facility '{name}' updated successfully."
            else:
                facility = Facility.objects.create(
                    institution=self.institution,
                    name=name,
                    facility_type=facility_type,
                    is_available=is_available
                )
                message = f"Facility '{name}' created successfully."
            return True, message, facility
        except Exception as e:
            return False, f"Error saving facility: {str(e)}", None

    def delete_facility(self, facility_id):
        """کسی مخصوص سہولت کے ریکارڈ کو ڈیٹا بیس سے مستقل طور پر حذف کرنا۔"""
        self._check_access()
        try:
            facility = get_object_or_404(Facility, pk=facility_id, institution=self.institution)
            name = facility.name
            facility.delete()
            return True, f"Facility '{name}' deleted.", None
        except Exception as e:
            return False, f"Error deleting facility: {str(e)}", None
    def handle_facility_actions(self, request):
        """سہولیات کے POST ایکشنز (محفوظ کرنا، ڈیلیٹ کرنا) کو سنبھالنا"""
        self._check_access()
        action = request.POST.get("action")
        facility_id = request.POST.get("facility_id")
        
        if action == "delete":
            return self.delete_facility(facility_id)
            
        from ..forms import FacilityForm
        editing_facility = None
        if facility_id:
             editing_facility = get_object_or_404(Facility, pk=facility_id, institution=self.institution)
             
        form = FacilityForm(request.POST, instance=editing_facility)
        if form.is_valid():
             return self.save_facility(
                 name=form.cleaned_data['name'],
                 facility_type=form.cleaned_data['facility_type'],
                 is_available=form.cleaned_data['is_available'],
                 facility_id=facility_id
             )
             
        return False, "فارم میں غلطیاں ہیں، براہ کرم درست کریں۔", form

    def get_list_context(self, request, override_form=None):
        """تیاری: سہولیات (Facilities) کی فہرست کا سیاق و سباق"""
        self._check_access()
        from ..forms import FacilityForm
        
        edit_id = request.GET.get("edit")
        editing_facility = None
        if edit_id:
            editing_facility = get_object_or_404(Facility, pk=edit_id, institution=self.institution)
            
        form = override_form or FacilityForm(instance=editing_facility)
        
        facilities = self.get_all()
        return {
            "institution": self.institution,
            "facilities": facilities,
            "form": form,
            "editing_facility": editing_facility,
            "available_count": facilities.filter(is_available=True).count(),
            "facility_types_count": facilities.values('facility_type').distinct().count(),
        }
