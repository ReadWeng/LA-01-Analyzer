import os

path = "fit_lactate_fire.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_logic = """                if start_time:
                    elapsed_min = (record_time - start_time).total_seconds() / 60.0

                records.append({
                    "elapsed_minutes": elapsed_min,
                    "lactate_mmol": final_la,
                    "record_time": record_time
                })"""

new_logic = """                if start_time:
                    elapsed_min = (record_time - start_time).total_seconds() / 60.0
                    # 過濾：只抓取與 FIT 檔起始時間正負 1 小時 (60分鐘) 內的數據
                    if abs(elapsed_min) > 60:
                        continue

                records.append({
                    "elapsed_minutes": elapsed_min,
                    "lactate_mmol": final_la,
                    "record_time": record_time
                })"""

content = content.replace(old_logic, new_logic)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Added 1 hour time filter.")
