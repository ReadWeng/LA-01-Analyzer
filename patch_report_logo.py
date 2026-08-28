import os
import base64

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Generate base64 string for the logo
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 50px; vertical-align: middle; border-radius: 50%; object-fit: cover;">'
except:
    img_tag = '<span class="logo-icon">🩸</span>'

old_span = '<span class="logo-icon">🩸</span>'
# Be careful: Python string might have it encoded, but reading as utf-8 it's exactly the character.
# Since my script has the actual character, let's use the unicode escape
old_span = '<span class="logo-icon">\U0001fa78</span>'

content = content.replace(old_span, img_tag)

# Also let's remove any css styling that was specific to the text logo if it messes up the image
# Actually the css for logo-icon was:
# .logo-icon { font-size: 2.2rem; filter: drop-shadow(0 0 10px rgba(0, 230, 118, 0.3)); }
# That should work fine on an image or we can just leave it.
# Let's remove font-size just in case, but it shouldn't affect <img> since we forced height: 50px.

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched LactateReport/integrate_reports.py for logo.")
