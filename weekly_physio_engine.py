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


_FIT_SPORT_CACHE = {}
_FIT_METADATA_CACHE = {}

def _init_local_metadata_cache():
    """
    掃描本地所有報告與 FIT 檔案目錄，建立 fit 檔名至專項與真實活動時長的精準快取映射
    """
    global _FIT_METADATA_CACHE, _FIT_SPORT_CACHE
    if _FIT_METADATA_CACHE:
        return _FIT_METADATA_CACHE
        
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(cur_dir)
    base_dirs = [cur_dir, parent_dir]
    sub_names = ["RunDataRead", "RunDataDayu", "RunDataMei", "DataYen", "DataMindy", "DataSunday", "0521", "bikeData", "."]
    
    for b in base_dirs:
        for s in sub_names:
            folder = os.path.normpath(os.path.join(b, s))
            if not os.path.isdir(folder):
                continue
            folder_lower = s.lower()
            is_run = "run" in folder_lower
            is_bike = "bike" in folder_lower or "cycle" in folder_lower
            def_sp = "running" if is_run else ("cycling" if is_bike else None)
            
            # 1. 掃描報告 HTML 檔案 (精準抓取檔名與真實活動時長)
            for hpath in glob.glob(os.path.join(folder, "*.html")):
                try:
                    with open(hpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    m_fit = re.search(r"檔案名稱.*?:?\s*([\w\-]+\.fit)", content)
                    m_dur = re.search(r"活動時長.*?<div class=[\"']kpi-value[\"'][^>]*>(.*?)</div>", content, re.S)
                    
                    dur_val = 0.0
                    if m_dur:
                        dur_text = m_dur.group(1).strip()
                        m_min_sec = re.search(r"(\d+)\s*分(?:\s*(\d+)\s*秒)?", dur_text)
                        if m_min_sec:
                            mins = float(m_min_sec.group(1))
                            secs = float(m_min_sec.group(2)) if m_min_sec.group(2) else 0.0
                            dur_val = round(mins + secs / 60.0, 1)
                            
                    if m_fit:
                        fit_fn = m_fit.group(1).strip()
                        resolved_sp = def_sp if def_sp else ("cycling" if is_bike else "running")
                        meta_obj = {
                            "sport": resolved_sp,
                            "sub_sport": "indoor_cycling" if resolved_sp == "cycling" else "generic",
                            "duration_min": dur_val,
                            "source_html": os.path.basename(hpath)
                        }
                        _FIT_METADATA_CACHE[fit_fn] = meta_obj
                        _FIT_METADATA_CACHE[fit_fn.replace(".fit", "")] = meta_obj
                        _FIT_SPORT_CACHE[fit_fn] = (resolved_sp, meta_obj["sub_sport"])
                        _FIT_SPORT_CACHE[fit_fn.replace(".fit", "")] = (resolved_sp, meta_obj["sub_sport"])
                except Exception:
                    pass
                    
            # 2. 掃描實體 .fit 檔案 (使用 fitparse 讀取官方 sport 欄位)
            for fpath in glob.glob(os.path.join(folder, "*.fit")):
                fit_fn = os.path.basename(fpath)
                if fit_fn not in _FIT_SPORT_CACHE:
                    try:
                        import fitparse
                        fit = fitparse.FitFile(fpath, check_crc=False)
                        sp = None
                        sub = 'generic'
                        for m in fit.get_messages('sport'):
                            vals = {x.name: x.value for x in m.fields}
                            if vals.get('sport'):
                                sp = str(vals.get('sport')).lower()
                                if vals.get('sub_sport'):
                                    sub = str(vals.get('sub_sport')).lower()
                                break
                        if not sp:
                            for m in fit.get_messages('session'):
                                vals = {x.name: x.value for x in m.fields}
                                if vals.get('sport'):
                                    sp = str(vals.get('sport')).lower()
                                    if vals.get('sub_sport'):
                                        sub = str(vals.get('sub_sport')).lower()
                                    break
                        if sp:
                            _FIT_SPORT_CACHE[fit_fn] = (sp, sub)
                            _FIT_SPORT_CACHE[fit_fn.replace('.fit', '')] = (sp, sub)
                            if fit_fn not in _FIT_METADATA_CACHE:
                                _FIT_METADATA_CACHE[fit_fn] = {"sport": sp, "sub_sport": sub, "duration_min": 0.0}
                    except Exception:
                        pass
                        
    return _FIT_METADATA_CACHE


def get_fit_file_metadata(file_name):
    """
    隨需快速查詢特定 FIT 檔案的元數據 (sport, sub_sport, duration_min)
    """
    if not file_name:
        return None
    _init_local_metadata_cache()
    fn_clean = os.path.basename(str(file_name)).strip()
    m_fit = re.search(r'([\w\-]+\.fit)', fn_clean, re.IGNORECASE)
    target_fit = m_fit.group(1) if m_fit else (fn_clean if fn_clean.lower().endswith('.fit') else None)
    
    if target_fit and target_fit in _FIT_METADATA_CACHE:
        return _FIT_METADATA_CACHE[target_fit]
    if fn_clean in _FIT_METADATA_CACHE:
        return _FIT_METADATA_CACHE[fn_clean]
    return None


def get_fit_file_sport(file_name):
    """
    隨需快速查詢特定 FIT 檔案的官方 sport / sub_sport，具備記憶快取（秒開、不卡頓）
    """
    meta = get_fit_file_metadata(file_name)
    if meta:
        return (meta["sport"], meta.get("sub_sport", "generic"))
    return None


def get_workspace_fit_sport_cache():
    _init_local_metadata_cache()
    return _FIT_SPORT_CACHE


def resolve_sport_type(filename_or_text, avg_power=0, avg_hr=0, cadence=0, default_sport=None):
    """
    結合 FIT 檔/報告快取、檔名關鍵字、生理指標與功率特徵綜合研判真實運動專項。
    特別防禦：
    1. 跑步功率計（如 Stryd / Garmin Running Power）功率常見於 180W~350W，且心率常在 140~175 bpm，嚴禁武斷視為自行車！
    2. 自行車判定必須具備明確 bike/cycling/騎行關鍵字或 40~110 rpm 踏頻特徵。
    3. 純數字檔名手錶活動在無自行車特徵時，預設一律校正為跑步（running）。
    """
    fn_clean = os.path.basename(str(filename_or_text)).strip()
    
    # 1. 優先從本地報告與 FIT 官方快取查詢 (秒開精確解析)
    fit_res = get_fit_file_sport(fn_clean)
    if fit_res:
        return fit_res
    
    # 2. 檢查檔名與文字中的明確關鍵字
    txt_lower = fn_clean.lower()
    if any(k in txt_lower for k in ['run', '跑步', '慢跑', '路跑', 'treadmill', 'rundata']):
        return ('running', 'generic')
    if any(k in txt_lower for k in ['bike', 'cycling', '自行車', '騎行', '單車', '飛輪', 'indoor_cycling', 'bikedata']):
        return ('cycling', 'indoor_cycling')
        
    # 3. 檢查步頻 (Cadence): 跑步步頻通常在 140~200，自行車踏頻在 60~110
    if cadence > 120:
        return ('running', 'generic')
    if 40 <= cadence <= 110 and any(k in txt_lower for k in ['bike', 'ride', 'cycle']):
        return ('cycling', 'indoor_cycling')
        
    # 4. 生理與功率特徵防禦（跑步功率計 180W~350W 且心率較高）
    if avg_power >= 180 and avg_hr >= 140 and cadence == 0:
        return ('running', 'generic')

    # 5. 若 default_sport 存在且可靠
    if default_sport and default_sport not in ['unknown', 'None', '', 'generic']:
        # 若標記為 cycling 但檔名為純數字手錶紀錄且心率在跑步心率區間，校正為 running
        is_numeric_fn = bool(re.match(r'^\d+(\.fit)?$', fn_clean))
        if default_sport == 'cycling' and is_numeric_fn and avg_hr >= 140:
            return ('running', 'generic')
        return (default_sport, 'generic')
        
    # 6. 預設 fallback 為跑步
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






def fetch_firestore_dataset_with_status(uid, token, session_limit=7, sport_filter="all", refresh_token=None):
    """
    從 Firebase Firestore 抓取登入者真實歷史訓練與汗乳酸紀錄，支援自動刷新 Token 與明確錯誤原因回報
    回傳: (sessions: list, active_token: str, error_msg: str or None)
    """
    if not uid or not token:
        return [], token, "未提供登入 UID 或認證 Token，請先於側邊欄登入"

    active_token = token
    headers = {"Authorization": f"Bearer {active_token}"}
    
    # 1. 抓取 fit_records
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"
    fit_sessions = []
    try:
        r_fit = requests.get(fit_url, headers=headers, timeout=12)
        
        # 若遭遇 401 Unauthorized 且具備 refresh_token，自動刷新一次
        if r_fit.status_code in [401, 403] and refresh_token:
            try:
                API_KEY_LOCAL = "AIzaSyAhU1n_IIF7AEHXkrQCoToR3gkKe2umpuM"
                r_ref = requests.post(
                    f"https://securetoken.googleapis.com/v1/token?key={API_KEY_LOCAL}",
                    data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                    timeout=8
                )
                if r_ref.status_code == 200:
                    active_token = r_ref.json().get("id_token")
                    headers = {"Authorization": f"Bearer {active_token}"}
                    r_fit = requests.get(fit_url, headers=headers, timeout=12)
            except Exception:
                pass

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
                
                local_meta = get_fit_file_metadata(file_name)
                sport, sub_sport = resolve_sport_type(
                    file_name,
                    avg_power=avg_pwr,
                    avg_hr=avg_hr,
                    default_sport=raw_sport
                )
                if local_meta:
                    sport = local_meta.get("sport", sport)
                    sub_sport = local_meta.get("sub_sport", sub_sport)
                elif raw_sub and sub_sport == 'generic':
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
                duration_min = 0.0
                if local_meta and local_meta.get("duration_min", 0) > 0:
                    duration_min = float(local_meta["duration_min"])
                else:
                    # 1. 優先取頂層 duration_minutes
                    duration_min = _get_fs_val(f.get("duration_minutes", {}), 0.0)
                    # 2. 次優先取 time_series 最後一點
                    if duration_min <= 0 and ts_values:
                        last_pt = ts_values[-1].get("mapValue", {}).get("fields", {})
                        duration_min = _get_fs_val(last_pt.get("elapsed_minutes", {}), 0.0)

                source_val = f.get("source", {}).get("stringValue", "manual_fit")
                act_name = f.get("activity_name", {}).get("stringValue", file_name)
                icu_load = _get_fs_val(f.get("icu_training_load", {}), 0.0)

                fit_sessions.append({
                    "id": doc.get("name"),
                    "source_file": file_name,
                    "activity_name": act_name,
                    "source": source_val,
                    "icu_training_load": icu_load,
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
        else:
            if r_fit.status_code in [401, 403]:
                return [], active_token, f"Firebase 認證 Token 已過期或權限不足 (HTTP {r_fit.status_code})，請重新登入"
            return [], active_token, f"讀取 fit_records 失敗 (HTTP {r_fit.status_code})"
    except Exception as e:
        return [], active_token, f"連線至 fit_records 失敗: {e}"

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

    # 2.1 乳酸紀錄時間去重 (同一分鐘僅保留一筆最新/最高精度值)
    dedup_lactate = []
    seen_la_times = set()
    for la in all_lactate:
        la_key = la["record_time"].strftime("%Y%m%d_%H%M")
        if la_key not in seen_la_times:
            seen_la_times.add(la_key)
            dedup_lactate.append(la)
    all_lactate = dedup_lactate

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

        # 校正運動時長：嚴禁以運動結束後休息/恢復期的乳酸採血時間點覆蓋真正的運動時長！
        # 運動時長 (duration_min) 若已有正值，保持真實運動時長；只有在缺失 (<= 0) 時才作為備援
        if s["duration_min"] <= 0:
            if matched_la:
                max_la_t = max([x["time_min"] for x in matched_la])
                s["duration_min"] = round(max_la_t, 1)
            else:
                s["duration_min"] = 35.0

    valid = [s for s in fit_sessions if s["start_time"] is not None]
    
    # 4. 針對資料庫中可能存在的歷史重複訓練場次進行去重 (Deduplication)
    # 若同一次訓練被重複登記 (開始時間相差 <= 180 秒)，自動去重，合併保留數據最完整的一筆
    unique_sessions = []
    seen_session_times = []
    for s in valid:
        s_dt = s["start_time"]
        matched_idx = -1
        for idx, ex_dt in enumerate(seen_session_times):
            if abs((s_dt - ex_dt).total_seconds()) <= 180:
                matched_idx = idx
                break
        if matched_idx == -1:
            seen_session_times.append(s_dt)
            unique_sessions.append(s)
        else:
            # 發現重複登記！比較完整度評分：優先保留乳酸採樣點更多、時長更完整或平均功率有值的紀錄
            existing = unique_sessions[matched_idx]
            curr_score = len(s.get("lactate_readings", [])) * 10 + (1 if s.get("avg_power", 0) > 0 else 0) + (1 if s.get("duration_min", 0) > 0 else 0)
            ex_score = len(existing.get("lactate_readings", [])) * 10 + (1 if existing.get("avg_power", 0) > 0 else 0) + (1 if existing.get("duration_min", 0) > 0 else 0)
            if curr_score > ex_score:
                unique_sessions[matched_idx] = s
                seen_session_times[matched_idx] = s_dt
    valid = unique_sessions

    # 依運動專項篩選
    if sport_filter and sport_filter != "all":
        valid = [s for s in valid if s.get("sport") == sport_filter]

    if not valid:
        return [], active_token, f"在【{sport_filter}】專項篩選下查無任何運動紀錄"

    valid = sorted(valid, key=lambda x: x["start_time"])

    # 找出所有包含汗乳酸採樣的關鍵測驗場次
    lactate_sessions = [
        s for s in valid
        if len(s.get("lactate_readings", [])) > 0 or s.get("avg_lactate", 0) > 0
    ]

    if not lactate_sessions:
        return [], active_token, "查無任何包含汗乳酸採樣的測驗紀錄，請先登錄乳酸測試數據"

    # 取最近 N 場（預設 5 場）含乳酸之關鍵測驗場次
    target_la_count = session_limit if (session_limit and session_limit > 0) else 5
    target_la_sessions = lactate_sessions[-target_la_count:]
    earliest_la_time = target_la_sessions[0]["start_time"]

    # 關鍵策略：拉入自最早該場乳酸測驗起至最新一場之間的所有運動
    # （包含這 5 場乳酸測驗 + 期間所有中間有運動但沒乳酸的手錶日常數據）
    final_sessions = [s for s in valid if s["start_time"] >= earliest_la_time]

    return final_sessions, active_token, None


def fetch_firestore_dataset(uid, token, session_limit=5, sport_filter="all", refresh_token=None):
    """
    相容舊版介面，回傳訓練場次清單
    """
    sessions, _, _ = fetch_firestore_dataset_with_status(
        uid, token, session_limit=session_limit, sport_filter=sport_filter, refresh_token=refresh_token
    )
    return sessions


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
        has_lactate = len(s.get("lactate_readings", [])) > 0 or s.get("avg_lactate", 0) > 0
        
        if has_lactate:
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
            la = s.get("avg_lactate", 0)
            
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
        else:
            # 手錶日常背景訓練 (未採樣汗乳酸)
            avg_hr = s.get("avg_hr", 0)
            if avg_hr >= 165:
                s["type"] = "耐力刺激 / 閾值提升"
            elif avg_hr >= 140:
                s["type"] = "有氧燃脂 / 節奏巡航"
            else:
                s["type"] = "基礎耐力 / 動態恢復"
            s["metabolic_efficiency"] = None
            s["efficiency_unit"] = "未採樣"

    # 4. 代謝效率變化率 (最新場次 vs 前期場次)
    eff_delta_pct = 0.0
    latest = sessions[-1]
    valid_eff_sessions = [s for s in sessions if s.get("metabolic_efficiency") is not None and s.get("metabolic_efficiency", 0) > 0]
    if len(valid_eff_sessions) >= 2 and latest.get("metabolic_efficiency") is not None:
        prior_effs = [s["metabolic_efficiency"] for s in valid_eff_sessions[:-1]]
        if prior_effs:
            mean_prior = np.mean(prior_effs)
            eff_delta_pct = round(((latest["metabolic_efficiency"] - mean_prior) / mean_prior) * 100.0, 1)

    # 5. 汗乳酸加權負荷積分與極化區間計算
    total_sweat_load = 0.0
    zone_duration = {"Low_Recovery": 0.0, "Tempo_Aerobic": 0.0, "High_Glycolytic": 0.0}

    for s in sessions:
        dur_hrs = s.get("duration_min", 0) / 60.0
        la = s.get("avg_lactate", 0)
        has_lactate = len(s.get("lactate_readings", [])) > 0 or la > 0
        avg_hr = s.get("avg_hr", 0)
        
        if has_lactate:
            if la <= baseline_low:
                w = 1.0
                zone_duration["Low_Recovery"] += s.get("duration_min", 0)
            elif la <= baseline_high:
                w = 1.8
                zone_duration["Tempo_Aerobic"] += s.get("duration_min", 0)
            else:
                w = 3.5
                zone_duration["High_Glycolytic"] += s.get("duration_min", 0)
        else:
            # 依心率區間推算極化區間
            if avg_hr >= 165:
                w = 2.5
                zone_duration["High_Glycolytic"] += s.get("duration_min", 0)
            elif avg_hr >= 140:
                w = 1.5
                zone_duration["Tempo_Aerobic"] += s.get("duration_min", 0)
            else:
                w = 1.0
                zone_duration["Low_Recovery"] += s.get("duration_min", 0)

        # 間隔天數微調係數：若連日運動（間隔<=1天），疲勞累積加成
        interval_factor = 1.2 if (s.get("days_since_prior") is not None and s.get("days_since_prior") <= 1.0) else 1.0
        
        # 若來自手錶且具備 Intervals.icu Training Load (TSS)，優先結合手錶負荷
        if s.get("icu_training_load", 0) > 0:
            session_load = round(float(s["icu_training_load"]) * interval_factor, 1)
        else:
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

