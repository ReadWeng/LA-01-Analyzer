import os
import base64

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Generate base64 string for the logo
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 40px; vertical-align: middle; margin-right: 10px; border-radius: 50%; object-fit: cover;">'
except:
    img_tag = ''

# The old line to replace:
# <div class="header">🩸 FIT 檔與乳酸協同報告</div>
old_line = '<div class="header">\U0001fa78 FIT 檔與乳酸協同報告</div>'
new_line = f'<div class="header" style="display: flex; align-items: center; justify-content: center;">{img_tag}FIT 檔與乳酸協同報告</div>'

content = content.replace(old_line, new_line)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched single-session HTML report title.")
