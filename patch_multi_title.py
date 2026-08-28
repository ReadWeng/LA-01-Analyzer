import os
import base64

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Generate base64 string for the logo
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 50px; vertical-align: middle; margin-right: 15px; border-radius: 50%; object-fit: cover;">'
except:
    img_tag = ''

# The old line to replace: 
# st.markdown('<div class="title-container">🩸 多期乳酸與生理指標整合工具</div>', unsafe_allow_html=True)
old_line = '<div class="title-container">\U0001fa78 多期乳酸與生理指標整合工具</div>'
new_line = f'<div class="title-container" style="display: flex; align-items: center;">{img_tag}多期乳酸與生理指標整合工具</div>'

content = content.replace(old_line, new_line)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched UI title for multi-session tool.")
