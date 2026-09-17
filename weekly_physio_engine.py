# -*- coding: utf-8 -*-
"""
weekly_physio_engine.py
汗乳酸 (Sweat Lactate) 運動生理學與跨期負荷運算核心引擎

領域特性：
1. 監控對象為【汗乳酸 (Sweat Lactate)】，數值尺度不可與侵入式血乳酸（2.0/4.0 mmol/L）一概而論。
   汗乳酸數值常在 5 ~ 25+ mmol/L，需以受測者個人相對歷史 Baseline 與動態分佈評估。
2. 支援以「實際訓練場次（Sessions）」為主軸，不侷限於連續 5~7 天，時間跨度可橫跨 2~4 週甚至整個月。
3. 精確計算「相鄰場次間隔天數 (Rest/Interval Days)」，探討休息充分度對汗乳酸生成的影響。
4. 核心分析：縱向對比各場次的「平均功率 / 平均心率」與「汗乳酸濃度」，評估代謝經濟性（W/mmol, bpm/mmol）與疲勞累積。
"""

import os
import re
import glob
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import requests


_FIT_SPORT_CACHE = None

def get_workspace_fit_sport_cache():
    """
    掃描本地工作區所有已知 FIT 檔案，提取原生官方 sport 與 sub_sport，
    建立以檔名為鍵的索引表，以達到 100% 精準匹配。
    """
    global _FIT_SPORT_CACHE
    if _FIT_SPORT_CACHE is not None:
        return _FIT_SPORT_CACHE
        
    cache = {}
    try:
        import fitparse
        search_dirs = [".", "DataYen", "DataMindy", "DataSunday", "0521", "RunDataRead"]
        seen_files = set()
        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.endswith('.fit') and f not in seen_files:
                        seen_files.add(f)
                        p = os.path.join(root, f)
                        try:
                            fit = fitparse.FitFile(p)
                            sp = None
                            sub = 'generic'
                            for m in fit.get_messages('sport'):
                                vals = {x.name: x.value for x in m.fields}
                                if vals.get('sport'):
                                    sp = str(vals.get('sport')).lower()
                                    if vals.get('sub_sport'):
                                        sub = str(vals.get('sub_sport')).lower()
                            if not sp:
                                for m in fit.get_messages('session'):
                                    vals = {x.name: x.value for x in m.fields}
                                    if vals.get('sport'):
                                        sp = str(vals.get('sport')).lower()
                                        if vals.get('sub_sport'):
                                            sub = str(vals.get('sub_sport')).lower()
                            if sp:
                                cache[f] = (sp, sub)
                                cache[f.replace('.fit', '')] = (sp, sub)
                        except Exception:
                            pass
    except Exception:
        pass
        
    _FIT_SPORT_CACHE = cache
    return _FIT_SPORT_CACHE


def resolve_sport_type(filename_or_text, avg_power=0, avg_hr=0, cadence=0, default_sport=None):
    """
    結合 FIT 檔官方資訊、檔名關鍵字、步頻特徵與功率水準綜合研判真實運動專項。
    """
    fn_clean = os.path.basename(str(filename_or_text)).strip()
    
    # 1. 優先從 FIT 檔官方快取查詢
    cache = get_workspace_fit_sport_cache()
    m_fit = re.search(r'([\w\-]+\.fit)', fn_clean, re.IGNORECASE)
    if m_fit and m_fit.group(1) in cache:
        return cache[m_fit.group(1)]
    if fn_clean in cache:
        return cache[fn_clean]
    
    # 2. 檢查檔名與文字中的明確關鍵字
    txt_lower = fn_clean.lower()
    if any(k in txt_lower for k in ['run', '跑步', '慢跑', '路跑', 'treadmill']):
        return ('running', 'generic')
    if any(k in txt_lower for k in ['bike', 'cycling', '自行車', '騎行', '單車', '飛輪', 'indoor_cycling']):
        return ('cycling', 'indoor_cycling')
        
    # 3. 檢查步頻 (Cadence): 跑步步頻通常在 140~200，自行車踏頻在 60~110
    if cadence > 130:
        return ('running', 'generic')
    if 40 <= cadence <= 120 and avg_power > 0:
        return ('cycling', 'indoor_cycling')
        
    # 4. 如果已有明確的 default_sport (且非 unknown)
    if default_sport and default_sport not in ['unknown', 'None', '']:
        return (default_sport, 'generic')
        
    # 5. 特徵啟發判斷：若功率極高 (例如 >=260W) 且心率很高 (>=145bpm)，常為 Stryd 跑步功率計
    # 自行車飛輪受試者功率多在 100~150W
    if avg_power >= 260 and avg_hr >= 145:
        return ('running', 'generic')
        
    if avg_power > 0 and avg_power < 250:
        return ('cycling', 'indoor_cycling')
        
    return ('running', 'generic')


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


def infer_session_type_sweat(power, hr, avg_lactate, max_lactate, baseline_low=6.0, baseline_high=15.0):
    """
    根據受測者的汗乳酸動態範圍與心率/功率推斷強度層級
    汗乳酸特性：
    - 低濃度區 (主動恢復 / 基礎代謝): 汗乳酸 <= baseline_low
    - 中等濃度區 (節奏耐力 / 穩定有氧): baseline_low < 汗乳酸 <= baseline_high
    - 高濃度區 (高醣解刺激 / 無氧耐受): 汗乳酸 > baseline_high
    """
    la = max_lactate if max_lactate > 0 else avg_lactate
    
    if la >= (baseline_high * 1.3) or hr >= 170:
        return "超高代謝負荷 (強烈醣解/無氧耐受刺激)"
    elif la >= baseline_high or hr >= 158:
        return "高代謝負荷 (高糖解輸出/閾值刺激)"
    elif la >= baseline_low or hr >= 140:
        return "中等代謝負荷 (節奏耐力/穩定有氧)"
    elif la > 0 or hr > 0:
        if hr <= 125 or la <= baseline_low:
            return "低代謝負荷 (主動排酸/低強度修復)"
        return "基礎有氧負荷 (脂肪氧化/有氧構建)"
    return "常規運動訓練"


def parse_local_html_report(fpath):
    """
    強健解析單份 lactate_report_*.html 獲取汗乳酸與運動指標
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
        if not dur_m:
            dur_m = re.search(r'活動時長.*?<div[^>]*metric-value[^>]*>(.*?)</div>', content, re.DOTALL | re.IGNORECASE)
        if dur_m:
            duration_min = parse_duration_to_minutes(dur_m.group(1))
        else:
            plain_dur = re.search(r'時長.*?(\d+(?:\.\d+)?)\s*分(?:\s*(\d+)\s*秒)?', content, re.DOTALL)
            if plain_dur:
                duration_min = float(plain_dur.group(1)) + (float(plain_dur.group(2))/60.0 if plain_dur.group(2) else 0)
            else:
                duration_min = 0.0

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

        # 4. 心率
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

        # 5. 汗乳酸採樣點解析
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
                        if 0.2 <= la_pt <= 60.0:  # 汗乳酸範圍寬廣，可達更高濃度
                            la_readings.append({"time_min": time_pt, "lactate": la_pt})
                    except Exception:
                        pass

        if not la_readings:
            all_la_matches = re.findall(r'(\d+(?:\.\d+)?)\s*mmol/L', content)
            la_vals = [float(x) for x in all_la_matches if 0.4 <= float(x) <= 60.0]
            for i, v in enumerate(la_vals):
                la_readings.append({"time_min": round((i + 1) * (duration_min / (len(la_vals) + 1)), 1), "lactate": v})

        raw_lactates = [pt["lactate"] for pt in la_readings]
        avg_la = round(float(np.mean(raw_lactates)), 2) if raw_lactates else 0.0
        max_la = round(float(np.max(raw_lactates)), 2) if raw_lactates else 0.0
        init_la = raw_lactates[0] if raw_lactates else 0.0
        final_la = raw_lactates[-1] if raw_lactates else 0.0

        # 若時長未成功抓取或為 0，且有乳酸時間點，以最大乳酸時間點校正時長
        if duration_min <= 0 and la_readings:
            max_la_pt_time = max([pt["time_min"] for pt in la_readings])
            if max_la_pt_time > 0:
                duration_min = round(max_la_pt_time, 1)
        if duration_min <= 0:
            duration_min = 60.0

        # 6. 解析運動類型 (sport, sub_sport)
        fit_match = re.search(r'([\w\-]+\.fit)', content, re.IGNORECASE)
        ref_fn = fit_match.group(1) if fit_match else os.path.basename(fpath)
        sport, sub_sport = resolve_sport_type(ref_fn, avg_power=avg_p, avg_hr=avg_h)

        sport_icon_map = {
            'cycling': ('🚴 自行車', '#00f2fe'),
            'running': ('🏃 跑步', '#ff5252'),
            'swimming': ('🏊 游泳', '#4facfe'),
            'walking': ('🚶 健走', '#00e676'),
            'generic': ('🏅 綜合訓練', '#ffab00'),
            'unknown': ('🎯 運動紀錄', '#94a3b8')
        }
        sport_display, sport_color = sport_icon_map.get(sport, (f"🏅 {sport.capitalize()}", "#ffab00"))

        return {
            "source_file": os.path.basename(fpath),
            "start_time": start_dt,
            "date": start_dt.strftime("%m/%d"),
            "full_date": start_dt.strftime("%Y-%m-%d"),
            "duration_min": round(duration_min, 1),
            "sport": sport,
            "sub_sport": sub_sport,
            "sport_display": sport_display,
            "sport_color": sport_color,
            "avg_power": round(avg_p, 1),
            "max_power": round(max_p, 1),
            "avg_hr": round(avg_h, 1),
            "max_hr": round(max_h, 1),
            "lactate_readings": la_readings,
            "lactate_values": raw_lactates,
            "avg_lactate": avg_la,
            "max_lactate": max_la,
            "initial_lactate": init_la,
            "final_lactate": final_la
        }
    except Exception as e:
        print(f"解析 {fpath} 發生錯誤: {e}")
        return None


def fetch_local_dataset(folder_path="DataMindy", session_limit=7, sport_filter="all"):
    """
    從本地資料夾載入歷史 HTML 報告，篩選最近有效訓練場次 (Sessions)
    以實際運動日為準，不限定連續天數；支援依運動專項 (sport_filter) 進行分流篩選
    """
    html_files = sorted(glob.glob(os.path.join(folder_path, "lactate_report_*.html")))
    sessions = []
    for fp in html_files:
        parsed = parse_local_html_report(fp)
        if parsed and parsed.get("duration_min", 0) > 5:
            sessions.append(parsed)

    if not sessions:
        return get_benchmark_dataset()

    # 依運動專項篩選
    if sport_filter and sport_filter != "all":
        sessions = [s for s in sessions if s.get("sport") == sport_filter]

    if not sessions:
        # 若該專項無紀錄，回傳空清單讓外層提示
        return []

    sessions = sorted(sessions, key=lambda x: x["start_time"])
    return sessions[-session_limit:]


def fetch_firestore_dataset(uid, token, session_limit=7, sport_filter="all"):
    """
    從 Firebase Firestore 抓取登入者真實歷史訓練與汗乳酸紀錄，支援依運動專項篩選
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

                def _get_fs_val(obj, default=0.0):
                    if not obj:
                        return default
                    if "doubleValue" in obj:
                        return float(obj["doubleValue"])
                    if "integerValue" in obj:
                        return float(obj["integerValue"])
                    return default

                avg_pwr = _get_fs_val(f.get("avg_power", {}), 0.0)
                max_pwr = _get_fs_val(f.get("max_power", {}), 0.0)
                avg_hr = _get_fs_val(f.get("avg_hr", {}), 0.0)
                max_hr = _get_fs_val(f.get("max_hr", {}), 0.0)

                # 讀取運動專項 (sport / sub_sport) 並透過工作區快取與特徵進行智能校正
                raw_sport = f.get("sport", {}).get("stringValue")
                raw_sub = f.get("sub_sport", {}).get("stringValue")
                
                sport, sub_sport = resolve_sport_type(
                    file_name,
                    avg_power=avg_pwr,
                    avg_hr=avg_hr,
                    default_sport=raw_sport
                )
                if raw_sub and sub_sport == 'generic':
                    sub_sport = raw_sub

                sport_icon_map = {
                    'cycling': ('🚴 自行車', '#00f2fe'),
                    'running': ('🏃 跑步', '#ff5252'),
                    'swimming': ('🏊 游泳', '#4facfe'),
                    'walking': ('🚶 健走', '#00e676'),
                    'generic': ('🏅 綜合訓練', '#ffab00'),
                    'unknown': ('🎯 運動紀錄', '#94a3b8')
                }
                sport_display, sport_color = sport_icon_map.get(sport, (f"🏅 {sport.capitalize()}", "#ffab00"))

                ts_values = f.get("time_series", {}).get("arrayValue", {}).get("values", [])
                # 1. 優先取頂層 duration_minutes
                duration_min = _get_fs_val(f.get("duration_minutes", {}), 0.0)
                # 2. 次優先取 time_series 最後一點
                if duration_min <= 0 and ts_values:
                    last_pt = ts_values[-1].get("mapValue", {}).get("fields", {})
                    duration_min = _get_fs_val(last_pt.get("elapsed_minutes", {}), 0.0)

                fit_sessions.append({
                    "id": doc.get("name"),
                    "source_file": file_name,
                    "start_time": start_dt,
                    "duration_min": round(duration_min, 1),
                    "sport": sport,
                    "sub_sport": sub_sport,
                    "sport_display": sport_display,
                    "sport_color": sport_color,
                    "avg_power": round(avg_pwr, 1),
                    "max_power": round(max_pwr, 1),
                    "avg_hr": round(avg_hr, 1),
                    "max_hr": round(max_hr, 1),
                    "has_gps": f.get("has_gps", {}).get("booleanValue", False),
                    "total_distance_m": _get_fs_val(f.get("total_distance_m", {}), 0.0),
                    "min_altitude": _get_fs_val(f.get("min_altitude", {}), 0.0),
                    "max_altitude": _get_fs_val(f.get("max_altitude", {}), 0.0),
                    "lactate_readings": []
                })
    except Exception as e:
        print(f"Error fetching fit_records: {e}")

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
        print(f"Error fetching lactate_records: {e}")

    # 3. 配對汗乳酸數據
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
        s["date"] = s_time.strftime("%m/%d") if s_time else "近期"
        s["full_date"] = s_time.strftime("%Y-%m-%d") if s_time else "2026-09-10"

        # 校正運動時長：若 duration_min 缺失 (<= 0) 或明顯小於乳酸測試點時間，以乳酸採樣最大時間點校正為真實時長
        if matched_la:
            max_la_t = max([x["time_min"] for x in matched_la])
            if s["duration_min"] <= 0 or s["duration_min"] < max_la_t or (s["duration_min"] == 45.0 and max_la_t > 40.0):
                s["duration_min"] = round(max_la_t, 1)
        if s["duration_min"] <= 0:
            s["duration_min"] = 60.0

    valid = [s for s in fit_sessions if s["start_time"] is not None]
    
    # 依運動專項篩選
    if sport_filter and sport_filter != "all":
        valid = [s for s in valid if s.get("sport") == sport_filter]

    valid = sorted(valid, key=lambda x: x["start_time"])
    return valid[-session_limit:] if valid else []


def calculate_comprehensive_load(sessions):
    """
    計算運動生理學綜合負荷、汗乳酸動力學、真實間隔天數與代謝經濟性指標
    """
    if not sessions:
        return {}

    # 1. 計算相鄰兩場訓練之間的真實間隔天數 (Days since prior session)
    for i, s in enumerate(sessions):
        if i == 0:
            s["days_since_prior"] = None  # 第一場無前置對比
            s["interval_desc"] = "首場基準"
        else:
            prev_dt = sessions[i - 1]["start_time"]
            curr_dt = s["start_time"]
            diff_days = round((curr_dt - prev_dt).total_seconds() / 86400.0, 1)
            s["days_since_prior"] = diff_days
            if diff_days <= 1.0:
                s["interval_desc"] = "連日訓練 (背靠背)"
            elif diff_days <= 3.0:
                s["interval_desc"] = f"間隔 {diff_days:.0f} 天"
            else:
                s["interval_desc"] = f"充分休整 (隔 {diff_days:.0f} 天)"

    # 總跨越天數
    time_span_days = (sessions[-1]["start_time"] - sessions[0]["start_time"]).days + 1
    total_duration_min = sum(s.get("duration_min", 0) for s in sessions)
    total_hours = round(total_duration_min / 60.0, 1)

    # 2. 分析受測者本週期的個人汗乳酸動態範圍 (Relative Sweat Lactate Range)
    all_las = [s.get("avg_lactate", 0) for s in sessions if s.get("avg_lactate", 0) > 0]
    if all_las:
        min_la = min(all_las)
        max_la = max([s.get("max_lactate", 0) for s in sessions])
        median_la = float(np.median(all_las))
    else:
        min_la, max_la, median_la = 2.0, 15.0, 7.0

    baseline_low = round(min_la * 1.35, 1)      # 低代謝壓力門檻
    baseline_high = round(median_la * 1.35, 1)   # 高糖解刺激門檻

    # 分析本週期專項組成 (Sport Breakdown)
    sport_counts = {}
    for s in sessions:
        sp = s.get("sport", "cycling")
        sport_counts[sp] = sport_counts.get(sp, 0) + 1
        
    dominant_sport = max(sport_counts, key=sport_counts.get) if sport_counts else "cycling"
    is_pure_cycling = len(sport_counts) == 1 and "cycling" in sport_counts
    is_pure_running = len(sport_counts) == 1 and "running" in sport_counts
    is_mixed_sports = len(sport_counts) > 1

    # 檢查功率是否完整（若有任一場次缺失或完全無功率，即判定為功率有缺失）
    has_full_power = (
        len(sessions) > 0
        and all(
            s.get("avg_power") is not None
            and float(s.get("avg_power", 0)) > 0
            and not np.isnan(float(s.get("avg_power", 0)))
            for s in sessions
        )
    )

    # 3. 為每場次標定汗乳酸強度等級，並計算代謝效率比
    efficiency_trend = []
    for s in sessions:
        s["type"] = infer_session_type_sweat(
            s.get("avg_power", 0) if has_full_power else 0,
            s.get("avg_hr", 0),
            s.get("avg_lactate", 0),
            s.get("max_lactate", 0),
            baseline_low=baseline_low,
            baseline_high=baseline_high
        )
        
        # 代謝經濟性 (Output per Sweat Lactate)
        p = s.get("avg_power", 0)
        h = s.get("avg_hr", 0)
        la = s.get("avg_lactate", 0) if s.get("avg_lactate", 0) > 0 else 1.0
        
        # 若功率有缺失，直接統一用心率 (bpm/mmol) 做比較，保持跨場次評估單位一致且不秀功率
        if has_full_power and p > 0:
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

    # 4. 代謝效率變化率 (最新場次 vs 前期場次)
    eff_delta_pct = 0.0
    latest = sessions[-1]
    if len(sessions) >= 2 and latest.get("metabolic_efficiency", 0) > 0:
        prior_effs = [s["metabolic_efficiency"] for s in sessions[:-1] if s.get("metabolic_efficiency", 0) > 0]
        if prior_effs:
            mean_prior = np.mean(prior_effs)
            eff_delta_pct = round(((latest["metabolic_efficiency"] - mean_prior) / mean_prior) * 100.0, 1)

    # 5. 汗乳酸加權負荷積分與極化區間計算
    total_sweat_load = 0.0
    zone_duration = {"Low_Recovery": 0.0, "Tempo_Aerobic": 0.0, "High_Glycolytic": 0.0}

    for s in sessions:
        dur_hrs = s.get("duration_min", 0) / 60.0
        la = s.get("avg_lactate", 0)
        
        if la <= baseline_low:
            w = 1.0
            zone_duration["Low_Recovery"] += s.get("duration_min", 0)
        elif la <= baseline_high:
            w = 1.8
            zone_duration["Tempo_Aerobic"] += s.get("duration_min", 0)
        else:
            w = 3.5
            zone_duration["High_Glycolytic"] += s.get("duration_min", 0)

        # 間隔天數微調係數：若連日運動（間隔<=1天），疲勞累積加成
        interval_factor = 1.2 if (s.get("days_since_prior") is not None and s.get("days_since_prior") <= 1.0) else 1.0
        
        session_load = round(dur_hrs * 100.0 * w * interval_factor, 1)
        s["calculated_load"] = session_load
        total_sweat_load += session_load

    zone_pct = {}
    if total_duration_min > 0:
        for k, v in zone_duration.items():
            zone_pct[k] = round((v / total_duration_min) * 100.0, 1)
    else:
        zone_pct = {"Low_Recovery": 0.0, "Tempo_Aerobic": 0.0, "High_Glycolytic": 0.0}

    # 6. 疲勞與恢復狀態判定 (結合最新場次間隔天數與汗乳酸水平)
    days_since_last = latest.get("days_since_prior", 2.0) or 2.0
    latest_la = latest.get("avg_lactate", 0)

    if (days_since_last <= 1.0 and latest_la >= baseline_high) or total_sweat_load >= 1200:
        recovery_state = "高代謝累積疲勞 (連日刺激/需排酸修復)"
        state_color = "#ff5252"
        recommended_action = "近期間隔密集或高酸負荷累積，建議安排 1~2 天超低強度主動恢復（有助促進汗腺與局部循環代謝物排出），或徹底休息。"
    elif eff_delta_pct >= 15.0 and latest_la <= baseline_high:
        recovery_state = "代謝適應優異 (處於超補償突破期)"
        state_color = "#00e676"
        recommended_action = "在相同或更高負荷下汗乳酸明顯收斂，有氧經濟性與抗疲勞性提升，可維持規律進展課表。"
    else:
        recovery_state = "良性代謝適應 (負荷平穩)"
        state_color = "#ffab00"
        recommended_action = "生理指標維持平穩，汗乳酸與心率功率呈現穩定對應，可按預定節奏進行課表。"

    return {
        "period_start": sessions[0]["full_date"],
        "period_end": sessions[-1]["full_date"],
        "time_span_days": time_span_days,
        "session_count": len(sessions),
        "total_duration_min": round(total_duration_min, 1),
        "total_hours": total_hours,
        "total_sweat_load": round(total_sweat_load, 1),
        "peak_sweat_lactate": max_la,
        "avg_sweat_lactate": round(float(np.mean(all_las)), 2) if all_las else 0.0,
        "min_sweat_lactate": min_la,
        "baseline_low": baseline_low,
        "baseline_high": baseline_high,
        "zone_duration_min": zone_duration,
        "zone_percentage": zone_pct,
        "latest_efficiency": latest.get("metabolic_efficiency", 0),
        "efficiency_unit": latest.get("efficiency_unit", "W/mmol"),
        "efficiency_delta_pct": eff_delta_pct,
        "days_since_prior": days_since_last,
        "has_full_power": has_full_power,
        "intensity_label": "平均功率 (W)" if has_full_power else "平均心率 (bpm)",
        "recovery_state": recovery_state,
        "state_color": state_color,
        "recommended_action": recommended_action,
        "sport_counts": sport_counts,
        "dominant_sport": dominant_sport,
        "is_pure_cycling": is_pure_cycling,
        "is_pure_running": is_pure_running,
        "is_mixed_sports": is_mixed_sports,
        "sessions": sessions
    }


def get_benchmark_dataset():
    """標準基準模擬數據（跨月 5 場，包含真實心率、功率與採樣汗乳酸）"""
    return [
        {
            "source_file": "2026-08-22-mock.html",
            "start_time": datetime(2026, 8, 22, 7, 32),
            "date": "08/22",
            "full_date": "2026-08-22",
            "duration_min": 32.1,
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "sport_display": "🚴 自行車",
            "sport_color": "#00f2fe",
            "avg_power": 186.7,
            "max_power": 245.0,
            "avg_hr": 152.9,
            "max_hr": 178.0,
            "lactate_readings": [{"time_min": 10, "lactate": 14.5}, {"time_min": 30, "lactate": 18.3}],
            "lactate_values": [14.5, 18.3],
            "avg_lactate": 16.4,
            "max_lactate": 18.3,
            "initial_lactate": 14.5,
            "final_lactate": 18.3
        },
        {
            "source_file": "2026-08-26-mock.html",
            "start_time": datetime(2026, 8, 26, 18, 30),
            "date": "08/26",
            "full_date": "2026-08-26",
            "duration_min": 41.7,
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "sport_display": "🚴 自行車",
            "sport_color": "#00f2fe",
            "avg_power": 184.3,
            "max_power": 230.0,
            "avg_hr": 132.1,
            "max_hr": 155.0,
            "lactate_readings": [{"time_min": 15, "lactate": 8.5}, {"time_min": 35, "lactate": 10.0}],
            "lactate_values": [8.5, 10.0],
            "avg_lactate": 9.25,
            "max_lactate": 10.0,
            "initial_lactate": 8.5,
            "final_lactate": 10.0
        },
        {
            "source_file": "2026-08-29-mock.html",
            "start_time": datetime(2026, 8, 29, 5, 51),
            "date": "08/29",
            "full_date": "2026-08-29",
            "duration_min": 96.1,
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "sport_display": "🚴 自行車",
            "sport_color": "#00f2fe",
            "avg_power": 194.0,
            "max_power": 260.0,
            "avg_hr": 151.6,
            "max_hr": 182.0,
            "lactate_readings": [{"time_min": 25, "lactate": 11.2}, {"time_min": 60, "lactate": 15.6}, {"time_min": 90, "lactate": 19.7}],
            "lactate_values": [11.2, 15.6, 19.7],
            "avg_lactate": 15.5,
            "max_lactate": 19.7,
            "initial_lactate": 11.2,
            "final_lactate": 19.7
        },
        {
            "source_file": "2026-09-08-mock.html",
            "start_time": datetime(2026, 9, 8, 19, 45),
            "date": "09/08",
            "full_date": "2026-09-08",
            "duration_min": 33.1,
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "sport_display": "🚴 自行車",
            "sport_color": "#00f2fe",
            "avg_power": 189.0,
            "max_power": 255.0,
            "avg_hr": 159.0,
            "max_hr": 181.0,
            "lactate_readings": [{"time_min": 10, "lactate": 9.8}, {"time_min": 25, "lactate": 14.5}, {"time_min": 32, "lactate": 17.1}],
            "lactate_values": [9.8, 14.5, 17.1],
            "avg_lactate": 13.8,
            "max_lactate": 17.1,
            "initial_lactate": 9.8,
            "final_lactate": 17.1
        },
        {
            "source_file": "2026-09-10-mock.html",
            "start_time": datetime(2026, 9, 10, 19, 54),
            "date": "09/10",
            "full_date": "2026-09-10",
            "duration_min": 60.0,
            "sport": "cycling",
            "sub_sport": "indoor_cycling",
            "sport_display": "🚴 自行車",
            "sport_color": "#00f2fe",
            "avg_power": 196.9,
            "max_power": 282.0,
            "avg_hr": 149.6,
            "max_hr": 160.0,
            "lactate_readings": [{"time_min": 15, "lactate": 6.2}, {"time_min": 35, "lactate": 7.8}, {"time_min": 58, "lactate": 10.5}],
            "lactate_values": [6.2, 7.8, 10.5],
            "avg_lactate": 8.17,
            "max_lactate": 10.5,
            "initial_lactate": 6.2,
            "final_lactate": 10.5
        }
    ]
