# Power BI DAX Formula Troubleshooting

## Original Formula (Not Working)
```dax
Replacement Risk Positiv =
CALCULATE (
    SUM ( 'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] ),
    FILTER (
        'Netting - Maximum Contract Volume [Verweis]',
        'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0
    )
)
```

## Common Issues and Solutions

### 1. Table/Column Name Issues
The table name contains special characters and spaces. Try these solutions:

**Solution A: Use proper escaping**
```dax
Replacement Risk Positiv = 
CALCULATE(
    SUM('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]),
    FILTER(
        'Netting - Maximum Contract Volume [Verweis]',
        'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0
    )
)
```

**Solution B: Alternative syntax without FILTER**
```dax
Replacement Risk Positiv = 
CALCULATE(
    SUM('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]),
    'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0
)
```

### 2. Simpler SUMX Approach
```dax
Replacement Risk Positiv = 
SUMX(
    FILTER(
        'Netting - Maximum Contract Volume [Verweis]',
        'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0
    ),
    'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]
)
```

### 3. Using Variables for Better Readability
```dax
Replacement Risk Positiv = 
VAR _Table = 'Netting - Maximum Contract Volume [Verweis]'
VAR _Result = 
    CALCULATE(
        SUM(_Table[Maximum Replacement Risk [Total]]),
        _Table[Maximum Replacement Risk [Total]] > 0
    )
RETURN
    _Result
```

### 4. Check for Data Type Issues
If the column is text instead of numeric:
```dax
Replacement Risk Positiv = 
CALCULATE(
    SUM(
        VALUE('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]])
    ),
    FILTER(
        'Netting - Maximum Contract Volume [Verweis]',
        VALUE('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]) > 0
    )
)
```

### 5. Alternative with KEEPFILTERS
```dax
Replacement Risk Positiv = 
CALCULATE(
    SUM('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]),
    KEEPFILTERS('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0)
)
```

## Debugging Steps

1. **Check Table Name**: Verify the exact table name in Power BI
   - Right-click on the table in the Fields pane
   - Check if there are any extra spaces or special characters

2. **Check Column Name**: Verify the exact column name
   - Expand the table in the Fields pane
   - Check the exact spelling and brackets

3. **Check Data Type**: Ensure the column is numeric
   - In Power Query Editor or Model view
   - Check if the column is set to Decimal/Whole Number

4. **Test Simplified Version**: Start with a simple SUM first
   ```dax
   Test = SUM('Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]])
   ```

5. **Check for Relationships**: Ensure proper relationships exist if this is a calculated column

## Most Likely Working Solution

```dax
Replacement Risk Positiv = 
SUMX(
    FILTER(
        'Netting - Maximum Contract Volume [Verweis]',
        'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]] > 0
    ),
    'Netting - Maximum Contract Volume [Verweis]'[Maximum Replacement Risk [Total]]
)
```

This approach is more straightforward and less prone to context transition issues.