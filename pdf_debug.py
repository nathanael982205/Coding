import pdfplumber
import json
import os

# 📌 Eingabe-Datei
in_file = "0001-2179_V60 - AlarmAndWarningListMk567-11.pdf"

# Prüfen ob die Datei existiert
if not os.path.exists(in_file):
    print(f"❌ FEHLER: Die PDF-Datei '{in_file}' wurde nicht gefunden!")
    print(f"Aktueller Pfad: {os.getcwd()}")
    print(f"Verfügbare Dateien: {os.listdir('.')}")
    exit(1)

print("=== PDF Debug-Analyse ===\n")

with pdfplumber.open(in_file) as pdf:
    # Nur die ersten 3 Seiten analysieren
    for page_num, page in enumerate(pdf.pages[:3], start=1):
        print(f"\n{'='*60}")
        print(f"SEITE {page_num}")
        print(f"{'='*60}")
        
        # Tabelle extrahieren
        table = page.extract_table()
        
        if not table:
            print("❌ Keine Tabelle gefunden")
            continue
            
        print(f"✅ Tabelle gefunden mit {len(table)} Zeilen")
        
        # Erste 10 Zeilen der Tabelle anzeigen
        print("\n📊 Erste 10 Zeilen der Tabelle:")
        for i, row in enumerate(table[:10]):
            print(f"\nZeile {i}: {len(row)} Zellen")
            for j, cell in enumerate(row):
                cell_content = cell.strip() if cell else "[LEER]"
                print(f"  Zelle [{j}]: '{cell_content}'")
        
        # Nach "No:" Zeilen suchen
        print("\n🔍 Suche nach 'No:' Zeilen:")
        no_count = 0
        for i, row in enumerate(table):
            if row and row[0] and row[0].strip().startswith("No:"):
                no_count += 1
                print(f"\nZeile {i}: No: gefunden")
                print(f"  Komplette Zeile: {row}")
                
        print(f"\n✅ Insgesamt {no_count} 'No:' Einträge auf Seite {page_num}")
        
        # Tabellenstruktur analysieren
        print("\n📐 Tabellenstruktur-Analyse:")
        if table:
            # Maximale Anzahl von Spalten finden
            max_cols = max(len(row) for row in table if row)
            print(f"  Maximale Spaltenanzahl: {max_cols}")
            
            # Typische Zeilenlängen
            row_lengths = {}
            for row in table:
                if row:
                    length = len(row)
                    row_lengths[length] = row_lengths.get(length, 0) + 1
            
            print("  Zeilenlängen-Verteilung:")
            for length, count in sorted(row_lengths.items()):
                print(f"    {length} Spalten: {count} Zeilen")

# Spezielle Analyse für Muster
print("\n\n🔍 SPEZIELLE MUSTER-ANALYSE:")
print("="*60)

with pdfplumber.open(in_file) as pdf:
    page = pdf.pages[0]  # Erste Seite
    table = page.extract_table()
    
    if table:
        print("\n📋 Suche nach Label-Value Paaren:")
        for i, row in enumerate(table[:20]):  # Erste 20 Zeilen
            if not row or len(row) < 2:
                continue
                
            # Prüfe ob es ein Label-Value Paar sein könnte
            first_cell = row[0].strip() if row[0] else ""
            second_cell = row[1].strip() if row[1] else ""
            
            # Labels die wir suchen
            search_labels = ["SupervisionID", "Name", "Log text", "Subsystem name", 
                           "Type", "Timeout", "Acknowledgement", "Shutdown type",
                           "Allowed attempts", "Time window", "Max time disconnect",
                           "Max time eliminate", "Stabilize period", "Category", "Criteria"]
            
            for label in search_labels:
                if label.lower() in first_cell.lower():
                    print(f"\nZeile {i}: Mögliches Label '{label}' gefunden")
                    print(f"  Zelle 0: '{first_cell}'")
                    print(f"  Zelle 1: '{second_cell}'")
                    if len(row) > 2:
                        print(f"  Weitere Zellen: {[row[j].strip() if row[j] else '' for j in range(2, len(row))]}")