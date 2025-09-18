import pdfplumber
import pandas as pd
import json

# 📌 Eingabe-/Ausgabe-Dateien
in_file = "0001-2179_V60 - AlarmAndWarningListMk567-11.pdf"
out_file = "alarms_extracted.xlsx"

# Erwartete Spalten
columns = [
    "No", "SupervisionID", "Name",
    "Log text", "Subsystem name", "Type", "Timeout", "Acknowledgement",
    "Shutdown type", "Allowed attempts", "Time window",
    "Max time disconnect", "Max time eliminate",
    "Stabilize period", "Category",
    "Criteria"
]

# Label-Mapping für robuste Erkennung
label_map = {
    "supervisionid": "SupervisionID",
    "name": "Name",
    "log text": "Log text",
    "subsystem name": "Subsystem name",
    "type": "Type",
    "timeout": "Timeout",
    "acknowledgement": "Acknowledgement",
    "shutdown type": "Shutdown type",
    "allowed attempts": "Allowed attempts",
    "time window": "Time window",
    "max time disconnect": "Max time disconnect",
    "max time eliminate": "Max time eliminate",
    "stabilize period": "Stabilize period",
    "category": "Category",
    "criteria": "Criteria"
}

def safe_strip(val):
    return val.strip() if val else ""

def normalize(text):
    return " ".join(text.lower().split()) if text else ""

def debug_pdf_structure():
    """Debug function to analyze PDF structure"""
    try:
        with pdfplumber.open(in_file) as pdf:
            print(f"📄 PDF Info: {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages[:3], start=1):  # Only first 3 pages for debugging
                print(f"\n🔍 PAGE {page_num}:")
                print(f"   Page size: {page.width} x {page.height}")
                
                # Try different extraction methods
                print("\n--- Method 1: extract_table() ---")
                table = page.extract_table()
                if table:
                    print(f"   Found table with {len(table)} rows")
                    for i, row in enumerate(table[:5]):  # First 5 rows
                        print(f"   Row {i}: {row}")
                else:
                    print("   No table found")
                
                print("\n--- Method 2: extract_tables() ---")
                tables = page.extract_tables()
                if tables:
                    print(f"   Found {len(tables)} tables")
                    for t_idx, table in enumerate(tables):
                        print(f"   Table {t_idx}: {len(table)} rows")
                        for i, row in enumerate(table[:3]):  # First 3 rows of each table
                            print(f"     Row {i}: {row}")
                else:
                    print("   No tables found")
                
                print("\n--- Method 3: extract_text() ---")
                text = page.extract_text()
                if text:
                    lines = text.split('\n')[:10]  # First 10 lines
                    print(f"   Text preview ({len(lines)} lines):")
                    for i, line in enumerate(lines):
                        print(f"     Line {i}: '{line.strip()}'")
                else:
                    print("   No text found")
                
                print("\n" + "="*50)
                
    except Exception as e:
        print(f"❌ Error analyzing PDF: {e}")

def parse_pdf_improved():
    """Improved parsing function with debugging"""
    records = []
    current_record = {}
    collecting_criteria = False
    
    try:
        with pdfplumber.open(in_file) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                print(f"\n🔍 Processing page {page_num}")
                
                # Try different table extraction settings
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3
                }
                
                table = page.extract_table(table_settings)
                if not table:
                    # Try without settings
                    table = page.extract_table()
                
                if not table:
                    print(f"   No table found on page {page_num}")
                    continue
                
                print(f"   Found table with {len(table)} rows")
                
                for row_idx, row in enumerate(table):
                    if not row or not any(cell for cell in row if cell):
                        continue
                    
                    print(f"   Row {row_idx}: {row}")
                    
                    first_cell = safe_strip(row[0]) if row[0] else ""
                    norm_label = normalize(first_cell)
                    
                    # --- Fall 1: Neuer Datensatz (No:)
                    if first_cell.startswith("No:"):
                        if current_record:
                            records.append(current_record)
                            print(f"     ✅ Saved record: {current_record.get('No', 'Unknown')}")
                        
                        current_record = {col: "" for col in columns}
                        collecting_criteria = False
                        
                        # No extrahieren
                        no_value = first_cell.split("No:")[-1].strip()
                        current_record["No"] = no_value
                        print(f"     🆕 New record No: {no_value}")
                        
                        # Kopfzeile: Paare durchgehen (1/2, 3/4, ...)
                        for i in range(1, len(row), 2):
                            raw_label = safe_strip(row[i]) if i < len(row) else ""
                            value = safe_strip(row[i+1]) if i+1 < len(row) else ""
                            norm_label_pair = normalize(raw_label)
                            if norm_label_pair in label_map:
                                current_record[label_map[norm_label_pair]] = value
                                print(f"       📝 {raw_label} -> {value}")
                    
                    # --- Fall 2: Criteria (Start)
                    elif norm_label == "criteria":
                        collecting_criteria = True
                        current_record["Criteria"] = safe_strip(row[1]) if len(row) > 1 else ""
                        print(f"     📋 Criteria start: {current_record['Criteria']}")
                    
                    # --- Fall 3: Normale Key/Value Labels (0/1-Logik)
                    elif norm_label in label_map:
                        label = label_map[norm_label]
                        value = safe_strip(row[1]) if len(row) > 1 else ""
                        current_record[label] = value
                        collecting_criteria = False
                        print(f"     🔑 {first_cell} -> {value}")
                    
                    # --- Fall 4: Criteria-Mehrzeilen
                    elif collecting_criteria:
                        extra_text = " ".join(safe_strip(c) for c in row if c)
                        current_record["Criteria"] += " " + extra_text
                        print(f"     📋+ Criteria continued: {extra_text}")
                    
                    else:
                        print(f"     ❓ Unrecognized row: {first_cell}")
        
        # Letzten Record speichern
        if current_record:
            records.append(current_record)
            print(f"     ✅ Saved final record: {current_record.get('No', 'Unknown')}")
        
        return records
        
    except Exception as e:
        print(f"❌ Error parsing PDF: {e}")
        return []

if __name__ == "__main__":
    print("🚀 Starting PDF analysis...")
    
    # First, debug the PDF structure
    debug_pdf_structure()
    
    print("\n" + "="*60)
    print("🔄 Now trying to parse with improved logic...")
    
    # Then try parsing
    records = parse_pdf_improved()
    
    if records:
        print(f"\n✅ Successfully extracted {len(records)} records")
        
        # Show summary of what was found
        for i, record in enumerate(records):
            print(f"\nRecord {i+1}:")
            for key, value in record.items():
                if value:  # Only show non-empty values
                    print(f"  {key}: {value}")
        
        # Save to Excel
        df = pd.DataFrame(records, columns=columns)
        df.to_excel(out_file, index=False)
        print(f"\n💾 Saved to {out_file}")
        
        # Show which columns are empty
        empty_cols = [col for col in columns if df[col].isna().all() or (df[col] == "").all()]
        if empty_cols:
            print(f"\n⚠️  Empty columns: {empty_cols}")
    else:
        print("\n❌ No records found!")