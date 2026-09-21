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
                        "source": src
                    }
                    lactates_by_date.setdefault(date_str, []).append(la_item)
    except Exception as e:
        print(f"Error fetching lactate records for calendar: {e}")

    # 對每場活動關聯乳酸標記
    for d_str, acts in activities_by_date.items():
        las = lactates_by_date.get(d_str, [])
        for act in acts:
            if act["has_lactate"] or len(las) > 0:
                act["has_lactate"] = True
                act["lactate_count"] = len(las)

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

    # 關聯乳酸數據
    lactate_rows = []
    if lactates_on_day:
        for la in lactates_on_day:
            la_time = la.get("record_time", start_time)
            diff_min = round((la_time - start_time).total_seconds() / 60.0, 1)
            if abs(diff_min) > duration_min * 2 and duration_min > 0:
                diff_min = 0.0
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


def render_activity_calendar(uid: str, token: str, theme: str = "dark"):
    """
    手機極致響應式運動數據月曆：
    1. 採用純 CSS Grid (repeat(7, 1fr))，在手機螢幕上絕不縱向折疊破版，全月 31 天一覽無遺。
    2. 點擊日期格子立即切換選定日期，下方展開活動卡片。
    3. 同步提供拇指友善的快速日期下拉選單，雙重保障手機端體驗。
    """
    today = date.today()
    if "cal_view_year" not in st.session_state:
        st.session_state["cal_view_year"] = today.year
        st.session_state["cal_view_month"] = today.month

    # 處理來自 HTML 點擊的 Query Params 跳轉
    if "cal_date" in st.query_params:
        st.session_state["cal_selected_date"] = st.query_params.get("cal_date")
        del st.query_params["cal_date"]
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
        del st.query_params["cal_m"]
        st.rerun()

    v_year = st.session_state["cal_view_year"]
    v_month = st.session_state["cal_view_month"]

    # 1. 抓取雲端數據
    with st.spinner("載入雲端活動與乳酸紀錄中..."):
        acts_by_date, las_by_date = fetch_user_calendar_data(uid, token)

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

    # 3. 建立極致響應式 CSS 樣式 (完美適應手機 360px ~ 420px 寬度)
    css_styles = f"""
    <style>
    .m-cal-container {{
        width: 100%;
        max-width: 100%;
        margin: 0 auto 12px auto;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        box-sizing: border-box;
    }}
    .m-cal-nav {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, rgba(0, 242, 254, 0.12), rgba(79, 172, 254, 0.06));
        border: 1px solid rgba(0, 242, 254, 0.25);
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }}
    .m-cal-nav-title {{
        font-size: 1.05rem;
        font-weight: 700;
        color: #00f2fe;
        text-align: center;
        flex-grow: 1;
        margin: 0 4px;
    }}
    .m-cal-nav-btn {{
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 6px;
        color: #e2e8f0 !important;
        text-decoration: none !important;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 5px 9px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        white-space: nowrap;
        transition: all 0.15s;
    }}
    .m-cal-nav-btn:hover {{
        background: rgba(0, 242, 254, 0.25);
        border-color: #00f2fe;
        color: #ffffff !important;
    }}
    .m-cal-stats-bar {{
        display: flex;
        gap: 5px;
        margin-bottom: 8px;
        width: 100%;
    }}
    .m-cal-stat-pill {{
        flex: 1;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 6px 2px;
        text-align: center;
        min-width: 0;
    }}
    .m-cal-stat-pill .num {{
        font-size: 0.95rem;
        font-weight: 700;
        line-height: 1.1;
    }}
    .m-cal-stat-pill .lbl {{
        font-size: 0.65rem;
        color: #94a3b8;
        line-height: 1.1;
        margin-top: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .m-cal-legend {{
        display: flex;
        justify-content: center;
        gap: 10px;
        font-size: 0.72rem;
        color: #94a3b8;
        margin-bottom: 6px;
        flex-wrap: wrap;
    }}
    .m-cal-legend span {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }}
    .m-cal-grid {{
        display: grid !important;
        grid-template-columns: repeat(7, 1fr) !important;
        gap: 3px !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}
    .m-cal-wkday {{
        text-align: center;
        font-size: 0.75rem;
        font-weight: 700;
        color: #94a3b8;
        padding: 4px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .m-cal-cell {{
        aspect-ratio: 1 / 1;
        min-height: 42px;
        max-height: 54px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        color: #cbd5e1 !important;
        padding: 1px;
        box-sizing: border-box;
        position: relative;
        transition: all 0.15s ease;
    }}
    .m-cal-cell:hover {{
        border-color: #00f2fe;
        background: rgba(0, 242, 254, 0.15);
    }}
    .m-cal-cell.empty {{
        background: transparent;
        border: none;
        pointer-events: none;
    }}
    .m-cal-cell.today {{
        border: 1.5px solid #ffab00 !important;
    }}
    .m-cal-cell.selected {{
        background: rgba(0, 242, 254, 0.22) !important;
        border: 2px solid #00f2fe !important;
        box-shadow: 0 0 8px rgba(0, 242, 254, 0.4);
    }}
    .m-day-num {{
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 1;
    }}
    .m-badges-row {{
        display: flex;
        gap: 2px;
        margin-top: 2px;
        align-items: center;
        justify-content: center;
        font-size: 0.6rem;
        line-height: 1;
    }}
    .dot-fit {{
        background-color: #00e676;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        display: inline-block;
    }}
    .dot-la {{
        background-color: #ff5252;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        display: inline-block;
    }}
    .tag-fit {{
        background: rgba(0, 230, 118, 0.2);
        color: #00e676;
        border-radius: 3px;
        padding: 0 2px;
        font-size: 0.58rem;
        font-weight: 700;
    }}
    .tag-la {{
        background: rgba(255, 82, 82, 0.25);
        color: #ff5252;
        border-radius: 3px;
        padding: 0 2px;
        font-size: 0.58rem;
        font-weight: 700;
    }}
    </style>
    """

    # 4. 生成 HTML 月曆元件
    cal_matrix = calendar.monthcalendar(v_year, v_month)
    weekdays_zh = ["一", "二", "三", "四", "五", "六", "日"]

    html_parts = [
        css_styles,
        '<div class="m-cal-container">',
        '  <div class="m-cal-nav">',
        '    <a href="?cal_m=prev" target="_self" class="m-cal-nav-btn">◀ 上月</a>',
        f'   <div class="m-cal-nav-title">📅 {v_year} 年 {v_month:02d} 月</div>',
        '    <a href="?cal_m=next" target="_self" class="m-cal-nav-btn">下月 ▶</a>',
        '    <a href="?cal_m=current" target="_self" class="m-cal-nav-btn" style="margin-left:4px;">本月</a>',
        '  </div>',
        '  <div class="m-cal-stats-bar">',
        f'   <div class="m-cal-stat-pill"><div class="num" style="color:#00f2fe;">{len(month_acts)}</div><div class="lbl">🏃 FIT運動</div></div>',
        f'   <div class="m-cal-stat-pill"><div class="num" style="color:#4facfe;">{dur_h}h{dur_m}m</div><div class="lbl">⏱️ 總時長</div></div>',
        f'   <div class="m-cal-stat-pill"><div class="num" style="color:#ff5252;">{len(month_acts_with_la)}</div><div class="lbl">🩸 已測乳酸</div></div>',
        f'   <div class="m-cal-stat-pill"><div class="num" style="color:#00e676;">{unbound_count}</div><div class="lbl">⚡ 待標乳酸</div></div>',
        '  </div>',
        '  <div class="m-cal-legend">',
        '    <span><span class="dot-fit"></span> FIT運動</span>',
        '    <span><span class="dot-la"></span> 乳酸數據</span>',
        '    <span><span style="border:1px solid #ffab00; border-radius:2px; width:7px; height:7px; display:inline-block;"></span> 今日</span>',
        '    <span><span style="border:1.5px solid #00f2fe; background:rgba(0,242,254,0.3); border-radius:2px; width:7px; height:7px; display:inline-block;"></span> 選中</span>',
        '  </div>',
        '  <div class="m-cal-grid">'
    ]

    # 星期標題
    for w in weekdays_zh:
        html_parts.append(f'<div class="m-cal-wkday">{w}</div>')

    # 繪製日期方格
    for week in cal_matrix:
        for day_num in week:
            if day_num == 0:
                html_parts.append('<div class="m-cal-cell empty"></div>')
                continue

            d_str = f"{v_year:04d}-{v_month:02d}-{day_num:02d}"
            is_selected = (d_str == selected_date)
            is_today = (d_str == today.strftime("%Y-%m-%d"))

            day_acts = acts_by_date.get(d_str, [])
            day_las = las_by_date.get(d_str, [])

            cell_cls = ["m-cal-cell"]
            if is_selected:
                cell_cls.append("selected")
            if is_today:
                cell_cls.append("today")

            # 徽章標示
            badge_html = ""
            if day_acts and day_las:
                badge_html = '<div class="m-badges-row"><span class="tag-fit">🏃</span><span class="tag-la">🩸</span></div>'
            elif day_acts:
                sp_ico, _ = get_sport_badge(day_acts[0].get("sport", ""))
                badge_html = f'<div class="m-badges-row"><span class="tag-fit">{sp_ico}</span></div>'
            elif day_las:
                badge_html = f'<div class="m-badges-row"><span class="tag-la">🩸</span></div>'
            else:
                badge_html = '<div class="m-badges-row" style="color:rgba(255,255,255,0.15);">·</div>'

            cell_html = f"""
            <a href="?cal_date={d_str}" target="_self" class="{' '.join(cell_cls)}" title="{d_str}: {len(day_acts)}場活動, {len(day_las)}筆乳酸">
              <span class="m-day-num">{day_num}</span>
              {badge_html}
            </a>
            """
            html_parts.append(cell_html)

    html_parts.append('  </div>')
    html_parts.append('</div>')

    # 一次性渲染完整月曆
    st.markdown("".join(html_parts), unsafe_allow_html=True)

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
                info_parts.append(f"🩸{len(d_las)}筆乳酸")
            lbl = f"{d} | {' · '.join(info_parts)}"
            date_options.append(lbl)
            date_map[lbl] = d

        cur_idx = 0
        for i, opt in enumerate(date_options):
            if date_map[opt] == selected_date:
                cur_idx = i
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

            with st.container():
                st.markdown(f"""
                <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px; padding: 12px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 1.05rem; font-weight: 700; color: #f8fafc;">{sp_icon} {act.get('activity_name', act.get('file_name'))}</span>
                        <span style="font-size: 0.85rem; color: #00f2fe; font-weight: 600;">🕒 {st_time_str} ({dur}分鐘)</span>
                    </div>
                    <div style="display: flex; gap: 12px; font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px; flex-wrap: wrap;">
                        <span>⚡ 功率: <b style="color:#e2e8f0;">{avg_p}</b> / {max_p} W</span>
                        <span>❤️ 心率: <b style="color:#e2e8f0;">{avg_h}</b> / {max_h} bpm</span>
                        <span>{'<span style="color:#ff5252; font-weight:700;">🩸 已綁定乳酸數據</span>' if (has_la or len(sel_las) > 0) else '<span style="color:#00e676; font-weight:700;">⚡ 待標定乳酸</span>'}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                btn_text = "🔄 載入活動並修改乳酸數據" if (has_la or len(sel_las) > 0) else "🚀 載入此活動並標定乳酸數據"
                if st.button(btn_text, key=f"btn_load_act_{act['doc_id']}_{idx}", type="primary", use_container_width=True):
                    session_obj = build_session_from_fit_record(act, sel_las)
                    st.session_state["active_cloud_session"] = session_obj
                    st.session_state["custom_lactate"] = session_obj["lactate_df"]
                    st.session_state.pop("custom_lactate_editor", None)
                    st.toast(f"✅ 成功載入 {curr_sel} 運動數據！正在開啟分析圖表與乳酸編輯器...", icon="🚀")
                    st.rerun()

        if sel_las and not sel_acts:
            st.markdown("#### 🩸 當日乳酸紀錄（未關聯手錶 FIT 檔案）：")
            la_table = []
            for la in sel_las:
                la_table.append({
                    "採樣時間": la["record_time"].strftime("%H:%M"),
                    "乳酸值 (mmol/L)": la["lactate_mmol"],
                    "血糖值 (mg/dL)": la.get("glucose_mgdl", "-")
                })
            st.table(pd.DataFrame(la_table))
            st.info("💡 如有該次測驗的手錶 .fit 檔案，請於左側上傳，系統將自動將上述乳酸數值與運動生理軌跡對齊。")
