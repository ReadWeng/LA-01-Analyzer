import os
import re

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    # Skip the "use_demo" logic block
    if "use_demo = False" in line:
        skip = True
    if skip and ("# 我們要解析的檔案 bytes" in line or "# 我們要解析的" in line or "fit_bytes = None" in line):
        skip = False
        
    if "elif st.session_state.get('use_demo', False):" in line:
        skip = True
    if skip and "if 'last_file' not in st.session_state:" in line:
        skip = False
        # But we need to keep "if 'last_file'"
        new_lines.append(line)
        continue
    
    # Check if there is another line we shouldn't skip
    if "st.session_state['use_demo'] = False" in line:
        continue # remove this line as well
        
    if not skip:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Removed demo button logic.")
