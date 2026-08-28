import os
import re

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update page_icon
old_config = """st.set_page_config(
    page_title="FIT 檔與乳酸協同分析工具",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)"""
new_config = """from PIL import Image
try:
    page_icon_img = Image.open("logo.jpg")
except:
    page_icon_img = "🩸"

st.set_page_config(
    page_title="FIT 檔與乳酸協同分析工具",
    page_icon=page_icon_img,
    layout="wide",
    initial_sidebar_state="expanded"
)"""
content = content.replace(old_config, new_config)

# 2. Update title markdown
old_title = """st.markdown('<div class="title-container">🩸 FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)"""
new_title = """import base64
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 50px; vertical-align: middle; margin-right: 15px; border-radius: 50%; object-fit: cover;">'
    st.markdown(f'<div class="title-container" style="display: flex; align-items: center;">{img_tag}FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)
except:
    st.markdown('<div class="title-container">🩸 FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)"""
content = content.replace(old_title, new_title)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied for logo.")
