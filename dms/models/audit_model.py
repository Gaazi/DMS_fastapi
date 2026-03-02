from django.db import models
from django.utils import timezone
from safedelete.models import SafeDeleteModel, SOFT_DELETE_CASCADE
from simple_history.models import HistoricalRecords

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: AuditModel (Line 13) - Abstract base for all tracking models
"""

class AuditModel(SafeDeleteModel):
    """
    بنیادی ماڈل جو سافٹ ڈیلیٹ اور لائبریری کی سہولت فراہم کرتا ہے۔
    """
    _safedelete_policy = SOFT_DELETE_CASCADE
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
