import os
import math
import json
import sqlite3

RATES_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rates_config.json")

def load_rates_config():
    """Loads versioned interest rates and tariff matrices from rates_config.json."""
    if os.path.exists(RATES_CONFIG_PATH):
        try:
            with open(RATES_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to load rates_config.json: {e}")
    return {}

_RATES_CONFIG = load_rates_config()
_SAVINGS_RATES = _RATES_CONFIG.get("small_savings_rates", {})

# Official Speed Post Distance & Weight Tariff Matrix (dynamic from config with fallback)
TARIFF_MATRIX = _RATES_CONFIG.get("speed_post_tariff") or {
    "local": {
        "label": "Local (Intra-city)",
        "up_to_50g": 15,
        "up_to_200g": 25,
        "up_to_500g": 30,
        "addl_500g": 10
    },
    "up_to_200": {
        "label": "Up to 200 km",
        "up_to_50g": 35,
        "up_to_200g": 35,
        "up_to_500g": 50,
        "addl_500g": 15
    },
    "201_to_1000": {
        "label": "201 to 1000 km",
        "up_to_50g": 35,
        "up_to_200g": 40,
        "up_to_500g": 60,
        "addl_500g": 30
    },
    "1001_to_2000": {
        "label": "1001 to 2000 km",
        "up_to_50g": 35,
        "up_to_200g": 60,
        "up_to_500g": 80,
        "addl_500g": 40
    },
    "above_2000": {
        "label": "Above 2000 km",
        "up_to_50g": 35,
        "up_to_200g": 70,
        "up_to_500g": 90,
        "addl_500g": 50
    }
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pincodes.db")

def _get_ro_sqlite_conn(db_path: str):
    """Opens a safe, read-only SQLite URI connection with busy timeout."""
    abs_path = os.path.abspath(db_path).replace(os.sep, "/")
    uri = f"file:{abs_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    return conn

def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * (math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c, 2)

def get_pincode_info(pincode: str):
    """Retrieves office name, district, state, and geographic coordinates for a given 6-digit PIN code."""
    p_clean = str(pincode).strip()
    if not p_clean.isdigit() or len(p_clean) != 6:
        return None
    
    if os.path.exists(DB_PATH):
        try:
            conn = _get_ro_sqlite_conn(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT pincode, office_name, office_type, district, state, circle, latitude, longitude FROM pincodes WHERE pincode = ? LIMIT 1", (p_clean,))
            row = cur.fetchone()
            conn.close()
            if row:
                lat = float(row["latitude"]) if row["latitude"] else None
                lon = float(row["longitude"]) if row["longitude"] else None
                return {
                    "pincode": row["pincode"],
                    "office_name": row["office_name"] or "",
                    "district": row["district"] or "",
                    "state": row["state"] or "",
                    "circle": row["circle"] or "",
                    "latitude": lat,
                    "longitude": lon
                }
        except Exception as e:
            print(f"[-] Pincode DB lookup error for {p_clean}: {e}")
    return None

def calculate_pincode_distance(from_pincode: str, to_pincode: str):
    """
    Calculates geographic distance and determines official India Post distance slab between two PIN codes.
    Returns calculated distance in km, origin/destination details, and tariff slab key.
    """
    from_p = str(from_pincode or "").strip()
    to_p = str(to_pincode or "").strip()

    from_info = get_pincode_info(from_p)
    to_info = get_pincode_info(to_p)

    from_loc_str = f"{from_info['office_name']}, {from_info['district']} ({from_info['state']})" if from_info else f"PIN {from_p}"
    to_loc_str = f"{to_info['office_name']}, {to_info['district']} ({to_info['state']})" if to_info else f"PIN {to_p}"

    # 1. Exact same PIN code
    if from_p and to_p and from_p == to_p:
        return {
            "from_pincode": from_p,
            "to_pincode": to_p,
            "from_location": from_loc_str,
            "to_location": to_loc_str,
            "distance_km": 0.0,
            "distance_key": "local",
            "distance_label": TARIFF_MATRIX["local"]["label"],
            "calculation_method": "same_pincode"
        }

    # 2. Coordinates available for both PIN codes
    if from_info and to_info and from_info["latitude"] is not None and from_info["longitude"] is not None and to_info["latitude"] is not None and to_info["longitude"] is not None:
        dist_km = _haversine_km(from_info["latitude"], from_info["longitude"], to_info["latitude"], to_info["longitude"])
        
        # Local delivery rules: same district & distance <= 35km or distance <= 25km
        is_same_district = from_info["district"] and (from_info["district"].upper() == to_info["district"].upper())
        
        if dist_km <= 25.0 or (is_same_district and dist_km <= 35.0):
            dist_key = "local"
        elif dist_km <= 200.0:
            dist_key = "up_to_200"
        elif dist_km <= 1000.0:
            dist_key = "201_to_1000"
        elif dist_km <= 2000.0:
            dist_key = "1001_to_2000"
        else:
            dist_key = "above_2000"

        return {
            "from_pincode": from_p,
            "to_pincode": to_p,
            "from_location": from_loc_str,
            "to_location": to_loc_str,
            "distance_km": dist_km,
            "distance_key": dist_key,
            "distance_label": TARIFF_MATRIX[dist_key]["label"],
            "calculation_method": "haversine_coordinates"
        }

    # 3. Fallback: Prefix-based estimation if coordinates are unavailable
    estimated_km = 150.0
    dist_key = "up_to_200"

    if from_p and to_p:
        if from_p[:3] == to_p[:3]:
            estimated_km = 20.0
            dist_key = "local"
        elif from_p[:2] == to_p[:2]:
            estimated_km = 120.0
            dist_key = "up_to_200"
        elif from_p[0] == to_p[0]:
            estimated_km = 450.0
            dist_key = "201_to_1000"
        else:
            estimated_km = 1250.0
            dist_key = "1001_to_2000"

    return {
        "from_pincode": from_p or "N/A",
        "to_pincode": to_p or "N/A",
        "from_location": from_loc_str,
        "to_location": to_loc_str,
        "distance_km": estimated_km,
        "distance_key": dist_key,
        "distance_label": TARIFF_MATRIX[dist_key]["label"],
        "calculation_method": "prefix_estimation"
    }

def resolve_distance_category(distance_input):
    """Normalizes numeric km or category string to valid tariff matrix key."""
    if isinstance(distance_input, (int, float)):
        km = float(distance_input)
        if km <= 25:
            return "local"
        elif km <= 200:
            return "up_to_200"
        elif km <= 1000:
            return "201_to_1000"
        elif km <= 2000:
            return "1001_to_2000"
        else:
            return "above_2000"
    
    key = str(distance_input).lower().strip().replace(" ", "_")
    if key in TARIFF_MATRIX:
        return key
    if "local" in key:
        return "local"
    if "200" in key and "1000" not in key:
        return "up_to_200"
    if "1000" in key and "2000" not in key:
        return "201_to_1000"
    if "2000" in key and "above" in key or "above_2000" in key:
        return "above_2000"
    if "2000" in key:
        return "1001_to_2000"
    
    return "up_to_200"

def calculate_speed_post(weight_g, distance_input=None, from_pincode=None, to_pincode=None):
    """
    Calculates Domestic Speed Post charges based on weight (grams) and From/To PIN codes (or manual distance).
    Returns base tariff, 18% GST, route distance, and total payable amount.
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 50.0

    if weight <= 0:
        weight = 1.0

    route_info = None
    if from_pincode and to_pincode:
        route_info = calculate_pincode_distance(from_pincode, to_pincode)
        dist_key = route_info["distance_key"]
    elif distance_input:
        dist_key = resolve_distance_category(distance_input)
    else:
        dist_key = "up_to_200"

    rates = TARIFF_MATRIX[dist_key]
    
    base_tariff = 0
    weight_slab = ""

    if weight <= 50:
        base_tariff = rates["up_to_50g"]
        weight_slab = "Up to 50 g"
    elif weight <= 200:
        base_tariff = rates["up_to_200g"]
        weight_slab = "51 g to 200 g"
    elif weight <= 500:
        base_tariff = rates["up_to_500g"]
        weight_slab = "201 g to 500 g"
    else:
        base_tariff = rates["up_to_500g"]
        extra_weight = weight - 500
        extra_slabs = math.ceil(extra_weight / 500.0)
        additional_cost = extra_slabs * rates["addl_500g"]
        base_tariff += additional_cost
        weight_slab = f"500 g + {extra_slabs} x 500g additional"

    gst_amount = round(base_tariff * 0.18, 2)
    total_payable = round(base_tariff + gst_amount, 2)

    res = {
        "service": "Speed Post (Domestic)",
        "weight_g": weight,
        "distance_key": dist_key,
        "distance_label": rates["label"],
        "weight_slab": weight_slab,
        "base_tariff": base_tariff,
        "gst_rate": "18%",
        "gst_amount": gst_amount,
        "total_payable": total_payable
    }

    if route_info:
        res["from_pincode"] = route_info["from_pincode"]
        res["to_pincode"] = route_info["to_pincode"]
        res["from_location"] = route_info["from_location"]
        res["to_location"] = route_info["to_location"]
        res["distance_km"] = route_info["distance_km"]
        res["rate_description"] = f"Calculated Route: {route_info['distance_km']} km ({rates['label']})"
    else:
        res["rate_description"] = rates["label"]

    return res

def calculate_ordinary_letter(weight_g):
    """
    Official India Post Domestic Letter Tariff:
    - Weight not exceeding 20 grams: Rs. 5.00
    - Every additional 20 grams or fraction thereof: Rs. 5.00 (Max 2 kg)
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 20.0
    weight = max(1.0, min(2000.0, weight))

    slabs = math.ceil(weight / 20.0)
    total_cost = slabs * 5.0
    return {
        "service": "Letters (Domestic)",
        "weight_g": weight,
        "slabs": slabs,
        "rate_description": "₹5 per 20 grams or part thereof",
        "base_tariff": total_cost,
        "gst_amount": 0.0,
        "total_payable": total_cost
    }

def calculate_inland_letter():
    """Official India Post Letter Card (Inland Letter): Rs. 2.50 flat."""
    return {
        "service": "Letter Card (Inland Letter)",
        "rate_description": "₹2.50 per card",
        "base_tariff": 2.50,
        "gst_amount": 0.0,
        "total_payable": 2.50
    }

def calculate_postcard(card_type="single"):
    """
    Official India Post Postcard Tariff:
    - Single Postcard: 50 paise (Rs. 0.50)
    - Reply Postcard: Rs. 1.00
    - Printed Postcard: Rs. 6.00
    - Competition Postcard: Rs. 10.00
    - Meghdoot Postcard: 25 paise (Rs. 0.25)
    """
    card_type_clean = str(card_type).lower().strip()
    rates = {
        "single": (0.50, "Single Postcard (50 paise)"),
        "reply": (1.00, "Reply Postcard (₹1.00)"),
        "printed": (6.00, "Printed Postcard (₹6.00)"),
        "competition": (10.00, "Competition Postcard (₹10.00)"),
        "meghdoot": (0.25, "Meghdoot Postcard (25 paise)")
    }
    price, desc = rates.get(card_type_clean, (0.50, "Single Postcard (50 paise)"))
    return {
        "service": "Postcard",
        "card_type": card_type_clean,
        "rate_description": desc,
        "base_tariff": price,
        "gst_amount": 0.0,
        "total_payable": price
    }

def calculate_book_post(weight_g, is_printed_books=False):
    """
    Official India Post Book Post / Book Packet Tariff:
    - Printed Books: First 100g = Rs. 1.00, Every addl 100g = Rs. 1.00
    - Regular Book Packet: First 50g = Rs. 4.00, Every addl 50g = Rs. 3.00 (Max 5 kg)
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 50.0
    weight = max(1.0, min(5000.0, weight))

    if is_printed_books:
        slabs = math.ceil(weight / 100.0)
        cost = float(slabs * 1.0)
        desc = "Printed Books: ₹1 per 100g or part thereof"
    else:
        if weight <= 50:
            cost = 4.0
            desc = "First 50g: ₹4.00"
        else:
            extra_weight = weight - 50
            extra_slabs = math.ceil(extra_weight / 50.0)
            cost = 4.0 + (extra_slabs * 3.0)
            desc = f"First 50g (₹4) + {extra_slabs} x 50g additional (₹3 each)"

    return {
        "service": "Book Post / Book Packet",
        "category": "Printed Books" if is_printed_books else "Book Packet",
        "weight_g": weight,
        "rate_description": desc,
        "base_tariff": cost,
        "gst_amount": 0.0,
        "total_payable": cost
    }

def calculate_periodical_post(weight_g, value_tier="tier1"):
    """
    Official India Post Periodical Post Tariff:
    - Value ₹1 to ₹20: First 100g = Rs. 2.00, Every addl 100g = Rs. 3.00
    - Value ₹21 to ₹50: First 100g = Rs. 4.00, Every addl 100g = Rs. 5.00
    - Value ₹51 and above: First 100g = Rs. 8.00, Every addl 100g = Rs. 9.00
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 100.0
    weight = max(1.0, min(5000.0, weight))

    tier = str(value_tier).lower()
    if "51" in tier or "above" in tier or "high" in tier or "tier3" in tier:
        base_100, addl_100 = 8.0, 9.0
        val_desc = "Value ₹51 and above"
    elif "21" in tier or "50" in tier or "mid" in tier or "tier2" in tier:
        base_100, addl_100 = 4.0, 5.0
        val_desc = "Value ₹21 to ₹50"
    else:
        base_100, addl_100 = 2.0, 3.0
        val_desc = "Value ₹1 to ₹20"

    if weight <= 100:
        cost = base_100
        desc = f"First 100g ({val_desc}): ₹{base_100:.2f}"
    else:
        extra_slabs = math.ceil((weight - 100) / 100.0)
        cost = base_100 + (extra_slabs * addl_100)
        desc = f"First 100g (₹{base_100}) + {extra_slabs} x 100g (₹{addl_100} each) ({val_desc})"

    return {
        "service": "Periodical Post",
        "value_tier": val_desc,
        "weight_g": weight,
        "rate_description": desc,
        "base_tariff": cost,
        "gst_amount": 0.0,
        "total_payable": cost
    }

def calculate_registered_newspaper(weight_g, is_multiple_copies=False):
    """
    Official India Post Registered Newspaper Tariff:
    - Single Copy: Up to 50g = 25 paise, 51-100g = 50 paise, Every addl 100g = 20 paise
    - Multiple Copies Packet: Up to 100g = 50 paise, Every addl 100g = 20 paise
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 50.0
    weight = max(1.0, weight)

    if is_multiple_copies:
        if weight <= 100:
            cost = 0.50
            desc = "Multiple copies packet up to 100g: 50 paise"
        else:
            extra_slabs = math.ceil((weight - 100) / 100.0)
            cost = 0.50 + (extra_slabs * 0.20)
            desc = f"First 100g (50p) + {extra_slabs} x 100g (20p each)"
    else:
        if weight <= 50:
            cost = 0.25
            desc = "Single copy up to 50g: 25 paise"
        elif weight <= 100:
            cost = 0.50
            desc = "Single copy 51-100g: 50 paise"
        else:
            extra_slabs = math.ceil((weight - 100) / 100.0)
            cost = 0.50 + (extra_slabs * 0.20)
            desc = f"First 100g (50p) + {extra_slabs} x 100g (20p each)"

    return {
        "service": "Registered Newspaper",
        "category": "Multiple Copies Packet" if is_multiple_copies else "Single Copy",
        "weight_g": weight,
        "rate_description": desc,
        "base_tariff": round(cost, 2),
        "gst_amount": 0.0,
        "total_payable": round(cost, 2)
    }

def calculate_blind_literature(weight_g=1000):
    """
    Official India Post Literature for the Blind:
    - Free / Exempted from postage charges up to 7 kg.
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 1000.0
    weight = max(1.0, min(7000.0, weight))

    return {
        "service": "Literature for the Blind",
        "weight_g": weight,
        "rate_description": "Exempted from postage (Max 7 kg free)",
        "base_tariff": 0.0,
        "gst_amount": 0.0,
        "total_payable": 0.0
    }

def calculate_gyan_post(weight_g):
    """
    Official India Post Gyan Post Tariff:
    - Up to 300g: Rs. 20.00
    - 301 to 500g: Rs. 25.00
    - 501 to 1000g: Rs. 30.00
    - Every addl 1000g: Rs. 20.00
    * Applicable GST (18%) extra.
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 300.0
    weight = max(1.0, weight)

    if weight <= 300:
        base = 20.0
        desc = "Up to 300g: ₹20"
    elif weight <= 500:
        base = 25.0
        desc = "301g to 500g: ₹25"
    elif weight <= 1000:
        base = 30.0
        desc = "501g to 1000g: ₹30"
    else:
        extra_kg = math.ceil((weight - 1000) / 1000.0)
        base = 30.0 + (extra_kg * 20.0)
        desc = f"First 1000g (₹30) + {extra_kg} x 1000g additional (₹20 each)"

    gst = round(base * 0.18, 2)
    total = round(base + gst, 2)
    return {
        "service": "Gyan Post",
        "weight_g": weight,
        "rate_description": desc,
        "base_tariff": base,
        "gst_rate": "18%",
        "gst_amount": gst,
        "total_payable": total
    }

def calculate_ordinary_parcel(weight_g):
    """
    Official India Post Ordinary Parcel Tariff:
    - Weight not exceeding 500g: Rs. 19.00
    - Every additional 500g or part thereof: Rs. 16.00 (Max 20 kg for registered, 4 kg for unregistered)
    """
    try:
        weight = float(weight_g)
    except (ValueError, TypeError):
        weight = 500.0
    weight = max(1.0, weight)

    if weight <= 500:
        cost = 19.0
        desc = "First 500g: ₹19.00"
    else:
        extra_weight = weight - 500
        extra_slabs = math.ceil(extra_weight / 500.0)
        cost = 19.0 + (extra_slabs * 16.0)
        desc = f"First 500g (₹19) + {extra_slabs} x 500g additional (₹16 each)"

    return {
        "service": "Ordinary Parcel",
        "weight_g": weight,
        "rate_description": desc,
        "base_tariff": cost,
        "gst_amount": 0.0,
        "total_payable": cost
    }

def calculate_registered_post(postage_base=5.0, ad_required=False):
    """
    Official India Post Registered Post Tariff:
    - Registration Fee: Rs. 17.00 (in addition to standard postage)
    - Optional Acknowledgement Due (AD) card: Rs. 3.00
    """
    reg_fee = 17.0
    ad_fee = 3.0 if ad_required else 0.0
    total = postage_base + reg_fee + ad_fee
    desc = f"Base Postage (₹{postage_base:.2f}) + Registration Fee (₹17.00)"
    if ad_required:
        desc += " + Acknowledgement Card (₹3.00)"

    return {
        "service": "Registered Post",
        "base_postage": postage_base,
        "registration_fee": reg_fee,
        "ad_card_fee": ad_fee,
        "rate_description": desc,
        "base_tariff": total,
        "gst_amount": 0.0,
        "total_payable": total
    }

def calculate_insurance(value_amount):
    """
    Official India Post Insurance Fee:
    - Value up to Rs. 200: Rs. 10.00
    - Every additional Rs. 100 or fraction thereof: Rs. 6.00
    """
    try:
        val = float(value_amount)
    except (ValueError, TypeError):
        val = 200.0
    val = max(1.0, val)

    if val <= 200:
        fee = 10.0
        desc = "Insured value up to ₹200: ₹10.00"
    else:
        extra_val = val - 200
        extra_slabs = math.ceil(extra_val / 100.0)
        fee = 10.0 + (extra_slabs * 6.0)
        desc = f"First ₹200 (₹10) + {extra_slabs} x ₹100 additional (₹6 each)"

    return {
        "service": "Insurance Fee",
        "insured_value": val,
        "rate_description": desc,
        "base_tariff": fee,
        "gst_amount": 0.0,
        "total_payable": fee
    }

# Small Savings Schemes Financial Maturity Calculators

def calculate_sukanya_maturity(annual_deposit, tenure_years=21):
    """8.2% p.a. compounded annually. Deposits made for 15 years, matures in 21 years."""
    cfg = _SAVINGS_RATES.get("sukanya", {})
    r = float(cfg.get("rate", 0.082))
    min_dep = float(cfg.get("min_deposit", 250.0))
    max_dep = float(cfg.get("max_deposit", 150000.0))
    dep_years = int(cfg.get("deposit_years", 15))
    mat_years = int(cfg.get("maturity_years", 21))

    dep = max(min_dep, min(max_dep, float(annual_deposit)))
    total_invested = dep * dep_years
    balance = 0.0
    for year in range(1, mat_years + 1):
        if year <= dep_years:
            balance += dep
        balance += balance * r
    
    maturity_val = round(balance, 2)
    interest_earned = round(maturity_val - total_invested, 2)
    return {
        "scheme": "Sukanya Samriddhi Account (SSA)",
        "annual_deposit": dep,
        "deposit_years": dep_years,
        "maturity_years": mat_years,
        "interest_rate": f"{r * 100:.1f}%",
        "total_invested": total_invested,
        "interest_earned": interest_earned,
        "maturity_value": maturity_val
    }

def calculate_scss_payout(deposit_amount):
    """8.2% p.a. paid quarterly (5 year tenure, max 30 Lakhs)."""
    cfg = _SAVINGS_RATES.get("scss", {})
    r = float(cfg.get("rate", 0.082))
    min_dep = float(cfg.get("min_deposit", 1000.0))
    max_dep = float(cfg.get("max_deposit", 3000000.0))
    tenure = int(cfg.get("tenure_years", 5))

    dep = max(min_dep, min(max_dep, float(deposit_amount)))
    quarterly_interest = round((dep * r) / 4.0, 2)
    total_interest = round(quarterly_interest * (tenure * 4.0), 2)
    return {
        "scheme": "Senior Citizen Savings Scheme (SCSS)",
        "deposit_amount": dep,
        "tenure_years": tenure,
        "interest_rate": f"{r * 100:.1f}%",
        "quarterly_payout": quarterly_interest,
        "annual_payout": round(quarterly_interest * 4.0, 2),
        "total_interest_earned": total_interest,
        "total_maturity_payout": round(dep + total_interest, 2)
    }

def calculate_ppf_maturity(annual_deposit, tenure_years=15):
    """7.1% p.a. compounded annually."""
    cfg = _SAVINGS_RATES.get("ppf", {})
    r = float(cfg.get("rate", 0.071))
    min_dep = float(cfg.get("min_deposit", 500.0))
    max_dep = float(cfg.get("max_deposit", 150000.0))
    t_years = int(tenure_years or cfg.get("tenure_years", 15))

    dep = max(min_dep, min(max_dep, float(annual_deposit)))
    total_invested = dep * t_years
    balance = 0.0
    for _ in range(t_years):
        balance = (balance + dep) * (1 + r)
    maturity_val = round(balance, 2)
    return {
        "scheme": "Public Provident Fund (PPF)",
        "annual_deposit": dep,
        "tenure_years": t_years,
        "interest_rate": f"{r * 100:.1f}%",
        "total_invested": total_invested,
        "interest_earned": round(maturity_val - total_invested, 2),
        "maturity_value": maturity_val
    }

def calculate_mis_payout(deposit_amount):
    """7.4% p.a. paid monthly (5 year tenure, max 9 Lakhs single / 15 Lakhs joint)."""
    cfg = _SAVINGS_RATES.get("mis", {})
    r = float(cfg.get("rate", 0.074))
    min_dep = float(cfg.get("min_deposit", 1000.0))
    max_dep = float(cfg.get("max_deposit", 1500000.0))
    tenure = int(cfg.get("tenure_years", 5))

    dep = max(min_dep, min(max_dep, float(deposit_amount)))
    monthly_interest = round((dep * r) / 12.0, 2)
    total_interest = round(monthly_interest * (tenure * 12.0), 2)
    return {
        "scheme": "Post Office Monthly Income Scheme (MIS)",
        "deposit_amount": dep,
        "tenure_years": tenure,
        "interest_rate": f"{r * 100:.1f}%",
        "monthly_payout": monthly_interest,
        "annual_payout": round(monthly_interest * 12.0, 2),
        "total_interest_earned": total_interest,
        "total_maturity_payout": round(dep + total_interest, 2)
    }

def calculate_nsc_maturity(deposit_amount, tenure_years=5):
    """7.7% p.a. compounded annually for 5 years."""
    cfg = _SAVINGS_RATES.get("nsc", {})
    r = float(cfg.get("rate", 0.077))
    min_dep = float(cfg.get("min_deposit", 1000.0))
    t_years = int(tenure_years or cfg.get("tenure_years", 5))

    dep = max(min_dep, float(deposit_amount))
    maturity_val = round(dep * ((1 + r) ** t_years), 2)
    return {
        "scheme": "National Savings Certificate (NSC VIII Issue)",
        "deposit_amount": dep,
        "tenure_years": t_years,
        "interest_rate": f"{r * 100:.1f}%",
        "interest_earned": round(maturity_val - dep, 2),
        "maturity_value": maturity_val
    }

def calculate_kvp_maturity(deposit_amount):
    """7.5% p.a. compounded annually, doubles in 115 months."""
    cfg = _SAVINGS_RATES.get("kvp", {})
    r = float(cfg.get("rate", 0.075))
    min_dep = float(cfg.get("min_deposit", 1000.0))
    t_months = int(cfg.get("tenure_months", 115))
    t_disp = str(cfg.get("tenure_display", "9 Years 7 Months"))

    dep = max(min_dep, float(deposit_amount))
    maturity_val = round(dep * 2.0, 2)
    return {
        "scheme": "Kisan Vikas Patra (KVP)",
        "deposit_amount": dep,
        "tenure_months": t_months,
        "tenure_display": t_disp,
        "interest_rate": f"{r * 100:.1f}%",
        "interest_earned": dep,
        "maturity_value": maturity_val
    }

def calculate_mssc_maturity(deposit_amount):
    """
    Mahila Samman Savings Certificate (MSSC):
    - 7.5% p.a. compounded quarterly, 2 years tenure.
    - Max deposit Rs. 2 Lakhs (Min Rs. 1,000).
    """
    cfg = _SAVINGS_RATES.get("mssc", {})
    r = float(cfg.get("rate", 0.075))
    min_dep = float(cfg.get("min_deposit", 1000.0))
    max_dep = float(cfg.get("max_deposit", 200000.0))
    tenure = int(cfg.get("tenure_years", 2))

    dep = max(min_dep, min(max_dep, float(deposit_amount)))
    r_quarterly = r / 4.0
    maturity_val = round(dep * ((1 + r_quarterly) ** (tenure * 4)), 2)
    interest_earned = round(maturity_val - dep, 2)
    return {
        "scheme": "Mahila Samman Savings Certificate (MSSC)",
        "deposit_amount": dep,
        "tenure_years": tenure,
        "interest_rate": f"{r * 100:.1f}%",
        "compounding": "Quarterly",
        "interest_earned": interest_earned,
        "maturity_value": maturity_val
    }

def calculate_potd_maturity(deposit_amount, tenure_years=5):
    """
    Post Office Time Deposit (POTD):
    - 1 Year: 6.9% p.a.
    - 2 Years: 7.0% p.a.
    - 3 Years: 7.1% p.a.
    - 5 Years: 7.5% p.a. (Qualifies for Section 80C deduction)
    - Compounded quarterly, calculated annually.
    """
    dep = max(1000.0, float(deposit_amount))
    tenure = int(tenure_years) if int(tenure_years) in [1, 2, 3, 5] else 5
    cfg = _SAVINGS_RATES.get("potd", {})
    default_rates = {1: 0.069, 2: 0.070, 3: 0.071, 5: 0.075}
    configured_rates = {int(k): float(v) for k, v in cfg.get("rates", {}).items()} if "rates" in cfg else default_rates
    r = configured_rates.get(tenure, default_rates.get(tenure, 0.075))
    
    # Quarterly compounding
    quarters = tenure * 4
    maturity_val = round(dep * ((1 + (r / 4.0)) ** quarters), 2)
    interest_earned = round(maturity_val - dep, 2)
    annual_interest = round(interest_earned / tenure, 2)

    return {
        "scheme": f"Post Office Time Deposit (POTD {tenure}-Year)",
        "deposit_amount": dep,
        "tenure_years": tenure,
        "interest_rate": f"{r * 100:.1f}%",
        "compounding": "Quarterly",
        "tax_benefit": "Qualifies for Section 80C" if tenure == 5 else "No 80C rebate",
        "annual_interest": annual_interest,
        "interest_earned": interest_earned,
        "maturity_value": maturity_val
    }

def calculate_rd_maturity(monthly_deposit, tenure_years=5):
    """
    Post Office Recurring Deposit (PORD):
    - 6.7% p.a. compounded quarterly, 5 years (60 monthly deposits).
    - Minimum Rs. 100/month.
    """
    cfg = _SAVINGS_RATES.get("rd", {})
    r = float(cfg.get("rate", 0.067))
    min_dep = float(cfg.get("min_deposit", 100.0))
    total_months = int(cfg.get("total_installments", 60))

    m_dep = max(min_dep, float(monthly_deposit))
    total_invested = round(m_dep * total_months, 2)
    
    # Monthly compounding using quarterly rate
    i = r / 4.0
    maturity_val = 0.0
    for month in range(1, total_months + 1):
        rem_months = total_months - month + 1
        quarters = rem_months / 3.0
        maturity_val += m_dep * ((1 + i) ** quarters)
    
    maturity_val = round(maturity_val, 2)
    interest_earned = round(maturity_val - total_invested, 2)

    return {
        "scheme": "Post Office Recurring Deposit (PORD 5-Year)",
        "monthly_deposit": m_dep,
        "tenure_years": 5,
        "tenure_months": 60,
        "interest_rate": "6.7%",
        "total_invested": total_invested,
        "interest_earned": interest_earned,
        "maturity_value": maturity_val
    }

if __name__ == "__main__":
    print("PIN Distance (575004 -> 560001):", calculate_pincode_distance("575004", "560001"))
    print("MSSC 2 Lakh:", calculate_mssc_maturity(200000))
    print("5-Year TD 1 Lakh:", calculate_potd_maturity(100000, 5))
    print("5-Year RD 5000/mo:", calculate_rd_maturity(5000))

