import os
import re
import requests
import sys

input_md = r"d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report.md"
output_md = r"d:\Bullshit\2.0\SE\EXAM\ExamApp_Final_Report_Rendered.md"
diagram_dir = r"d:\Bullshit\2.0\SE\EXAM\diagrams"

os.makedirs(diagram_dir, exist_ok=True)

with open(input_md, "r", encoding="utf-8") as f:
    content = f.read()

# Find all blocks first
blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
print(f"Found {len(blocks)} mermaid diagrams to render.")

def replace_mermaid(match):
    global diagram_counter
    mermaid_code = match.group(1).strip()
    mermaid_code = mermaid_code.replace("\\n", "<br/>")
    
    img_path = os.path.join(diagram_dir, f"diagram_{diagram_counter}.png")
    rel_img_path = f"diagrams/diagram_{diagram_counter}.png"
    
    print(f"Rendering diagram {diagram_counter}...")
    try:
        resp = requests.post("https://kroki.io/mermaid/png", data=mermaid_code.encode("utf-8"), headers={"Content-Type": "text/plain"}, timeout=15)
        
        if resp.status_code == 200:
            with open(img_path, "wb") as img_file:
                img_file.write(resp.content)
            print(f"Saved {img_path}")
            replacement = f"![Diagram {diagram_counter}]({rel_img_path})"
        else:
            print(f"Failed to render diagram {diagram_counter}. Status: {resp.status_code}")
            print(resp.text[:200])
            replacement = match.group(0) # don't replace if failed
    except Exception as e:
        print(f"Exception rendering diagram {diagram_counter}: {e}")
        replacement = match.group(0)
        
    diagram_counter += 1
    return replacement

diagram_counter = 1
new_content = re.sub(r"```mermaid\n(.*?)\n```", replace_mermaid, content, flags=re.DOTALL)

with open(output_md, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done. Saved rendered markdown to:", output_md)
