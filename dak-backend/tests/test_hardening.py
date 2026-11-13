"""
Production Hardening Smoke Tests for Dak Sahayak AI Backend.
Verifies PII masking, ReportLab text overflow protection, TTS browser fallback, and in-memory Form-1 streaming.
"""

import unittest
import io
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, mask_pii
from forms.pdf_filler import draw_fitted_text, generate_filled_pdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pypdf

class TestProductionHardening(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # 1. Smoke test: mask_pii()
    def test_mask_pii_string_patterns(self):
        text = "User PAN is ABCDE1234F, mobile is 9876543210, Aadhaar is 1234 5678 9012, email is rajesh.kumar@example.com."
        masked = mask_pii(text)
        self.assertNotIn("ABCDE1234F", masked)
        self.assertNotIn("9876543210", masked)
        self.assertNotIn("1234 5678 9012", masked)
        self.assertNotIn("rajesh.kumar@example.com", masked)
        self.assertIn("AB******4F", masked)
        self.assertIn("98******10", masked)
        self.assertIn("XXXXXXXX****", masked)
        self.assertIn("r***@example.com", masked)

    def test_mask_pii_dict(self):
        payload = {
            "applicant_name": "Suresh Raina",
            "pan": "BNZPR1234K",
            "mobile": "9845012345",
            "email": "suresh@india.gov.in",
            "metadata": {
                "nominee_name": "Priyanka Raina",
                "phone": "9988776655"
            }
        }
        masked = mask_pii(payload)
        self.assertEqual(masked["pan"], "BN******4K")
        self.assertEqual(masked["mobile"], "98******45")
        self.assertIn("****", masked["applicant_name"])
        self.assertEqual(masked["metadata"]["phone"], "99******55")
        self.assertIn("****", masked["metadata"]["nominee_name"])

    # 2. Smoke test: draw_fitted_text()
    def test_draw_fitted_text_auto_scale_and_wrap(self):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        
        # Test long name fitting inside 100pt box
        long_name = "Dr. Venkata Ramanathan Subramanian Swaminathan"
        draw_fitted_text(c, 100, 700, long_name, font_name="Helvetica-Bold", font_size=10, max_width=120)

        # Test multi-line address wrapping inside 150pt box
        long_address = "Flat 402, Building C, Krishna Heritage Apartments, Near Government High School, Kadri Hills, Mangalore, Karnataka - 575004"
        draw_fitted_text(c, 100, 600, long_address, font_name="Helvetica", font_size=9, max_width=150, max_height=80, allow_wrap=True)

        c.showPage()
        c.save()
        buf.seek(0)
        
        # Verify generated PDF is valid and readable
        reader = pypdf.PdfReader(buf)
        self.assertEqual(len(reader.pages), 1)

    # 3. Smoke test: /api/tts fallback JSON
    def test_api_tts_empty_or_failure_fallback(self):
        # Empty text returns 400
        res_empty = self.app.post("/api/tts", json={})
        self.assertEqual(res_empty.status_code, 400)

        # When Edge TTS fails / returns empty, API gracefully returns HTTP 200 with browser_tts fallback
        from unittest.mock import patch
        with patch("app.generate_indian_speech", return_value=b""):
            res_fallback = self.app.post("/api/tts", json={"text": "Namaste Dak Sahayak", "language": "Hindi"})
            self.assertEqual(res_fallback.status_code, 200)
            self.assertIn("application/json", res_fallback.content_type)
            data = json.loads(res_fallback.data.decode("utf-8"))
            self.assertEqual(data.get("fallback"), "browser_tts")
            self.assertEqual(data.get("language"), "Hindi")

        # When Edge TTS succeeds, returns audio/mpeg
        with patch("app.generate_indian_speech", return_value=b"FAKE_MP3_STREAM"):
            res_audio = self.app.post("/api/tts", json={"text": "Speed post charges", "language": "English"})
            self.assertEqual(res_audio.status_code, 200)
            self.assertEqual(res_audio.content_type, "audio/mpeg")
            self.assertEqual(res_audio.data, b"FAKE_MP3_STREAM")

    # 4. Smoke test: /api/forms/fill in-memory streaming
    def test_api_forms_fill_in_memory_stream(self):
        sample_payload = {
            "scheme": "ppf",
            "language": "en",
            "data": {
                "applicant_name": "RAMESH CHANDRA",
                "father_or_spouse_name": "SURESH CHANDRA",
                "dob": "15/08/1985",
                "gender": "Male",
                "pan": "ABCDE1234F",
                "aadhaar": "123456789012",
                "mobile": "9876543210",
                "address": "42 MG Road, Bangalore",
                "pincode": "560001",
                "initial_deposit": 5000,
                "nominee_name": "SITA CHANDRA",
                "nominee_relationship": "Spouse",
                "nominee_share": 100
            }
        }
        res = self.app.post("/api/forms/fill", json=sample_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/pdf")
        self.assertTrue(res.data.startswith(b"%PDF-"))
        self.assertIn("attachment; filename=PPF_Account_Opening_Form1.pdf", res.headers.get("Content-Disposition", ""))

if __name__ == "__main__":
    unittest.main()
