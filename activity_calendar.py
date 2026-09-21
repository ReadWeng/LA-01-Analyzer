# -*- coding: utf-8 -*-
"""
activity_calendar.py - 雲端運動紀錄月曆與乳酸資料綁定模組
支援將 Firebase Firestore 中的日常 FIT 運動紀錄以月曆呈現，
標記哪幾天已擷取 FIT 數據、哪幾天有乳酸測試，並支援點入載入活動綁定乳酸數據。
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
                    # 統一轉至當地時間 UTC+8 便於月曆對齊
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
            # 計算相對於運動開始的相對分鐘數
            diff_min = round((la_time - start_time).total_seconds() / 60.0, 1)
            # 若無精準小時分鐘，若同一天則依順序放置
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
    sub = str(sub_sport).lower()
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


def render_activity_calendar(uid: str, token: str, theme: str = "dark"):
    """
    在單期分析主畫面渲染精美、互動式的月曆檢視。
    顯示哪些天已擷取 FIT 數據、哪些天有乳酸，並支援一鍵點入綁定乳酸數據。
    """
    st.markdown("""
    <style>
    .cal-header-box {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, rgba(0, 242, 254, 0.08), rgba(79, 172, 254, 0.05));
        border: 1px solid rgba(0, 242, 254, 0.2);
        border-radius: 12px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }
    .cal-weekday-header {
        text-align: center;
        font-weight: 700;
        font-size: 0.95rem;
        color: #94a3b8;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    .cal-stat-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 8px 12px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    today = date.today()
    if "cal_view_year" not in st.session_state:
        st.session_state["cal_view_year"] = today.year
        st.session_state["cal_view_month"] = today.month

    v_year = st.session_state["cal_view_year"]
    v_month = st.session_state["cal_view_month"]

    # 1. 抓取雲端數據
    with st.spinner("載入雲端活動與乳酸紀錄中..."):
        acts_by_date, las_by_date = fetch_user_calendar_data(uid, token)

    # 2. 月曆頂部導覽列 (月份切換與重新整理)
    col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 2.5, 1, 1])

    with col_nav1:
        if st.button("◀ 上個月", key="btn_cal_prev_month", use_container_width=True):
            if v_month == 1:
                st.session_state["cal_view_year"] = v_year - 1
                st.session_state["cal_view_month"] = 12
            else:
                st.session_state["cal_view_month"] = v_month - 1
            st.rerun()

    with col_nav2:
        st.markdown(
            f"<h3 style='text-align: center; margin: 0; color: #00f2fe;'>📅 {v_year} 年 {v_month:02d} 月 訓練活動月曆</h3>",
            unsafe_allow_html=True
        )

    with col_nav3:
        if st.button("下個月 ▶", key="btn_cal_next_month", use_container_width=True):
            if v_month == 12:
                st.session_state["cal_view_year"] = v_year + 1
                st.session_state["cal_view_month"] = 1
            else:
                st.session_state["cal_view_month"] = v_month + 1
            st.rerun()

    with col_nav4:
        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            if st.button("本月", key="btn_cal_today_month", use_container_width=True):
                st.session_state["cal_view_year"] = today.year
                st.session_state["cal_view_month"] = today.month
                st.rerun()
        with col_sub2:
            if st.button("🔄", help="重新從 Firebase 同步最新資料", key="btn_cal_reload_data", use_container_width=True):
                fetch_user_calendar_data(uid, token, force_reload=True)
                st.rerun()

    # 3. 統計小卡區 (當前月份概況)
    month_prefix = f"{v_year:04d}-{v_month:02d}"
    month_acts = [act for d, acts in acts_by_date.items() if d.startswith(month_prefix) for act in acts]
    month_las = [la for d, las in las_by_date.items() if d.startswith(month_prefix) for la in las]
    month_acts_with_la = [act for act in month_acts if act.get("has_lactate")]
    tot_dur = sum(a.get("duration_minutes", 0) for a in month_acts)

    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.markdown(f'<div class="cal-stat-card"><div style="font-size:0.85rem; color:#94a3b8;">🏃 本月擷取 FIT 總場次</div><div style="font-size:1.3rem; font-weight:700; color:#00f2fe;">{len(month_acts)} 場</div></div>', unsafe_allow_html=True)
    with stat_cols[1]:
        dur_h = int(tot_dur // 60)
        dur_m = int(tot_dur % 60)
        st.markdown(f'<div class="cal-stat-card"><div style="font-size:0.85rem; color:#94a3b8;">⏱️ 本月累計訓練時長</div><div style="font-size:1.3rem; font-weight:700; color:#4facfe;">{dur_h}小時 {dur_m}分</div></div>', unsafe_allow_html=True)
    with stat_cols[2]:
        st.markdown(f'<div class="cal-stat-card"><div style="font-size:0.85rem; color:#94a3b8;">🩸 已標定乳酸測試</div><div style="font-size:1.3rem; font-weight:700; color:#ff5252;">{len(month_acts_with_la)} 場 ({len(month_las)} 點)</div></div>', unsafe_allow_html=True)
    with stat_cols[3]:
        unbound_count = len(month_acts) - len(month_acts_with_la)
        st.markdown(f'<div class="cal-stat-card"><div style="font-size:0.85rem; color:#94a3b8;">⚡ 待綁乳酸日常運動</div><div style="font-size:1.3rem; font-weight:700; color:#00e676;">{unbound_count} 場</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

    # 4. 繪製星期標題列 (週一至週日)
    weekdays_tw = ["週一 (Mon)", "週二 (Tue)", "週三 (Wed)", "週四 (Thu)", "週五 (Fri)", "週六 (Sat)", "週日 (Sun)"]
    hdr_cols = st.columns(7)
    for i, w_name in enumerate(weekdays_tw):
        with hdr_cols[i]:
            st.markdown(f"<div class='cal-weekday-header'>{w_name}</div>", unsafe_allow_html=True)

    # 5. 計算當月份排版 (使用 calendar.monthcalendar，每週 7 天，0 代表非當月)
    cal_matrix = calendar.monthcalendar(v_year, v_month)
    selected_date = st.session_state.get("cal_selected_date")

    # 若尚未選定日期，預設選取本月最近有活動的一天或今天
    if not selected_date or not selected_date.startswith(month_prefix):
        month_active_dates = sorted([d for d in acts_by_date.keys() if d.startswith(month_prefix)], reverse=True)
        if month_active_dates:
            selected_date = month_active_dates[0]
        else:
            selected_date = f"{v_year:04d}-{v_month:02d}-{today.day:02d}" if (today.year == v_year and today.month == v_month) else f"{v_year:04d}-{v_month:02d}-01"
        st.session_state["cal_selected_date"] = selected_date

    # 6. 逐週、逐日繪製日曆按鈕與狀態 Badge
    for week in cal_matrix:
        row_cols = st.columns(7)
        for w_idx, day_num in enumerate(week):
            with row_cols[w_idx]:
                if day_num == 0:
                    # 非本月留白
                    st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
                    continue

                d_str = f"{v_year:04d}-{v_month:02d}-{day_num:02d}"
                is_selected = (d_str == selected_date)
                is_today = (d_str == today.strftime("%Y-%m-%d"))

                day_acts = acts_by_date.get(d_str, [])
                day_las = las_by_date.get(d_str, [])

                # 組合按鈕文字與狀態標記
                btn_lines = [f"{day_num:02d}"]
                if day_acts:
                    for a in day_acts[:2]:
                        sp_ico, _ = get_sport_badge(a.get("sport", ""))
                        dur = int(a.get("duration_minutes", 0))
                        btn_lines.append(f"{sp_ico}{dur}m")
                    if len(day_acts) > 2:
                        btn_lines.append(f"+{len(day_acts)-2}場")
                
                if day_las:
                    btn_lines.append(f"🩸{len(day_las)}點")
                elif not day_acts:
                    btn_lines.append("·")

                btn_label = "\n".join(btn_lines)

                # 按鈕外觀型態：選中時 primary，有乳酸時特殊提示
                btn_type = "primary" if is_selected else "secondary"
                
                if st.button(btn_label, key=f"btn_d_{d_str}", type=btn_type, use_container_width=True):
                    st.session_state["cal_selected_date"] = d_str
                    st.rerun()

    # 7. 當日活動清單與一鍵綁定乳酸操作區
    st.markdown("---")
    curr_sel = st.session_state.get("cal_selected_date", today.strftime("%Y-%m-%d"))
    sel_acts = acts_by_date.get(curr_sel, [])
    sel_las = las_by_date.get(curr_sel, [])

    col_det_title, col_det_badge = st.columns([3, 1])
    with col_det_title:
        st.markdown(f"### 📋 【{curr_sel}】運動活動與乳酸資料")
    with col_det_badge:
        if sel_acts:
            st.success(f"已擷取 {len(sel_acts)} 場 FIT 運動數據")
        else:
            st.caption("當日尚未有 FIT 數據記錄")

    if not sel_acts and not sel_las:
        st.info(f"💡 **{curr_sel}** 尚未有任何手錶 FIT 運動記錄或乳酸數據。\n\n您可以使用左側邊欄：\n1. **【上傳您的 FIT 檔 (.fit)】** 手動上傳當天測試。\n2. **【🔗 運動手錶雲端綁定 (Intervals.icu)】** 一鍵同步該時段的手錶數據。")
    else:
        # 列出當日活動卡片
        for idx, act in enumerate(sel_acts):
            sp_icon, sp_col = get_sport_badge(act.get("sport", ""))
            dur = int(act.get("duration_minutes", 0))
            st_time_str = act["start_time"].strftime("%H:%M")
            avg_p = act.get("avg_power", 0)
            max_p = act.get("max_power", 0)
            avg_h = act.get("avg_hr", 0)
            max_h = act.get("max_hr", 0)
            has_la = act.get("has_lactate", False)

            # 建立卡片
            with st.container():
                col_c1, col_c2, col_c3, col_c4 = st.columns([2.5, 2.5, 1.8, 2.2])

                with col_c1:
                    st.markdown(f"**{sp_icon} 活動 {idx+1}：{act.get('activity_name', act.get('file_name'))}**")
                    st.caption(f"🕒 開始時間: `{st_time_str}` | ⏱️ 時長: **{dur} 分鐘** | 專項: `{act.get('sport')}`")

                with col_c2:
                    pwr_str = f"⚡ 功率: **{avg_p}** / {max_p} W" if avg_p > 0 else "⚡ 功率: 未記錄"
                    hr_str = f"❤️ 心率: **{avg_h}** / {max_h} bpm" if avg_h > 0 else "❤️ 心率: 未記錄"
                    st.markdown(f"{pwr_str}<br>{hr_str}", unsafe_allow_html=True)

                with col_c3:
                    if has_la or len(sel_las) > 0:
                        l_cnt = act.get("lactate_count", len(sel_las))
                        st.markdown(f"<span style='color: #ff5252; font-weight:700;'>🩸 已綁定 {l_cnt} 筆乳酸</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color: #00e676; font-weight:700;'>⚡ 待標定乳酸</span>", unsafe_allow_html=True)

                with col_c4:
                    btn_text = "🔄 載入活動並修改乳酸" if (has_la or len(sel_las) > 0) else "🚀 載入此活動並標定乳酸"
                    if st.button(btn_text, key=f"btn_load_act_{act['doc_id']}_{idx}", type="primary", use_container_width=True):
                        session_obj = build_session_from_fit_record(act, sel_las)
                        st.session_state["active_cloud_session"] = session_obj
                        st.session_state["custom_lactate"] = session_obj["lactate_df"]
                        st.session_state.pop("custom_lactate_editor", None)
                        st.toast(f"✅ 成功載入 {curr_sel} 運動數據！正在開啟分析圖表與乳酸編輯器...", icon="🚀")
                        st.rerun()

        # 若當天有乳酸但無關聯 FIT
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
        # 更新 fit_record 的 has_lactate = True
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

