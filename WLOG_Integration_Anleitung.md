# WLOG Integration für Wind Turbine Monitoring

## Übersicht
Diese Lösung integriert WLOG-Ereignisse (Fehlermeldungen) in Ihr bestehendes Wind-Turbinen-Monitoring-Visual. Kritische WLOG-Events werden als rote Punkte über dem Zeitstrahl angezeigt.

## Schritt 1: Datenmodell vorbereiten

### 1.1 WLOG Filter Tabelle erstellen
Erstellen Sie eine separate Tabelle mit den wichtigsten WLOG-Codes:

```DAX
WLOG_Filter = 
DATATABLE(
    "WLOG_Code", INTEGER,
    "Beschreibung", STRING,
    "Kritisch", BOOLEAN,
    {
        {266, "Pitch: Power", TRUE},
        {223, "Stop kW RPM", TRUE}, 
        {165, "Low oil-level hydraulic", TRUE},
        {222, "Emergency kW RPM", TRUE},
        {282, "Yawing manually stopped", FALSE},
        {102, "Emergency circuit open", TRUE},
        {276, "Start auto-outyawing CCW", FALSE},
        {281, "Start manual yawing CCW", FALSE},
        {892, "Yaw gear protection stop", TRUE},
        {161, "Max time hydr. pumping sec", FALSE},
        {226, "Power cutout", TRUE},
        {224, "Pause kW RPM", FALSE},
        {227, "Power cutin", FALSE}
    }
)
```

### 1.2 Beziehungen einrichten
- Erstellen Sie eine Beziehung zwischen Ihrer Faktentabelle und der WLOG-Tabelle über das Feld `event_time`
- Stellen Sie sicher, dass die WLOG_Filter Tabelle mit der WLOG-Tabelle über `WLOG_Code` verknüpft ist

## Schritt 2: DAX Measures erstellen

### 2.1 WLOG Event Detection
```DAX
Hat_Kritisches_WLOG = 
VAR CurrentTime = SELECTEDVALUE(Faktentabelle[event_time])
RETURN
IF(
    NOT ISBLANK(CurrentTime),
    CALCULATE(
        COUNTROWS(WLOG_Tabelle),
        WLOG_Tabelle[event_time] = CurrentTime,
        WLOG_Filter[Kritisch] = TRUE
    ) > 0,
    FALSE
)
```

### 2.2 WLOG Details für Tooltip
```DAX
WLOG_Details = 
VAR CurrentTime = SELECTEDVALUE(Faktentabelle[event_time])
VAR WLOGInfo = 
    CALCULATE(
        CONCATENATEX(
            WLOG_Tabelle,
            "Code: " & WLOG_Tabelle[WLOG_Code] & 
            " | " & WLOG_Tabelle[WLOG_Mess_Rem] & 
            " | Relevanz: " & WLOG_Tabelle[Relevanz],
            UNICHAR(10)
        ),
        WLOG_Tabelle[event_time] = CurrentTime,
        WLOG_Filter[Kritisch] = TRUE
    )
RETURN
IF(ISBLANK(WLOGInfo), "Keine kritischen WLOG Events", WLOGInfo)
```

### 2.3 WLOG Relevanz Color
```DAX
WLOG_Color = 
VAR CurrentTime = SELECTEDVALUE(Faktentabelle[event_time])
VAR MaxRelevanz = 
    CALCULATE(
        MAX(WLOG_Tabelle[Relevanz]),
        WLOG_Tabelle[event_time] = CurrentTime,
        WLOG_Filter[Kritisch] = TRUE
    )
RETURN
SWITCH(
    MaxRelevanz,
    "Sehr hoch", "#DC143C",
    "Hoch", "#FF4500", 
    "Mittel", "#FFA500",
    "#808080"
)
```

## Schritt 3: Deneb Visual konfigurieren

### 3.1 Datenfelder hinzufügen
Fügen Sie diese Felder zu Ihrem Deneb Visual hinzu:
- `event_time` (von Faktentabelle)
- `wind_speed` (von Faktentabelle)  
- `power_output` (von Faktentabelle)
- `Hat_Kritisches_WLOG` (Measure)
- `WLOG_Details` (Measure)
- `WLOG_Color` (Measure)

### 3.2 JSON Spezifikation verwenden
Verwenden Sie die bereitgestellte JSON-Datei `wind_turbine_advanced_wlog.json` als Basis für Ihr Deneb Visual.

## Schritt 4: Visual anpassen

### 4.1 Farben anpassen
- Sehr hohe Relevanz: Rot (#DC143C)
- Hohe Relevanz: Orange-Rot (#FF4500)
- Mittlere Relevanz: Orange (#FFA500)

### 4.2 Punkt-Größen
- Sehr hoch: 150px
- Hoch: 120px  
- Mittel: 80px

### 4.3 Interaktivität
- Hover-Effekt vergrößert die Punkte
- Tooltip zeigt detaillierte WLOG-Informationen
- Filter für Relevanz-Stufen

## Schritt 5: Testing und Optimierung

### 5.1 Performance
- Verwenden Sie Indizes auf `event_time` Feldern
- Begrenzen Sie den Zeitbereich für bessere Performance
- Filtern Sie nur relevante WLOG-Codes

### 5.2 Benutzerfreundlichkeit
- Fügen Sie eine Legende hinzu
- Implementieren Sie Zoom-Funktionalität
- Ermöglichen Sie das Ein-/Ausblenden verschiedener WLOG-Kategorien

## Troubleshooting

### Häufige Probleme:
1. **Keine roten Punkte sichtbar**: Überprüfen Sie die Beziehungen zwischen den Tabellen
2. **Performance-Probleme**: Reduzieren Sie den Zeitbereich oder die Anzahl der WLOG-Codes
3. **Tooltip funktioniert nicht**: Stellen Sie sicher, dass die WLOG_Details Measure korrekt ist

### Debug-Measures:
```DAX
Debug_WLOG_Count = 
CALCULATE(
    COUNTROWS(WLOG_Tabelle),
    WLOG_Tabelle[event_time] = SELECTEDVALUE(Faktentabelle[event_time])
)
```

## Erweiterte Features

### Zeitbereichs-Aggregation
Für bessere Übersicht bei großen Zeiträumen können Sie WLOG-Events in Zeitintervallen aggregieren:

```DAX
WLOG_Hourly_Count = 
VAR CurrentHour = HOUR(SELECTEDVALUE(Faktentabelle[event_time]))
VAR CurrentDate = DATE(
    YEAR(SELECTEDVALUE(Faktentabelle[event_time])),
    MONTH(SELECTEDVALUE(Faktentabelle[event_time])),
    DAY(SELECTEDVALUE(Faktentabelle[event_time]))
)
RETURN
CALCULATE(
    COUNTROWS(WLOG_Tabelle),
    HOUR(WLOG_Tabelle[event_time]) = CurrentHour,
    DATE(
        YEAR(WLOG_Tabelle[event_time]),
        MONTH(WLOG_Tabelle[event_time]),
        DAY(WLOG_Tabelle[event_time])
    ) = CurrentDate,
    WLOG_Filter[Kritisch] = TRUE
)
```

Diese Lösung bietet Ihnen eine vollständige Integration von WLOG-Events in Ihr Wind-Turbinen-Monitoring mit flexibler Konfiguration und benutzerfreundlicher Darstellung.