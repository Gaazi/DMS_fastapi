"""
SMS Notification Service for DMS
─────────────────────────────────
Supported providers:
  - msg91   : MSG91 (India — سب سے مشہور)
  - fast2sms: Fast2SMS (India — مفت ٹرائل)
  - twilio  : Twilio (International)
  - console : Development-only (terminal پر print)

Configuration (environment variables):
  SMS_PROVIDER   = msg91 | fast2sms | twilio | console
  SMS_API_KEY    = <your API key>
  SMS_AUTH_TOKEN = <auth token — Twilio only>
  SMS_SENDER_ID  = <Sender ID / route>
  SMS_COUNTRY    = IN  (default: IN for India)

India Setup Guide:
  MSG91:    https://msg91.com  → API Key سے کam چلے گا
  Fast2SMS: https://www.fast2sms.com → Free 200 SMS trial
"""

import os
import logging
from typing import Optional, List
from datetime import date as dt_date, datetime

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Phone Number Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_phone(phone: str, country: str = "IN") -> str:
    """نمبر کو صحیح format میں لانا۔"""
    p = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if country == "IN":
        # India: 10 digit → 91XXXXXXXXXX
        if p.startswith("+91"): return p[1:]   # +91... → 91...
        if p.startswith("91") and len(p) == 12: return p
        if len(p) == 10: return "91" + p
    elif country == "PK":
        # Pakistan: 03XX → 923XX
        if p.startswith("+92"): return p[1:]
        if p.startswith("0"): return "92" + p[1:]
    return p


# ─────────────────────────────────────────────────────────────────────────────
# SMS Provider Adapters
# ─────────────────────────────────────────────────────────────────────────────

class SMSProvider:
    """بنیادی SMS Provider کا خاکہ"""
    country: str = "IN"
    def send(self, to: str, message: str) -> bool:
        raise NotImplementedError


class ConsoleSMSProvider(SMSProvider):
    """Development mode: SMS کو terminal میں print کرتا ہے"""
    def send(self, to: str, message: str) -> bool:
        phone = normalize_phone(to)
        print(f"\n📱 [SMS — Console Mode]\nTo: {phone}\nMsg: {message}\n{'─'*40}")
        return True


class TwilioSMSProvider(SMSProvider):
    """Twilio API"""
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token  = auth_token
        self.from_number = from_number

    def send(self, to: str, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(body=message, from_=self.from_number, to=to)
            logger.info(f"Twilio SMS sent to {to}: {msg.sid}")
            return True
        except ImportError:
            logger.error("Twilio library not installed. Run: pip install twilio")
            return False
        except Exception as e:
            logger.error(f"Twilio SMS failed to {to}: {e}")
            return False


class MSG91Provider(SMSProvider):
    """
    MSG91 — India کا سب سے مشہور SMS Gateway
    Sign up: https://msg91.com
    API Docs: https://docs.msg91.com/reference/send-sms
    """
    country = "IN"

    def __init__(self, api_key: str, sender_id: str = "DMSSYS", route: str = "4"):
        self.api_key   = api_key
        self.sender_id = sender_id[:6].upper()  # MSG91 max 6 chars
        self.route     = route  # 4=transactional, 1=promotional

    def send(self, to: str, message: str) -> bool:
        try:
            import urllib.request, urllib.parse, json
            phone = normalize_phone(to, "IN")

            payload = json.dumps({
                "sender":    self.sender_id,
                "route":     self.route,
                "country":   "91",
                "sms": [{
                    "message": message,
                    "to":      [phone]
                }]
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.msg91.com/api/v2/sendsms",
                data=payload,
                headers={
                    "authkey":     self.api_key,
                    "content-type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                logger.info(f"MSG91 response for {phone}: {result}")
                return result.get("type") == "success"
        except Exception as e:
            logger.error(f"MSG91 SMS failed to {to}: {e}")
            return False


class Fast2SMSProvider(SMSProvider):
    """
    Fast2SMS — India (مفت ٹرائل: 200 SMS)
    Sign up: https://www.fast2sms.com
    API Docs: https://docs.fast2sms.com
    """
    country = "IN"

    def __init__(self, api_key: str, sender_id: str = "FSTSMS", route: str = "q"):
        self.api_key   = api_key
        self.sender_id = sender_id
        self.route     = route  # q=quick (free), dlt=DLT template

    def send(self, to: str, message: str) -> bool:
        try:
            import urllib.request, urllib.parse
            phone = normalize_phone(to, "IN")
            # Fast2SMS uses 10-digit number only
            if phone.startswith("91") and len(phone) == 12:
                phone = phone[2:]

            params = urllib.parse.urlencode({
                "authorization": self.api_key,
                "sender_id":     self.sender_id,
                "message":       message,
                "language":      "english",
                "route":         self.route,
                "numbers":       phone,
            })
            url = f"https://www.fast2sms.com/dev/bulkV2?{params}"
            req = urllib.request.Request(url, headers={"cache-control": "no-cache"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                import json
                result = json.loads(resp.read().decode())
                logger.info(f"Fast2SMS response for {phone}: {result}")
                return result.get("return") is True
        except Exception as e:
            logger.error(f"Fast2SMS failed to {to}: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Main SMS Service
# ─────────────────────────────────────────────────────────────────────────────

class SMSService:
    """
    مرکزی SMS سروس:
    - provider کا انتخاب environment سے
    - bulk SMS support
    - template-based messages
    """

    def __init__(self, provider: Optional[SMSProvider] = None):
        self._provider = provider or self._build_provider_from_env()

    @staticmethod
    def _build_provider_from_env() -> SMSProvider:
        sms_provider = os.getenv("SMS_PROVIDER", "console").lower()

        if sms_provider == "msg91":
            return MSG91Provider(
                api_key=os.getenv("SMS_API_KEY", ""),
                sender_id=os.getenv("SMS_SENDER_ID", "DMSSYS"),
                route=os.getenv("SMS_ROUTE", "4")
            )
        elif sms_provider == "fast2sms":
            return Fast2SMSProvider(
                api_key=os.getenv("SMS_API_KEY", ""),
                sender_id=os.getenv("SMS_SENDER_ID", "FSTSMS"),
                route=os.getenv("SMS_ROUTE", "q")
            )
        elif sms_provider == "twilio":
            return TwilioSMSProvider(
                account_sid=os.getenv("SMS_API_KEY", ""),
                auth_token=os.getenv("SMS_AUTH_TOKEN", ""),
                from_number=os.getenv("SMS_SENDER_ID", "")
            )
        else:
            return ConsoleSMSProvider()

    def send(self, to: str, message: str) -> bool:
        """ایک نمبر پر SMS بھیجنا"""
        if not to or not message:
            return False
        return self._provider.send(to, message)

    def send_bulk(self, recipients: List[dict], message_template: str) -> dict:
        """
        بہت سے لوگوں کو SMS بھیجنا۔
        recipients = [{"name": ..., "phone": ..., "extra": ...}, ...]
        template variables: {name}, {phone}, {extra}
        """
        sent = 0; failed = 0; skipped = 0
        for r in recipients:
            phone = r.get("phone", "").strip()
            if not phone:
                skipped += 1
                continue
            try:
                msg = message_template.format(**r)
            except KeyError:
                msg = message_template
            success = self.send(phone, msg)
            if success: sent += 1
            else: failed += 1
        return {"sent": sent, "failed": failed, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Notification Manager — business logic
# ─────────────────────────────────────────────────────────────────────────────

class NotificationLogic:
    """
    DMS notifications:
    1. غیر حاضری کی اطلاع — والدین کو
    2. فیس بقایا کی یاد دہانی
    3. ماہانہ حاضری خلاصہ
    """

    def __init__(self, session, institution, user=None, sms_service: Optional[SMSService] = None):
        self.session = session
        self.institution = institution
        self.user = user
        self.sms = sms_service or SMSService()

    # ─── 1. حاضری کی غیر موجودگی کی اطلاع ──────────────────────────────────

    def notify_absences_today(self, target_date=None) -> dict:
        """
        آج غیر حاضر طلبہ کے والدین کو SMS بھیجنا۔
        ہر طالب علم کے لیے صرف ایک بار (پہلی غیر حاضری پر)۔
        """
        from sqlmodel import select
        from app.models import Student, Attendance, ClassSession
        from app.models.links import StudentParentLink
        from app.models.people import Parent

        today = target_date or dt_date.today()
        inst_name = self.institution.name

        # آج کے تمام غیر حاضر طلبہ
        absent_records = self.session.exec(
            select(Attendance, ClassSession, Student)
            .join(ClassSession, Attendance.session_id == ClassSession.id)
            .join(Student, Attendance.student_id == Student.id)
            .where(
                ClassSession.date == today,
                Student.inst_id == self.institution.id,
                Attendance.status == 'absent'
            )
        ).all()

        if not absent_records:
            return {"sent": 0, "skipped": 0, "message": "آج کوئی غیر حاضر نہیں۔"}

        recipients = []
        processed_students = set()

        for att, cs, student in absent_records:
            if student.id in processed_students:
                continue
            processed_students.add(student.id)

            # والدین کا نمبر
            parent_links = self.session.exec(
                select(Parent).join(StudentParentLink, StudentParentLink.parent_id == Parent.id)
                .where(StudentParentLink.student_id == student.id)
            ).all()

            for parent in parent_links:
                phone = parent.mobile or parent.mobile2
                if phone:
                    recipients.append({
                        "phone":    phone,
                        "name":     parent.full_name or "والدین",
                        "student":  student.full_name,
                        "date":     str(today),
                        "inst":     inst_name,
                    })

        if not recipients:
            # طالب علم کا اپنا نمبر استعمال کریں اگر والدین نہ ہوں
            for att, cs, student in absent_records:
                if student.mobile:
                    recipients.append({
                        "phone":   student.mobile,
                        "name":    student.full_name,
                        "student": student.full_name,
                        "date":    str(today),
                        "inst":    inst_name,
                    })

        msg_template = (
            "السلام علیکم {name}،\n"
            "آپ کے بچے {student} آج ({date}) {inst} میں غیر حاضر ہیں۔\n"
            "براہ کرم ادارے سے رابطہ کریں۔"
        )

        result = self.sms.send_bulk(recipients, msg_template)
        result["date"] = str(today)
        result["message"] = f"✅ {result['sent']} والدین کو غیر حاضری کی اطلاع دی گئی۔"
        return result

    # ─── 2. فیس بقایا کی یاد دہانی ─────────────────────────────────────────

    def notify_pending_fees(self, overdue_only: bool = False) -> dict:
        """
        واجب الادا فیس والے طلبہ یا والدین کو reminder بھیجنا۔
        overdue_only=True: صرف وہ جن کی due_date گزر چکی ہے
        """
        from sqlmodel import select
        from app.models import Student, Fee
        from app.models.links import StudentParentLink
        from app.models.people import Parent

        today = dt_date.today()

        q = select(Fee, Student).join(Student, Fee.student_id == Student.id).where(
            Student.inst_id == self.institution.id,
            Student.deleted_at == None,
            Fee.status.in_(["Pending", "Partial"])
        )
        if overdue_only:
            q = q.where(Fee.due_date < today)

        fee_records = self.session.exec(q).all()

        if not fee_records:
            return {"sent": 0, "skipped": 0, "message": "کوئی واجب الادا فیس نہیں۔"}

        recipients = []
        processed = set()

        for fee, student in fee_records:
            if student.id in processed:
                continue
            processed.add(student.id)

            balance = (fee.amount_due or 0) - sum(
                p.amount_paid for p in self.session.exec(
                    select(__import__('app.models.finance', fromlist=['Fee_Payment']).Fee_Payment)
                    .where(__import__('app.models.finance', fromlist=['Fee_Payment']).Fee_Payment.student_id == student.id,
                           __import__('app.models.finance', fromlist=['Fee_Payment']).Fee_Payment.fee_id == fee.id)
                ).all()
            )
            if balance <= 0:
                continue

            # والدین کو بھیجیں
            parents = self.session.exec(
                select(Parent).join(StudentParentLink, StudentParentLink.parent_id == Parent.id)
                .where(StudentParentLink.student_id == student.id)
            ).all()

            sent_to_parent = False
            for p in parents:
                ph = p.mobile or p.mobile2
                if ph:
                    recipients.append({"phone": ph, "name": p.full_name or "والدین",
                                       "student": student.full_name, "amount": int(balance),
                                       "inst": self.institution.name})
                    sent_to_parent = True

            if not sent_to_parent and student.mobile:
                recipients.append({"phone": student.mobile, "name": student.full_name,
                                   "student": student.full_name, "amount": int(balance),
                                   "inst": self.institution.name})

        msg_template = (
            "السلام علیکم {name}،\n"
            "{student} کی {inst} میں {amount} روپے فیس واجب الادا ہے۔\n"
            "برائے مہربانی جلد ادائیگی کریں۔ جزاک اللہ"
        )

        result = self.sms.send_bulk(recipients, msg_template)
        result["message"] = f"✅ {result['sent']} افراد کو فیس یاد دہانی بھیجی گئی۔"
        return result

    # ─── 3. ماہانہ خلاصہ ───────────────────────────────────────────────────

    def notify_monthly_summary(self, month: int = None, year: int = None) -> dict:
        """
        ہر طالب علم کے والدین کو مہینے کا حاضری خلاصہ بھیجنا۔
        """
        from sqlmodel import select
        from app.models import Student, Attendance, ClassSession, Admission
        from app.models.links import StudentParentLink
        from app.models.people import Parent
        import calendar

        today = dt_date.today()
        mn = month or today.month
        yr = year or today.year
        start = dt_date(yr, mn, 1)
        _, last_day = calendar.monthrange(yr, mn)
        end = dt_date(yr, mn, last_day)
        month_name = calendar.month_name[mn]

        students = self.session.exec(
            select(Student).where(Student.inst_id == self.institution.id, Student.deleted_at == None)
        ).all()

        recipients = []
        for student in students:
            # ماہانہ حاضری
            present_count = self.session.exec(
                select(__import__('sqlmodel', fromlist=['func']).func.count(Attendance.id))
                .join(ClassSession, Attendance.session_id == ClassSession.id)
                .where(Attendance.student_id == student.id, Attendance.status == 'present',
                       ClassSession.date >= start, ClassSession.date <= end)
            ).one() or 0

            total = self.session.exec(
                select(__import__('sqlmodel', fromlist=['func']).func.count(Attendance.id))
                .join(ClassSession, Attendance.session_id == ClassSession.id)
                .where(Attendance.student_id == student.id,
                       ClassSession.date >= start, ClassSession.date <= end)
            ).one() or 0

            pct = round(present_count / total * 100) if total else 0

            # والدین
            parents = self.session.exec(
                select(Parent).join(StudentParentLink, StudentParentLink.parent_id == Parent.id)
                .where(StudentParentLink.student_id == student.id)
            ).all()

            for p in parents:
                ph = p.mobile or p.mobile2
                if ph:
                    recipients.append({
                        "phone":   ph, "name": p.full_name or "والدین",
                        "student": student.full_name, "present": present_count,
                        "total":   total, "pct": pct, "month": month_name,
                        "inst":    self.institution.name
                    })

        msg_template = (
            "السلام علیکم {name}،\n"
            "{month} میں {student} کی حاضری:\n"
            "{present}/{total} دن ({pct}%)\n"
            "— {inst}"
        )

        result = self.sms.send_bulk(recipients, msg_template)
        result["message"] = f"✅ {month_name} کا خلاصہ {result['sent']} افراد کو بھیجا گیا۔"
        return result
