import pdfplumber
import pandas as pd
import re

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

# Erweiterte Label-Mappings für robuste Erkennung
label_map = {
    # Exakte Matches
    "supervisionid": "SupervisionID",
    "supervision id": "SupervisionID",
    "name": "Name",
    "log text": "Log text",
    "logtext": "Log text",
    "subsystem name": "Subsystem name",
    "subsystemname": "Subsystem name",
    "subsystem": "Subsystem name",
    "type": "Type",
    "timeout": "Timeout",
    "time out": "Timeout",
    "acknowledgement": "Acknowledgement",
    "acknowledge": "Acknowledgement",
    "ack": "Acknowledgement",
    "shutdown type": "Shutdown type",
    "shutdowntype": "Shutdown type",
    "shutdown": "Shutdown type",
    "allowed attempts": "Allowed attempts",
    "allowedattempts": "Allowed attempts",
    "attempts": "Allowed attempts",
    "time window": "Time window",
    "timewindow": "Time window",
    "window": "Time window",
    "max time disconnect": "Max time disconnect",
    "maxtimeddisconnect": "Max time disconnect",
    "max disconnect": "Max time disconnect",
    "disconnect": "Max time disconnect",
    "max time eliminate": "Max time eliminate",
    "maxtimeeliminate": "Max time eliminate",
    "max eliminate": "Max time eliminate",
    "eliminate": "Max time eliminate",
    "stabilize period": "Stabilize period",
    "stabilizeperiod": "Stabilize period",
    "stabilize": "Stabilize period",
    "category": "Category",
    "cat": "Category",
    "criteria": "Criteria",
    "criterion": "Criteria"
}

def safe_strip(val):
    """Safely strip whitespace from a value"""
    return val.strip() if val and isinstance(val, str) else ""

def normalize(text):
    """Normalize text for comparison"""
    if not text:
        return ""
    # Remove extra whitespace, convert to lowercase
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    # Remove common punctuation that might interfere
    normalized = re.sub(r'[:\-_]+', '', normalized)
    return normalized

def find_label_match(text):
    """Find the best matching label for given text"""
    if not text:
        return None
    
    normalized = normalize(text)
    
    # Direct match
    if normalized in label_map:
        return label_map[normalized]
    
    # Partial matches (for cases where label might have extra text)
    for key, value in label_map.items():
        if key in normalized or normalized in key:
            return value
    
    return None

def extract_number_from_no_field(text):
    """Extract number from 'No:' field"""
    if not text:
        return ""
    
    # Look for patterns like "No: 123" or "No:123" 
    match = re.search(r'no\s*:?\s*(\d+)', text.lower())
    if match:
        return match.group(1)
    
    # Fallback: just remove 'No:' and clean up
    return re.sub(r'no\s*:?\s*', '', text, flags=re.IGNORECASE).strip()

def parse_pdf_advanced():
    """Advanced PDF parsing with multiple strategies"""
    records = []
    current_record = {}
    collecting_criteria = False
    
    try:
        with pdfplumber.open(in_file) as pdf:
            print(f"📄 Processing PDF with {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, start=1):
                print(f"\n🔍 Page {page_num}")
                
                # Try multiple table extraction strategies
                strategies = [
                    # Strategy 1: Default settings
                    {},
                    # Strategy 2: Line-based detection
                    {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 3,
                        "join_tolerance": 3
                    },
                    # Strategy 3: Text-based detection
                    {
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "snap_tolerance": 5,
                        "join_tolerance": 5
                    },
                    # Strategy 4: Explicit table detection
                    {
                        "vertical_strategy": "explicit",
                        "horizontal_strategy": "explicit",
                        "explicit_vertical_lines": [],
                        "explicit_horizontal_lines": []
                    }
                ]
                
                table = None
                for i, strategy in enumerate(strategies):
                    try:
                        if i == 3:  # For explicit strategy, try to find lines first
                            # Get all line objects
                            lines = page.lines
                            if lines:
                                strategy["explicit_vertical_lines"] = [line for line in lines if abs(line["x0"] - line["x1"]) < 5]
                                strategy["explicit_horizontal_lines"] = [line for line in lines if abs(line["y0"] - line["y1"]) < 5]
                        
                        table = page.extract_table(strategy)
                        if table and len(table) > 0:
                            print(f"   ✅ Strategy {i+1} successful: {len(table)} rows")
                            break
                    except Exception as e:
                        print(f"   ❌ Strategy {i+1} failed: {e}")
                        continue
                
                if not table:
                    print(f"   ⚠️  No table found on page {page_num}, trying text extraction")
                    # Fallback: parse as text
                    text = page.extract_text()
                    if text:
                        # Try to parse structured text
                        table = parse_text_as_table(text)
                
                if not table:
                    continue
                
                # Process the extracted table
                for row_idx, row in enumerate(table):
                    if not row or not any(cell for cell in row if cell and str(cell).strip()):
                        continue
                    
                    # Clean up row
                    clean_row = [safe_strip(str(cell)) if cell else "" for cell in row]
                    
                    if not clean_row[0]:  # Skip empty first cells
                        continue
                    
                    first_cell = clean_row[0]
                    print(f"   Processing row: {clean_row}")
                    
                    # Check if this starts a new record
                    if re.match(r'no\s*:?\s*\d+', first_cell.lower()) or first_cell.lower().startswith('no:'):
                        # Save previous record
                        if current_record and any(current_record.values()):
                            records.append(current_record)
                            print(f"     ✅ Saved record No: {current_record.get('No', 'Unknown')}")
                        
                        # Start new record
                        current_record = {col: "" for col in columns}
                        collecting_criteria = False
                        
                        # Extract number
                        no_value = extract_number_from_no_field(first_cell)
                        current_record["No"] = no_value
                        print(f"     🆕 New record No: {no_value}")
                        
                        # Process remaining cells in pairs (label, value)
                        for i in range(1, len(clean_row) - 1, 2):
                            if i + 1 < len(clean_row):
                                label_text = clean_row[i]
                                value_text = clean_row[i + 1]
                                
                                matched_label = find_label_match(label_text)
                                if matched_label:
                                    current_record[matched_label] = value_text
                                    print(f"       📝 {label_text} -> {matched_label}: {value_text}")
                    
                    # Check for criteria start
                    elif normalize(first_cell) == "criteria":
                        collecting_criteria = True
                        criteria_value = clean_row[1] if len(clean_row) > 1 else ""
                        current_record["Criteria"] = criteria_value
                        print(f"     📋 Criteria: {criteria_value}")
                    
                    # Check for other labels
                    else:
                        matched_label = find_label_match(first_cell)
                        if matched_label:
                            value = clean_row[1] if len(clean_row) > 1 else ""
                            current_record[matched_label] = value
                            collecting_criteria = False
                            print(f"     🔑 {first_cell} -> {matched_label}: {value}")
                        
                        # Continue criteria if we're collecting
                        elif collecting_criteria:
                            extra_text = " ".join(cell for cell in clean_row if cell)
                            if current_record["Criteria"]:
                                current_record["Criteria"] += " " + extra_text
                            else:
                                current_record["Criteria"] = extra_text
                            print(f"     📋+ Criteria continued: {extra_text}")
            
            # Save final record
            if current_record and any(current_record.values()):
                records.append(current_record)
                print(f"     ✅ Saved final record No: {current_record.get('No', 'Unknown')}")
    
    except Exception as e:
        print(f"❌ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
    
    return records

def parse_text_as_table(text):
    """Parse structured text as a table when table extraction fails"""
    lines = text.split('\n')
    table = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to split by multiple spaces or tabs
        cells = re.split(r'\s{2,}|\t+', line)
        if len(cells) > 1:
            table.append(cells)
    
    return table if table else None

if __name__ == "__main__":
    print("🚀 Starting advanced PDF parsing...")
    
    records = parse_pdf_advanced()
    
    if records:
        print(f"\n✅ Successfully extracted {len(records)} records")
        
        # Create DataFrame
        df = pd.DataFrame(records, columns=columns)
        
        # Show summary
        print(f"\n📊 Summary:")
        print(f"   Total records: {len(df)}")
        
        # Check which columns have data
        filled_cols = []
        empty_cols = []
        
        for col in columns:
            non_empty = df[col].notna() & (df[col] != "")
            if non_empty.any():
                filled_cols.append(f"{col} ({non_empty.sum()}/{len(df)})")
            else:
                empty_cols.append(col)
        
        if filled_cols:
            print(f"   Columns with data: {', '.join(filled_cols)}")
        if empty_cols:
            print(f"   Empty columns: {', '.join(empty_cols)}")
        
        # Save to Excel
        df.to_excel(out_file, index=False)
        print(f"\n💾 Saved to {out_file}")
        
        # Show first few records for verification
        print(f"\n🔍 First few records:")
        for i, (_, record) in enumerate(df.head(3).iterrows()):
            print(f"\nRecord {i+1}:")
            for col, val in record.items():
                if pd.notna(val) and str(val).strip():
                    print(f"  {col}: {val}")
    else:
        print("\n❌ No records found!")
        print("Please check:")
        print("1. Is the PDF file in the correct location?")
        print("2. Does the PDF contain the expected table structure?")
        print("3. Try running the debug version first: python pdf_parser_debug.py")