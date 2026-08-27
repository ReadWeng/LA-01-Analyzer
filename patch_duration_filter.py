import os
import re

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update function signature
old_func_def = "def fetch_firebase_lactate_records(start_time=None):"
new_func_def = "def fetch_firebase_lactate_records(start_time=None, duration_minutes=0.0):"
content = content.replace(old_func_def, new_func_def)

# 2. Update filter logic
old_filter_logic = """                        elapsed_min = (record_time - start_time).total_seconds() / 60.0
                        if abs(elapsed_min) > 60:
                            continue"""

new_filter_logic = """                        elapsed_min = (record_time - start_time).total_seconds() / 60.0
                        # 條件: 起始時間 - 60分鐘 <= 記錄時間 <= 起始時間 + 運動時間 + 60分鐘
                        if elapsed_min < -60 or elapsed_min > (duration_minutes + 60):
                            continue"""
content = content.replace(old_filter_logic, new_filter_logic)

# 3. Update function call
old_call = "cloud_records = fetch_firebase_lactate_records(start_time)"
new_call = "cloud_records = fetch_firebase_lactate_records(start_time, duration_minutes)"
content = content.replace(old_call, new_call)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied for duration filter.")
