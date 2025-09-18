import pdfplumber
import pandas as pd
import re

# 📌 Eingabe-/Ausgabe-Dateien
in_file = "0001-2179_V60 - AlarmAndWarningListMk567-11.pdf"  # Ihre echte PDF
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

# WICHTIG: Exakte Label-Mapping - Reihenfolge ist wichtig!
# Längere/spezifischere Labels zuerst, um falsche Matches zu vermeiden
label_map = [
    ("supervision id", "SupervisionID"),
    ("supervisionid", "SupervisionID"),
    ("subsystem name", "Subsystem name"),  # VOR "name"!
    ("shutdown type", "Shutdown type"),    # VOR "type"!
    ("log text", "Log text"),
    ("logtext", "Log text"),
    ("name", "Name"),
    ("type", "Type"),
    ("timeout", "Timeout"),
    ("time out", "Timeout"),
    ("acknowledgement", "Acknowledgement"),
    ("acknowledge", "Acknowledgement"),
    ("ack", "Acknowledgement"),
    ("allowed attempts", "Allowed attempts"),
    ("attempts", "Allowed attempts"),
    ("time window", "Time window"),
    ("timewindow", "Time window"),
    ("max time disconnect", "Max time disconnect"),
    ("max disconnect", "Max time disconnect"),
    ("disconnect", "Max time disconnect"),
    ("max time eliminate", "Max time eliminate"),
    ("max eliminate", "Max time eliminate"),
    ("eliminate", "Max time eliminate"),
    ("stabilize period", "Stabilize period"),
    ("stabilize", "Stabilize period"),
    ("category", "Category"),
    ("criteria", "Criteria"),
]

def safe_strip(val):
    """Sicheres Strip mit None-Check"""
    return val.strip() if val else ""

def normalize(text):
    """Normalisiert Text für Vergleiche"""
    if not text:
        return ""
    # Entferne Doppelpunkte am Ende
    text = text.rstrip(":")
    # Entferne mehrfache Leerzeichen und konvertiere zu Kleinbuchstaben
    text = " ".join(text.lower().split())
    # Entferne Sonderzeichen für besseren Vergleich
    text = re.sub(r'[-_]+', ' ', text)
    return text.strip()

def find_label_in_text(text):
    """Findet ein Label im Text und gibt (Label, Position) zurück"""
    norm_text = normalize(text)
    for pattern, label in label_map:
        if pattern in norm_text:
            return label, norm_text.find(pattern)
    return None, -1

def extract_value_after_colon(text):
    """Extrahiert Wert nach einem Doppelpunkt"""
    if ":" in text:
        parts = text.split(":", 1)
        if len(parts) > 1:
            return parts[1].strip()
    return ""

def parse_row_smart(row, current_record):
    """Intelligentes Parsing einer Tabellenzeile"""
    updates = {}
    
    # Strategie 1: Suche nach Label:Wert Paaren in jeder Zelle
    for cell in row:
        if not cell:
            continue
            
        cell_text = safe_strip(cell)
        
        # Prüfe ob die Zelle ein Label:Wert Paar enthält
        if ":" in cell_text:
            label, _ = find_label_in_text(cell_text)
            if label:
                value = extract_value_after_colon(cell_text)
                if value:
                    updates[label] = value
    
    # Strategie 2: Paarweises Durchgehen (Label in Zelle i, Wert in Zelle i+1)
    i = 0
    while i < len(row) - 1:
        cell1 = safe_strip(row[i])
        cell2 = safe_strip(row[i + 1])
        
        if cell1 and cell2:
            # Entferne Doppelpunkt am Ende für Vergleich
            label, _ = find_label_in_text(cell1)
            
            if label and not updates.get(label):  # Nur wenn noch kein Wert gefunden
                # Prüfe ob cell2 kein Label ist
                label2, _ = find_label_in_text(cell2)
                if not label2:  # cell2 ist ein Wert
                    updates[label] = cell2
                    i += 2  # Überspringe das Wertfeld
                    continue
        
        i += 1
    
    return updates

# Debug-Ausgabe
debug_lines = []

def debug_print(msg):
    """Print und speichere Debug-Nachrichten"""
    print(msg)
    debug_lines.append(msg)

debug_print("=== PDF Extractor - Finale Version ===\n")

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
            
            # Extrahiere die Tabelle mit Standard-Einstellungen
            table = page.extract_table()
            
            if not table:
                debug_print("❌ Keine Tabelle auf dieser Seite gefunden")
                continue
            
            debug_print(f"✅ Tabelle gefunden mit {len(table)} Zeilen")
            
            for row_idx, row in enumerate(table):
                if not row or not any(row):  # Überspringe komplett leere Zeilen
                    continue
                
                # Rekonstruiere die Zeile (füge geteilte Texte zusammen)
                reconstructed_row = []
                temp_text = ""
                
                for cell in row:
                    if cell is None:
                        cell = ""
                    cell = str(cell).strip()
                    
                    # Wenn die Zelle mit einem Label beginnt oder ein : enthält, 
                    # ist es wahrscheinlich ein neues Feld
                    if cell and (find_label_in_text(cell)[0] or ":" in cell):
                        if temp_text:
                            reconstructed_row.append(temp_text)
                        temp_text = cell
                    else:
                        # Füge zum vorherigen Text hinzu
                        if temp_text and cell:
                            temp_text += " " + cell
                        elif cell:
                            temp_text = cell
                
                if temp_text:
                    reconstructed_row.append(temp_text)
                
                # Verwende die rekonstruierte Zeile
                if reconstructed_row:
                    row = reconstructed_row
                
                first_cell = safe_strip(row[0])
                
                # Debug-Ausgabe für interessante Zeilen
                if row_idx < 5 or first_cell.startswith("No:") or any(find_label_in_text(safe_strip(cell))[0] for cell in row if cell):
                    debug_print(f"\nZeile {row_idx}: {row}")
                
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
                    
                    # Parse die gesamte Zeile
                    updates = parse_row_smart(row, current_record)
                    for key, value in updates.items():
                        current_record[key] = value
                        debug_print(f"  → {key}: {value}")
                
                # --- Fall 2: Criteria
                elif normalize(first_cell) == "criteria":
                    collecting_criteria = True
                    # Sammle alle Werte in der Zeile
                    criteria_parts = []
                    for i in range(1, len(row)):
                        val = safe_strip(row[i])
                        if val:
                            criteria_parts.append(val)
                    current_record["Criteria"] = " ".join(criteria_parts)
                    debug_print(f"  → Criteria: {current_record['Criteria']}")
                
                # --- Fall 3: Normale Zeilen
                else:
                    # Prüfe ob wir Criteria sammeln
                    if collecting_criteria and first_cell and not find_label_in_text(first_cell)[0]:
                        # Fortsetzung von Criteria
                        extra_text = " ".join(safe_strip(c) for c in row if c)
                        current_record["Criteria"] = (current_record.get("Criteria", "") + " " + extra_text).strip()
                        debug_print(f"  → Criteria (Fortsetzung): {extra_text}")
                    else:
                        # Parse normale Label-Value Zeilen
                        updates = parse_row_smart(row, current_record)
                        if updates:
                            collecting_criteria = False  # Beende Criteria-Sammlung
                            for key, value in updates.items():
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
        else:
            debug_print(f"  - {col}: KEINE DATEN ⚠️")
    
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
            debug_print(f"\n{'='*40}")
            debug_print(f"Datensatz {idx + 1}:")
            debug_print(f"{'='*40}")
            for col in columns:
                val = str(df.iloc[idx][col])
                if val and val != "":
                    debug_print(f"  {col}: {val}")

except FileNotFoundError:
    print(f"❌ FEHLER: Die PDF-Datei '{in_file}' wurde nicht gefunden!")
    print("Bitte stellen Sie sicher, dass die PDF-Datei im gleichen Verzeichnis liegt.")
except Exception as e:
    print(f"❌ FEHLER beim Verarbeiten der PDF: {str(e)}")
    import traceback
    traceback.print_exc()