# -*- coding: utf-8 -*-
"""
weekly_physio_engine.py
運動生理學與乳酸負荷運算核心引擎
功能：
1. 支援從本地 HTML/FIT 或 Firebase Firestore 抓取 5~7 天訓練與乳酸數據
2. 精準解析時長、心率、功率與各採血時間點乳酸值（修正跨行正則表達式缺失問題）
3. 計算運動生理學核心指標：
   - 代謝效率比 (Metabolic Efficiency Ratio: W/mmol 或 HR/mmol)
   - 高乳酸暴露累積量 (Lactate AUC / 代謝壓力負荷)
   - 乳酸加權訓練負荷 (Lactate-Weighted TRIMP / Load Score)
   - 5~7 天極化區間時間佔比 (Zone 1-2, Zone 3-4, Zone 5+)
   - 疲勞與恢復狀態指標 (Recovery & Adaptation Status)
"""

import os
import re
import glob
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import requests


def parse_duration_to_minutes(text):
    """精準解析 '59 分 59 秒' 或 '40.5 分' 或 '01:15:30' 為浮點數分鐘"""
    if not text:
        return 0.0
    text = str(text).strip()
    
    m = re.search(r'(\d+(?:\.\d+)?)\s*分(?:\s*(\d+(?:\.\d+)?)\s*秒)?', text)
    if m:
        mins = float(m.group(1))
        secs = float(m.group(2)) if m.group(2) else 0.0
        return round(mins + secs / 60.0, 1)
        
    parts = text.split(':')
    if len(parts) == 3:
        try:
            return round(float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0, 1)
        except Exception:
            pass
    elif len(parts) == 2:
        try:
            return round(float(parts[0]) + float(parts[1]) / 60.0, 1)
        except Exception:
            pass

    num_m = re.search(r'(\d+(?:\.\d+)?)', text)
    if num_m:
        return round(float(num_m.group(1)), 1)

    return 0.0


def infer_session_type(power, hr, avg_lactate, max_lactate):
    """
    依乳酸值為主體、心率與功率為輔，判斷生理強度層級
    - Zone 1-2 (主動恢復 / 基礎有氧): 乳酸 < 2.0 mmol/L
    - Zone 3 (節奏有氧 / LT1 臨界): 乳酸 2.0 ~ 4.0 mmol/L
    - Zone 4 (乳酸閾值 / 無氧臨界 LT2): 乳酸 4.0 ~ 8.0 mmol/L
    - Zone 5+ (超高強度 / 無氧耐受刺激): 乳酸 > 8.0 mmol/L
    """
    la = max_lactate if max_lactate > 0 else avg_lactate
    if la >= 12.0 or hr >= 170:
        return "Zone 5+ 超高強度 (無氧耐受刺激)"
    elif la >= 8.0 or hr >= 160:
        return "Zone 5 高強度 (無氧醣解刺激)"
    elif la >= 4.0 or hr >= 148:
        return "Zone 4 閾值強度 (無氧臨界 LT2)"
    elif la >= 2.5 or hr >= 135:
        return "Zone 3 節奏耐力 (有氧閾值 LT1~LT2)"
    elif la > 0 or hr > 0:
        if (la <= 1.8 if la > 0 else True) and (hr <= 125 if hr > 0 else True):
            return "Zone 1 主動恢復 (低代謝壓力)"
        return "Zone 2 基礎有氧 (脂肪氧化/粒線體構建)"
    return "一般常規訓練"


def parse_local_html_report(fpath):
    """
    強健解析單份 lactate_report_*.html
    修正原本正則表達式跨行失靈造成心率為 0 或時長為預設值的問題
    """
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 1. 開始時間
        tm = re.search(r'活動開始時間.*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', content, re.DOTALL)
        if tm:
            st_str = tm.group(1)
        else:
            fn_m = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', os.path.basename(fpath))
            if fn_m:
                st_str = f"{fn_m.group(1)}-{fn_m.group(2)}-{fn_m.group(3)} 08:00:00"
            else:
                st_str = "2026-09-10 08:00:00"

        try:
            start_dt = datetime.strptime(st_str[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            start_dt = datetime(2026, 9, 10, 8, 0, 0)

        # 2. 活動時長
        dur_m = re.search(r'活動時長.*?<div[^>]*kpi-value[^>]*>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
        if dur_m:
            duration_min = parse_duration_to_minutes(dur_m.group(1))
        else:
            plain_dur = re.search(r'時長.*?(\d+(?:\.\d+)?)\s*分(?:\s*(\d+)\s*秒)?', content, re.DOTALL)
            if plain_dur:
                duration_min = float(plain_dur.group(1)) + (float(plain_dur.group(2))/60.0 if plain_dur.group(2) else 0)
            else:
                duration_min = 45.0

        # 3. 功率
        avg_p, max_p = 0.0, 0.0
        p_m = re.search(r'功率.*?<div[^>]*kpi-value[^>]*>.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*W', content, re.DOTALL | re.IGNORECASE)
        if p_m:
            avg_p = float(p_m.group(1))
            max_p = float(p_m.group(2))
        else:
            plain_p = re.search(r'功率.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*W', content, re.DOTALL)
            if plain_p:
                avg_p = float(plain_p.group(1))
                max_p = float(plain_p.group(2))

        # 4. 心率 (使用 re.DOTALL 解決跨行問題)
        avg_h, max_h = 0.0, 0.0
        h_m = re.search(r'心率.*?<div[^>]*kpi-value[^>]*>.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*bpm', content, re.DOTALL | re.IGNORECASE)
        if h_m:
            avg_h = float(h_m.group(1))
            max_h = float(h_m.group(2))
        else:
            plain_h = re.search(r'心率.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*bpm', content, re.DOTALL)
            if plain_h:
                avg_h = float(plain_h.group(1))
                max_h = float(plain_h.group(2))

        # 5. 乳酸採樣點解析
        la_readings = []
        table_m = re.search(r'<table[^>]*summary-table[^>]*>(.*?)</table>', content, re.DOTALL | re.IGNORECASE)
        if not table_m:
            table_m = re.search(r'<table[^>]*>(.*?)</table>', content, re.DOTALL | re.IGNORECASE)

        if table_m:
            tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_m.group(1), re.DOTALL | re.IGNORECASE)
            for tr in tr_matches:
                tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
                if len(tds) >= 2:
                    clean_vals = [re.sub(r'<.*?>', '', td).strip() for td in tds]
                    try:
                        time_pt = float(re.search(r'(\d+(?:\.\d+)?)', clean_vals[0]).group(1))
                        la_pt = float(re.search(r'(\d+(?:\.\d+)?)', clean_vals[1]).group(1))
                        if 0.4 <= la_pt <= 35.0:
                            la_readings.append({"time_min": time_pt, "lactate": la_pt})
                    except Exception:
                        pass

        # 若未從表格抓到，嘗試全文字搜尋
        if not la_readings:
            all_la_matches = re.findall(r'(\d+(?:\.\d+)?)\s*mmol/L', content)
            la_vals = [float(x) for x in all_la_matches if 0.5 <= float(x) <= 35.0]
            for i, v in enumerate(la_vals):
                la_readings.append({"time_min": round((i + 1) * (duration_min / (len(la_vals) + 1)), 1), "lactate": v})

        raw_lactates = [pt["lactate"] for pt in la_readings]
        avg_la = round(float(np.mean(raw_lactates)), 2) if raw_lactates else 0.0
        max_la = round(float(np.max(raw_lactates)), 2) if raw_lactates else 0.0
        init_la = raw_lactates[0] if raw_lactates else 0.0
        final_la = raw_lactates[-1] if raw_lactates else 0.0

        return {
            "source_file": os.path.basename(fpath),
            "start_time": start_dt,
            "date": start_dt.strftime("%m/%d"),
            "full_date": start_dt.strftime("%Y-%m-%d"),
            "duration_min": round(duration_min, 1),
            "avg_power": round(avg_p, 1),
            "max_power": round(max_p, 1),
            "avg_hr": round(avg_h, 1),
            "max_hr": round(max_h, 1),
            "lactate_readings": la_readings,
            "lactate_values": raw_lactates,
            "avg_lactate": avg_la,
            "max_lactate": max_la,
            "initial_lactate": init_la,
            "final_lactate": final_la,
            "type": infer_session_type(avg_p, avg_h, avg_la, max_la)
        }
    except Exception as e:
        print(f"解析 {fpath} 發生錯誤: {e}")
        return None


def fetch_local_dataset(folder_path="DataMindy", days_limit=7):
    """從本地資料夾載入歷史 HTML 報告並篩選最近 5~7 天數據"""
    html_files = sorted(glob.glob(os.path.join(folder_path, "lactate_report_*.html")))
    sessions = []
    for fp in html_files:
        parsed = parse_local_html_report(fp)
        if parsed and parsed.get("duration_min", 0) > 5:
            sessions.append(parsed)

    if not sessions:
        return get_benchmark_dataset()

    sessions = sorted(sessions, key=lambda x: x["start_time"])
    return sessions[-days_limit:]


def fetch_firestore_dataset(uid, token, days_limit=7):
    """
    從 Firebase Firestore 抓取登入者真實 fit_records 與 lactate_records
    """
    if not uid or not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 抓取 fit_records
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"
    fit_sessions = []
    try:
        r_fit = requests.get(fit_url, headers=headers, timeout=12)
        if r_fit.status_code == 200:
            fit_docs = r_fit.json().get("documents", [])
            for doc in fit_docs:
                f = doc.get("fields", {})
                file_name = f.get("file_name", {}).get("stringValue", "Activity")
                st_val = f.get("start_time", {}).get("timestampValue")
                start_dt = None
                if st_val:
                    try:
                        clean_ts = st_val.replace("Z", "+00:00")
                        start_dt = datetime.fromisoformat(clean_ts)
                    except Exception:
                        pass

                avg_pwr = float(f.get("avg_power", {}).get("integerValue", 0))
                max_pwr = float(f.get("max_power", {}).get("integerValue", 0))
                avg_hr = float(f.get("avg_hr", {}).get("integerValue", 0))
                max_hr = float(f.get("max_hr", {}).get("integerValue", 0))

                ts_values = f.get("time_series", {}).get("arrayValue", {}).get("values", [])
                duration_min = 0.0
                if ts_values:
                    last_pt = ts_values[-1].get("mapValue", {}).get("fields", {})
                    duration_min = float(last_pt.get("elapsed_minutes", {}).get("doubleValue", 0.0))

                fit_sessions.append({
                    "id": doc.get("name"),
                    "source_file": file_name,
                    "start_time": start_dt,
                    "duration_min": round(duration_min, 1) if duration_min > 0 else 45.0,
                    "avg_power": round(avg_pwr, 1),
                    "max_power": round(max_pwr, 1),
                    "avg_hr": round(avg_hr, 1),
                    "max_hr": round(max_hr, 1),
                    "lactate_readings": []
                })
    except Exception as e:
        print(f"Error fetching fit_records from Firestore: {e}")

    # 2. 抓取 lactate_records
    la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records"
    all_lactate = []
    try:
        r_la = requests.get(la_url, headers=headers, timeout=12)
        if r_la.status_code == 200:
            la_docs = r_la.json().get("documents", [])
            for doc in la_docs:
                f = doc.get("fields", {})
                year = int(f.get("year", {}).get("integerValue", 0))
                month = int(f.get("month", {}).get("integerValue", 0))
                day = int(f.get("day", {}).get("integerValue", 0))
                hour = int(f.get("hour", {}).get("integerValue", 0))
                minute = int(f.get("minute", {}).get("integerValue", 0))
                final_la_obj = f.get("final_la_mmol", {})
                final_la = float(final_la_obj.get("doubleValue", final_la_obj.get("integerValue", 0)))
                
                if year > 0:
                    full_year = year + 2000 if year < 100 else year
                    try:
                        rec_dt = datetime(full_year, month, day, hour, minute)
                        all_lactate.append({
                            "record_time": rec_dt,
                            "lactate_mmol": final_la
                        })
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error fetching lactate_records from Firestore: {e}")

    # 3. 配對乳酸數據
    for s in fit_sessions:
        s_time = s["start_time"]
        matched_la = []
        if s_time:
            s_naive = s_time.replace(tzinfo=None)
            dur = s["duration_min"]
            for la in all_lactate:
                diff_min = (la["record_time"] - s_naive).total_seconds() / 60.0
                if -30 <= diff_min <= (dur + 45):
                    matched_la.append({"time_min": max(0, round(diff_min, 1)), "lactate": la["lactate_mmol"]})
        
        raw_las = [x["lactate"] for x in matched_la]
        s["lactate_readings"] = matched_la
        s["lactate_values"] = raw_las
        s["avg_lactate"] = round(float(np.mean(raw_las)), 2) if raw_las else 0.0
        s["max_lactate"] = round(float(np.max(raw_las)), 2) if raw_las else 0.0
        s["initial_lactate"] = raw_las[0] if raw_las else 0.0
        s["final_lactate"] = raw_las[-1] if raw_las else 0.0
        s["date"] = s_time.strftime("%m/%d") if s_time else "近期"
        s["full_date"] = s_time.strftime("%Y-%m-%d") if s_time else "2026-09-10"
        s["type"] = infer_session_type(s["avg_power"], s["avg_hr"], s["avg_lactate"], s["max_lactate"])

    valid = [s for s in fit_sessions if s["start_time"] is not None]
    valid = sorted(valid, key=lambda x: x["start_time"])
    return valid[-days_limit:] if valid else get_benchmark_dataset()


def calculate_comprehensive_load(sessions):
    """
    計算運動生理學綜合負荷與代謝動力學指標
    """
    if not sessions:
        return {}

    total_duration_min = sum(s.get("duration_min", 0) for s in sessions)
    total_hours = round(total_duration_min / 60.0, 1)

    total_lactate_load = 0.0
    zone_duration = {"Z1_2_Aerobic": 0.0, "Z3_Tempo": 0.0, "Z4_Threshold": 0.0, "Z5_Anaerobic": 0.0}

    for s in sessions:
        dur_hrs = s.get("duration_min", 0) / 60.0
        la = s.get("max_lactate", 0) if s.get("max_lactate", 0) > 0 else s.get("avg_lactate", 0)
        
        if la < 2.0:
            weight = 1.0
            zone_duration["Z1_2_Aerobic"] += s.get("duration_min", 0)
        elif la < 4.0:
            weight = 1.6
            zone_duration["Z3_Tempo"] += s.get("duration_min", 0)
        elif la < 8.0:
            weight = 2.8
            zone_duration["Z4_Threshold"] += s.get("duration_min", 0)
        else:
            weight = 4.2
            zone_duration["Z5_Anaerobic"] += s.get("duration_min", 0)

        intensity_boost = 1.0
        if s.get("avg_hr", 0) > 155:
            intensity_boost += 0.2
        if s.get("avg_power", 0) > 200:
            intensity_boost += 0.2

        session_load = round(dur_hrs * 100.0 * weight * intensity_boost, 1)
        s["calculated_load"] = session_load
        total_lactate_load += session_load

    zone_pct = {}
    if total_duration_min > 0:
        for k, v in zone_duration.items():
            zone_pct[k] = round((v / total_duration_min) * 100.0, 1)
    else:
        zone_pct = {"Z1_2_Aerobic": 0.0, "Z3_Tempo": 0.0, "Z4_Threshold": 0.0, "Z5_Anaerobic": 0.0}

    efficiency_trend = []
    for s in sessions:
        p = s.get("avg_power", 0)
        h = s.get("avg_hr", 0)
        la = s.get("avg_lactate", 0) if s.get("avg_lactate", 0) > 0 else 1.0
        
        if p > 0:
            eff = round(p / la, 1)  # W per mmol
            unit = "W/mmol"
        elif h > 0:
            eff = round(h / la, 1)  # bpm per mmol
            unit = "bpm/mmol"
        else:
            eff = 0.0
            unit = "N/A"
        s["metabolic_efficiency"] = eff
        s["efficiency_unit"] = unit
        efficiency_trend.append(eff)

    eff_delta_pct = 0.0
    latest = sessions[-1]
    if len(sessions) >= 2 and latest.get("metabolic_efficiency", 0) > 0:
        prior_effs = [s["metabolic_efficiency"] for s in sessions[:-1] if s.get("metabolic_efficiency", 0) > 0]
        if prior_effs:
            mean_prior = np.mean(prior_effs)
            eff_delta_pct = round(((latest["metabolic_efficiency"] - mean_prior) / mean_prior) * 100.0, 1)

    high_la_minutes = 0.0
    for s in sessions:
        if s.get("max_lactate", 0) >= 4.0:
            high_la_ratio = min(1.0, (s["max_lactate"] - 3.5) / 10.0)
            high_la_minutes += s.get("duration_min", 0) * high_la_ratio

    if total_lactate_load >= 650 or high_la_minutes >= 60 or latest.get("avg_lactate", 0) >= 10.0:
        recovery_state = "高代謝疲勞 (需主動排酸/低強度修復)"
        state_color = "#ff5252"
        recommended_action = "限制強度在 Zone 1~2，乳酸嚴格控制在 2.0 mmol/L 以下，加速組織清理與肝醣回補。"
    elif total_lactate_load >= 400 or latest.get("avg_lactate", 0) >= 7.0:
        recovery_state = "良性累積疲勞 (適應刺激期)"
        state_color = "#ffab00"
        recommended_action = "維持中等負荷，可進行技術性微間歇或節奏耐力，監控乳酸平穩度。"
    else:
        recovery_state = "恢復充足 (處於超補償/突破窗口)"
        state_color = "#00e676"
        recommended_action = "神經與代謝狀態優異，具備進行高質量閾值測試或高強度間歇的生理儲備。"

    return {
        "period_start": sessions[0]["full_date"],
        "period_end": sessions[-1]["full_date"],
        "session_count": len(sessions),
        "total_duration_min": round(total_duration_min, 1),
        "total_hours": total_hours,
        "total_lactate_load": round(total_lactate_load, 1),
        "peak_lactate_week": max([s.get("max_lactate", 0) for s in sessions]),
        "avg_lactate_week": round(float(np.mean([s.get("avg_lactate", 0) for s in sessions])), 2),
        "zone_duration_min": zone_duration,
        "zone_percentage": zone_pct,
        "high_lactate_minutes": round(high_la_minutes, 1),
        "latest_efficiency": latest.get("metabolic_efficiency", 0),
        "efficiency_unit": latest.get("efficiency_unit", "W/mmol"),
        "efficiency_delta_pct": eff_delta_pct,
        "recovery_state": recovery_state,
        "state_color": state_color,
        "recommended_action": recommended_action,
        "sessions": sessions
    }


def get_benchmark_dataset():
    """標準基準模擬數據（完整 5 場，包含真實心率、功率與採樣乳酸）"""
    return [
        {
            "source_file": "2026-08-31-mock.html",
            "start_time": datetime(2026, 8, 31, 20, 14),
            "date": "08/31",
            "full_date": "2026-08-31",
            "duration_min": 56.3,
            "avg_power": 178.0,
            "max_power": 240.0,
            "avg_hr": 138.0,
            "max_hr": 158.0,
            "lactate_readings": [{"time_min": 15, "lactate": 2.2}, {"time_min": 35, "lactate": 5.4}, {"time_min": 50, "lactate": 7.22}],
            "lactate_values": [2.2, 5.4, 7.22],
            "avg_lactate": 4.95,
            "max_lactate": 7.22,
            "initial_lactate": 2.2,
            "final_lactate": 7.22,
            "type": "Zone 3 節奏耐力 (有氧閾值 LT1~LT2)"
        },
        {
            "source_file": "2026-09-02-mock.html",
            "start_time": datetime(2026, 9, 2, 19, 30),
            "date": "09/02",
            "full_date": "2026-09-02",
            "duration_min": 42.0,
            "avg_power": 195.0,
            "max_power": 275.0,
            "avg_hr": 162.0,
            "max_hr": 182.0,
            "lactate_readings": [{"time_min": 10, "lactate": 3.5}, {"time_min": 25, "lactate": 9.8}, {"time_min": 40, "lactate": 25.5}],
            "lactate_values": [3.5, 9.8, 25.5],
            "avg_lactate": 12.93,
            "max_lactate": 25.5,
            "initial_lactate": 3.5,
            "final_lactate": 25.5,
            "type": "Zone 5+ 超高強度 (無氧耐受刺激)"
        },
        {
            "source_file": "2026-09-08-mock.html",
            "start_time": datetime(2026, 9, 8, 19, 45),
            "date": "09/08",
            "full_date": "2026-09-08",
            "duration_min": 33.1,
            "avg_power": 189.0,
            "max_power": 255.0,
            "avg_hr": 159.0,
            "max_hr": 181.0,
            "lactate_readings": [{"time_min": 10, "lactate": 4.2}, {"time_min": 20, "lactate": 11.5}, {"time_min": 32, "lactate": 17.1}],
            "lactate_values": [4.2, 11.5, 17.1],
            "avg_lactate": 10.93,
            "max_lactate": 17.1,
            "initial_lactate": 4.2,
            "final_lactate": 17.1,
            "type": "Zone 5 高強度 (無氧醣解刺激)"
        },
        {
            "source_file": "2026-09-09-mock.html",
            "start_time": datetime(2026, 9, 9, 21, 37),
            "date": "09/09",
            "full_date": "2026-09-09",
            "duration_min": 45.0,
            "avg_power": 140.0,
            "max_power": 180.0,
            "avg_hr": 124.0,
            "max_hr": 139.0,
            "lactate_readings": [{"time_min": 15, "lactate": 1.6}, {"time_min": 30, "lactate": 1.9}, {"time_min": 45, "lactate": 2.1}],
            "lactate_values": [1.6, 1.9, 2.1],
            "avg_lactate": 1.87,
            "max_lactate": 2.1,
            "initial_lactate": 1.6,
            "final_lactate": 2.1,
            "type": "Zone 1 主動恢復 (低代謝壓力)"
        },
        {
            "source_file": "2026-09-10-mock.html",
            "start_time": datetime(2026, 9, 10, 19, 54),
            "date": "09/10",
            "full_date": "2026-09-10",
            "duration_min": 60.0,
            "avg_power": 196.9,
            "max_power": 282.0,
            "avg_hr": 149.6,
            "max_hr": 160.0,
            "lactate_readings": [{"time_min": 15, "lactate": 3.8}, {"time_min": 35, "lactate": 6.8}, {"time_min": 58, "lactate": 10.5}],
            "lactate_values": [3.8, 6.8, 10.5],
            "avg_lactate": 7.03,
            "max_lactate": 10.5,
            "initial_lactate": 3.8,
            "final_lactate": 10.5,
            "type": "Zone 4 閾值強度 (無氧臨界 LT2)"
        }
    ]
