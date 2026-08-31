import os

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace {} with {{}}
content = content.replace("Object.assign({},", "Object.assign({{}},")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed syntax error in integrate_reports.py")
