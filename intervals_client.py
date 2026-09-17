# -*- coding: utf-8 -*-
"""
intervals_client.py - Intervals.icu API 客戶端模組
支援將 Garmin Connect、COROS 等穿戴設備透過 Intervals.icu 自動同步日常運動數據至 Firebase Firestore。
"""

import os
import re
import base64
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional


INTERVALS_BASE_URL = "https://intervals.icu/api/v1"


def get_basic_auth_header(api_key: str) -> Dict[str, str]:
    """
    產生 Intervals.icu Basic Auth Header
    用戶名固定為 'API_KEY'，密碼為使用者的 API Key
    """
    token = base64.b64encode(f"API_KEY:{api_key.strip()}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }


def test_intervals_connection(api_key: str, athlete_id: str = "0") -> Tuple[bool, str]:
    """
    測試 Intervals.icu API Key 是否有效
    回傳 (是否成功, 訊息/運動員名稱)
    """
    if not api_key or not api_key.strip():
        return False, "API Key 不能為空"
        
    ath_id = athlete_id.strip() if athlete_id and athlete_id.strip() else "0"
    url = f"{INTERVALS_BASE_URL}/athlete/{ath_id}"
    headers = get_basic_auth_header(api_key)
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ath_name = data.get("name") or data.get("id") or "運動員"
            return True, f"連線成功！歡迎，{ath_name}"
        elif resp.status_code == 401:
            return False, "授權失敗：請檢查 Intervals.icu API Key 是否正確"
        elif resp.status_code == 404:
            return False, f"找不到 Athlete ID: {ath_id}，若為個人帳號請填入 0"
        else:
            return False, f"連線失敗 (HTTP {resp.status_code}): {resp.text[:100]}"
    except Exception as e:
        return False, f"連線逾時或網路錯誤: {str(e)}"


def calculate_pre_lactate_date_ranges(lactate_dates: List[datetime], lookback_days: int = 5) -> List[Tuple[str, str]]:
    """
    根據所有有乳酸紀錄的日期清單，計算每一天的前 N 天 (預設 5 天) 區間，
    並自動合併重疊或相鄰的日期區間，產生最精簡的 (oldest, newest) 清單。
    格式: YYYY-MM-DD
    """
    if not lactate_dates:
        return []

    # 1. 產生所有需要覆蓋的單日 (包含乳酸日前 5 天與乳酸日當天)
    target_days = set()
    for dt in lactate_dates:
        d = dt.date() if isinstance(dt, datetime) else dt
        for i in range(lookback_days + 1):
            target_days.add(d - timedelta(days=i))

    sorted_days = sorted(target_days)
    if not sorted_days:
        return []

    # 2. 合併連續日期成區間 [start_date, end_date]
    ranges = []
    start_d = sorted_days[0]
    prev_d = start_d

    for current_d in sorted_days[1:]:
        if current_d == prev_d + timedelta(days=1):
            prev_d = current_d
        else:
            ranges.append((start_d.strftime("%Y-%m-%d"), prev_d.strftime("%Y-%m-%d")))
            start_d = current_d
            prev_d = current_d
    ranges.append((start_d.strftime("%Y-%m-%d"), prev_d.strftime("%Y-%m-%d")))

    return ranges


def fetch_intervals_activities(api_key: str, athlete_id: str = "0", oldest: str = None, newest: str = None) -> List[Dict[str, Any]]:
    """
    從 Intervals.icu 拉取指定日期區間內的活動
    oldest, newest 格式: 'YYYY-MM-DD'
    """
    ath_id = athlete_id.strip() if athlete_id and athlete_id.strip() else "0"
    url = f"{INTERVALS_BASE_URL}/athlete/{ath_id}/activities"
    headers = get_basic_auth_header(api_key)
    params = {}
    if oldest:
        params["oldest"] = oldest
    if newest:
        params["newest"] = newest

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Intervals.icu API Error ({resp.status_code}): {resp.text}")
            return []
    except Exception as e:
        print(f"Error fetching activities from Intervals.icu: {e}")
        return []


def map_intervals_sport_type(icu_type: str) -> Tuple[str, str]:
    """
    將 Intervals.icu 的運動類型映射為 MyLactate 專項 (sport, sub_sport)
    """
    t_lower = str(icu_type).lower() if icu_type else "generic"
    if any(k in t_lower for k in ["ride", "bike", "cycling", "virtualride", "gravel"]):
        sub = "indoor_cycling" if "virtual" in t_lower or "indoor" in t_lower else "road_cycling"
        return "cycling", sub
    elif any(k in t_lower for k in ["run", "trail", "treadmill"]):
        sub = "treadmill" if "treadmill" in t_lower else "generic"
        return "running", sub
    elif any(k in t_lower for k in ["swim"]):
        return "swimming", "generic"
    elif any(k in t_lower for k in ["walk", "hike"]):
        return "walking", "generic"
    elif any(k in t_lower for k in ["row"]):
        return "rowing", "generic"
    else:
        return "generic", "generic"


def convert_intervals_activity_to_firebase_fit_record(act: Dict[str, Any]) -> Dict[str, Any]:
    """
    將 Intervals.icu 的單場活動轉換為標準 Firestore fit_records 格式
    """
    start_str = act.get("start_date_local") or act.get("start_date")
    start_dt = None
    if start_str:
        try:
            clean_ts = start_str.replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(clean_ts)
        except Exception:
            pass

    if not start_dt:
        start_dt = datetime.utcnow()

    icu_type = act.get("type", "Workout")
    sport, sub_sport = map_intervals_sport_type(icu_type)

    moving_time_s = act.get("moving_time") or act.get("elapsed_time") or 0
    duration_min = round(float(moving_time_s) / 60.0, 1)

    avg_pwr = float(act.get("average_watts") or 0.0)
    max_pwr = float(act.get("max_watts") or 0.0)
    avg_hr = float(act.get("average_heartrate") or 0.0)
    max_hr = float(act.get("max_heartrate") or 0.0)
    tot_dist = float(act.get("distance") or 0.0)
    tot_elev = float(act.get("total_elevation_gain") or 0.0)
    training_load = float(act.get("icu_training_load") or act.get("trimp") or 0.0)
    intensity = float(act.get("icu_intensity") or 0.0)
    cadence = float(act.get("average_cadence") or 0.0)
    act_id = str(act.get("id", ""))
    act_name = act.get("name", f"{sport.capitalize()} Session")

    clean_time = start_dt.strftime("%Y%m%d_%H%M%S")
    doc_id = f"fit_{clean_time}_icu_{act_id}"

    payload = {
        "fields": {
            "file_name": {"stringValue": f"intervals_{act_id}_{icu_type}.fit"},
            "activity_name": {"stringValue": act_name},
            "start_time": {"timestampValue": start_dt.isoformat() + "Z"},
            "sport": {"stringValue": sport},
            "sub_sport": {"stringValue": sub_sport},
            "duration_minutes": {"doubleValue": duration_min},
            "avg_power": {"integerValue": str(int(avg_pwr))},
            "max_power": {"integerValue": str(int(max_pwr))},
            "avg_hr": {"integerValue": str(int(avg_hr))},
            "max_hr": {"integerValue": str(int(max_hr))},
            "total_distance_m": {"doubleValue": round(tot_dist, 1)},
            "elevation_gain_m": {"doubleValue": round(tot_elev, 1)},
            "cadence": {"integerValue": str(int(cadence))},
            "icu_training_load": {"doubleValue": round(training_load, 1)},
            "icu_intensity": {"doubleValue": round(intensity, 2)},
            "source": {"stringValue": "intervals_icu"},
            "has_lactate": {"booleanValue": False}, # 標記為日常訓練（無採樣乳酸）
            "time_series": {"arrayValue": {"values": []}}
        }
    }

    return {
        "doc_id": doc_id,
        "start_time": start_dt,
        "payload": payload,
        "raw": act
    }


def sync_pre_lactate_activities_to_firebase(
    uid: str,
    firebase_token: str,
    intervals_api_key: str,
    athlete_id: str = "0",
    lookback_days: int = 5
) -> Tuple[int, int, str]:
    """
    高階整合同步主函式：
    1. 從 Firestore 讀取現有所有的乳酸採樣日期。
    2. 自動推算所有「乳酸日前 lookback_days 天」的有效日期區間。
    3. 呼叫 Intervals.icu 抓取日常運動數據。
    4. 檢查 Firestore 現有 fit_records，若該時段已有原創乳酸測試 FIT 檔則跳過（防覆蓋有乳酸的珍貴測驗）。
    5. 透過 PATCH 冪等寫入 Firestore。
    回傳: (同步成功筆數, 跳過重疊筆數, 訊息)
    """
    if not uid or not firebase_token:
        return 0, 0, "未登入 Firebase 雲端帳號"
    if not intervals_api_key:
        return 0, 0, "未提供 Intervals.icu API Key"

    headers_fb = {"Authorization": f"Bearer {firebase_token}", "Content-Type": "application/json"}

    # 1. 抓取所有現有乳酸記錄的時間點
    la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records"
    lactate_dates = []
    try:
        r_la = requests.get(la_url, headers=headers_fb, timeout=12)
        if r_la.status_code == 200:
            la_docs = r_la.json().get("documents", [])
            for doc in la_docs:
                f = doc.get("fields", {})
                year = int(f.get("year", {}).get("integerValue", 0))
                month = int(f.get("month", {}).get("integerValue", 0))
                day = int(f.get("day", {}).get("integerValue", 0))
                if year > 0 and month > 0 and day > 0:
                    full_year = year + 2000 if year < 100 else year
                    lactate_dates.append(datetime(full_year, month, day))
    except Exception as e:
        print(f"Error fetching lactate dates: {e}")

    # 若無乳酸紀錄，預設抓取最近 30 天日常運動
    if not lactate_dates:
        now_dt = datetime.now()
        date_ranges = [((now_dt - timedelta(days=30)).strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d"))]
    else:
        date_ranges = calculate_pre_lactate_date_ranges(lactate_dates, lookback_days=lookback_days)

    if not date_ranges:
        return 0, 0, "未找到有效的同步日期區間"

    # 2. 抓取現有的 fit_records 以便比對重疊
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"
    existing_session_times = []
    try:
        r_fit = requests.get(fit_url, headers=headers_fb, timeout=12)
        if r_fit.status_code == 200:
            for doc in r_fit.json().get("documents", []):
                st_val = doc.get("fields", {}).get("start_time", {}).get("timestampValue")
                if st_val:
                    try:
                        clean_ts = st_val.replace("Z", "+00:00")
                        existing_session_times.append(datetime.fromisoformat(clean_ts))
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error fetching existing fit sessions: {e}")

    # 3. 依區間從 Intervals.icu 抓取活動
    all_activities = []
    seen_act_ids = set()
    for oldest, newest in date_ranges:
        acts = fetch_intervals_activities(intervals_api_key, athlete_id=athlete_id, oldest=oldest, newest=newest)
        for a in acts:
            aid = str(a.get("id"))
            if aid not in seen_act_ids:
                seen_act_ids.add(aid)
                all_activities.append(a)

    if not all_activities:
        return 0, 0, f"在覆蓋的 {len(date_ranges)} 個日期區間內，Intervals.icu 未查到任何運動紀錄"

    # 4. 轉換並寫入 Firestore
    synced_count = 0
    skipped_count = 0

    for act in all_activities:
        rec = convert_intervals_activity_to_firebase_fit_record(act)
        act_start = rec["start_time"]

        # 防重複/防覆蓋檢查：如果該時段 (前後 5 分鐘內) 已經有由原版 FIT 或 HTML 匯入的測驗，跳過寫入
        is_overlap = False
        for ex_dt in existing_session_times:
            if abs((act_start.replace(tzinfo=None) - ex_dt.replace(tzinfo=None)).total_seconds()) <= 300:
                is_overlap = True
                break

        if is_overlap:
            skipped_count += 1
            continue

        # 寫入 Firestore (使用 PATCH 進行冪等寫入)
        doc_id = rec["doc_id"]
        post_url = f"{fit_url}/{doc_id}"
        try:
            r_post = requests.patch(post_url, headers=headers_fb, json=rec["payload"], timeout=10)
            if r_post.status_code in [200, 201]:
                synced_count += 1
                existing_session_times.append(act_start)
            else:
                print(f"Failed to upsert Intervals activity {doc_id}: {r_post.text}")
        except Exception as e:
            print(f"Error upserting activity {doc_id}: {e}")

    msg = f"Intervals.icu 同步完成！共掃描 {len(all_activities)} 場日常活動，成功同步 {synced_count} 筆背景訓練，跳過 {skipped_count} 筆現有重疊紀錄。"
    return synced_count, skipped_count, msg
