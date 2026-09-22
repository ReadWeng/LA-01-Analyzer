# -*- coding: utf-8 -*-
"""
activity_calendar.py - 雲端運動紀錄月曆與乳酸資料綁定模組 (手機極致響應優化版)
支援將 Firebase Firestore 中的日常 FIT 運動紀錄以極致響應式月曆呈現，
在手機上保證「一眼看盡（7欄不折疊、全月不換行）」、標記已擷取 FIT 數據與乳酸測試，
並支援一鍵點入載入活動綁定乳酸數據。
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import calendar
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Tuple, Optional


def _get_fs_field(field_obj: Dict[str, Any], default=None):
    """從 Firestore 欄位物件中安全解析數值"""
    if not field_obj or not isinstance(field_obj, dict):
        return default
    if "stringValue" in field_obj:
        return field_obj["stringValue"]
    if "integerValue" in field_obj:
        return int(field_obj["integerValue"])
    if "doubleValue" in field_obj:
        return float(field_obj["doubleValue"])
    if "booleanValue" in field_obj:
        return bool(field_obj["booleanValue"])
    if "timestampValue" in field_obj:
        return field_obj["timestampValue"]
    return default


def fetch_user_calendar_data(
    uid: str,
    token: str,
    force_reload: bool = False
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """
    從 Firestore 抓取該使用者的所有 fit_records 與 lactate_records，
    並依日期 'YYYY-MM-DD' 分組回傳。
    回傳: (activities_by_date, lactates_by_date)
    """
    cache_key = f"cal_cache_data_{uid}"
    if not force_reload and cache_key in st.session_state:
        return st.session_state[cache_key]

    activities_by_date: Dict[str, List[Dict[str, Any]]] = {}
    lactates_by_date: Dict[str, List[Dict[str, Any]]] = {}

    if not uid or not token:
        return activities_by_date, lactates_by_date

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. 抓取 fit_records (設定 pageSize=300 一次抓齊)
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records?pageSize=300"
    try:
        r_fit = requests.get(fit_url, headers=headers, timeout=12)
        if r_fit.status_code == 200:
            docs = r_fit.json().get("documents", [])
            for doc in docs:
                f = doc.get("fields", {})
                doc_id = doc.get("name", "").split("/")[-1]
                st_val = _get_fs_field(f.get("start_time"))
                if not st_val:
                    continue

                try:
                    clean_ts = st_val.replace("Z", "+00:00")
                    start_dt = datetime.fromisoformat(clean_ts)
                    if start_dt.tzinfo is not None:
                        start_dt = start_dt.astimezone().replace(tzinfo=None)
                except Exception:
                    continue

                date_str = start_dt.strftime("%Y-%m-%d")
                sport = _get_fs_field(f.get("sport"), "unknown")
                sub_sport = _get_fs_field(f.get("sub_sport"), "generic")
                dur_min = float(_get_fs_field(f.get("duration_minutes"), 0.0))
                avg_pwr = int(_get_fs_field(f.get("avg_power"), 0))
                max_pwr = int(_get_fs_field(f.get("max_power"), 0))
                avg_hr = int(_get_fs_field(f.get("avg_hr"), 0))
                max_hr = int(_get_fs_field(f.get("max_hr"), 0))
                has_la = bool(_get_fs_field(f.get("has_lactate"), False))
                file_name = _get_fs_field(f.get("file_name"), f"activity_{date_str}.fit")
                act_name = _get_fs_field(f.get("activity_name"), file_name)
                source = _get_fs_field(f.get("source"), "fit_upload")

                act_item = {
                    "doc_id": doc_id,
                    "date_str": date_str,
                    "start_time": start_dt,
                    "file_name": file_name,
                    "activity_name": act_name,
                    "sport": sport,
                    "sub_sport": sub_sport,
                    "duration_minutes": dur_min,
                    "avg_power": avg_pwr,
                    "max_power": max_pwr,
                    "avg_hr": avg_hr,
                    "max_hr": max_hr,
                    "has_lactate": has_la,
                    "source": source,
                    "raw_fields": f
                }
                activities_by_date.setdefault(date_str, []).append(act_item)

        # 1.1 自動去重防護網：若同一天存在多份開始時間極近 (<= 3分鐘) 的重複訓練，進行智慧合併去重
        for d_str in activities_by_date:
            day_acts = activities_by_date[d_str]
            if len(day_acts) > 1:
                # 排序依據：優先手動上傳 / 帶有乳酸測驗的記錄
                def _act_score(a):
                    score = 0
                    if a.get("has_lactate"):
                        score += 20
                    if a.get("source") != "intervals_icu":
                        score += 10
                    # 包含更多時間數列點者優先
                    pts = len(a.get("raw_fields", {}).get("time_series", {}).get("arrayValue", {}).get("values", []))
                    score += min(pts, 50)
                    return score

                day_acts_sorted = sorted(day_acts, key=_act_score, reverse=True)
                deduped = []
                for a in day_acts_sorted:
                    is_dup = False
                    a_st = a["start_time"]
                    for kept in deduped:
                        k_st = kept["start_time"]
                        time_diff = abs((a_st - k_st).total_seconds())
                        # 前後 180 秒內視為同一場訓練
                        if time_diff <= 180:
                            is_dup = True
                            # 若被合併項有乳酸標記，保留給留存項
                            if a.get("has_lactate"):
                                kept["has_lactate"] = True
                            break
                    if not is_dup:
                        deduped.append(a)
                # 依開始時間重新由早到晚排序
                activities_by_date[d_str] = sorted(deduped, key=lambda x: x["start_time"])

    except Exception as e:
        print(f"Error fetching fit records for calendar: {e}")

    # 2. 抓取 lactate_records (設定 pageSize=300 一次抓齊)
    la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records?pageSize=300"
    try:
        r_la = requests.get(la_url, headers=headers, timeout=12)
        if r_la.status_code == 200:
            la_docs = r_la.json().get("documents", [])
            for doc in la_docs:
                f = doc.get("fields", {})
                doc_id = doc.get("name", "").split("/")[-1]
                year = int(_get_fs_field(f.get("year"), 0))
                month = int(_get_fs_field(f.get("month"), 0))
                day = int(_get_fs_field(f.get("day"), 0))
                hour = int(_get_fs_field(f.get("hour"), 0))
                minute = int(_get_fs_field(f.get("minute"), 0))
                la_val = float(_get_fs_field(f.get("final_la_mmol"), 0.0))
                glu_val = _get_fs_field(f.get("final_glu_mgdl"))
                src = _get_fs_field(f.get("source"), "")
                fit_bound_id = _get_fs_field(f.get("fit_doc_id"), "")

                if year > 0 and month > 0 and day > 0:
                    full_year = year + 2000 if year < 100 else year
                    try:
                        rec_dt = datetime(full_year, month, day, hour, minute)
                        date_str = rec_dt.strftime("%Y-%m-%d")
                    except Exception:
                        date_str = f"{full_year:04d}-{month:02d}-{day:02d}"
                        rec_dt = datetime(full_year, month, day)

                    la_item = {
                        "doc_id": doc_id,
                        "date_str": date_str,
                        "record_time": rec_dt,
                        "lactate_mmol": la_val,
                        "glucose_mgdl": glu_val,
                        "source": src,
                        "fit_doc_id": fit_bound_id
                    }
                    lactates_by_date.setdefault(date_str, []).append(la_item)
    except Exception as e:
        print(f"Error fetching lactate records for calendar: {e}")

    # 對每場活動關聯乳酸標記 (精確關聯：同活動 ID 或時間窗口符合)
    for d_str, acts in activities_by_date.items():
        las = lactates_by_date.get(d_str, [])
        for act in acts:
            act_id = act.get("doc_id", "")
            act_start = act.get("start_time")
            dur = act.get("duration_minutes", 0.0)
            end_limit = act_start + timedelta(minutes=dur + 60.0) if act_start else None
            start_limit = act_start - timedelta(minutes=30.0) if act_start else None

            matching_la = []
            for la in las:
                b_id = la.get("fit_doc_id")
                if b_id and b_id == act_id:
                    matching_la.append(la)
                elif not b_id and start_limit and end_limit:
                    if start_limit <= la["record_time"] <= end_limit:
                        matching_la.append(la)

            if matching_la or act.get("has_lactate"):
                act["has_lactate"] = True
                act["lactate_count"] = len(matching_la) if matching_la else act.get("lactate_count", 0)

    st.session_state[cache_key] = (activities_by_date, lactates_by_date)
    return activities_by_date, lactates_by_date


def build_session_from_fit_record(
    act_item: Dict[str, Any],
    lactates_on_day: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    將 Firestore 中的 fit_record 還原為應用程式標準 Session 物件 (df, df_laps, start_time 等)
    並自動關聯已存在的乳酸測驗點。
    """
    raw_fields = act_item.get("raw_fields", {})
    ts_values = raw_fields.get("time_series", {}).get("arrayValue", {}).get("values", [])
    start_time = act_item.get("start_time", datetime.now())
    duration_min = act_item.get("duration_minutes", 0.0)

    rows = []
    for pt in ts_values:
        pf = pt.get("mapValue", {}).get("fields", {})
        el_min = float(_get_fs_field(pf.get("elapsed_minutes"), 0.0))
        r = {"elapsed_minutes": el_min}

        hr = _get_fs_field(pf.get("heart_rate"))
        r["heart_rate"] = float(hr) if hr is not None else np.nan

        pwr = _get_fs_field(pf.get("power"))
        if pwr is None:
            pwr = _get_fs_field(pf.get("power_30s"))
        r["power"] = float(pwr) if pwr is not None else np.nan

        core = _get_fs_field(pf.get("core_temp"))
        r["core_temp"] = float(core) if core is not None else np.nan

        cad = _get_fs_field(pf.get("cadence"))
        r["cadence"] = float(cad) if cad is not None else np.nan

        lat = _get_fs_field(pf.get("lat"))
        r["lat"] = float(lat) if lat is not None else np.nan

        lng = _get_fs_field(pf.get("lng"))
        r["lng"] = float(lng) if lng is not None else np.nan

        alt = _get_fs_field(pf.get("altitude"))
        r["altitude"] = float(alt) if alt is not None else np.nan

        dist = _get_fs_field(pf.get("distance"))
        r["distance"] = float(dist) if dist is not None else np.nan

        rows.append(r)

    # 若 time_series 為空，建立基礎時間軸
    if not rows and duration_min > 0:
        step_min = 0.5
        total_steps = int(duration_min / step_min) + 1
        avg_p = act_item.get("avg_power", 0)
        avg_h = act_item.get("avg_hr", 0)
        for i in range(total_steps):
            m = i * step_min
            rows.append({
                "elapsed_minutes": m,
                "power": float(avg_p) if avg_p > 0 else np.nan,
                "heart_rate": float(avg_h) if avg_h > 0 else np.nan,
                "core_temp": np.nan,
                "cadence": np.nan,
                "lat": np.nan,
                "lng": np.nan,
                "altitude": np.nan,
                "distance": np.nan
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("elapsed_minutes").reset_index(drop=True)
        df["timestamp"] = [start_time + timedelta(minutes=float(m)) for m in df["elapsed_minutes"]]
    else:
        df = pd.DataFrame(columns=["elapsed_minutes", "timestamp", "heart_rate", "power", "core_temp"])

    # 關聯乳酸數據（精確活動級別關聯）
    lactate_rows = []
    act_doc_id = act_item.get("doc_id", "")
    if lactates_on_day:
        for la in lactates_on_day:
            b_id = la.get("fit_doc_id")
            la_time = la.get("record_time", start_time)
            diff_min = round((la_time - start_time).total_seconds() / 60.0, 1)

            # 若此乳酸有明確綁定活動 ID，必須相符
            if b_id and b_id != act_doc_id:
                continue

            # 若未指定綁定 ID，採樣時間必須在合理範圍：開始前 30 分鐘 ~ 結束後 60 分鐘
            if not b_id and duration_min > 0:
                if diff_min < -30.0 or diff_min > (duration_min + 60.0):
                    continue

            lactate_rows.append({
                "相對時間 (分鐘)": diff_min,
                "乳酸值 (mmol/L)": float(la.get("lactate_mmol", 0.0)),
                "血糖值 (mg/dL)": float(la["glucose_mgdl"]) if la.get("glucose_mgdl") is not None else np.nan
            })

    if lactate_rows:
        df_la = pd.DataFrame(lactate_rows).sort_values("相對時間 (分鐘)").reset_index(drop=True)
    else:
        df_la = pd.DataFrame({
            "相對時間 (分鐘)": pd.Series(dtype="float"),
            "乳酸值 (mmol/L)": pd.Series(dtype="float"),
            "血糖值 (mg/dL)": pd.Series(dtype="float")
        })

    return {
        "df": df,
        "df_laps": pd.DataFrame(),
        "start_time": start_time,
        "sport": act_item.get("sport", "running"),
        "sub_sport": act_item.get("sub_sport", "generic"),
        "file_name": act_item.get("file_name", "Cloud_Activity.fit"),
        "activity_name": act_item.get("activity_name", ""),
        "doc_id": act_item.get("doc_id", ""),
        "lactate_df": df_la,
        "from_cloud": True
    }


def convert_firebase_activity_to_session_dict(
    act_item: Dict[str, Any],
    lactates_on_day: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    將 Firestore 中的 fit_record 與當日乳酸紀錄，轉換為 integrate_reports.build_integrated_html()
    所要求的多期 session_dict 結構。
    """
    raw_fields = act_item.get("raw_fields", {})
    ts_values = raw_fields.get("time_series", {}).get("arrayValue", {}).get("values", [])
    start_time = act_item.get("start_time", datetime.now())
    duration_min = float(act_item.get("duration_minutes", 0.0))

    power_30s = []
    hr_30s = []
    temp_10s = []

    # 降採樣以維持前端 Chart.js 極致效能 (~500 點)
    step = max(1, len(ts_values) // 500) if ts_values else 1

    for i in range(0, len(ts_values), step):
        pt = ts_values[i]
        pf = pt.get("mapValue", {}).get("fields", {})
        el_min = round(float(_get_fs_field(pf.get("elapsed_minutes"), 0.0)), 2)

        pwr = _get_fs_field(pf.get("power"))
        if pwr is None:
            pwr = _get_fs_field(pf.get("power_30s"))
        if pwr is not None and not np.isnan(float(pwr)):
            power_30s.append({'x': el_min, 'y': round(float(pwr), 1)})

        hr = _get_fs_field(pf.get("heart_rate"))
        if hr is not None and not np.isnan(float(hr)):
            hr_30s.append({'x': el_min, 'y': round(float(hr), 1)})

        core = _get_fs_field(pf.get("core_temp"))
        if core is not None and not np.isnan(float(core)):
            temp_10s.append({'x': el_min, 'y': round(float(core), 2)})

    if not power_30s and duration_min > 0:
        avg_p = float(act_item.get("avg_power", 0))
        avg_h = float(act_item.get("avg_hr", 0))
        for m in [0.0, round(duration_min / 2.0, 1), round(duration_min, 1)]:
            if avg_p > 0:
                power_30s.append({'x': m, 'y': avg_p})
            if avg_h > 0:
                hr_30s.append({'x': m, 'y': avg_h})

    lactate_pts = []
    glucose_pts = []

    act_doc_id = act_item.get("doc_id", "")
    if lactates_on_day:
        for la in lactates_on_day:
            b_id = la.get("fit_doc_id")
            la_time = la.get("record_time", start_time)
            diff_min = round((la_time - start_time).total_seconds() / 60.0, 1)

            # 若此乳酸有明確綁定活動 ID，必須相符
            if b_id and b_id != act_doc_id:
                continue

            # 若未指定綁定 ID，採樣時間必須在合理範圍：開始前 30 分鐘 ~ 結束後 60 分鐘
            if not b_id and duration_min > 0:
                if diff_min < -30.0 or diff_min > (duration_min + 60.0):
                    continue

            pw_at_t = None
            hr_at_t = None
            if power_30s:
                nearest_pw = min(power_30s, key=lambda pt: abs(pt['x'] - diff_min))
                if abs(nearest_pw['x'] - diff_min) <= 3.0:
                    pw_at_t = int(nearest_pw['y'])
            if hr_30s:
                nearest_hr = min(hr_30s, key=lambda pt: abs(pt['x'] - diff_min))
                if abs(nearest_hr['x'] - diff_min) <= 3.0:
                    hr_at_t = int(nearest_hr['y'])

            la_val = la.get("lactate_mmol")
            if la_val is not None:
                item = {
                    'x': diff_min,
                    'y': float(la_val),
                    'source': la.get("source", "採樣點")
                }
                if pw_at_t is not None:
                    item['power'] = pw_at_t
                if hr_at_t is not None:
                    item['hr'] = hr_at_t
                lactate_pts.append(item)

            glu_val = la.get("glucose_mgdl")
            if glu_val is not None and str(glu_val) != "-":
                item_g = {
                    'x': diff_min,
                    'y': float(glu_val),
                    'source': la.get("source", "採樣點")
                }
                if pw_at_t is not None:
                    item_g['power'] = pw_at_t
                if hr_at_t is not None:
                    item_g['hr'] = hr_at_t
                glucose_pts.append(item_g)

    lactate_pts.sort(key=lambda p: p['x'])
    glucose_pts.sort(key=lambda p: p['x'])

    dur_m = int(duration_min)
    dur_s = int(round((duration_min - dur_m) * 60))
    dur_str = f"{dur_m:02d}:{dur_s:02d}"

    stats = {
        'duration': dur_str,
        'avg_power': int(act_item.get("avg_power", 0)),
        'max_power': int(act_item.get("max_power", 0)),
        'avg_hr': int(act_item.get("avg_hr", 0)),
        'max_hr': int(act_item.get("max_hr", 0)),
    }
    if lactate_pts:
        max_lac = max(pt['y'] for pt in lactate_pts if pt.get('y') is not None)
        stats['max_lactate'] = f"{max_lac:.1f} mmol/L"
    if glucose_pts:
        max_glu = max(pt['y'] for pt in glucose_pts if pt.get('y') is not None)
        stats['max_glucose'] = f"{int(max_glu)} mg/dL"

    st_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        'startTime': st_str,
        'power_30s': power_30s,
        'hr_30s': hr_30s,
        'temp_10s': temp_10s,
        'lactate': lactate_pts,
        'glucose': glucose_pts,
        'stats': stats,
        'source': 'firebase',
        'activity_name': act_item.get("activity_name", act_item.get("file_name", "Cloud Activity"))
    }


def get_sport_badge(sport: str, sub_sport: str = "") -> Tuple[str, str]:
    """取得運動項目的 Emoji 圖示與顏色"""
    sp = str(sport).lower()
    if "cycl" in sp or "bike" in sp or "騎" in sp:
        return "🚴", "#00f2fe"
    elif "run" in sp or "跑" in sp:
        return "🏃", "#ff5252"
    elif "swim" in sp or "游" in sp:
        return "🏊", "#4facfe"
    elif "walk" in sp or "健走" in sp or "步" in sp:
        return "🚶", "#00e676"
    elif "fit" in sp or "gym" in sp or "重訓" in sp:
        return "🏋️", "#ffab00"
    return "🎯", "#94a3b8"


def save_bound_lactate_to_firestore(
    uid: str,
    token: str,
    fit_doc_id: str,
    start_time: datetime,
    lactate_df: pd.DataFrame
) -> Tuple[bool, str]:
    """
    將使用者在介面中輸入的乳酸數據綁定至特定 fit_record，並寫入 Firestore lactate_records。
    同時將該 fit_record 標記為 has_lactate = True。
    """
    if not uid or not token:
        return False, "未登入 MyLactate 雲端帳號"
    if lactate_df is None or lactate_df.empty:
        return False, "乳酸數據為空，請在表格中至少輸入一筆數據"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    valid_count = 0

    for _, row in lactate_df.iterrows():
        t = row.get("相對時間 (分鐘)")
        la = row.get("乳酸值 (mmol/L)")
        glu = row.get("血糖值 (mg/dL)")

        if pd.isna(t) or pd.isna(la):
            continue

        rec_dt = start_time + timedelta(minutes=float(t))
        la_payload = {
            "fields": {
                "year": {"integerValue": str(rec_dt.year)},
                "month": {"integerValue": str(rec_dt.month)},
                "day": {"integerValue": str(rec_dt.day)},
                "hour": {"integerValue": str(rec_dt.hour)},
                "minute": {"integerValue": str(rec_dt.minute)},
                "final_la_mmol": {"doubleValue": float(la)},
                "source": {"stringValue": "calendar_bind"}
            }
        }
        if fit_doc_id:
            la_payload["fields"]["fit_doc_id"] = {"stringValue": str(fit_doc_id)}
        if pd.notna(glu):
            la_payload["fields"]["final_glu_mgdl"] = {"doubleValue": float(glu)}

        la_doc_id = f"la_{rec_dt.strftime('%Y%m%d_%H%M%S')}"
        la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records/{la_doc_id}"
        try:
            r = requests.patch(la_url, headers=headers, json=la_payload, timeout=8)
            if r.status_code in [200, 201]:
                valid_count += 1
        except Exception:
            pass

    if valid_count > 0 and fit_doc_id:
        fit_patch_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records/{fit_doc_id}?updateMask.fieldPaths=has_lactate"
        fit_patch_payload = {
            "fields": {
                "has_lactate": {"booleanValue": True}
            }
        }
        try:
            requests.patch(fit_patch_url, headers=headers, json=fit_patch_payload, timeout=8)
        except Exception:
            pass

    # 清除快取以即時更新月曆
    st.session_state.pop(f"cal_cache_data_{uid}", None)
    st.session_state.pop("cached_weekly_report_html", None)
    st.session_state.pop(f"date_bounds_v4_{uid}", None)

    return True, f"成功綁定並儲存 {valid_count} 筆乳酸數據至雲端！"


def render_activity_calendar(uid: str, token: str, theme: str = "dark", mode: str = "single"):
    """
    手機極致響應式運動數據月曆 (支援單期/多期模式、單擊選取/單擊取消、URL模式記憶)
    """
    today = date.today()
    if "cal_view_year" not in st.session_state:
        st.session_state["cal_view_year"] = today.year
        st.session_state["cal_view_month"] = today.month

    mode_param = "multi" if mode == "multi" else "single"

    # 1. 抓取雲端數據 (優先載入，以提供選取及運算所需之資料)
    acts_by_date, las_by_date = fetch_user_calendar_data(uid, token)

    # 多期模式：純下拉選單連續批次選取 (完全不顯示月曆，直覺迅速，先選完再統一運算)
    if mode == "multi":
        st.markdown("#### ☁️ 快速選取要納入多期對照的歷史期數")
        st.caption("💡 點開下方下拉選單，即可**連續勾選多個歷史測驗**（支援打字搜尋日期或關鍵字）。選取完成後，滑至下方確認清單並點擊「🚀 開始整合並繪製多期對照圖表」即可完成運算。")

        cloud_pool = st.session_state.setdefault("multi_selected_cloud_sessions", {})
        currently_selected_dates = sorted(
            list(set([k.split("_")[0] for k in cloud_pool.keys()])),
            reverse=True
        )

        all_dates = sorted(list(set(list(acts_by_date.keys()) + list(las_by_date.keys()))), reverse=True)

        if not all_dates:
            st.info("💡 目前您的 MyLactate 雲端帳號中尚未有任何手錶 FIT 運動記錄或乳酸數據。")
            return

        def _format_date_label(d_val):
            d_acts = acts_by_date.get(d_val, [])
            d_las = las_by_date.get(d_val, [])
            parts = []
            if d_acts:
                sp_ico, _ = get_sport_badge(d_acts[0].get("sport", ""))
                tot_m = int(sum(a.get("duration_minutes", 0) for a in d_acts))
                parts.append(f"{sp_ico}{tot_m}分({len(d_acts)}場)")
            if d_las:
                parts.append(f"💧{len(d_las)}筆乳酸")
            return f"📅 {d_val} | {' · '.join(parts)}" if parts else f"📅 {d_val}"

        col_b1, col_b2 = st.columns([1, 4])
        with col_b1:
            if st.button("🗑️ 清空所有勾選", key="btn_clear_all_multi_dates", use_container_width=True):
                st.session_state["multi_selected_cloud_sessions"] = {}
                st.session_state.pop('latest_output_html', None)
                st.rerun()

        picked_dates = st.multiselect(
            "請點選或搜尋加入多期對照的日期（可連續點選加入）：",
            options=all_dates,
            default=[d for d in currently_selected_dates if d in all_dates],
            format_func=_format_date_label,
            key="multi_cloud_dates_picker",
            placeholder="點擊此處展開下拉選單，連續加入要比較的期數..."
        )

        if set(picked_dates) != set(currently_selected_dates):
            new_pool = {}
            for d_str in picked_dates:
                day_acts = acts_by_date.get(d_str, [])
                day_las = las_by_date.get(d_str, [])
                if day_acts:
                    for a_i, a in enumerate(day_acts):
                        new_pool[f"{d_str}_{a.get('doc_id', a_i)}"] = convert_firebase_activity_to_session_dict(a, day_las)
                elif day_las:
                    fake_act = {
                        "start_time": day_las[0].get("record_time", datetime.strptime(d_str, "%Y-%m-%d")),
                        "duration_minutes": 30.0,
                        "avg_power": 0, "max_power": 0, "avg_hr": 0, "max_hr": 0,
                        "activity_name": f"乳酸檢測 ({len(day_las)}筆)"
                    }
                    new_pool[d_str] = convert_firebase_activity_to_session_dict(fake_act, day_las)
            st.session_state["multi_selected_cloud_sessions"] = new_pool
            st.session_state.pop('latest_output_html', None)
            st.rerun()

        if picked_dates:
            st.success(f"📋 目前已選取 **{len(cloud_pool)}** 個歷史期數。請滑至下方「📋 待整合之多期數據清單」確認並點擊開始運算。")
        else:
            st.info("👆 請於上方下拉選單中連續點選要比較的歷史期數。")

        return

    # ==========================================
    # 以下為單期分析模式月曆邏輯 (mode == "single")
    # ==========================================
    # 處理來自 HTML 點擊的 Query Params 跳轉 (支援單擊選取 / 選中後單擊取消)
    if "cal_date" in st.query_params:
        clicked_date = st.query_params.get("cal_date")
        try:
            c_y, c_m = [int(p) for p in clicked_date.split("-")[:2]]
            st.session_state["cal_view_year"] = c_y
            st.session_state["cal_view_month"] = c_m
        except Exception:
            pass

        # 單期模式：單擊選中，再次單擊取消
        curr_selected = st.session_state.get("cal_selected_date")
        if curr_selected == clicked_date:
            st.session_state["cal_selected_date"] = None
            st.toast(f"ℹ️ 已取消選取 {clicked_date}", icon="ℹ️")
        else:
            st.session_state["cal_selected_date"] = clicked_date
        st.session_state.pop("cal_quick_date_select", None)

        del st.query_params["cal_date"]
        st.query_params["app_mode"] = mode_param
        st.rerun()

    if "cal_m" in st.query_params:
        m_act = st.query_params.get("cal_m")
        v_y = st.session_state.get("cal_view_year", today.year)
        v_m = st.session_state.get("cal_view_month", today.month)
        if m_act == "prev":
            if v_m == 1:
                st.session_state["cal_view_year"] = v_y - 1
                st.session_state["cal_view_month"] = 12
            else:
                st.session_state["cal_view_month"] = v_m - 1
        elif m_act == "next":
            if v_m == 12:
                st.session_state["cal_view_year"] = v_y + 1
                st.session_state["cal_view_month"] = 1
            else:
                st.session_state["cal_view_month"] = v_m + 1
        elif m_act == "current":
            st.session_state["cal_view_year"] = today.year
            st.session_state["cal_view_month"] = today.month
        st.session_state.pop("cal_quick_date_select", None)
        del st.query_params["cal_m"]
        st.query_params["app_mode"] = mode_param
        st.rerun()

    v_year = st.session_state["cal_view_year"]
    v_month = st.session_state["cal_view_month"]

    # 2. 月份統計運算
    month_prefix = f"{v_year:04d}-{v_month:02d}"
    month_acts = [act for d, acts in acts_by_date.items() if d.startswith(month_prefix) for act in acts]
    month_las = [la for d, las in las_by_date.items() if d.startswith(month_prefix) for la in las]
    month_acts_with_la = [act for act in month_acts if act.get("has_lactate")]
    tot_dur = sum(a.get("duration_minutes", 0) for a in month_acts)
    dur_h = int(tot_dur // 60)
    dur_m = int(tot_dur % 60)
    unbound_count = len(month_acts) - len(month_acts_with_la)



    selected_date = st.session_state.get("cal_selected_date")
    if not selected_date or not selected_date.startswith(month_prefix):
        month_active_dates = sorted([d for d in acts_by_date.keys() if d.startswith(month_prefix)], reverse=True)
        if month_active_dates:
            selected_date = month_active_dates[0]
        else:
            selected_date = f"{v_year:04d}-{v_month:02d}-{today.day:02d}" if (today.year == v_year and today.month == v_month) else f"{v_year:04d}-{v_month:02d}-01"
        st.session_state["cal_selected_date"] = selected_date

    # 3. 雙模式配色設定 (Dark / Light 護眼高對比，全面移除刺眼螢光，乳酸改用水滴💧)
    is_dark = (str(theme).lower() != "light")

    if not is_dark:
        # 淺色模式：採用自然中性石板灰底與低飽和水滴藍，徹底告別刺眼與眩光
        pal = {
            "bg_nav": "#f8fafc",
            "bd_nav": "1px solid #e2e8f0",
            "title_nav": "#1e293b",       # 典雅石板黑灰 (高對比、不刺眼)
            "btn_bg": "#ffffff",
            "btn_bd": "1px solid #cbd5e1",
            "btn_color": "#334155",
            "stat_bg": "#ffffff",
            "stat_bd": "1px solid #e2e8f0",
            "stat_lbl": "#64748b",
            "stat_fit": "#0f766e",        # 沉著森林青綠
            "stat_dur": "#475569",        # 沉穩石板灰
            "stat_la": "#0284c7",         # 沉穩水滴藍 (象徵汗水乳酸)
            "stat_unbound": "#16a34a",    # 溫潤綠
            "th_normal": "#64748b",
            "th_weekend": "#e11d48",
            "th_bd": "1px solid #e2e8f0",
            "cell_bg_normal": "#ffffff",
            "cell_bd_normal": "1px solid #e2e8f0",
            "cell_num_normal": "#334155",
            "cell_bg_today": "#fefce8",   # 柔和暖象牙底
            "cell_bd_today": "2px solid #f59e0b",
            "cell_num_today": "#b45309",
            "cell_bg_sel": "#f1f5f9",     # 低飽和石板灰底 (取代刺眼天藍)
            "cell_bd_sel": "2px solid #334155", # 沉著深灰外框
            "cell_sh_sel": "box-shadow: 0 1px 3px rgba(0,0,0,0.12);",
            "cell_num_sel": "#0f172a",
            "badge_fit_bg": "#ecfdf5",
            "badge_fit_col": "#047857",
            "badge_la_bg": "#f0f9ff",     # 輕柔水滴藍
            "badge_la_col": "#0369a1",
            "dot_empty": "#cbd5e1",
            "legend_col": "#64748b",
            "legend_today_bg": "#fefce8",
            "legend_today_bd": "#f59e0b",
            "legend_sel_bg": "#f1f5f9",
            "legend_sel_bd": "#334155",
            "card_bg": "#ffffff",
            "card_bd": "1px solid #e2e8f0",
            "card_sh": "box-shadow: 0 1px 3px rgba(0,0,0,0.05);",
            "card_title": "#0f172a",
            "card_time": "#475569",
            "card_meta": "#64748b",
            "card_meta_bold": "#1e293b",
            "card_bound_la": "#0284c7",   # 水滴藍
            "card_unbound_la": "#16a34a"
        }
    else:
        # 深色模式：科技暗黑風格
        pal = {
            "bg_nav": "linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(30, 41, 59, 0.4))",
            "bd_nav": "1px solid rgba(56, 189, 248, 0.28)",
            "title_nav": "#38bdf8",
            "btn_bg": "rgba(255,255,255,0.08)",
            "btn_bd": "1px solid rgba(255,255,255,0.2)",
            "btn_color": "#e2e8f0",
            "stat_bg": "rgba(255, 255, 255, 0.03)",
            "stat_bd": "1px solid rgba(255, 255, 255, 0.08)",
            "stat_lbl": "#94a3b8",
            "stat_fit": "#38bdf8",
            "stat_dur": "#818cf8",
            "stat_la": "#38bdf8",
            "stat_unbound": "#34d399",
            "th_normal": "#94a3b8",
            "th_weekend": "#f87171",
            "th_bd": "1px solid rgba(255,255,255,0.1)",
            "cell_bg_normal": "rgba(255, 255, 255, 0.04)",
            "cell_bd_normal": "1px solid rgba(255, 255, 255, 0.09)",
            "cell_num_normal": "#cbd5e1",
            "cell_bg_today": "rgba(251, 191, 36, 0.12)",
            "cell_bd_today": "1.5px solid #fbbf24",
            "cell_num_today": "#fbbf24",
            "cell_bg_sel": "rgba(56, 189, 248, 0.2)",
            "cell_bd_sel": "2px solid #38bdf8",
            "cell_sh_sel": "box-shadow: 0 0 8px rgba(56, 189, 248, 0.35);",
            "cell_num_sel": "#ffffff",
            "badge_fit_bg": "rgba(52, 211, 153, 0.2)",
            "badge_fit_col": "#34d399",
            "badge_la_bg": "rgba(56, 189, 248, 0.25)",
            "badge_la_col": "#38bdf8",
            "dot_empty": "rgba(255,255,255,0.12)",
            "legend_col": "#94a3b8",
            "legend_today_bg": "transparent",
            "legend_today_bd": "#fbbf24",
            "legend_sel_bg": "rgba(56, 189, 248, 0.3)",
            "legend_sel_bd": "#38bdf8",
            "card_bg": "rgba(255, 255, 255, 0.04)",
            "card_bd": "1px solid rgba(255, 255, 255, 0.12)",
            "card_sh": "",
            "card_title": "#f8fafc",
            "card_time": "#38bdf8",
            "card_meta": "#94a3b8",
            "card_meta_bold": "#e2e8f0",
            "card_bound_la": "#38bdf8",
            "card_unbound_la": "#34d399"
        }

    # 4. 生成原生 HTML Table 月曆 (手機嚴格 7 欄不折疊)
    cal_matrix = calendar.monthcalendar(v_year, v_month)
    weekdays_zh = ["一", "二", "三", "四", "五", "六", "日"]

    html_parts = []
    
    # (A) 月曆頂部導覽列 (原生按鈕版，點擊完全不跳轉不重載)
    col_nav1, col_nav2, col_nav3 = st.columns([1.2, 2.6, 1.2])
    with col_nav1:
        if st.button("◀ 上月", key=f"btn_cal_nav_prev_{mode}_{v_year}_{v_month}", use_container_width=True):
            if v_month == 1:
                st.session_state["cal_view_year"] = v_year - 1
                st.session_state["cal_view_month"] = 12
            else:
                st.session_state["cal_view_month"] = v_month - 1
            st.session_state.pop("cal_quick_date_select", None)
            st.rerun()
    with col_nav2:
        t_color = pal["title_nav"]
        st.markdown(f"<div style='text-align:center; font-weight:800; font-size:15px; color:{t_color}; padding:6px 0; white-space:nowrap;'>📅 {v_year} 年 {v_month:02d} 月</div>", unsafe_allow_html=True)
    with col_nav3:
        if st.button("下月 ▶", key=f"btn_cal_nav_next_{mode}_{v_year}_{v_month}", use_container_width=True):
            if v_month == 12:
                st.session_state["cal_view_year"] = v_year + 1
                st.session_state["cal_view_month"] = 1
            else:
                st.session_state["cal_view_month"] = v_month + 1
            st.session_state.pop("cal_quick_date_select", None)
            st.rerun()

    # (B) 當月運動摘要統計列 (4 格等寬 Table，永不換行)
    html_parts.append(f'''
    <table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:4px; margin-bottom:8px;">
      <tr>
        <td style="width:25%; background:{pal['stat_bg']}; border:{pal['stat_bd']}; border-radius:8px; text-align:center; padding:6px 2px; vertical-align:middle;">
          <div style="font-size:14px; font-weight:800; color:{pal['stat_fit']}; line-height:1.1;">{len(month_acts)}</div>
          <div style="font-size:10px; color:{pal['stat_lbl']}; margin-top:2px; white-space:nowrap;">🏃 FIT運動</div>
        </td>
        <td style="width:25%; background:{pal['stat_bg']}; border:{pal['stat_bd']}; border-radius:8px; text-align:center; padding:6px 2px; vertical-align:middle;">
          <div style="font-size:14px; font-weight:800; color:{pal['stat_dur']}; line-height:1.1;">{dur_h}h{dur_m}m</div>
          <div style="font-size:10px; color:{pal['stat_lbl']}; margin-top:2px; white-space:nowrap;">⏱️ 總時長</div>
        </td>
        <td style="width:25%; background:{pal['stat_bg']}; border:{pal['stat_bd']}; border-radius:8px; text-align:center; padding:6px 2px; vertical-align:middle;">
          <div style="font-size:14px; font-weight:800; color:{pal['stat_la']}; line-height:1.1;">{len(month_acts_with_la)}</div>
          <div style="font-size:10px; color:{pal['stat_lbl']}; margin-top:2px; white-space:nowrap;">💧 已測乳酸</div>
        </td>
        <td style="width:25%; background:{pal['stat_bg']}; border:{pal['stat_bd']}; border-radius:8px; text-align:center; padding:6px 2px; vertical-align:middle;">
          <div style="font-size:14px; font-weight:800; color:{pal['stat_unbound']}; line-height:1.1;">{unbound_count}</div>
          <div style="font-size:10px; color:{pal['stat_lbl']}; margin-top:2px; white-space:nowrap;">⚡ 待標乳酸</div>
        </td>
      </tr>
    </table>
    ''')

    # (C) 圖例列
    html_parts.append(f'''
    <div style="display:flex; justify-content:center; gap:8px; font-size:11px; color:{pal['legend_col']}; margin-bottom:6px; flex-wrap:wrap;">
      <span style="display:inline-flex; align-items:center; gap:3px;"><span style="background-color:#16a34a; width:6px; height:6px; border-radius:50%; display:inline-block;"></span> FIT運動</span>
      <span style="display:inline-flex; align-items:center; gap:3px;"><span style="background-color:{pal['stat_la']}; width:6px; height:6px; border-radius:50%; display:inline-block;"></span> 💧 乳酸數據</span>
      <span style="display:inline-flex; align-items:center; gap:3px;"><span style="border:1px solid {pal['legend_today_bd']}; background:{pal['legend_today_bg']}; border-radius:2px; width:7px; height:7px; display:inline-block;"></span> 今日</span>
      <span style="display:inline-flex; align-items:center; gap:3px;"><span style="border:1.5px solid {pal['legend_sel_bd']}; background:{pal['legend_sel_bg']}; border-radius:2px; width:7px; height:7px; display:inline-block;"></span> 選中</span>
    </div>
    ''')

    # (D) 月曆主表格 (HTML Table，瀏覽器原生 7 欄約束，手機絕對不變直條)
    html_parts.append('<table style="width:100%; table-layout:fixed; border-collapse:separate; border-spacing:3px; margin:0 auto 10px auto; box-sizing:border-box;">')
    
    # 星期標題 (Th)
    html_parts.append('<thead><tr>')
    for w in weekdays_zh:
        color = pal['th_weekend'] if w in ["六", "日"] else pal['th_normal']
        html_parts.append(f'<th style="width:14.28%; text-align:center; padding:3px 0; font-size:12px; font-weight:700; color:{color}; border-bottom:{pal["th_bd"]};">{w}</th>')
    html_parts.append('</tr></thead>')

    # 日期方格 (Tb)
    html_parts.append('<tbody>')
    for week in cal_matrix:
        html_parts.append('<tr>')
        for day_num in week:
            if day_num == 0:
                html_parts.append('<td style="width:14.28%; height:44px; background:transparent; border:none;"></td>')
                continue

            d_str = f"{v_year:04d}-{v_month:02d}-{day_num:02d}"
            is_selected = (d_str == selected_date)
            is_today = (d_str == today.strftime("%Y-%m-%d"))

            day_acts = acts_by_date.get(d_str, [])
            day_las = las_by_date.get(d_str, [])

            # 樣式計算 (多期模式下檢查是否已被勾選入池)
            cloud_pool = st.session_state.get("multi_selected_cloud_sessions", {})
            is_multi_sel = (mode == "multi" and any(k.startswith(d_str) for k in cloud_pool.keys()))

            if is_multi_sel or (mode == "single" and is_selected):
                bg = pal['cell_bg_sel']
                bd = pal['cell_bd_sel']
                box_sh = pal['cell_sh_sel']
                num_col = pal['cell_num_sel']
            elif is_today:
                bg = pal['cell_bg_today']
                bd = pal['cell_bd_today']
                box_sh = ""
                num_col = pal['cell_num_today']
            else:
                bg = pal['cell_bg_normal']
                bd = pal['cell_bd_normal']
                box_sh = ""
                num_col = pal['cell_num_normal']

            # 徽章標示 (乳酸改為流汗水滴 💧，多期選中時附加 ✓ 標籤)
            badges = []
            if is_multi_sel:
                badges.append('<span style="background:#dcfce7; color:#15803d; border-radius:3px; padding:0 2px; font-size:9px; font-weight:800; line-height:1;">✓</span>')

            if day_acts and day_las:
                badges.append(f'<span style="background:{pal["badge_fit_bg"]}; color:{pal["badge_fit_col"]}; border-radius:3px; padding:0 2px; font-size:9px; font-weight:700; line-height:1;">🏃</span><span style="background:{pal["badge_la_bg"]}; color:{pal["badge_la_col"]}; border-radius:3px; padding:0 2px; font-size:9px; font-weight:700; line-height:1; margin-left:1px;">💧</span>')
            elif day_acts:
                sp_ico, _ = get_sport_badge(day_acts[0].get("sport", ""))
                badges.append(f'<span style="background:{pal["badge_fit_bg"]}; color:{pal["badge_fit_col"]}; border-radius:3px; padding:0 2px; font-size:9px; font-weight:700; line-height:1;">{sp_ico}</span>')
            elif day_las:
                badges.append(f'<span style="background:{pal["badge_la_bg"]}; color:{pal["badge_la_col"]}; border-radius:3px; padding:0 2px; font-size:9px; font-weight:700; line-height:1;">💧</span>')
            else:
                if not badges:
                    badges.append(f'<span style="color:{pal["dot_empty"]}; font-size:10px; line-height:1;">·</span>')

            badge_html = "".join(badges)

            cell_html = (
                f'<td style="width:14.28%; height:44px; padding:1px; vertical-align:middle; text-align:center; background:{bg}; border:{bd}; border-radius:6px; {box_sh}">'
                f'<a href="?cal_date={d_str}&app_mode={mode_param}" target="_self" style="display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%; text-decoration:none;" title="{d_str}: {len(day_acts)}場活動, {len(day_las)}筆乳酸">'
                f'<span style="font-size:13px; font-weight:700; line-height:1.1; color:{num_col};">{day_num}</span>'
                f'<div style="margin-top:2px; height:12px; display:flex; align-items:center; justify-content:center;">{badge_html}</div>'
                f'</a>'
                f'</td>'
            )
            html_parts.append(cell_html)
        html_parts.append('</tr>')

    html_parts.append('</tbody></table>')

    # 一次性渲染原生 Table 月曆
    st.markdown("".join(html_parts), unsafe_allow_html=True)

    if mode == "multi":
        cloud_pool = st.session_state.get("multi_selected_cloud_sessions", {})
        if cloud_pool:
            st.success(f"📋 目前已連續加入 **{len(cloud_pool)}** 個歷史期數（請至下方「📋 待整合之多期數據清單」確認並點擊開始運算）。")
        else:
            st.info("💡 目前尚未勾選任何期數。請於上方多選清單中連續點選要比較的歷史期數。")
        return


    # 5. 手機友善的快速日期下拉選單 (供拇指快速切換)
    all_dates_with_data = sorted(
        list(set(list(acts_by_date.keys()) + list(las_by_date.keys()))),
        reverse=True
    )
    month_dates_with_data = [d for d in all_dates_with_data if d.startswith(month_prefix)]

    if month_dates_with_data:
        date_options = []
        date_map = {}
        for d in month_dates_with_data:
            d_acts = acts_by_date.get(d, [])
            d_las = las_by_date.get(d, [])
            info_parts = []
            if d_acts:
                sp_ico, _ = get_sport_badge(d_acts[0].get("sport", ""))
                tot_m = int(sum(a.get("duration_minutes", 0) for a in d_acts))
                info_parts.append(f"{sp_ico}{tot_m}分({len(d_acts)}場)")
            if d_las:
                info_parts.append(f"💧{len(d_las)}筆乳酸")
            lbl = f"{d} | {' · '.join(info_parts)}"
            date_options.append(lbl)
            date_map[lbl] = d

        cur_idx = 0
        for i, opt in enumerate(date_options):
            if date_map[opt] == selected_date:
                cur_idx = i
                st.session_state["cal_quick_date_select"] = opt
                break

        col_q1, col_q2 = st.columns([3, 1])
        with col_q1:
            sel_opt = st.selectbox(
                "📌 快速挑選當月有運動/乳酸的日期：",
                date_options,
                index=cur_idx,
                key="cal_quick_date_select"
            )
            if sel_opt and date_map[sel_opt] != selected_date:
                st.session_state["cal_selected_date"] = date_map[sel_opt]
                st.rerun()
        with col_q2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 重新整理", key="btn_cal_force_refresh", use_container_width=True):
                fetch_user_calendar_data(uid, token, force_reload=True)
                st.rerun()

    # 6. 當日活動清單與一鍵綁定乳酸操作區
    st.markdown("---")
    curr_sel = st.session_state.get("cal_selected_date", today.strftime("%Y-%m-%d"))
    sel_acts = acts_by_date.get(curr_sel, [])
    sel_las = las_by_date.get(curr_sel, [])

    st.markdown(f"#### 📋 【{curr_sel}】運動活動與乳酸資料")

    if not sel_acts and not sel_las:
        st.info(f"💡 **{curr_sel}** 尚未有任何手錶 FIT 運動記錄或乳酸數據。\n\n您可以使用左側邊欄：\n1. **【上傳您的 FIT 檔 (.fit)】** 手動上傳當天測試。\n2. **【🔗 運動手錶雲端綁定 (Intervals.icu)】** 一鍵同步該時段的手錶數據。")
    else:
        for idx, act in enumerate(sel_acts):
            sp_icon, sp_col = get_sport_badge(act.get("sport", ""))
            dur = int(act.get("duration_minutes", 0))
            st_time_str = act["start_time"].strftime("%H:%M")
            avg_p = act.get("avg_power", 0)
            max_p = act.get("max_power", 0)
            avg_h = act.get("avg_hr", 0)
            max_h = act.get("max_hr", 0)
            has_la = act.get("has_lactate", False)

            la_badge = f'<span style="color:{pal["card_bound_la"]}; font-weight:700;">💧 已綁定乳酸數據</span>' if (has_la or len(sel_las) > 0) else f'<span style="color:{pal["card_unbound_la"]}; font-weight:700;">⚡ 待標定乳酸</span>'

            with st.container():
                st.markdown(f'''
                <div style="background:{pal['card_bg']}; border:{pal['card_bd']}; {pal['card_sh']} border-radius:10px; padding:12px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:1.05rem; font-weight:700; color:{pal['card_title']};">{sp_icon} {act.get('activity_name', act.get('file_name'))}</span>
                        <span style="font-size:0.85rem; color:{pal['card_time']}; font-weight:600;">🕒 {st_time_str} ({dur}分鐘)</span>
                    </div>
                    <div style="display:flex; gap:12px; font-size:0.85rem; color:{pal['card_meta']}; margin-bottom:8px; flex-wrap:wrap;">
                        <span>⚡ 功率: <b style="color:{pal['card_meta_bold']};">{avg_p}</b> / {max_p} W</span>
                        <span>❤️ 心率: <b style="color:{pal['card_meta_bold']};">{avg_h}</b> / {max_h} bpm</span>
                        <span>{la_badge}</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                if mode == "multi":
                    cloud_pool = st.session_state.setdefault("multi_selected_cloud_sessions", {})
                    sess_key = f"{curr_sel}_{act.get('doc_id', idx)}"
                    is_in_pool = sess_key in cloud_pool

                    if is_in_pool:
                        if st.button(f"✅ 已在多期對照清單中（點擊移除）", key=f"btn_rem_multi_{act.get('doc_id', idx)}_{idx}", use_container_width=True):
                            cloud_pool.pop(sess_key, None)
                            st.rerun()
                    else:
                        if st.button(f"➕ 加入此活動至多期對照清單", key=f"btn_add_multi_{act.get('doc_id', idx)}_{idx}", type="primary", use_container_width=True):
                            sess_dict = convert_firebase_activity_to_session_dict(act, sel_las)
                            cloud_pool[sess_key] = sess_dict
                            st.toast(f"✅ 已將 {curr_sel} 運動加入多期對照清單！", icon="📊")
                            st.rerun()
                else:
                    btn_text = "🔄 載入活動並修改乳酸數據" if (has_la or len(sel_las) > 0) else "🚀 載入此活動並標定乳酸數據"
                    if st.button(btn_text, key=f"btn_load_act_{act['doc_id']}_{idx}", type="primary", use_container_width=True):
                        session_obj = build_session_from_fit_record(act, sel_las)
                        st.session_state["active_cloud_session"] = session_obj
                        st.session_state["custom_lactate"] = session_obj["lactate_df"]
                        st.session_state.pop("custom_lactate_editor", None)
                        st.toast(f"✅ 成功載入 {curr_sel} 運動數據！正在開啟分析圖表與乳酸編輯器...", icon="🚀")
                        st.rerun()

        if sel_las and not sel_acts:
            st.markdown("#### 💧 當日乳酸紀錄（未關聯手錶 FIT 檔案）：")
            la_table = []
            for la in sel_las:
                la_table.append({
                    "採樣時間": la["record_time"].strftime("%H:%M"),
                    "乳酸值 (mmol/L)": la["lactate_mmol"],
                    "血糖值 (mg/dL)": la.get("glucose_mgdl", "-")
                })
            st.table(pd.DataFrame(la_table))
            st.info("💡 如有該次測驗的手錶 .fit 檔案，請於左側上傳，系統將自動將上述乳酸數值與運動生理軌跡對齊。")
