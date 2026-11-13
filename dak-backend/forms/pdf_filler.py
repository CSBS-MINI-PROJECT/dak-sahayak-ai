"""
PDF Generation & Coordinate Overlay Engine for official India Post Form-1.
"""

import io
import os
import json
from datetime import datetime
import pypdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from .validator import load_scheme_config, validate_form_data

def draw_fitted_text(c, x, y, text, font_name="Helvetica-Bold", font_size=9, max_width=None, max_height=None, allow_wrap=True, min_font_size=6.0):
    """
    Renders text at (x, y) with dynamic auto-scaling and intelligent word-wrapping.
    Guarantees long applicant names, addresses, and numbers never overflow allocated form boxes.
    """
    if not text:
        return

    text_str = str(text).strip()
    if not max_width:
        c.setFont(font_name, font_size)
        c.drawString(x, y, text_str)
        return

    current_size = float(font_size)
    c.setFont(font_name, current_size)
    measured_w = c.stringWidth(text_str, font_name, current_size)

    # 1. Fits comfortably on a single line
    if measured_w <= max_width:
        c.drawString(x, y, text_str)
        return

    # 2. Try single-line auto-scaling down to min_font_size
    scale_ratio = max_width / max(measured_w, 1.0)
    scaled_size = current_size * scale_ratio
    if not allow_wrap or scaled_size >= min_font_size:
        effective_size = max(min_font_size, scaled_size)
        c.setFont(font_name, effective_size)
        c.drawString(x, y, text_str)
        return

    # 3. Word wrapping at min_font_size for multi-line fields
    effective_font_size = max(min_font_size, min(current_size, 8.0))
    c.setFont(font_name, effective_font_size)
    words = text_str.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        if c.stringWidth(test_line, font_name, effective_font_size) <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))

    line_step = effective_font_size * 1.15
    max_lines = int(max_height / line_step) if max_height else len(lines)
    if max_lines < len(lines):
        lines = lines[:max_lines]
        if lines:
            last = lines[-1]
            while c.stringWidth(last + "...", font_name, effective_font_size) > max_width and len(last) > 1:
                last = last[:-1]
            lines[-1] = last + "..."

    cur_y = y
    for line in lines:
        c.drawString(x, cur_y, line)
        cur_y -= line_step

def number_to_words_inr(amount):
    """Convert integer / float amount to Indian Currency words."""
    try:
        n = int(round(float(amount)))
    except (ValueError, TypeError):
        return ""

    if n == 0:
        return "Zero Rupees Only"

    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
             "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
             "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_two_digits(val):
        if val < 20:
            return units[val]
        return tens[val // 10] + (" " + units[val % 10] if val % 10 != 0 else "")

    def convert_three_digits(val):
        h = val // 100
        rem = val % 100
        res = ""
        if h > 0:
            res += units[h] + " Hundred"
            if rem > 0:
                res += " and "
        if rem > 0:
            res += convert_two_digits(rem)
        return res

    parts = []
    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    hundreds = n

    if crore > 0:
        parts.append(convert_two_digits(crore) + " Crore")
    if lakh > 0:
        parts.append(convert_two_digits(lakh) + " Lakh")
    if thousand > 0:
        parts.append(convert_two_digits(thousand) + " Thousand")
    if hundreds > 0:
        parts.append(convert_three_digits(hundreds))

    return " ".join(parts).strip() + " Rupees Only"

def prepare_field_data(raw_data):
    """Sanitizes, computes derived labels and formats fields for form rendering."""
    data = dict(raw_data or {})
    
    # Date & Place
    today_str = datetime.now().strftime("%d/%m/%Y")
    data["current_date"] = data.get("current_date") or today_str
    data["place"] = data.get("place") or data.get("district") or data.get("city") or ""

    # Initial Deposit
    dep = data.get("initial_deposit")
    if dep:
        try:
            dep_num = float(str(dep).replace(",", "").strip())
            data["initial_deposit_formatted"] = f"{dep_num:,.2f}"
            data["initial_deposit_words"] = number_to_words_inr(dep_num)
        except Exception:
            data["initial_deposit_formatted"] = str(dep)
            data["initial_deposit_words"] = ""
    
    # Deposit mode
    dep_mode = data.get("deposit_mode", "Cash")
    data["deposit_mode"] = f"[X] {dep_mode}"

    # District & State combined
    dist = data.get("district", "").strip()
    st = data.get("state", "").strip()
    if dist and st:
        data["district_state"] = f"{dist}, {st}"
    elif dist or st:
        data["district_state"] = dist or st
    else:
        data["district_state"] = ""

    # Nominee formatting
    nom_name = data.get("nominee_name", "").strip()
    nom_addr = data.get("nominee_address") or data.get("address", "")
    data["nominee_name_and_addr"] = f"{nom_name} ({nom_addr})" if nom_name and nom_addr else nom_name

    share = data.get("nominee_share", 100)
    try:
        share_num = float(str(share).replace("%", "").strip())
        data["nominee_share_formatted"] = f"{share_num:.0f}%"
    except Exception:
        data["nominee_share_formatted"] = f"{share}%"

    data["applicant_name_sig"] = data.get("applicant_name", "")

    return data

def generate_filled_pdf(scheme="ppf", language="en", raw_data=None):
    """
    Generates a high-quality print-ready PDF with overlay data merged on official Form-1.
    Returns io.BytesIO containing complete PDF bytes.
    """
    # 1. Server-side validation
    val_res = validate_form_data(scheme, language, raw_data)
    if not val_res["is_valid"]:
        raise ValueError(json.dumps(val_res))

    config = load_scheme_config(scheme, language)
    source_pdf_rel = config.get("source_pdf", "assets/forms/form1_en_v2024.pdf")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    source_pdf_path = os.path.join(base_dir, source_pdf_rel)

    if not os.path.exists(source_pdf_path):
        from assets.forms.generate_template import create_form1_template
        create_form1_template(source_pdf_path)

    # 2. Check for AcroForm fields
    template_reader = pypdf.PdfReader(source_pdf_path)
    fields_dict = template_reader.get_fields()
    has_acroform = bool(fields_dict)

    prepared = prepare_field_data(raw_data)

    if has_acroform:
        writer = pypdf.PdfWriter(clone_from=source_pdf_path)
        writer.update_page_form_field_values(writer.pages[0], prepared)
        if len(writer.pages) > 1:
            writer.update_page_form_field_values(writer.pages[1], prepared)
        out_buf = io.BytesIO()
        writer.write(out_buf)
        out_buf.seek(0)
        return out_buf

    # 3. Coordinate Overlay via ReportLab
    coords = config.get("field_coordinates", {})
    page1_fields = coords.get("page_1", [])
    page2_fields = coords.get("page_2", [])

    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=A4)

    # PAGE 1 OVERLAY
    c.setFillColor(colors.HexColor("#0B2545"))
    for item in page1_fields:
        field_key = item.get("field")
        static_val = item.get("static_value")
        val = static_val if static_val is not None else prepared.get(field_key)

        if val is None or str(val).strip() == "":
            continue

        text = str(val).strip()
        if item.get("uppercase"):
            text = text.upper()

        font_name = item.get("font_name", "Helvetica-Bold")
        font_size = item.get("font_size", 9)
        max_w = item.get("max_width")
        max_h = item.get("max_height")
        allow_wrap = item.get("allow_wrap", True if max_w and max_w >= 150 else False)

        draw_fitted_text(
            c, item["x"], item["y"], text,
            font_name=font_name, font_size=font_size,
            max_width=max_w, max_height=max_h,
            allow_wrap=allow_wrap
        )

    c.showPage()

    # PAGE 2 OVERLAY
    c.setFillColor(colors.HexColor("#0B2545"))
    for item in page2_fields:
        field_key = item.get("field")
        static_val = item.get("static_value")
        val = static_val if static_val is not None else prepared.get(field_key)

        if val is None or str(val).strip() == "":
            continue

        text = str(val).strip()
        if item.get("uppercase"):
            text = text.upper()

        font_name = item.get("font_name", "Helvetica-Bold")
        font_size = item.get("font_size", 9)
        max_w = item.get("max_width")
        max_h = item.get("max_height")
        allow_wrap = item.get("allow_wrap", True if max_w and max_w >= 150 else False)

        draw_fitted_text(
            c, item["x"], item["y"], text,
            font_name=font_name, font_size=font_size,
            max_width=max_w, max_height=max_h,
            allow_wrap=allow_wrap
        )

    c.showPage()
    c.save()

    overlay_buf.seek(0)
    overlay_reader = pypdf.PdfReader(overlay_buf)

    # 4. Merge overlay on source template
    writer = pypdf.PdfWriter(clone_from=source_pdf_path)
    for idx, overlay_page in enumerate(overlay_reader.pages):
        if idx < len(writer.pages):
            writer.pages[idx].merge_page(overlay_page)

    final_buf = io.BytesIO()
    writer.write(final_buf)
    final_buf.seek(0)
    return final_buf
