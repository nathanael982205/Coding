import pdfplumber
import pandas as pd
import re

# 📌 Eingabe-/Ausgabe-Dateien
in_file = "test_alarm_list.pdf"  # Verwende Test-PDF
out_file = "alarms_extracted.xlsx"
debug_file = "debug_output.txt"

# Erwartete Spalten
columns = [
    "No", "SupervisionID", "Name",
    "Log text", "Subsystem name", "Type", "Timeout", "Acknowledgement",
    "Shutdown type", "Allowed attempts", "Time window",
    "Max time disconnect", "Max time eliminate",
    "Stabilize period", "Category",
    "Criteria"
]

# Label-Mapping für robuste Erkennung (erweitert mit Varianten)
label_map = {
    "supervisionid": "SupervisionID",
    "supervision id": "SupervisionID",
    "supervision-id": "SupervisionID",
    "name": "Name",
    "log text": "Log text",
    "logtext": "Log text",
    "subsystem name": "Subsystem name",
    "subsystem": "Subsystem name",
    "type": "Type",
    "timeout": "Timeout",
    "time out": "Timeout",
    "acknowledgement": "Acknowledgement",
    "acknowledge": "Acknowledgement",
    "ack": "Acknowledgement",
    "shutdown type": "Shutdown type",
    "shutdowntype": "Shutdown type",
    "allowed attempts": "Allowed attempts",
    "attempts": "Allowed attempts",
    "time window": "Time window",
    "timewindow": "Time window",
    "max time disconnect": "Max time disconnect",
    "max disconnect": "Max time disconnect",
    "disconnect": "Max time disconnect",
    "max time eliminate": "Max time eliminate",
    "max eliminate": "Max time eliminate",
    "eliminate": "Max time eliminate",
    "stabilize period": "Stabilize period",
    "stabilize": "Stabilize period",
    "category": "Category",
    "criteria": "Criteria"
}

def safe_strip(val):
    """Sicheres Strip mit None-Check"""
    return val.strip() if val else ""

def normalize(text):
    """Normalisiert Text für Vergleiche"""
    if not text:
        return ""
    # Entferne mehrfache Leerzeichen und konvertiere zu Kleinbuchstaben
    text = " ".join(text.lower().split())
    # Entferne Sonderzeichen für besseren Vergleich
    text = re.sub(r'[:\-_]+', ' ', text)
    return text.strip()

def extract_value_from_cells(cells, start_idx=1):
    """Extrahiert Wert aus mehreren Zellen"""
    values = []
    for i in range(start_idx, len(cells)):
        val = safe_strip(cells[i])
        if val:
            values.append(val)
    return " ".join(values)

def parse_header_row(row):
    """Parst eine Kopfzeile mit mehreren Label-Value Paaren"""
    parsed = {}
    i = 0
    while i < len(row):
        cell = safe_strip(row[i])
        if not cell:
            i += 1
            continue
            
        # Normalisiere für Vergleich
        norm_cell = normalize(cell)
        
        # Prüfe ob es ein bekanntes Label ist
        matched_label = None
        for key, value in label_map.items():
            if key in norm_cell:
                matched_label = value
                break
        
        if matched_label:
            # Finde den Wert - könnte in der nächsten Zelle oder nach einem ":" sein
            if ":" in cell:
                # Wert könnte nach dem : in derselben Zelle sein
                parts = cell.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    parsed[matched_label] = parts[1].strip()
                elif i + 1 < len(row):
                    parsed[matched_label] = safe_strip(row[i + 1])
                    i += 1
            elif i + 1 < len(row):
                parsed[matched_label] = safe_strip(row[i + 1])
                i += 1
        
        i += 1
    
    return parsed

# Debug-Ausgabe
debug_lines = []

def debug_print(msg):
    """Print und speichere Debug-Nachrichten"""
    print(msg)
    debug_lines.append(msg)

debug_print("=== PDF Extractor - Verbesserte Version ===\n")

records = []
current_record = {}
collecting_criteria = False
record_count = 0

try:
    with pdfplumber.open(in_file) as pdf:
        debug_print(f"📄 PDF geöffnet: {len(pdf.pages)} Seiten gefunden\n")
        
        for page_num, page in enumerate(pdf.pages, start=1):
            debug_print(f"\n{'='*60}")
            debug_print(f"📖 Seite {page_num}")
            debug_print(f"{'='*60}")
            
            table = page.extract_table()
            if not table:
                debug_print("❌ Keine Tabelle auf dieser Seite gefunden")
                continue
            
            debug_print(f"✅ Tabelle gefunden mit {len(table)} Zeilen")
            
            for row_idx, row in enumerate(table):
                if not row or not any(row):  # Überspringe komplett leere Zeilen
                    continue
                
                first_cell = safe_strip(row[0])
                
                # Debug: Zeige interessante Zeilen
                if row_idx < 5 or first_cell.startswith("No:") or any(normalize(safe_strip(cell)) in label_map for cell in row if cell):
                    debug_print(f"\nZeile {row_idx}: {[safe_strip(c) for c in row if c]}")
                
                # --- Fall 1: Neuer Datensatz (No:)
                if first_cell.startswith("No:"):
                    # Speichere vorherigen Datensatz
                    if current_record and any(current_record.values()):
                        records.append(current_record)
                        record_count += 1
                        debug_print(f"✅ Datensatz {record_count} gespeichert")
                    
                    # Initialisiere neuen Datensatz
                    current_record = {col: "" for col in columns}
                    collecting_criteria = False
                    
                    # No extrahieren
                    no_match = re.search(r'No:\s*(\S+)', first_cell)
                    if no_match:
                        current_record["No"] = no_match.group(1)
                    
                    debug_print(f"\n🆕 Neuer Datensatz: No = {current_record['No']}")
                    
                    # Parse die restliche Zeile für weitere Felder
                    header_data = parse_header_row(row[1:])
                    for key, value in header_data.items():
                        current_record[key] = value
                        debug_print(f"  → {key}: {value}")
                
                # --- Fall 2: Criteria (Start)
                elif normalize(first_cell) == "criteria":
                    collecting_criteria = True
                    current_record["Criteria"] = extract_value_from_cells(row, 1)
                    debug_print(f"  → Criteria (Start): {current_record['Criteria']}")
                
                # --- Fall 3: Normale Key/Value Labels
                else:
                    norm_first = normalize(first_cell)
                    label_found = False
                    
                    # Prüfe ob die erste Zelle ein bekanntes Label enthält
                    for key, mapped_label in label_map.items():
                        if key in norm_first:
                            value = extract_value_from_cells(row, 1)
                            if value:  # Nur wenn ein Wert vorhanden ist
                                current_record[mapped_label] = value
                                collecting_criteria = False
                                debug_print(f"  → {mapped_label}: {value}")
                                label_found = True
                            break
                    
                    # --- Fall 4: Criteria-Mehrzeilen
                    if not label_found and collecting_criteria and first_cell:
                        extra_text = " ".join(safe_strip(c) for c in row if c)
                        current_record["Criteria"] = (current_record.get("Criteria", "") + " " + extra_text).strip()
                        debug_print(f"  → Criteria (Fortsetzung): {extra_text}")
                    
                    # --- Fall 5: Möglicherweise eine Zeile mit mehreren Label-Value Paaren
                    elif not label_found:
                        # Versuche die ganze Zeile zu parsen
                        parsed_data = parse_header_row(row)
                        if parsed_data:
                            for key, value in parsed_data.items():
                                current_record[key] = value
                                debug_print(f"  → {key}: {value}")
        
        # Letzten Record speichern
        if current_record and any(current_record.values()):
            records.append(current_record)
            record_count += 1
            debug_print(f"\n✅ Letzter Datensatz {record_count} gespeichert")
    
    # DataFrame erstellen
    df = pd.DataFrame(records, columns=columns)
    
    # Statistiken
    debug_print(f"\n{'='*60}")
    debug_print("📊 STATISTIKEN:")
    debug_print(f"{'='*60}")
    debug_print(f"Gesamtzahl Datensätze: {len(df)}")
    debug_print("\nSpalten mit Daten:")
    for col in columns:
        non_empty = df[col].astype(str).str.strip().ne("").sum()
        if non_empty > 0:
            debug_print(f"  - {col}: {non_empty} Einträge")
    
    # Excel speichern
    df.to_excel(out_file, index=False)
    debug_print(f"\n✅ Excel-Datei gespeichert: {out_file}")
    
    # Debug-Ausgabe speichern
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(debug_lines))
    debug_print(f"📝 Debug-Ausgabe gespeichert: {debug_file}")
    
    # Beispiel-Ausgabe der ersten Datensätze
    if len(df) > 0:
        debug_print("\n📋 Erste 3 Datensätze (Vorschau):")
        for idx in range(min(3, len(df))):
            debug_print(f"\nDatensatz {idx + 1}:")
            for col in columns:
                val = df.iloc[idx][col]
                if val:
                    debug_print(f"  {col}: {val}")

except FileNotFoundError:
    print(f"❌ FEHLER: Die PDF-Datei '{in_file}' wurde nicht gefunden!")
    print("Bitte stellen Sie sicher, dass die PDF-Datei im gleichen Verzeichnis liegt.")
except Exception as e:
    print(f"❌ FEHLER beim Verarbeiten der PDF: {str(e)}")
    import traceback
    traceback.print_exc()