import os
import re

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# using regex
old_pattern = r"if start_time:\s*elapsed_min = \(record_time - start_time\)\.total_seconds\(\) / 60\.0\s*records\.append\({"
new_replacement = """if start_time:
                    elapsed_min = (record_time - start_time).total_seconds() / 60.0
                    if abs(elapsed_min) > 60:
                        continue

                records.append({"""

content = re.sub(old_pattern, new_replacement, content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Regex patch applied.")
