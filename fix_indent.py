import os

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line == '                    elapsed_min = (record_time - start_time).total_seconds() / 60.0\n':
        lines[i] = '                        elapsed_min = (record_time - start_time).total_seconds() / 60.0\n'
    if line == '                    if abs(elapsed_min) > 60:\n':
        lines[i] = '                        if abs(elapsed_min) > 60:\n'
    if line == '                        continue\n':
        lines[i] = '                            continue\n'

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Indentation fixed.")
