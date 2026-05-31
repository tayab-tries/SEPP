import markdown
import os

md_path = r"d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report_Condensed.md"
html_path = r"d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report_Condensed.html"

with open(md_path, "r", encoding="utf-8") as f:
    text = f.read()

# Convert markdown to html
html = markdown.markdown(text, extensions=['tables'])

# Wrap in basic HTML structure
full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ExamApp Final Report</title>
    <style>
        body {{ font-family: Calibri, sans-serif; line-height: 1.6; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 1em; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    {html}
</body>
</html>
"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print("HTML file created successfully.")
