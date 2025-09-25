# So prüfen Sie den exakten Spaltennamen in Power BI:

1. **In der Datenansicht:**
   - Gehen Sie zur Datenansicht (Data View)
   - Finden Sie die Tabelle 'Netting - Maximum Contract Volume [Verweis]'
   - Schauen Sie in die Spaltenüberschriften

2. **Im Datenmodell:**
   - Gehen Sie zur Modellansicht (Model View)
   - Klicken Sie auf die Tabelle
   - Die Spaltennamen werden exakt angezeigt

3. **In Power Query:**
   - Gehen Sie zu "Daten transformieren" (Transform Data)
   - Wählen Sie die Tabelle
   - Die Spaltennamen sind hier exakt sichtbar

4. **Quick-Test mit IntelliSense:**
   - Beginnen Sie zu tippen: `'Netting - Maximum Contract Volume [Verweis]'[`
   - Power BI sollte Ihnen die verfügbaren Spalten vorschlagen

## Mögliche Spaltennamen-Varianten:
- `Maximum Replacement Risk [Total]` (mit eckigen Klammern)
- `Maximum Replacement Risk Total` (ohne eckige Klammern)
- `Maximum Replacement Risk (Total)` (mit runden Klammern)
- `Maximum_Replacement_Risk_Total` (mit Unterstrichen)