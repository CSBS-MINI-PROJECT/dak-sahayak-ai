import os
import sys
import csv
import sqlite3
import requests

def fetch_and_index_pincodes():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(backend_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    csv_dest = os.path.join(data_dir, "pincodes.csv")
    db_dest = os.path.join(data_dir, "pincodes.db")
    
    url = "https://raw.githubusercontent.com/dropdevrahul/pincodes-india/master/pincode.csv"
    print(f"[*] Downloading complete All-India Pincode dataset from:\n    {url}", flush=True)
    
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total_downloaded = 0
    with open(csv_dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 512):
            if chunk:
                f.write(chunk)
                total_downloaded += len(chunk)
                sys.stdout.write(f"\r[+] Downloaded: {total_downloaded / (1024 * 1024):.2f} MB")
                sys.stdout.flush()
    print("\n[+] Download complete!", flush=True)

    print("[*] Creating high-performance SQLite database...", flush=True)
    if os.path.exists(db_dest):
        try:
            os.remove(db_dest)
        except Exception:
            pass

    conn = sqlite3.connect(db_dest)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pincodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pincode TEXT NOT NULL,
            office_name TEXT,
            office_type TEXT,
            delivery_status TEXT,
            taluk TEXT,
            division TEXT,
            district TEXT,
            region TEXT,
            state TEXT,
            circle TEXT,
            latitude TEXT,
            longitude TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pincode ON pincodes(pincode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_office_name ON pincodes(office_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_district ON pincodes(district)")

    rows_to_insert = []
    with open(csv_dest, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pincode = (row.get("Pincode") or row.get("pincode") or "").strip()
            if pincode and len(pincode) == 6:
                rows_to_insert.append((
                    pincode,
                    row.get("OfficeName") or row.get("office_name") or "",
                    row.get("OfficeType") or row.get("office_type") or "Sub Post Office",
                    row.get("Delivery") or row.get("delivery_status") or "Delivery",
                    row.get("Taluk") or row.get("District") or "",
                    row.get("DivisionName") or row.get("division") or "",
                    row.get("District") or row.get("district") or "",
                    row.get("RegionName") or row.get("region") or "",
                    row.get("StateName") or row.get("state") or "",
                    row.get("CircleName") or row.get("circle") or "India Post",
                    row.get("Latitude") or "",
                    row.get("Longitude") or ""
                ))

    print(f"[*] Total postal records parsed: {len(rows_to_insert):,}", flush=True)
    print("[*] Inserting into SQLite...", flush=True)

    cur.executemany("""
        INSERT INTO pincodes (
            pincode, office_name, office_type, delivery_status, taluk, division,
            district, region, state, circle, latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM pincodes")
    count = cur.fetchone()[0]
    conn.close()

    print(f"[+] SUCCESS! {count:,} postal PIN code records successfully indexed in {db_dest}", flush=True)

if __name__ == "__main__":
    fetch_and_index_pincodes()
