import pdfplumber
import pandas as pd

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

records = []
current_record = {}
collecting_criteria = False

with pdfplumber.open(in_file) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        table = page.extract_table()
        if not table:
            continue

        for row in table:
            if not row or not row[0]:
                continue

            first_cell = safe_strip(row[0])
            norm_label = normalize(first_cell)

            # --- Fall 1: Neuer Datensatz (No:)
            if first_cell.startswith("No:"):
                if current_record:
                    records.append(current_record)

                current_record = {col: "" for col in columns}
                collecting_criteria = False

                # No extrahieren
                no_value = first_cell.split("No:")[-1].strip()
                current_record["No"] = no_value

                # Kopfzeile: Paare durchgehen (1/2, 3/4, ...)
                for i in range(1, len(row), 2):
                    raw_label = safe_strip(row[i]) if i < len(row) else ""
                    value = safe_strip(row[i+1]) if i+1 < len(row) else ""
                    norm_label = normalize(raw_label)
                    if norm_label in label_map:
                        current_record[label_map[norm_label]] = value

            # --- Fall 2: Criteria (Start)
            elif norm_label == "criteria":
                collecting_criteria = True
                current_record["Criteria"] = safe_strip(row[1]) if len(row) > 1 else ""

            # --- Fall 3: Normale Key/Value Labels (0/1-Logik)
            elif norm_label in label_map:
                label = label_map[norm_label]
                value = safe_strip(row[1]) if len(row) > 1 else ""
                current_record[label] = value
                collecting_criteria = False

            # --- Fall 4: Criteria-Mehrzeilen
            elif collecting_criteria:
                extra_text = " ".join(safe_strip(c) for c in row if c)
                current_record["Criteria"] += " " + extra_text

# Letzten Record speichern
if current_record:
    records.append(current_record)

# DataFrame bauen und speichern
df = pd.DataFrame(records, columns=columns)
df.to_excel(out_file, index=False)

print(f"✅ Fertig! {len(df)} Datensätze gespeichert in {out_file}")