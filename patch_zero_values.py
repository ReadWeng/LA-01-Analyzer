import os

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace condition `lac > 0` with `lac >= 0`
old_cond = '''has_lac = pd.notna(lac) and lac > 0
            has_glc = pd.notna(glc) and glc > 0'''

new_cond = '''has_lac = pd.notna(lac) and lac >= 0
            has_glc = pd.notna(glc) and glc >= 0'''

content = content.replace(old_cond, new_cond)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched 0 values check in fit_lactate_fire.py")
