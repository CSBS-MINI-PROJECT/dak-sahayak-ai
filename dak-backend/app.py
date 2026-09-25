import os
import re
import math
import requests
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types

from supabase_client import (
    get_user_from_token,
    get_user_conversations,
    create_user_conversation,
    update_conversation_title,
    get_conversation_messages,
    save_chat_message,
    delete_user_conversation,
    search_pincode_db
)
from vector_search import search_documents
from tts_service import generate_indian_speech
from calculator import (
    calculate_speed_post, calculate_ordinary_letter, calculate_postcard,
    calculate_inland_letter, calculate_ordinary_parcel, calculate_registered_post, calculate_insurance,
    calculate_sukanya_maturity, calculate_scss_payout, calculate_ppf_maturity,
    calculate_mis_payout, calculate_nsc_maturity, calculate_kvp_maturity
)

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("[AI Status] Gemini Client initialized: True")
    except Exception as e:
        print(f"[AI Status] Gemini Client initialization failed: {e}")
else:
    print("[AI Status] Gemini API Key missing!")

def get_auth_token():
    """Extracts the Bearer token from the request Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ")[1]

def get_auth_user():
    """Extracts and verifies Bearer token from request Authorization header."""
    token = get_auth_token()
    if not token:
        return None
    return get_user_from_token(token)

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "online",
        "service": "Dak Sahayak AI Backend API",
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat",
            "tts": "/api/tts",
            "translate": "/api/translate",
            "calculate": "/api/calculate"
        }
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Dak Sahayak AI Backend (Supabase + Gemini)"})

# --- Conversation Endpoints ---

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    user = get_auth_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_auth_token()
    conversations = get_user_conversations(user.id, token=token)
    return jsonify({"conversations": conversations})

@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    user = get_auth_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_auth_token()
    data = request.get_json() or {}
    title = str(data.get("title") or "New Chat").strip()
    conv_id = create_user_conversation(user.id, title=title, token=token)
    if not conv_id:
        return jsonify({"error": "Failed to create conversation"}), 500
    return jsonify({"conversation_id": conv_id, "title": title})

@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    user = get_auth_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_auth_token()
    success = delete_user_conversation(conversation_id, user.id, token=token)
    return jsonify({"success": success})

@app.route("/api/conversations/<conversation_id>/messages", methods=["GET"])
def list_messages(conversation_id):
    user = get_auth_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    token = get_auth_token()
    messages = get_conversation_messages(conversation_id, token=token)
    return jsonify({"messages": messages})

# --- Main Streaming Chat Endpoint with Supabase RAG ---

@app.route("/api/chat", methods=["POST"])
def chat():
    user = get_auth_user()
    token = get_auth_token()
    data = request.get_json() or {}
    user_message = str(data.get("message") or "").strip()
    conversation_id = str(data.get("conversation_id") or "").strip()
    language = str(data.get("language") or "English").strip()
    pincode = str(data.get("pincode") or "").strip()
    user_location = data.get("user_location") or {}

    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    # Auto-create conversation if not provided
    if user and not conversation_id:
        conversation_id = create_user_conversation(user.id, title=user_message[:40], token=token)

    # Save user message to Supabase
    if conversation_id:
        save_chat_message(conversation_id, "user", user_message, token=token)

    # 1. Instant PIN Code Resolution
    pin_matches = re.findall(r'\b[1-9][0-9]{5}\b', user_message)
    if pin_matches:
        po_records = search_pincode_db(pin_matches[0])
        if po_records:
            po = po_records[0]
            pin_response = f"""**PIN Code Details**

* **PIN Code:** {po.get('Pincode', pin_matches[0])}
* **Post Office Name:** {po.get('Name', 'N/A')}
* **Office Type:** {po.get('BranchType', 'Sub Post Office')} ({po.get('DeliveryStatus', 'Delivery')})
* **Taluk:** {po.get('Taluk', 'N/A')}
* **District:** {po.get('District', 'N/A')}
* **Postal Division:** {po.get('Division', 'N/A')}
* **Postal Region:** {po.get('Region', 'N/A')}
* **Postal Circle:** {po.get('Circle', 'N/A')}
* **Head Office (HO):** {po.get('HeadOffice', 'N/A')}"""
            if conversation_id:
                save_chat_message(conversation_id, "assistant", pin_response, token=token)
            return Response(pin_response, content_type="text/plain; charset=utf-8")

    # 1.1 Official Parcel / Consignment Tracking Resolution
    msg_l = user_message.lower().strip()
    is_tracking_query = any(k in msg_l for k in [
        "track", "tracking", "consignment", "trace", "parcel status",
        "speed post status", "shipment status", "where is my parcel", "where is my post",
        "speed post tracking", "registered post tracking", "package status"
    ])
    consignment_match = re.search(r'\b([A-Za-z]{2}\d{9}[A-Za-z]{2})\b', user_message)

    if is_tracking_query or consignment_match:
        if consignment_match:
            t_num = consignment_match.group(1).upper()
            tracking_response = f"""### 📦 India Post Consignment Tracking

* **Consignment Number:** `{t_num}`
* **Official Tracking Portal:** [India Post Consignment Tracking](https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx)

**How to Track:**
1. Visit the official [India Post Tracking Portal](https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx).
2. Enter your Consignment Number: `{t_num}`.
3. Solve the security captcha to view live transit milestones and delivery status.

📱 **SMS Tracking:** Send `POST TRACK {t_num}` to **166** or **51969**."""
        else:
            tracking_response = f"""### 📦 India Post Consignment Tracking

You can track your Speed Post, Registered Post, or Parcel through official India Post channels:

1. **Official Web Portal:**
   Visit [India Post Tracking Portal](https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx) and enter your 13-character Consignment Number (e.g. `EK123456789IN`).

2. **SMS Tracking Service:**
   Send `POST TRACK <Consignment Number>` (e.g., `POST TRACK EK123456789IN`) to **166** or **51969**."""

        if conversation_id:
            save_chat_message(conversation_id, "assistant", tracking_response)
        return Response(tracking_response, content_type="text/plain; charset=utf-8")

    # 2. Fetch past conversation history from Supabase for multi-turn context
    history_turns = []
    if conversation_id:
        past_msgs = get_conversation_messages(conversation_id, token=token)
        # Exclude the very last user message that was just saved
        for m in past_msgs[:-1]:
            role = "user" if m.get("role") == "user" else "model"
            content = m.get("content", "")
            if content:
                history_turns.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content)]
                ))

    # 3. Supabase pgvector Semantic Search (Top 3 Chunks)
    context_text = ""
    is_greeting = user_message.strip().lower() in ["hi", "hello", "hey", "namaste", "vanakkam", "namaskara", "good morning", "good afternoon", "good evening"]
    if not is_greeting:
        retrieved_chunks = search_documents(user_message, top_k=3, match_threshold=0.25)
        if retrieved_chunks:
            blocks = [c["text"] for c in retrieved_chunks if c.get("text")]
            context_text = "\n\n---\n\n".join(blocks)

    location_str = f"\nUser Geolocation PIN Code: {pincode} ({user_location.get('suburb', '')}, {user_location.get('city', '')}, {user_location.get('state', '')})" if pincode else ""

    # Detect financial calculations
    calc_context = ""
    msg_lower = user_message.lower()
    amt_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs|l)\b', msg_lower)
    raw_num_match = re.search(r'\b\d{4,7}\b', msg_lower)
    amt_val = None
    if amt_match:
        amt_val = float(amt_match.group(1)) * 100000.0
    elif raw_num_match:
        amt_val = float(raw_num_match.group(0))

    if amt_val:
        if any(k in msg_lower for k in ["sukanya", "ssa", "daughter", "girl"]):
            res = calculate_sukanya_maturity(amt_val)
            calc_context = f"\n\nCalculation Sukanya: Deposit ₹{res['annual_deposit']:,.2f}/yr | Total Invested ₹{res['total_invested']:,.2f} | Interest ₹{res['interest_earned']:,.2f} | Maturity ₹{res['maturity_value']:,.2f}"
        elif any(k in msg_lower for k in ["scss", "senior citizen", "senior"]):
            res = calculate_scss_payout(amt_val)
            calc_context = f"\n\nCalculation SCSS: Deposit ₹{res['deposit_amount']:,.2f} | Quarterly Payout ₹{res['quarterly_payout']:,.2f} | Total Interest ₹{res['total_interest_earned']:,.2f}"
        elif any(k in msg_lower for k in ["ppf", "provident"]):
            res = calculate_ppf_maturity(amt_val)
            calc_context = f"\n\nCalculation PPF: Annual Deposit ₹{res['annual_deposit']:,.2f} | Total Invested ₹{res['total_invested']:,.2f} | Maturity ₹{res['maturity_value']:,.2f}"
        elif any(k in msg_lower for k in ["mis", "monthly income"]):
            res = calculate_mis_payout(amt_val)
            calc_context = f"\n\nCalculation MIS: Deposit ₹{res['deposit_amount']:,.2f} | Monthly Income ₹{res['monthly_payout']:,.2f}"

    system_prompt = f"""You are Dak Sahayak, the official India Post AI assistant.
Respond strictly, fluently, and completely in {language}.
CRITICAL LANGUAGE GUIDELINES:
- When responding in a regional Indian language (such as Kannada, Hindi, Tamil, Telugu, Marathi, Bengali), write the ENTIRE content in that native script.
- Ensure all descriptions, bullet points, numbers, and rules are fully written in that regional language so readers and listeners receive a complete, coherent answer without skipped portions.
- For official scheme names, include the regional title and common acronym in brackets (for example: ಸುಕನ್ಯಾ ಸಮೃದ್ಧಿ ಯೋಜನೆ - SSA).
Always provide accurate, official information for Post Office Small Savings Schemes, POSB Banking charges, Mail/Speed Post rates, and Services.

Official India Post Consignment / Parcel Tracking:
- When a user asks to track a parcel, consignment, Speed Post, registered post, or article:
  - Direct them to the official India Post portal: https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx
  - Mention official SMS tracking: Send 'POST TRACK <Consignment Number>' to 166 or 51969.
  - Do NOT provide third-party tracking links.

Official India Post Small Savings Rates:
- Sukanya Samriddhi Account (SSA): 8.2% p.a. (Compounded annually)
- Senior Citizen Savings Scheme (SCSS): 8.2% p.a. (Paid quarterly)
- National Savings Certificate (NSC VIII): 7.7% p.a. (Compounded annually)
- Kisan Vikas Patra (KVP): 7.5% p.a. (Doubles in 115 months / 9 yrs 7 mos)
- Mahila Samman Savings Certificate (MSSC): 7.5% p.a. (Compounded quarterly)
- Post Office Time Deposit (5-Year FD): 7.5% p.a. (1-Yr 6.9%, 2-Yr 7.0%, 3-Yr 7.1%)
- Post Office Monthly Income Scheme (MIS): 7.4% p.a. (Paid monthly)
- Public Provident Fund (PPF): 7.1% p.a. (Compounded annually)
- Post Office Recurring Deposit (RD): 6.7% p.a. (Compounded quarterly)
- Post Office Savings Account (POSA): 4.0% p.a.

Official India Post Bank Fee Schedule:
- Duplicate Passbook: ₹50
- Statement of Account / Deposit Receipt: ₹20 per case
- Passbook in lieu of lost/mutilated certificate: ₹10 per registration
- Nomination change / cancellation: Completely Free (No fee applicable as per SB Order No. 05/2025)
- Account Transfer: ₹100
- Pledging of Account: ₹100
- Cheque Book: Free for up to 10 leaves/year, ₹2 per leaf thereafter
- Cheque Dishonour / Bounce: ₹100

{location_str}
{calc_context}

Official India Post Knowledge Base (from Supabase Vector DB):
{context_text}"""

    def generate_stream():
        full_text = ""
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.6-flash"]
        stream_success = False

        if client:
            for m in models_to_try:
                try:
                    chat_session = client.chats.create(
                        model=m,
                        history=history_turns,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2
                        )
                    )
                    response_stream = chat_session.send_message_stream(user_message)
                    for chunk in response_stream:
                        if chunk and chunk.text:
                            full_text += chunk.text
                            yield chunk.text
                    if full_text.strip():
                        stream_success = True
                        break
                except Exception as ex:
                    try:
                        response_stream = client.models.generate_content_stream(
                            model=m,
                            contents=f"System Prompt:\n{system_prompt}\n\nQuestion: {user_message}",
                            config=types.GenerateContentConfig(temperature=0.2)
                        )
                        for chunk in response_stream:
                            if chunk and chunk.text:
                                full_text += chunk.text
                                yield chunk.text
                        if full_text.strip():
                            stream_success = True
                            break
                    except Exception as ex2:
                        print(f"[-] Streaming error with {m}: {ex2}")

        if not stream_success or not full_text.strip():
            tracking_match = re.search(r'\b[A-Za-z]{2}\d{9}[A-Za-z]{2}\b', user_message)
            if tracking_match:
                t_num = tracking_match.group(0).upper()
                full_text = f"You can track your consignment **{t_num}** on the official India Post portal: https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx"
            elif any(w in msg_lower for w in ["track", "consignment", "parcel", "speed post"]):
                full_text = "You can track your parcel on the official India Post tracking portal: https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx"
            else:
                full_text = "India Post provides comprehensive Small Savings, Mail, and POSB Banking services across India."
            yield full_text

        # Save assistant response to Supabase messages table
        if conversation_id:
            save_chat_message(conversation_id, "assistant", full_text, token=token)
            # Update title on first turn
            if len(history_turns) == 0:
                update_conversation_title(conversation_id, user_message[:45], token=token)

    return Response(stream_with_context(generate_stream()), content_type="text/plain; charset=utf-8")

# --- Calculator & PIN Endpoints ---

@app.route("/api/calculator", methods=["POST"])
def api_calculator():
    data = request.get_json() or {}
    service = str(data.get("service", "speed_post")).lower().strip()
    weight = data.get("weight", 50)
    distance = data.get("distance", "local")

    if "letter" in service:
        res = calculate_ordinary_letter(weight)
    elif "postcard" in service:
        res = calculate_postcard(data.get("card_type", "single"))
    elif "parcel" in service and "speed" not in service:
        res = calculate_ordinary_parcel(weight)
    elif "registered" in service:
        res = calculate_registered_post(postage_base=float(data.get("postage", 5.0)), ad_required=bool(data.get("ad_card", False)))
    elif "insurance" in service:
        res = calculate_insurance(data.get("insured_value", 200))
    elif "sukanya" in service:
        res = calculate_sukanya_maturity(float(data.get("annual_deposit", 10000)))
    elif "ppf" in service:
        res = calculate_ppf_maturity(float(data.get("annual_deposit", 10000)))
    elif "scss" in service:
        res = calculate_scss_payout(float(data.get("deposit_amount", 100000)))
    elif "mis" in service:
        res = calculate_mis_payout(float(data.get("deposit_amount", 100000)))
    elif "nsc" in service:
        res = calculate_nsc_maturity(float(data.get("deposit_amount", 10000)))
    elif "kvp" in service:
        res = calculate_kvp_maturity(float(data.get("deposit_amount", 10000)))
    else:
        res = calculate_speed_post(weight, distance)

    return jsonify(res)

@app.route("/api/pincode/<query>", methods=["GET"])
def api_pincode(query):
    query_str = str(query).strip()
    results = search_pincode_db(query_str)
    if results:
        return jsonify({"status": "Success", "results": results})
    return jsonify({"status": "Error", "message": f"No post office found for '{query_str}'"}), 404

@app.route("/api/reverse-pincode", methods=["GET"])
def api_reverse_pincode():
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()

    if not lat or not lon:
        return jsonify({"status": "Error", "message": "Latitude and longitude required"}), 400

    headers = {"User-Agent": "DakSahayakApp/2.0 (India Post AI Assistant)"}
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            res_json = resp.json()
            address = res_json.get("address", {})
            postcode = address.get("postcode", "").strip()
            if postcode:
                postcode_match = re.search(r'\b[1-9][0-9]{5}\b', postcode)
                if postcode_match:
                    postcode = postcode_match.group(0)

            if postcode and len(postcode) == 6:
                results = search_pincode_db(postcode)
                return jsonify({
                    "status": "Success",
                    "pincode": postcode,
                    "address": address,
                    "results": results
                })
    except Exception as e:
        print(f"[-] Reverse geocoding error: {e}")

    return jsonify({
        "status": "Fallback",
        "message": "Unable to resolve location to a valid 6-digit PIN. Please enter your PIN manually."
    }), 200

# ================= FORMS ENGINE ENDPOINTS =================

@app.route("/api/forms/fill", methods=["POST"])
def api_fill_form():
    """Generates official filled India Post Form-1 PDF."""
    payload = request.get_json() or {}
    scheme = str(payload.get("scheme", "ppf")).strip().lower()
    language = str(payload.get("language", "en")).strip().lower()
    raw_data = payload.get("data", {})

    try:
        val_res = validate_form_data(scheme, language, raw_data)
        if not val_res["is_valid"]:
            return jsonify({
                "status": "error",
                "error_type": "validation_error",
                "message": val_res.get("message", "Validation failed"),
                "missing_fields": val_res.get("missing_fields", []),
                "invalid_fields": val_res.get("invalid_fields", [])
            }), 400

        pdf_buffer = generate_filled_pdf(scheme, language, raw_data)
        filename = f"{scheme.upper()}_Account_Opening_Form1.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        print(f"[-] Error generating form PDF: {e}")
        return jsonify({"status": "error", "message": f"Server error generating PDF: {str(e)}"}), 500

@app.route("/api/forms/chat-flow", methods=["POST"])
def api_form_chat_flow():
    """Handles structured multi-turn Q&A for auto-filling scheme forms."""
    payload = request.get_json() or {}
    scheme = str(payload.get("scheme", "ppf")).strip().lower()
    step_idx = int(payload.get("step_index", 0))
    collected = dict(payload.get("collected_data") or {})
    user_input = str(payload.get("user_input", "")).strip()

    steps = [
        {
            "field": "applicant_name",
            "prompt": "Let's prepare your official India Post **PPF Account Opening Form (Form-1)**.\n\n**Step 1/12**: What is your **Full Name** as per your Aadhaar / PAN card? (in BLOCK letters)",
            "validate": lambda v: len(v) >= 2,
            "error": "Please enter a valid full name (at least 2 characters)."
        },
        {
            "field": "father_or_spouse_name",
            "prompt": "**Step 2/12**: What is your **Father's, Mother's, or Spouse's Name**?",
            "validate": lambda v: len(v) >= 2,
            "error": "Please provide a valid name."
        },
        {
            "field": "dob",
            "prompt": "**Step 3/12**: What is your **Date of Birth**? (Please use DD/MM/YYYY or YYYY-MM-DD)",
            "validate": lambda v: bool(re.match(r"^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})$", v)),
            "error": "Please enter your date of birth in DD/MM/YYYY format (e.g. 15/08/1990)."
        },
        {
            "field": "gender",
            "prompt": "**Step 4/12**: What is your **Gender**? (Male / Female / Other)",
            "validate": lambda v: v.lower() in ["male", "female", "other", "m", "f", "o"],
            "error": "Please specify Male, Female, or Other."
        },
        {
            "field": "pan",
            "prompt": "**Step 5/12**: What is your **PAN Card Number**? (10 alphanumeric characters, e.g. ABCDE1234F)",
            "validate": lambda v: bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", v.upper())),
            "error": "Invalid PAN format. Must be 10 alphanumeric characters (e.g. ABCDE1234F)."
        },
        {
            "field": "aadhaar",
            "prompt": "**Step 6/12**: What is your **12-digit Aadhaar Number**? (or type *'Skip'* if you prefer to write it by hand)",
            "validate": lambda v: v.lower() in ["skip", "none", "na", "-"] or bool(re.match(r"^\d{12}$", v)),
            "error": "Please enter a valid 12-digit Aadhaar number or type 'Skip'."
        },
        {
            "field": "mobile",
            "prompt": "**Step 7/12**: What is your **10-digit Mobile Number**?",
            "validate": lambda v: bool(re.match(r"^[6-9]\d{9}$", v)),
            "error": "Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9."
        },
        {
            "field": "address",
            "prompt": "**Step 8/12**: What is your full **Residential Address** (House/Flat No, Street, Locality)?",
            "validate": lambda v: len(v) >= 5,
            "error": "Please provide a complete residential address."
        },
        {
            "field": "pincode",
            "prompt": "**Step 9/12**: What is your **6-digit PIN Code**?",
            "validate": lambda v: bool(re.match(r"^[1-9][0-9]{5}$", v)),
            "error": "Please enter a valid 6-digit postal PIN code (e.g. 575001)."
        },
        {
            "field": "initial_deposit",
            "prompt": "**Step 10/12**: What is your **Initial Deposit Amount** in ₹? (Minimum ₹500, Maximum ₹1,50,000 per financial year)",
            "validate": lambda v: (lambda clean: clean.isdigit() and 500 <= int(clean) <= 150000)(re.sub(r"[^\d]", "", v)),
            "error": "PPF deposit amount must be between ₹500 and ₹1,50,000 per financial year."
        },
        {
            "field": "nominee_name",
            "prompt": "**Step 11/12**: Please provide the **Full Name of your Nominee** for this account.",
            "validate": lambda v: len(v) >= 2,
            "error": "Please enter the nominee's full name."
        },
        {
            "field": "nominee_relationship",
            "prompt": "**Step 12/12**: What is your **Relationship with the Nominee**? (e.g. Spouse, Son, Daughter, Mother, Father)",
            "validate": lambda v: len(v) >= 2,
            "error": "Please specify the nominee relationship."
        }
    ]

    total_steps = len(steps)

    # Initial invocation (start flow)
    if step_idx == 0 and not user_input:
        return jsonify({
            "status": "in_progress",
            "step_index": 0,
            "total_steps": total_steps,
            "prompt": steps[0]["prompt"],
            "collected_data": {}
        })

    # Validate input for current step
    current_step = steps[step_idx]
    current_field = current_step["field"]

    if not current_step["validate"](user_input):
        return jsonify({
            "status": "in_progress",
            "step_index": step_idx,
            "total_steps": total_steps,
            "prompt": f"⚠️ {current_step['error']}\n\n{current_step['prompt']}",
            "collected_data": collected
        })

    # Process and store value
    if current_field == "pan":
        collected[current_field] = user_input.upper()
    elif current_field == "aadhaar":
        if user_input.lower() in ["skip", "none", "na", "-"]:
            collected[current_field] = ""
        else:
            collected[current_field] = user_input
    elif current_field == "initial_deposit":
        clean_num = re.sub(r"[^\d]", "", user_input)
        collected[current_field] = int(clean_num)
    elif current_field == "gender":
        if user_input.lower() in ["m", "male"]:
            collected[current_field] = "Male"
        elif user_input.lower() in ["f", "female"]:
            collected[current_field] = "Female"
        else:
            collected[current_field] = "Other"
    else:
        collected[current_field] = user_input

    next_idx = step_idx + 1

    # If completed all steps
    if next_idx >= total_steps:
        collected["nominee_share"] = 100
        return jsonify({
            "status": "completed",
            "form_ready": True,
            "scheme": scheme,
            "step_index": next_idx,
            "total_steps": total_steps,
            "prompt": "🎉 **All required details for your PPF Account Opening Form have been successfully collected!**\n\nYour official print-ready **India Post Form-1 (GSPR 2018)** is ready for download below.",
            "collected_data": collected
        })

    # Return next question
    next_step = steps[next_idx]
    return jsonify({
        "status": "in_progress",
        "step_index": next_idx,
        "total_steps": total_steps,
        "prompt": next_step["prompt"],
        "collected_data": collected
    })

# --- Text-to-Speech (TTS) Endpoint with Indian Neural Accents ---

@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    """Synthesizes text into high-quality Indian neural speech audio (MP3)."""
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        language = data.get("language", "English")
        gender = data.get("gender", "female")

        if not text:
            return jsonify({"error": "No text provided for speech synthesis"}), 400

        audio_bytes = generate_indian_speech(text=text, language=language, gender=gender)
        if not audio_bytes:
            return jsonify({"error": "Failed to synthesize speech audio"}), 500

        return Response(
            audio_bytes,
            mimetype="audio/mpeg",
            headers={
                "Content-Type": "audio/mpeg",
                "Content-Disposition": "inline; filename=speech.mp3",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        print(f"[TTS Route Error]: {e}")
        return jsonify({"error": f"Speech synthesis failed: {str(e)}"}), 500

# --- Translate to English Endpoint ---

@app.route("/api/translate", methods=["POST"])
def translate_to_english():
    """Translates non-English text to English using Gemini."""
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        source_language = data.get("source_language", "auto")

        if not text:
            return jsonify({"error": "No text provided for translation"}), 400

        if not client:
            return jsonify({"error": "AI service unavailable"}), 503

        prompt = f"""Translate the following text to English. 
Preserve the original formatting including bullet points, numbering, bold markers (**), and markdown structure.
Do NOT add any extra explanation, commentary, or preamble. Only output the translated text.

Source language: {source_language}

Text to translate:
{text}"""

        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"]
        translated = ""

        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=4096
                    )
                )
                if response.text and response.text.strip():
                    translated = response.text.strip()
                    break
            except Exception as e:
                print(f"[Translate] Model {m} failed: {e}")
                continue

        if not translated:
            return jsonify({"error": "Translation returned empty result"}), 500

        return jsonify({
            "translated_text": translated,
            "source_language": source_language
        })

    except Exception as e:
        print(f"[Translate Error]: {e}")
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
