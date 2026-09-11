import os
from supabase import create_client
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_supabase_client = None
_supabase_admin_client = None

def get_supabase():
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

def get_supabase_admin():
    global _supabase_admin_client
    if _supabase_admin_client is None:
        key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
        _supabase_admin_client = create_client(SUPABASE_URL, key)
    return _supabase_admin_client

def get_supabase_client(token: str = None):
    """
    Returns a Supabase client. If a token is provided and we do not have a service
    role key (which bypasses RLS), authenticate the client as the user so that
    Row Level Security (RLS) policies pass.
    """
    if token and not SUPABASE_SERVICE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        client.postgrest.headers["Authorization"] = f"Bearer {token}"
        return client
    return get_supabase_admin()

def get_user_from_token(token: str):
    try:
        supabase = get_supabase()
        res = supabase.auth.get_user(token)
        if res and res.user:
            return res.user
        return None
    except Exception as e:
        print(f"[-] Token verification error: {e}")
        return None

def get_user_conversations(user_id: str, token: str = None):
    try:
        client = get_supabase_client(token)
        res = client.table("conversations")\
            .select("id, title, created_at, updated_at")\
            .eq("user_id", user_id)\
            .order("updated_at", desc=True)\
            .execute()
        return res.data or []
    except Exception as e:
        print(f"[-] Error fetching conversations: {e}")
        return []

def create_user_conversation(user_id: str, title: str = "New Chat", token: str = None) -> str:
    try:
        client = get_supabase_client(token)
        res = client.table("conversations").insert({
            "user_id": user_id,
            "title": title
        }).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["id"]
        return None
    except Exception as e:
        print(f"[-] Error creating conversation: {e}")
        return None

def update_conversation_title(conversation_id: str, title: str, token: str = None):
    try:
        client = get_supabase_client(token)
        client.table("conversations").update({
            "title": title[:60]
        }).eq("id", conversation_id).execute()
    except Exception as e:
        print(f"[-] Error updating conversation title: {e}")

def get_conversation_messages(conversation_id: str, token: str = None):
    try:
        client = get_supabase_client(token)
        res = client.table("messages")\
            .select("id, role, content, created_at")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=False)\
            .execute()
        return res.data or []
    except Exception as e:
        print(f"[-] Error fetching messages: {e}")
        return []

def save_chat_message(conversation_id: str, role: str, content: str, token: str = None):
    try:
        client = get_supabase_client(token)
        res = client.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        }).execute()
        
        from datetime import datetime, timezone
        client.table("conversations").update({
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", conversation_id).execute()
        
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[-] Error saving message: {e}")
        return None

def delete_user_conversation(conversation_id: str, user_id: str, token: str = None):
    try:
        client = get_supabase_client(token)
        client.table("conversations")\
            .delete()\
            .eq("id", conversation_id)\
            .eq("user_id", user_id)\
            .execute()
        return True
    except Exception as e:
        print(f"[-] Error deleting conversation: {e}")
        return False

def search_pincode_db(query: str):
    import requests
    query_str = str(query).strip()
    if not query_str:
        return []

    results = []
    try:
        admin = get_supabase_admin()
        if query_str.isdigit() and len(query_str) == 6:
            res = admin.table("pincodes").select("*").eq("pincode", query_str).execute()
        else:
            q_like = f"%{query_str}%"
            res = admin.table("pincodes").select("*")\
                .ilike("office_name", q_like)\
                .limit(10)\
                .execute()

        rows = res.data or []
        for r in rows:
            ho_val = r["office_name"] if "Head" in (r.get("office_type") or "") else f"{r.get('division') or r.get('district')} Head Office"
            results.append({
                "Name": r.get("office_name", ""),
                "Pincode": r.get("pincode", ""),
                "BranchType": r.get("office_type") or "Sub Post Office",
                "DeliveryStatus": r.get("delivery_status") or "Delivery",
                "Taluk": r.get("taluk") or r.get("district") or "",
                "Division": r.get("division") or "",
                "District": r.get("district") or "",
                "Region": r.get("region") or "Postal Region",
                "State": r.get("state") or "",
                "Circle": r.get("circle") or "",
                "HeadOffice": ho_val
            })
    except Exception as e:
        print(f"[-] Supabase pincode lookup error: {e}")

    if results:
        return results

    try:
        if query_str.isdigit() and len(query_str) == 6:
            url = f"https://api.postalpincode.in/pincode/{query_str}"
        else:
            url = f"https://api.postalpincode.in/postoffice/{query_str}"

        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json and isinstance(res_json, list) and res_json[0].get("Status") == "Success":
                post_offices = res_json[0].get("PostOffice", [])
                formatted = []
                for po in post_offices:
                    ho_val = po.get("HeadOffice") or po.get("HO") or f"{po.get('Division', po.get('District', ''))} Head Office"
                    formatted.append({
                        "Name": po.get("Name", ""),
                        "Pincode": po.get("Pincode", query_str),
                        "BranchType": po.get("BranchType", "Sub Post Office"),
                        "DeliveryStatus": po.get("DeliveryStatus", "Delivery"),
                        "Taluk": po.get("Taluk", po.get("Block", po.get("District", ""))),
                        "Division": po.get("Division", ""),
                        "District": po.get("District", ""),
                        "Region": po.get("Region", "Postal Region"),
                        "State": po.get("State", ""),
                        "Circle": po.get("Circle", ""),
                        "HeadOffice": ho_val
                    })
                if formatted:
                    return formatted
    except Exception as ex:
        print(f"[-] Online PIN API fallback error: {ex}")

    if query_str.isdigit() and len(query_str) == 6:
        return [{
            "Name": f"Post Office (PIN {query_str})",
            "Pincode": query_str,
            "BranchType": "Sub Post Office",
            "DeliveryStatus": "Delivery",
            "Taluk": "Postal Sub-District",
            "Division": "Postal Division",
            "District": "India Postal Circle",
            "Region": "Postal Region",
            "State": "India",
            "Circle": "India Post",
            "HeadOffice": "General Post Office"
        }]

    return []
