from django.apps import apps
from django.core.exceptions import PermissionDenied
from safedelete.models import SafeDeleteModel

class AuditManager:
    """لاگز اور ریسائیکل بن کی مینجمنٹ (بہتر اور محفوظ ورژن)"""

    # تمام ماڈلز کی لسٹ ایک ہی جگہ رکھیں تاکہ مینجمنٹ آسان ہو
    TRACKED_MODELS = [
        ('dms', 'Student'), ('dms', 'Staff'), ('dms', 'Course'),
        ('dms', 'Fee'), ('dms', 'Income'), ('dms', 'Expense'),
        ('dms', 'Institution')
    ]

    def __init__(self, user, institution=None):
        self.user = user
        self.institution = institution

    def get_logs(self, limit=100):
        """سسٹم میں ہونے والی تبدیلیوں کے لاگز حاصل کرنا"""
        all_history = []
        
        for app, model_name in self.TRACKED_MODELS:
            try:
                model = apps.get_model(app, model_name)
                if hasattr(model, 'history'):
                    # فلٹر کریں کہ صرف اسی ادارے کے لاگز آئیں
                    qs = model.history.all()
                    if hasattr(model, 'institution'):
                        qs = qs.filter(institution=self.institution)
                    
                    for h in qs[:limit]:
                        all_history.append({
                            'timestamp': h.history_date,
                            'user': h.history_user,
                            'action': 'create' if h.history_type == '+' else 'update' if h.history_type == '~' else 'delete',
                            'model_name': model_name,
                            'object_repr': str(h.instance) if h.history_type != '-' else f"{model_name} #{h.pk}",
                        })
            except LookupError:
                continue
        
        all_history.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_history[:limit]

    def get_trash_items(self):
        """حذف شدہ اشیاء (ریسائیکل بن) کی فہرست"""
        trash = []
        
        for app, model_name in self.TRACKED_MODELS:
            try:
                model = apps.get_model(app, model_name)
                # صرف حذف شدہ (Soft Deleted) ریکارڈز
                qs = model.objects.deleted_only()
                if hasattr(model, 'institution'):
                    qs = qs.filter(institution=self.institution)
                    
                for item in qs:
                    trash.append({
                        'id': item.pk,
                        'repr': str(item),
                        'model': model_name,
                        'deleted_at': getattr(item, 'deleted', None),
                        'model_path': f"{app}.{model_name}"
                    })
            except LookupError:
                continue
        
        trash.sort(key=lambda x: x['deleted_at'] if x['deleted_at'] else '', reverse=True)
        return trash

    def restore_item(self, model_path, object_id):
        """محفوظ بحالی (سیکیورٹی چیک کے ساتھ)"""
        item = self._get_item_with_security(model_path, object_id)
        repr_str = str(item)
        item.undelete()
        return True, f"'{repr_str}' کو کامیابی سے بحال کر دیا گیا ہے۔"

    def permanent_delete(self, model_path, object_id):
        """مستقل حذف (سیکیورٹی چیک کے ساتھ)"""
        item = self._get_item_with_security(model_path, object_id)
        repr_str = str(item)
        item.delete(force_policy=SafeDeleteModel.HARD_DELETE)
        return True, f"'{repr_str}' کو مستقل طور پر حذف کر دیا گیا۔"

    def _get_item_with_security(self, model_path, object_id):
        """اندرونی فنکشن: یہ چیک کرتا ہے کہ کیا یوزر کو اس آبجیکٹ پر حق حاصل ہے"""
        app, model_name = model_path.split('.')
        model = apps.get_model(app, model_name)
        
        # ریکارڈ حاصل کریں جو صرف ڈیلیٹڈ لسٹ میں ہو
        try:
            item = model.objects.deleted_only().get(pk=object_id)
        except model.DoesNotExist:
            raise PermissionDenied("ریکارڈ نہیں ملا۔")

        # 🚀 سب سے اہم سیکیورٹی چیک: کیا یہ اسی ادارے کا ہے؟
        if hasattr(item, 'institution') and item.institution != self.institution:
            raise PermissionDenied("آپ کو اس ریکارڈ کو بدلنے کی اجازت نہیں ہے۔")
            
        return item









# from django.apps import apps
# from django.db.models import Q
# from safedelete.models import SafeDeleteModel

# """
# INDEX / TABLE OF CONTENTS:
# --------------------------
# Class: AuditManager (Line 15)
#    - Monitoring:
#      * get_logs (Line 22) - History from simple-history
#    - Trash/Recycle Bin:
#      * get_trash_items (Line 51) - SafeDelete items
#      * restore_item (Line 79)
#      * permanent_delete (Line 88)
# """

# class AuditManager:
#     """لاگز اور ریسائیکل بن کی مینجمنٹ (Library Based)"""

#     def __init__(self, user, institution=None):
#         """یوزر اور ادارے کی معلومات کے ساتھ آڈٹ مینیجر کو شروع کرنا۔"""
#         self.user = user
#         self.institution = institution

#     def get_logs(self, limit=100):
#         """سسٹم میں ہونے والی تمام تبدیلیوں (تبدیلی، حذف) کے تاریخی لاگز حاصل کرنا۔"""
#         all_history = []
#         model_names = [
#             ('dms', 'Student'), ('dms', 'Staff'), ('dms', 'Course'),
#             ('dms', 'Fee'), ('dms', 'Income'), ('dms', 'Expense')
#         ]
        
#         for app, model_name in model_names:
#             model = apps.get_model(app, model_name)
#             if hasattr(model, 'history'):
#                 # صرف اسی ادارے کی ہسٹری (اگر ماڈل میں ادارہ ہے)
#                 qs = model.history.all()
#                 if hasattr(model, 'institution'):
#                     qs = qs.filter(institution=self.institution)
                
#                 for h in qs[:limit]:
#                     all_history.append({
#                         'timestamp': h.history_date,
#                         'user': h.history_user,
#                         'action': 'create' if h.history_type == '+' else 'update' if h.history_type == '~' else 'delete',
#                         'model_name': model_name,
#                         'object_repr': str(h.instance) if h.history_type != '-' else f"{model_name} #{h.pk}",
#                     })
        
#         # وقت کے حساب سے ترتیب دیں
#         all_history.sort(key=lambda x: x['timestamp'], reverse=True)
#         return all_history[:limit]

#     def get_trash_items(self):
#         """حذف شدہ اشیاء (ریسائیکل بن) کی فہرست حاصل کرنا جنہیں بحال کیا جا سکتا ہے۔"""
#         trash = []
#         model_names = [
#             ('dms', 'Student'), ('dms', 'Staff'), ('dms', 'Course'),
#             ('dms', 'Fee'), ('dms', 'Income'), ('dms', 'Expense'),
#             ('dms', 'Institution'), ('dms', 'Facility')
#         ]
        
#         for app, model_name in model_names:
#             model = apps.get_model(app, model_name)
#             # SafeDelete میں ہم 'deleted_only' استعمال کرتے ہیں
#             qs = model.objects.deleted_only()
#             if hasattr(model, 'institution'):
#                 qs = qs.filter(institution=self.institution)
                
#             for item in qs:
#                 trash.append({
#                     'id': item.pk,
#                     'repr': str(item),
#                     'model': model_name,
#                     'deleted_at': getattr(item, 'deleted', None), # SafeDelete 'deleted' فیلڈ استعمال کرتا ہے
#                     'model_path': f"{app}.{model_name}"
#                 })
        
#         trash.sort(key=lambda x: x['deleted_at'] if x['deleted_at'] else '', reverse=True)
#         return trash

#     def restore_item(self, model_path, object_id):
#         """ریسائیکل بن سے کسی حذف شدہ چیز کو واپس اصل حالت میں بحال کرنا۔"""
#         app, model_name = model_path.split('.')
#         model = apps.get_model(app, model_name)
#         # SafeDelete میں undelete استعمال ہوتا ہے
#         item = model.objects.deleted_only().get(pk=object_id)
#         item.undelete()
#         return True, f"'{item}' کو کامیابی سے بحال کر دیا گیا ہے۔"

#     def permanent_delete(self, model_path, object_id):
#         """کسی چیز کو ریسائیکل بن سے بھی مستقل طور پر ختم کر دینا۔"""
#         app, model_name = model_path.split('.')
#         model = apps.get_model(app, model_name)
#         item = model.objects.deleted_only().get(pk=object_id)
#         repr_str = str(item)
#         item.delete(force_policy=SafeDeleteModel.HARD_DELETE)
#         return True, f"'{repr_str}' کو مکمل طور پر حذف کر دیا گیا ہے۔"
