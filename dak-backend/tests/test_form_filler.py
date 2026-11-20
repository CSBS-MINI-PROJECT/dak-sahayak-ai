"""
Unit and integration tests for India Post Account Opening Form generation.
"""

import io
import json
import unittest
import sys
import os
import pypdf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from forms.validator import validate_form_data, load_scheme_config
from forms.pdf_filler import generate_filled_pdf, number_to_words_inr

class TestFormFiller(unittest.TestCase):

    def setUp(self):
        self.valid_ppf_data = {
            "applicant_name": "Ramesh Kumar Sharma",
            "father_or_spouse_name": "Suresh Sharma",
            "dob": "15/08/1985",
            "gender": "Male",
            "pan": "ABCDE1234F",
            "aadhaar": "987654321012",
            "mobile": "9876543210",
            "email": "ramesh.sharma@example.com",
            "address": "Flat 402, Green Valley Apts, Kadri Hills",
            "pincode": "575004",
            "district": "Dakshina Kannada",
            "state": "Karnataka",
            "post_office": "Kadri Sub Post Office",
            "initial_deposit": 5000,
            "deposit_mode": "Cash",
            "nominee_name": "Priya Sharma",
            "nominee_relationship": "Spouse",
            "nominee_share": 100,
            "nominee_dob": "22/11/1988",
            "place": "Mangalore"
        }

        self.valid_ssa_data = {
            "applicant_name": "Ramesh Kumar Sharma",
            "minor_name": "Ananya Sharma",
            "minor_dob": "10/05/2018",
            "birth_cert_reg_no": "BC-MNG-2018-9982",
            "guardian_relationship": "Father",
            "pan": "ABCDE1234F",
            "mobile": "9876543210",
            "address": "Kadri Hills, Mangalore",
            "pincode": "575004",
            "initial_deposit": 1000,
            "district": "Dakshina Kannada",
            "state": "Karnataka"
        }

    def test_number_to_words(self):
        self.assertEqual(number_to_words_inr(5000), "Five Thousand Rupees Only")
        self.assertEqual(number_to_words_inr(150000), "One Lakh Fifty Thousand Rupees Only")
        self.assertEqual(number_to_words_inr(1250), "One Thousand Two Hundred and Fifty Rupees Only")

    def test_missing_required_fields(self):
        incomplete_data = {
            "applicant_name": "Ramesh Sharma",
        }
        res = validate_form_data("ppf", "en", incomplete_data)
        self.assertFalse(res["is_valid"])
        self.assertIn("pan", res["missing_fields"])
        self.assertIn("dob", res["missing_fields"])
        self.assertIn("mobile", res["missing_fields"])
        self.assertIn("initial_deposit", res["missing_fields"])
        self.assertIn("nominee_name", res["missing_fields"])

    def test_invalid_pan_and_pincode(self):
        invalid_data = dict(self.valid_ppf_data)
        invalid_data["pan"] = "INVALID123"
        invalid_data["pincode"] = "123"
        invalid_data["mobile"] = "12345"

        res = validate_form_data("ppf", "en", invalid_data)
        self.assertFalse(res["is_valid"])
        invalid_field_names = [item["field"] for item in res["invalid_fields"]]
        self.assertIn("pan", invalid_field_names)
        self.assertIn("pincode", invalid_field_names)
        self.assertIn("mobile", invalid_field_names)

    def test_successful_pdf_generation_ppf(self):
        pdf_buf = generate_filled_pdf("ppf", "en", self.valid_ppf_data)
        self.assertIsInstance(pdf_buf, io.BytesIO)
        pdf_bytes = pdf_buf.getvalue()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        self.assertEqual(len(reader.pages), 2)

    def test_successful_pdf_generation_ssa(self):
        pdf_buf = generate_filled_pdf("ssa", "en", self.valid_ssa_data)
        self.assertIsInstance(pdf_buf, io.BytesIO)
        pdf_bytes = pdf_buf.getvalue()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        self.assertEqual(len(reader.pages), 2)

if __name__ == "__main__":
    unittest.main()
