import os
import re
import math
import json
from functools import lru_cache
import requests
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types

from forms.validator import validate_form_data
from forms.pdf_filler import generate_filled_pdf

def mask_pii(data):
    """
    Recursively masks sensitive personally identifiable information (PII)
    including PAN, Aadhaar, Mobile, Email, and personal names for privacy compliance.
    """
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ["pan", "aadhaar", "mobile", "phone"]):
                v_str = str(v)
                if len(v_str) > 4:
                    masked[k] = v_str[:2] + "*" * (len(v_str) - 4) + v_str[-2:]
                else:
                    masked[k] = "****"
            elif "email" in k_lower:
                v_str = str(v)
                masked[k] = re.sub(r"(?<=.).(?=.*@)", "*", v_str) if "@" in v_str else "****"
            elif any(s in k_lower for s in ["applicant_name", "nominee_name", "father_or_spouse_name", "address"]):
                v_str = str(v)
                masked[k] = v_str[:2] + "****" if len(v_str) > 2 else "****"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_pii(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_pii(item) for item in data]
    elif isinstance(data, str):
        s = data
        s = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", lambda m: m.group()[:2] + "******" + m.group()[-2:], s)
        s = re.sub(r"\b[6-9]\d{9}\b", lambda m: m.group()[:2] + "******" + m.group()[-2:], s)
        s = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "XXXXXXXX****", s)
        s = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", lambda m: m.group()[0] + "***@" + m.group().split("@")[-1], s)
        return s
    return data

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
    calculate_speed_post, calculate_pincode_distance, calculate_ordinary_letter, calculate_postcard,
    calculate_inland_letter, calculate_ordinary_parcel, calculate_registered_post, calculate_insurance,
    calculate_book_post, calculate_periodical_post, calculate_registered_newspaper, calculate_blind_literature,
    calculate_gyan_post, calculate_sukanya_maturity, calculate_scss_payout, calculate_ppf_maturity,
    calculate_mis_payout, calculate_nsc_maturity, calculate_kvp_maturity, calculate_mssc_maturity,
    calculate_potd_maturity, calculate_rd_maturity
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
* **Official Portal:** [India Post Official Tracking Portal](https://www.indiapost.gov.in/)

**How to Track:**
1. Visit the official **[India Post Portal (indiapost.gov.in)](https://www.indiapost.gov.in/)**.
2. Locate the **Track 'N Trace** box on the homepage.
3. Enter your Consignment Number: `{t_num}`.
4. Complete the security captcha and click **Search / Track Now**.

📱 **SMS Tracking:** Send `POST TRACK {t_num}` to **166** or **51969**
📞 **Helpline:** Call India Post Toll-Free at **1800 266 6868**"""
        else:
            tracking_response = f"""### 📦 India Post Consignment Tracking

You can track your Speed Post, Registered Post, or Parcel through official India Post channels:

1. **Official Web Portal:**
   Visit **[India Post Official Portal (indiapost.gov.in)](https://www.indiapost.gov.in/)**, go to the **Track 'N Trace** section on the homepage, and enter your 13-character Consignment Number (e.g. `EK123456789IN`).

2. **SMS Tracking Service:**
   Send `POST TRACK <Consignment Number>` (e.g., `POST TRACK EK123456789IN`) to **166** or **51969**.

3. **Official Mobile App:**
   Download the **Postinfo** app from Google Play Store or Apple App Store.

📞 **Toll-Free Helpline:** **1800 266 6868** (Toll-Free)"""

        if conversation_id:
            save_chat_message(conversation_id, "assistant", tracking_response)
        return Response(tracking_response, content_type="text/plain; charset=utf-8")

    # 2. Fetch past conversation history from Supabase for multi-turn context
    history_turns = []
    if conversation_id:
        past_msgs = get_conversation_messages(conversation_id, token=token)
        # Keep only recent 6 turns to minimize context token latency while preserving flow
        recent_past = past_msgs[:-1][-6:]
        for m in recent_past:
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

    system_prompt = f"""You are Dak Sahayak (डाक सहायक), the dedicated and official AI assistant for India Post (Department of Posts, Ministry of Communications, Government of India).
Respond strictly, fluently, and completely in {language}.

=== CRITICAL DOMAIN GUARDRAILS & RESTRICTION RULE ===
1. STRICT POSTAL DOMAIN ONLY: You are exclusively designed to assist with India Post and Postal Services.
2. OUT-OF-DOMAIN QUESTIONS STRICT REFUSAL:
   - If the user asks about ANY topic outside India Post and postal services (such as science, biology, photosynthesis, physics, chemistry, mathematics, education, school homework, coding, programming, business strategies, sports, entertainment, movies, celebrities, politics, medical advice, cooking/recipes, general trivia, or any other non-postal field), you MUST STRICTLY AND POLITELY DECLINE to answer the query.
   - UNDER NO CIRCUMSTANCES should you answer, explain, summarize, or solve non-postal queries (e.g., NEVER explain what photosynthesis is, never write non-postal code, never answer general education, science, or business questions).
   - When declining, state politely in {language} that as Dak Sahayak (डाक सहायक), you only answer queries related to India Post services (such as Post Office Savings Schemes, POSB Banking, Speed Post & Mail tariffs, Consignment Tracking, PIN code lookup, Postal Life Insurance/PLI/RPLI, and Post Office forms/procedures) and invite the user to ask any postal-related questions.
3. ALLOWED IN-DOMAIN TOPICS:
   - India Post Small Savings Schemes (PPF, Sukanya Samriddhi SSA, Senior Citizen Savings Scheme SCSS, MIS, NSC, KVP, RD, TD/FD, Mahila Samman MSSC, POSA).
   - Post Office Savings Bank (POSB) & India Post Payments Bank (IPPB) banking services, rules, and fees.
   - Speed Post, Registered Post, Parcel, Ordinary Post, Postcards, Inland Letters, International Mail tariffs and delivery timelines.
   - Consignment & Parcel Tracking methods.
   - PIN Code search and Post Office branch locations.
   - Postal Life Insurance (PLI) & Rural Postal Life Insurance (RPLI).
   - India Post official forms (Form-1, nomination, KYC, etc.).
   - Standard polite greetings and identity queries ("Hi", "Namaste", "Who are you?", "How can you help me?").

CRITICAL RESPONSE SPEED & BREVITY GUIDELINES:
- Provide direct, concise, high-value answers immediately without unnecessary introductory fluff or long repetitive disclaimers.
- Use clear bullet points and bold figures (rates, fees, eligibility, timelines) for quick readability.
- When responding in a regional Indian language (such as Kannada, Hindi, Tamil, Telugu, Marathi, Bengali), write the ENTIRE content in that native script.
- Ensure all descriptions, bullet points, numbers, and rules are fully written in that regional language so readers and listeners receive a complete, coherent answer without skipped portions.
- For official scheme names, include the regional title and common acronym in brackets (for example: ಸುಕನ್ಯಾ ಸಮೃದ್ಧಿ ಯೋಜನೆ - SSA).
Always provide accurate, official information for Post Office Small Savings Schemes, POSB Banking charges, Mail/Speed Post rates, and Services.

Official India Post Consignment / Parcel Tracking:
- When a user asks to track a parcel, consignment, Speed Post, registered post, or article:
  - Direct them to the official India Post portal: https://www.indiapost.gov.in/
  - Mention official SMS tracking: Send 'POST TRACK <Consignment Number>' to 166 or 51969.
  - Mention the official Postinfo Mobile app and toll-free helpline 1800 266 6868.
  - Do NOT provide third-party tracking links.

Official India Post Domestic Mail & Parcel Tariffs (Published by Department of Posts):
- Letters:
  * Weight not exceeding 20g: ₹5.00
  * Every additional 20g or fraction thereof: ₹5.00 (Max 2 kg)
- Letter Cards (Inland Letter): ₹2.50 flat
- Postcards:
  * Single Postcard: 50 paise (₹0.50)
  * Reply Postcard: ₹1.00
  * Printed Postcard: ₹6.00
  * Competition Postcard: ₹10.00
  * Meghdoot Postcard: 25 paise (₹0.25)
- Book Post / Book Packet:
  * Printed Books: First 100g = ₹1.00, Every additional 100g = ₹1.00
  * Regular Book Packet: First 50g = ₹4.00, Every additional 50g = ₹3.00 (Max 5 kg)
- Periodical Post:
  * Value between ₹1 - ₹20: First 100g = ₹2.00, Every addl 100g = ₹3.00
  * Value between ₹21 - ₹50: First 100g = ₹4.00, Every addl 100g = ₹5.00
  * Value ₹51 and above: First 100g = ₹8.00, Every addl 100g = ₹9.00
- Literature for the Blind:
  * Completely Free / Exempted from postage (up to 7 kg)
- Registered Newspapers:
  * Single copy: Up to 50g = 25 paise, 51-100g = 50 paise, Every addl 100g = 20 paise
  * Multiple copies packet: Up to 100g = 50 paise, Every addl 100g = 20 paise
- Gyan Post:
  * Up to 300g = ₹20, 301-500g = ₹25, 501-1000g = ₹30, Every addl 1000g = ₹20 (+ 18% GST)
- Ordinary Parcel:
  * First 500g = ₹19.00, Every additional 500g = ₹16.00 (Max 20 kg registered, 4 kg unregistered)
- Registered Post:
  * Registration Fee: ₹17.00 + Base Postage (+ ₹3.00 optional Acknowledgement Due / AD card)
- Insurance Fee:
  * Up to ₹200 = ₹10.00, Every additional ₹100 = ₹6.00
- Domestic Speed Post (Weight & Distance Matrix, 18% GST applicable):
  * Local (Intra-city): Up to 50g = ₹15, 51-200g = ₹25, 201-500g = ₹30, Addl 500g = ₹10
  * Up to 200 km: Up to 50g = ₹35, 51-200g = ₹35, 201-500g = ₹50, Addl 500g = ₹15
  * 201 to 1000 km: Up to 50g = ₹35, 51-200g = ₹40, 201-500g = ₹60, Addl 500g = ₹30
  * 1001 to 2000 km: Up to 50g = ₹35, 51-200g = ₹60, 201-500g = ₹80, Addl 500g = ₹40
  * Above 2000 km: Up to 50g = ₹35, 51-200g = ₹70, 201-500g = ₹90, Addl 500g = ₹50

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
        # Ultra-fast low-latency models with 0-thinking budget
        models_to_try = ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3.5-flash-lite"]
        stream_success = False

        def get_chunk_safe(chunk):
            try:
                if hasattr(chunk, "text") and chunk.text:
                    return chunk.text
            except Exception:
                pass
            return ""

        try:
            if client:
                for m in models_to_try:
                    try:
                        # gemini-3.1-flash-lite supports thinking_budget=0 for instant first-token streaming
                        is_3_1 = "3.1" in m
                        gen_config = types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.2,
                            thinking_config=types.ThinkingConfig(thinking_budget=0) if is_3_1 else None
                        )
                        chat_session = client.chats.create(
                            model=m,
                            history=history_turns,
                            config=gen_config
                        )
                        response_stream = chat_session.send_message_stream(user_message)
                        for chunk in response_stream:
                            c_text = get_chunk_safe(chunk)
                            if c_text:
                                full_text += c_text
                                yield c_text
                        if full_text.strip():
                            stream_success = True
                            break
                    except Exception as ex:
                        err_msg = str(ex).lower()
                        print(f"[-] Chat error with {m}: {ex}")
                        # If model is unavailable (503/404/quota), skip to next candidate immediately
                        if any(err_code in err_msg for err_code in ["503", "unavailable", "404", "not_found", "quota"]):
                            continue
                        try:
                            is_3_1 = "3.1" in m
                            gen_config = types.GenerateContentConfig(
                                temperature=0.2,
                                thinking_config=types.ThinkingConfig(thinking_budget=0) if is_3_1 else None
                            )
                            response_stream = client.models.generate_content_stream(
                                model=m,
                                contents=f"System Prompt:\n{system_prompt}\n\nQuestion: {user_message}",
                                config=gen_config
                            )
                            for chunk in response_stream:
                                c_text = get_chunk_safe(chunk)
                                if c_text:
                                    full_text += c_text
                                    yield c_text
                            if full_text.strip():
                                stream_success = True
                                break
                        except Exception as ex2:
                            print(f"[-] Streaming fallback error with {m}: {ex2}")
                            continue

            if not stream_success or not full_text.strip():
                tracking_match = re.search(r'\b[A-Za-z]{2}\d{9}[A-Za-z]{2}\b', user_message)
                if tracking_match:
                    t_num = tracking_match.group(0).upper()
                    full_text = f"You can track your consignment **{t_num}** on the official India Post portal: https://www.indiapost.gov.in/ (enter your consignment number in the Track 'N Trace section)."
                elif any(w in msg_lower for w in ["track", "consignment", "parcel", "speed post"]):
                    full_text = "You can track your parcel on the official India Post portal: https://www.indiapost.gov.in/ (use the Track 'N Trace section on the homepage)."
                else:
                    full_text = "India Post provides comprehensive Small Savings, Mail, and POSB Banking services across India."
                yield full_text

            # Save assistant response to local/supabase messages table
            if conversation_id:
                save_chat_message(conversation_id, "assistant", full_text, token=token)
                # Update title on first turn
                if len(history_turns) == 0:
                    update_conversation_title(conversation_id, user_message[:45], token=token)

        except Exception as fatal_ex:
            print(f"[Streaming Fatal Error]: {fatal_ex}")
            if not full_text.strip():
                yield "I am Dak Sahayak, your India Post AI assistant. Please try asking your question again."

    return Response(stream_with_context(generate_stream()), content_type="text/plain; charset=utf-8")

# --- Calculator & PIN Endpoints ---

@app.route("/api/calculator", methods=["POST"])
def api_calculator():
    data = request.get_json() or {}
    service = str(data.get("service", "speed_post")).lower().strip()
    weight = data.get("weight", 50)
    distance = data.get("distance", "local")
    from_pincode = str(data.get("from_pincode") or data.get("from_pin") or "").strip()
    to_pincode = str(data.get("to_pincode") or data.get("to_pin") or "").strip()

    if "book" in service:
        res = calculate_book_post(weight, is_printed_books=bool(data.get("is_printed_books", False)))
    elif "periodical" in service:
        res = calculate_periodical_post(weight, value_tier=str(data.get("value_tier", "tier1")))
    elif "newspaper" in service:
        res = calculate_registered_newspaper(weight, is_multiple_copies=bool(data.get("is_multiple_copies", False)))
    elif "blind" in service:
        res = calculate_blind_literature(weight)
    elif "gyan" in service:
        res = calculate_gyan_post(weight)
    elif "inland" in service:
        res = calculate_inland_letter()
    elif "letter" in service:
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
    elif "mssc" in service or "mahila" in service:
        res = calculate_mssc_maturity(float(data.get("deposit_amount", 100000)))
    elif "td" in service or "time_deposit" in service or "potd" in service:
        res = calculate_potd_maturity(float(data.get("deposit_amount", 100000)), tenure_years=int(data.get("tenure_years", 5)))
    elif "rd" in service or "recurring" in service:
        res = calculate_rd_maturity(float(data.get("monthly_deposit") or data.get("deposit_amount", 5000)))
    else:
        res = calculate_speed_post(weight, distance_input=distance, from_pincode=from_pincode, to_pincode=to_pincode)

    if from_pincode and to_pincode and "distance_km" not in res:
        route = calculate_pincode_distance(from_pincode, to_pincode)
        res["from_pincode"] = route["from_pincode"]
        res["to_pincode"] = route["to_pincode"]
        res["from_location"] = route["from_location"]
        res["to_location"] = route["to_location"]
        res["distance_km"] = route["distance_km"]

    return jsonify(res)

@app.route("/api/pincode-distance", methods=["GET", "POST"])
def api_pincode_distance():
    if request.method == "POST":
        data = request.get_json() or {}
        from_pin = data.get("from_pincode") or data.get("from_pin") or ""
        to_pin = data.get("to_pincode") or data.get("to_pin") or ""
    else:
        from_pin = request.args.get("from", "")
        to_pin = request.args.get("to", "")

    if not from_pin or not to_pin:
        return jsonify({"status": "Error", "message": "Both from and to pincodes are required"}), 400

    route_info = calculate_pincode_distance(from_pin, to_pin)
    return jsonify({"status": "Success", **route_info})

@app.route("/api/pincode/<query>", methods=["GET"])
def api_pincode(query):
    query_str = str(query).strip()
    results = search_pincode_db(query_str)
    if results:
        return jsonify({"status": "Success", "results": results})
    return jsonify({"status": "Error", "message": f"No post office found for '{query_str}'"}), 404

@lru_cache(maxsize=1024)
def _fetch_reverse_geocode(lat_r: float, lon_r: float):
    """Cached reverse geocoding via OpenStreetMap Nominatim with rate-limit protection."""
    headers = {"User-Agent": "DakSahayak-IndiaPost-AI/2.1 (contact: dev@daksahayak.local)"}
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat_r}&lon={lon_r}&zoom=18&addressdetails=1"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            print("[-] Warning: Nominatim rate limit (429) encountered")
            return {"rate_limited": True}
    except Exception as ex:
        print(f"[-] Nominatim request error: {ex}")
    return None

@app.route("/api/reverse-pincode", methods=["GET"])
def api_reverse_pincode():
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()

    if not lat or not lon:
        return jsonify({"status": "Error", "message": "Latitude and longitude required"}), 400

    try:
        lat_r = round(float(lat), 4)
        lon_r = round(float(lon), 4)
        res_json = _fetch_reverse_geocode(lat_r, lon_r)
        if res_json and not res_json.get("rate_limited"):
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
    """Generates official filled India Post Form-1 PDF directly in-memory."""
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
        pdf_buffer.seek(0)
        filename = f"{scheme.upper()}_Account_Opening_Form1.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except ValueError as ve:
        return jsonify({"status": "error", "message": mask_pii(str(ve))}), 400
    except Exception as e:
        print(f"[-] Error generating form PDF: {mask_pii(str(e))}")
        return jsonify({"status": "error", "message": "Server error generating PDF"}), 500

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
    """Synthesizes text into high-quality Indian neural speech audio (MP3) with browser fallback."""
    language = "English"
    text = ""
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        language = data.get("language", "English")
        gender = data.get("gender", "female")

        if not text:
            return jsonify({"error": "No text provided for speech synthesis"}), 400

        audio_bytes = None
        try:
            audio_bytes = generate_indian_speech(text=text, language=language, gender=gender)
        except Exception as tts_err:
            print(f"[TTS Fallback Triggered]: {tts_err}")

        if not audio_bytes:
            return jsonify({
                "fallback": "browser_tts",
                "status": "degraded",
                "language": language,
                "text": text,
                "message": "Edge TTS service unavailable or rate limited. Client browser fallback activated."
            }), 200

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
        return jsonify({
            "fallback": "browser_tts",
            "status": "degraded",
            "language": language,
            "text": text,
            "message": "Edge TTS service exception. Client browser fallback activated."
        }), 200

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

        models_to_try = ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-3.5-flash-lite"]
        translated = ""

        for m in models_to_try:
            try:
                is_3_1 = "3.1" in m
                gen_config = types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    thinking_config=types.ThinkingConfig(thinking_budget=0) if is_3_1 else None
                )
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=gen_config
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
