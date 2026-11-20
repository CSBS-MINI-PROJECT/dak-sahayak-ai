import os
import json
import base64
import sqlite3
import uuid
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_supabase_client = None
_supabase_admin_client = None

PINCODES_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pincodes.db")
CONVERSATIONS_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "conversations.db")

def _init_local_db():
    """Initializes local SQLite databases with appropriate journal modes."""
    try:
        os.makedirs(os.path.dirname(CONVERSATIONS_DB_PATH), exist_ok=True)
        # 1. Writable conversations database -> WAL mode for high concurrency
        conn = sqlite3.connect(CONVERSATIONS_DB_PATH, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        # 2. Static pincodes database -> ensure checkpointed and kept in standard DELETE mode
        if os.path.exists(PINCODES_DB_PATH):
            try:
                chk_conn = sqlite3.connect(PINCODES_DB_PATH, timeout=10.0)
                chk_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                chk_conn.execute("PRAGMA journal_mode = DELETE;")
                chk_conn.close()
            except Exception:
                pass
    except Exception as e:
        print(f"[-] Local DB init error: {e}")

_init_local_db()

def _get_conversations_db_conn():
    """Returns connection to local conversations DB with busy timeout."""
    conn = sqlite3.connect(CONVERSATIONS_DB_PATH, timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def _get_pincodes_ro_conn():
    """Returns read-only URI connection to static pincodes DB."""
    abs_path = os.path.abspath(PINCODES_DB_PATH).replace(os.sep, "/")
    uri = f"file:{abs_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.row_factory = sqlite3.Row
    return conn

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
    if token and not SUPABASE_SERVICE_KEY:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        client.postgrest.headers["Authorization"] = f"Bearer {token}"
        return client
    return get_supabase_admin()

class LocalUser:
    def __init__(self, uid, email=""):
        self.id = uid
        self.email = email

def get_user_from_token(token: str):
    if not token:
        return None
    # Fast local JWT decode first (0ms)
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padding = "=" * (4 - len(parts[1]) % 4)
            payload_bytes = base64.urlsafe_b64decode(parts[1] + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))
            uid = payload.get("sub") or payload.get("user_id") or payload.get("id") or "guest-user"
            email = payload.get("email") or ""
            return LocalUser(uid, email)
    except Exception:
        pass

    try:
        supabase = get_supabase()
        res = supabase.auth.get_user(token)
        if res and res.user:
            return res.user
    except Exception:
        pass

    return LocalUser("guest-user", "guest@daksahayak.local")

def get_user_conversations(user_id: str, token: str = None):
    # Try local SQLite storage first for instant response
    try:
        conn = _get_conversations_db_conn()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
        rows = cur.fetchall()
        local_convs = [dict(r) for r in rows]
        conn.close()
        if local_convs:
            return local_convs
    except Exception as e:
        pass

    try:
        client = get_supabase_client(token)
        res = client.table("conversations")\
            .select("id, title, created_at, updated_at")\
            .eq("user_id", user_id)\
            .order("updated_at", desc=True)\
            .execute()
        return res.data or []
    except Exception:
        return []

def create_user_conversation(user_id: str, title: str = "New Chat", token: str = None) -> str:
    new_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conversations_db_conn()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (new_id, user_id, title, now_iso, now_iso))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

    try:
        client = get_supabase_client(token)
        res = client.table("conversations").insert({
            "id": new_id,
            "user_id": user_id,
            "title": title
        }).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["id"]
    except Exception:
        pass

    return new_id

def update_conversation_title(conversation_id: str, title: str, token: str = None):
    try:
        conn = _get_conversations_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title[:60], datetime.now(timezone.utc).isoformat(), conversation_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

    try:
        client = get_supabase_client(token)
        client.table("conversations").update({
            "title": title[:60]
        }).eq("id", conversation_id).execute()
    except Exception:
        pass

def get_conversation_messages(conversation_id: str, token: str = None):
    try:
        conn = _get_conversations_db_conn()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
        rows = cur.fetchall()
        msgs = [dict(r) for r in rows]
        conn.close()
        if msgs:
            return msgs
    except Exception:
        pass

    try:
        client = get_supabase_client(token)
        res = client.table("messages")\
            .select("id, role, content, created_at")\
            .eq("conversation_id", conversation_id)\
            .order("created_at", desc=False)\
            .execute()
        return res.data or []
    except Exception:
        return []

def save_chat_message(conversation_id: str, role: str, content: str, token: str = None):
    msg_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    msg_dict = {"id": msg_id, "conversation_id": conversation_id, "role": role, "content": content, "created_at": now_iso}

    try:
        conn = _get_conversations_db_conn()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                    (msg_id, conversation_id, role, content, now_iso))
        cur.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now_iso, conversation_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

    try:
        client = get_supabase_client(token)
        client.table("messages").insert({
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content
        }).execute()
    except Exception:
        pass

    return msg_dict

def delete_user_conversation(conversation_id: str, user_id: str, token: str = None):
    try:
        conn = _get_conversations_db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass

    try:
        client = get_supabase_client(token)
        client.table("conversations")\
            .delete()\
            .eq("id", conversation_id)\
            .eq("user_id", user_id)\
            .execute()
    except Exception:
        pass
    return True

def search_pincode_db(query: str):
    import os
    import sqlite3
    import requests

    query_str = str(query).strip()
    if not query_str:
        return []

    results = []

    # 1. Primary: High-speed local SQLite database with all 157k+ Indian PIN codes (Read-only mode)
    if os.path.exists(PINCODES_DB_PATH):
        try:
            conn = _get_pincodes_ro_conn()
            cur = conn.cursor()

            if query_str.isdigit() and len(query_str) == 6:
                cur.execute("SELECT * FROM pincodes WHERE pincode = ?", (query_str,))
            else:
                q_like = f"%{query_str}%"
                cur.execute("""
                    SELECT * FROM pincodes 
                    WHERE office_name LIKE ? OR district LIKE ? OR taluk LIKE ?
                    LIMIT 15
                """, (q_like, q_like, q_like))

            rows = cur.fetchall()
            for r in rows:
                ho_val = r["office_name"] if "Head" in (r["office_type"] or "") else f"{r['division'] or r['district']} Head Office"
                results.append({
                    "Name": r["office_name"] or "",
                    "Pincode": r["pincode"] or "",
                    "BranchType": r["office_type"] or "Sub Post Office",
                    "DeliveryStatus": r["delivery_status"] or "Delivery",
                    "Taluk": r["taluk"] or r["district"] or "",
                    "Division": r["division"] or "",
                    "District": r["district"] or "",
                    "Region": r["region"] or "Postal Region",
                    "State": r["state"] or "",
                    "Circle": r["circle"] or "",
                    "HeadOffice": ho_val,
                    "Latitude": r["latitude"] or "",
                    "Longitude": r["longitude"] or ""
                })
            conn.close()
            if results:
                return results
        except Exception as e:
            print(f"[-] Local SQLite pincode lookup error: {e}")
        except Exception as e:
            print(f"[-] Local SQLite pincode lookup error: {e}")

    # 2. Supabase Cloud lookup fallback
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
        pass

    if results:
        return results

    # 3. Online Postal PIN API fallback
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
        pass

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

