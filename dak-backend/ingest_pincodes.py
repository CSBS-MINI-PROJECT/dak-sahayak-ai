import os
import csv
import time
from dotenv import load_dotenv
from supabase_client import get_supabase_admin

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pincodes.csv")

def ingest_pincodes():
    print("[*] Ingesting PIN codes into Supabase 'pincodes' table...")
    admin = get_supabase_admin()

    if not os.path.exists(CSV_PATH):
        print(f"[-] CSV file not found: {CSV_PATH}")
        return

    # Check if pincodes table already populated
    try:
        count_res = admin.table("pincodes").select("id", count="exact").limit(1).execute()
        if count_res.count and count_res.count > 0:
            print(f"[*] 'pincodes' table already contains {count_res.count} records. Skipping CSV re-ingestion.")
            return
    except Exception as e:
        print(f"[*] Note checking pincodes table: {e}")

    rows_to_insert = []
    with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pincode = (row.get("pincode") or row.get("Pincode") or row.get("PIN") or "").strip()
            if pincode and len(pincode) == 6:
                rows_to_insert.append({
                    "pincode": pincode,
                    "office_name": row.get("OfficeName") or row.get("office_name") or row.get("Name") or "",
                    "office_type": row.get("OfficeType") or row.get("office_type") or "Sub Post Office",
                    "delivery_status": row.get("Delivery") or row.get("delivery_status") or "Delivery",
                    "taluk": row.get("Taluk") or row.get("taluk") or row.get("District") or row.get("district") or "",
                    "division": row.get("DivisionName") or row.get("division") or "",
                    "district": row.get("District") or row.get("district") or "",
                    "region": row.get("RegionName") or row.get("region") or "Postal Region",
                    "state": row.get("StateName") or row.get("state") or "",
                    "circle": row.get("CircleName") or row.get("circle") or "India Post"
                })

    print(f"[*] Total valid PIN rows parsed from CSV: {len(rows_to_insert)}")

    # Bulk insert in batches of 200
    batch_size = 200
    for i in range(0, len(rows_to_insert), batch_size):
        batch = rows_to_insert[i:i + batch_size]
        try:
            admin.table("pincodes").insert(batch).execute()
            print(f"  [+] Inserted batch {i // batch_size + 1}/{(len(rows_to_insert) + batch_size - 1) // batch_size}")
        except Exception as e:
            print(f"  [-] Error inserting batch: {e}")
        time.sleep(0.05)

    print("[+] PIN code ingestion complete!")

if __name__ == "__main__":
    ingest_pincodes()
