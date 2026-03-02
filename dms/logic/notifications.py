from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """
    نظامِ اطلاعات (Notification System)
    یہ کلاس SMS، واٹس ایپ اور سسٹم الرٹس کو مینیج کرتی ہے۔
    """
    
    @staticmethod
    def send_sms(phone_number, message, institution=None):
        """والدین یا اسٹاف کو ایس ایم ایس بھیجنا۔ (فی الحال یہ صرف لاگ کرتا ہے)"""
        if not phone_number:
            return False, "فون نمبر موجود نہیں ہے۔"
            
        # یہاں آپ اپنی ایس ایم ایس سروس (جیسے Twilio یا کوئی مقامی API) انٹیگریٹ کر سکتے ہیں۔
        log_msg = f"[SMS SENT] To: {phone_number} | Msg: {message}"
        logger.info(log_msg)
        print(log_msg) # فار ٹیسٹنگ
        
        return True, "ایس ایم ایس بھیجنے کی درخواست درج کر لی گئی ہے۔", None

    @staticmethod
    def notify_absence(student, session_date):
        """طالب علم کی غیر حاضری پر والدین کو اطلاع دینا۔"""
        msg = f"محترم سرپرست، آپ کا بچہ {student.name} آج {session_date} کو غیر حاضر رہا۔ شکریہ، {student.institution.name}"
        phone = student.mobile
        return NotificationService.send_sms(phone, msg, student.institution)

    @staticmethod
    def notify_fee_due(student, fee):
        """فیس کی ادائیگی کی یاد دہانی کرانا۔"""
        msg = f"محترم سرپرست، طالب علم {student.name} کی فیس {fee.amount_due} واجب الادا ہے۔ براہ کرم جلد از جلد جمع کرائیں۔ شکریہ"
        phone = student.mobile
        return NotificationService.send_sms(phone, msg, student.institution)
