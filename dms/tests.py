from django.test import TestCase

# یہ ایک سادہ ٹیسٹ ہے جو صرف یہ چیک کرے گا کہ 1+1 برابر 2 ہے یا نہیں
# اس کا مقصد یہ دیکھنا ہے کہ ٹیسٹنگ کا نظام کام کر رہا ہے یا نہیں
class SimpleTest(TestCase):
    def test_basic_math(self):
        self.assertEqual(1 + 1, 2)


    def test_homepage_access(self):
        # یہ چیک کرے گا کہ ویب سائٹ کا مین پیج کھل رہا ہے
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)