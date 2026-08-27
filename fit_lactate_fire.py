
import requests
import streamlit as st
import json

FIREBASE_API_KEY = "AIzaSyAhU1n_IIF7AEHXkrQCoToR3gkKe2umpuM"

def login_to_firebase(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        data = res.json()
        if "localId" in data:
            st.session_state["firebase_uid"] = data["localId"]
            st.session_state["firebase_token"] = data["idToken"]
            st.session_state["firebase_email"] = email
            st.success("Firebase 雲端登入成功！")
            st.rerun()
        else:
            error_message = data.get("error", {}).get("message", "未知錯誤")
            st.error(f"登入失敗: {error_message}")
    except Exception as e:
        st.error(f"網路連線失敗: {str(e)}")

def logout_firebase():
    if "firebase_uid" in st.session_state:
        del st.session_state["firebase_uid"]
    if "firebase_email" in st.session_state:
        del st.session_state["firebase_email"]
    st.rerun()

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import fitparse
from datetime import datetime, timedelta
import io
import os
import sys
import glob
import re
import streamlit.components.v1 as components

# Append LactateReport folder for importing the integration library
sys.path.append(os.path.abspath("LactateReport"))
try:
    import integrate_reports
    import importlib
    importlib.reload(integrate_reports)
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "LactateReport"))
    import integrate_reports
    import importlib
    importlib.reload(integrate_reports)

def generate_html_report(df_summary, fig, start_time, file_name, metrics):
    plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    
    # Render summary table as HTML
    table_html = df_summary.to_html(index=False, classes="summary-table")
    
    # Metrics breakdown
    duration_str = metrics['duration_str']
    power_str = f"{metrics['avg_power']} / {metrics['max_power']} W"
    hr_str = f"{metrics['avg_hr']} / {metrics['max_hr']} bpm"
    core_str = f"{metrics['max_core']:.2f} °C" if metrics['max_core'] is not None else "未偵測"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FIT 檔與乳酸協同分析報告 - {file_name}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@300;400;600;700&display=swap');
        body {{
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'Outfit', 'Inter', sans-serif;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(90deg, #00e676, #00b0ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #8b949e;
            font-size: 1.1rem;
            margin-bottom: 30px;
        }}
        .metadata-bar {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 0.95rem;
            margin-bottom: 30px;
            color: #8b949e;
        }}
        .metadata-bar strong {{
            color: #ffffff;
        }}
        .kpi-container {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            text-align: center;
        }}
        .kpi-label {{
            font-size: 0.85rem;
            color: #8b949e;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .kpi-value {{
            font-size: 1.6rem;
            font-weight: 700;
        }}
        .section-title {{
            font-size: 1.8rem;
            font-weight: 600;
            margin-top: 40px;
            margin-bottom: 20px;
            border-left: 4px solid #00e676;
            padding-left: 15px;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            overflow: hidden;
        }}
        .summary-table th, .summary-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .summary-table th {{
            background-color: rgba(255, 255, 255, 0.05);
            color: #ffffff;
            font-weight: 600;
        }}
        .summary-table tr:hover {{
            background-color: rgba(255, 255, 255, 0.04);
        }}
        .chart-container {{
            background: rgba(30, 30, 38, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 40px;
        }}
        .footer {{
            text-align: center;
            color: #8b949e;
            font-size: 0.85rem;
            margin-top: 60px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🩸 FIT 檔與乳酸協同分析報告</div>
        <div class="subtitle">生理指標對照與乳酸動力學分析結果</div>
        
        <div class="metadata-bar">
            📅 <strong>活動開始時間</strong>: {start_time.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 
            📄 <strong>檔案名稱</strong>: {file_name}
        </div>
        
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">⏱️ 活動時長</div>
                <div class="kpi-value" style="color: #00b0ff;">{duration_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">⚡ 平均 / 最大功率</div>
                <div class="kpi-value" style="color: #29b6f6;">{power_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">❤️ 平均 / 最大心率</div>
                <div class="kpi-value" style="color: #ff5252;">{hr_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">🔥 最大核心溫度</div>
                <div class="kpi-value" style="color: #ff9100;">{core_str}</div>
            </div>
        </div>
        
        <div class="section-title">📊 數據協同分析圖表</div>
        <div class="chart-container">
            {plotly_html}
        </div>
        
        <div class="section-title">📋 生理數據對照彙整表</div>
        <div style="overflow-x: auto;">
            {table_html}
        </div>
        
        <div class="footer">
            報告產生於：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 本報告由 FIT 檔與乳酸協同分析工具產生。
        </div>
    </div>
</body>
</html>
"""
    return html_content

# 頁面配置與高級視覺主題
st.set_page_config(
    page_title="FIT 檔與乳酸協同分析工具",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入高級感 CSS 樣式
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@300;400;600;700&display=swap');

/* 全域字體與背景 */
html, body, [class*="css"] {
    font-family: 'Outfit', 'Inter', sans-serif;
}

/* 漸層標題 */
.title-container {
    background: linear-gradient(90deg, #00e676, #00b0ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 2.5rem;
    margin-bottom: 0.2rem;
    letter-spacing: -0.05rem;
}

.subtitle-text {
    font-size: 1.05rem;
    color: #8b949e;
    margin-bottom: 1.8rem;
}

/* 玻璃擬態卡片 */
.metric-card {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    padding: 15px 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    text-align: center;
    margin-bottom: 10px;
}
.metric-card:hover {
    border-color: rgba(0, 230, 118, 0.3);
    box-shadow: 0 4px 20px rgba(0, 230, 118, 0.1);
    transform: translateY(-2px);
}

.metric-label {
    font-size: 0.85rem;
    color: #8b949e;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05rem;
    margin-bottom: 5px;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
}

/* 分隔線樣式 */
hr {
    border: 0;
    height: 1px;
    background: linear-gradient(to right, rgba(255,255,255,0), rgba(255,255,255,0.1), rgba(255,255,255,0));
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ----------------- 核心解析邏輯 -----------------

@st.cache_data(show_spinner=False)

def fetch_firebase_lactate_records(start_time=None):
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{st.session_state.get('firebase_uid')}/lactate_records"
    try:
        headers = {"Authorization": f"Bearer {st.session_state.get('firebase_token')}"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            documents = data.get("documents", [])
            
            records = []
            for doc in documents:
                fields = doc.get("fields", {})
                
                # Parse absolute time
                year = int(fields.get("year", {}).get("integerValue", 0))
                month = int(fields.get("month", {}).get("integerValue", 0))
                day = int(fields.get("day", {}).get("integerValue", 0))
                hour = int(fields.get("hour", {}).get("integerValue", 0))
                minute = int(fields.get("minute", {}).get("integerValue", 0))
                
                # Lactate value
                final_la_obj = fields.get("final_la_mmol", {})
                final_la = float(final_la_obj.get("doubleValue", final_la_obj.get("integerValue", 0)))
                
                if year > 0:
                    full_year = year + 2000 if year < 100 else year
                    record_time = datetime(full_year, month, day, hour, minute)
                    elapsed_min = 0.0
                    if start_time:
                    elapsed_min = (record_time - start_time).total_seconds() / 60.0
                    if abs(elapsed_min) > 60:
                        continue

                records.append({
                        "elapsed_minutes": elapsed_min,
                        "lactate_mmol": final_la,
                        "record_time": record_time
                    })
                    
            # Sort by absolute time
            records = sorted(records, key=lambda x: x["record_time"])
            return records
        else:
            st.error(f"Firestore API Error: {response.text}")
            return []
    except Exception as e:
        st.error(f"Firebase 連線失敗: {str(e)}")
    return []


def parse_fit_file_data(uploaded_file_bytes):
    """
    解析 FIT 檔案的 records 與 laps 數據。
    傳入 bytes 物件，使用 fitparse 解析，若失敗則自動 fallback 到 fitdecode。
    """
    records = []
    laps_list = []
    use_fallback = False
    
    try:
        fit_file = fitparse.FitFile(io.BytesIO(uploaded_file_bytes))
        for record in fit_file.get_messages('record'):
            vals = {field.name: field.value for field in record.fields}
            records.append(vals)
        for i, lap in enumerate(fit_file.get_messages('lap')):
            vals = {field.name: field.value for field in lap.fields}
            laps_list.append(vals)
    except Exception as e:
        use_fallback = True
        
    if use_fallback:
        records = []
        laps_list = []
        try:
            import fitdecode
            with fitdecode.FitReader(io.BytesIO(uploaded_file_bytes)) as fit:
                for frame in fit:
                    if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                        if frame.name == "record":
                            row = {field.name: field.value for field in frame.fields}
                            records.append(row)
                        elif frame.name == "lap":
                            row = {field.name: field.value for field in frame.fields}
                            laps_list.append(row)
        except Exception as fallback_err:
            return pd.DataFrame(), pd.DataFrame(), None
            
    df = pd.DataFrame(records)
    if df.empty or 'timestamp' not in df.columns:
        return pd.DataFrame(), pd.DataFrame(), None
        
    # 排序並取得開始時間 (FIT 檔時間預設為 UTC+0，加上 8 小時轉換為 UTC+8 當地時間)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 統一移除時區資訊，以防後續與其他 naive datetime 運算錯誤
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=8)
        
    start_time = df['timestamp'].iloc[0]
    df['elapsed_minutes'] = (df['timestamp'] - start_time).dt.total_seconds() / 60.0
    
    # 確保必要欄位存在
    for col in ['heart_rate', 'power', 'temperature', 'skin_temperature', 'core_temperature']:
        if col not in df.columns:
            df[col] = np.nan
            
    # 檢測替代心率欄位名稱
    if df['heart_rate'].isna().all():
        for alt_hr in ['heartrate', 'hr', 'HeartRate', 'Heart_Rate']:
            if alt_hr in df.columns and df[alt_hr].notna().any():
                df['heart_rate'] = df[alt_hr]
                break
            
    # 解析核心溫度 (優先檢測 core_temperature，若無則檢測 CORE 體溫感測器的開發者欄位 unknown_139)
    if 'core_temperature' in df.columns and df['core_temperature'].notna().any():
        df['core_temp'] = df['core_temperature'].apply(lambda x: x / 100.0 if (pd.notna(x) and x > 1000) else x)
    elif 'unknown_139' in df.columns:
        df['core_temp'] = df['unknown_139'].apply(lambda x: x / 100.0 if (pd.notna(x) and x > 1000) else x)
    else:
        df['core_temp'] = np.nan
        
    # Interpolate sparse core_temp data so the summary table can match it
    if df['core_temp'].notna().any():
        df['core_temp'] = df['core_temp'].ffill().bfill()
        
    # 保留乾淨的欄位
    df_clean = df[['timestamp', 'elapsed_minutes', 'heart_rate', 'power', 'core_temp', 'skin_temperature', 'temperature']].copy()
    
    # 2. 解析 Laps
    laps = []
    for i, lap_val in enumerate(laps_list):
        lap_start = lap_val.get('start_time')
        lap_duration = lap_val.get('total_elapsed_time') # 秒
        
        if lap_start is not None and lap_duration is not None:
            lap_start_dt = pd.to_datetime(lap_start)
            if lap_start_dt.tz is not None:
                lap_start_dt = lap_start_dt.tz_localize(None)
            lap_start_dt = lap_start_dt + pd.Timedelta(hours=8)
                
            lap_end = lap_start_dt + timedelta(seconds=float(lap_duration))
            start_el = (lap_start_dt - start_time).total_seconds() / 60.0
            end_el = (lap_end - start_time).total_seconds() / 60.0
            
            laps.append({
                'lap_index': i + 1,
                'start_time': lap_start_dt,
                'end_time': lap_end,
                'start_elapsed_minutes': start_el,
                'end_elapsed_minutes': end_el,
                'duration_sec': lap_duration,
                'avg_power': lap_val.get('avg_power'),
                'avg_heart_rate': lap_val.get('avg_heart_rate'),
                'distance_m': lap_val.get('total_distance')
            })
            
    df_laps = pd.DataFrame(laps)
    return df_clean, df_laps, start_time

# ----------------- 應用程式介面 -----------------


# Firebase 雲端登入區
st.sidebar.markdown("### ☁️ Firebase 雲端帳號")
if "firebase_uid" in st.session_state:
    st.sidebar.success(f"已登入: {st.session_state['firebase_email']}")
    if st.sidebar.button("登出帳號"):
        logout_firebase()
else:
    st.sidebar.info("登入與 LA-01 APP 相同的帳號以讀取個人數據")
    with st.sidebar.form("firebase_login_form"):
        email = st.text_input("電子郵件 (Email)")
        password = st.text_input("密碼 (Password)", type="password")
        submitted = st.form_submit_button("登入 Firebase")
        if submitted:
            login_to_firebase(email, password)
            
st.sidebar.markdown("---")
st.sidebar.markdown("### 介面設定")
chart_theme = st.sidebar.radio("圖表主題", ["深色模式 (Dark)", "淺色模式 (Light)"])
theme_str = "dark" if "Dark" in chart_theme else "light"
st.sidebar.markdown("---")

st.sidebar.markdown("### 🛠️ 整合分析工具模式")
app_mode = st.sidebar.radio(
    "功能模式選擇",
    ["單期分析與資料登錄", "多期數據整合儀表板 (LacV5)"],
    key="app_mode_select"
)

if app_mode == "多期數據整合儀表板 (LacV5)":
    st.markdown('<div class="title-container">🩸 多期乳酸與生理指標整合工具</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-text">請選取要整合的單期 HTML 報告檔案 (.html)，並指定輸出的整合報告儲存位置。</div>', unsafe_allow_html=True)
    
    st.markdown("### 1. 選擇要整合的單期 HTML 報告檔 (.html)")
    selected_html_files = st.file_uploader("請點擊或拖曳選擇單期 HTML 報告檔案（可多選）", type=["html"], accept_multiple_files=True, key="multi_html_select")
    
    st.markdown("### 2. 指定輸出報告儲存位置")
    output_html_path = st.text_input("輸出 HTML 報告儲存路徑", value="LactateReport/LacV5.html", help="請輸入包含檔名的完整路徑，例如 LactateReport/LacV5.html")
    
    # 預覽選擇的期數資訊
    if selected_html_files:
        st.markdown("### 📋 已選擇的訓練期數與狀態")
        parsed_preview = {}
        for f in selected_html_files:
            try:
                content_bytes = f.read()
                f.seek(0)
                date_str, s_dict = integrate_reports.parse_single_session_html(content_bytes)
                if date_str and s_dict.get('startTime'):
                    parsed_preview[date_str] = {
                        '檔案名稱': f.name,
                        '開始時間': s_dict.get('startTime'),
                        '功率/心率軌跡': f"{len(s_dict.get('power_30s', []))} 點",
                        '乳酸記錄': f"{len(s_dict.get('lactate', []))} 點" if s_dict.get('lactate') else '無',
                        '血糖記錄': f"{len(s_dict.get('glucose', []))} 點" if s_dict.get('glucose') else '無',
                    }
                else:
                    parsed_preview[f.name] = {
                        '檔案名稱': f.name,
                        '開始時間': '無法解析',
                        '功率/心率軌跡': '未知',
                        '乳酸記錄': '未知',
                        '血糖記錄': '未知'
                    }
            except Exception as e:
                parsed_preview[f.name] = {
                    '檔案名稱': f.name,
                    '開始時間': f'解析錯誤: {e}',
                    '功率/心率軌跡': '-',
                    '乳酸記錄': '-',
                    '血糖記錄': '-'
                }
                
        preview_df = pd.DataFrame.from_dict(parsed_preview, orient='index')
        preview_df.index.name = '日期'
        st.dataframe(preview_df, use_container_width=True)
    else:
        st.info("💡 請先在上方選取至少一個單期 HTML 報告檔案進行分析。")

    # 開始整合按鈕
    if st.button("🚀 開始整合與產生報告", use_container_width=True):
        if not selected_html_files:
            st.warning("請先選取要整合的單期 HTML 報告檔案。")
        elif not output_html_path.strip():
            st.warning("請指定輸出的 HTML 報告儲存路徑。")
        else:
            with st.spinner("正在整合您選取的單期 HTML 報告..."):
                try:
                    merged_data = {}
                    for f in selected_html_files:
                        content_bytes = f.read()
                        f.seek(0)
                        date_str, s_dict = integrate_reports.parse_single_session_html(content_bytes)
                        if date_str and (s_dict.get('power_30s') or s_dict.get('lactate')):
                            merged_data[date_str] = s_dict
                            st.write(f"✓ 成功整合檔案：`{f.name}` (期數日期: {date_str})")
                        else:
                            st.warning(f"⚠️ 檔案 `{f.name}` 無有效生理數據，已跳過。")
                            
                    if not merged_data:
                        st.error("選取的檔案中沒有可整合的有效數據，請檢查檔案內容。")
                    else:
                        # 產生 Chart.js 整合網頁儀表板
                        html_content = integrate_reports.build_integrated_html(merged_data, theme=theme_str)
                        
                        # 儲存至使用者指定的輸出檔案位置
                        out_dir = os.path.dirname(output_html_path)
                        if out_dir:
                            os.makedirs(out_dir, exist_ok=True)
                        with open(output_html_path, 'w', encoding='utf-8') as out_f:
                            out_f.write(html_content)
                            
                        st.success(f"✨ 多期數據整合成功！報告已儲存至：`{output_html_path}`")
                        st.session_state['latest_output_html'] = output_html_path
                except Exception as e:
                    st.error(f"整合過程中發生錯誤: {e}")
                    
    # 如果有成功輸出的報告檔，提供預覽與下載
    latest_out = st.session_state.get('latest_output_html', output_html_path)
    if latest_out and os.path.exists(latest_out):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 📊 整合報告互動預覽 (Chart.js)")
        
        with open(latest_out, 'r', encoding='utf-8') as out_f:
            html_report_data = out_f.read()
            
        st.download_button(
            label="📥 下載整合 HTML 網頁報告",
            data=html_report_data,
            file_name=os.path.basename(latest_out),
            mime="text/html",
            use_container_width=True
        )
        
        components.html(html_report_data, height=900, scrolling=True)
        
    st.stop()

st.markdown('<div class="title-container">🩸 FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">上傳運動 .fit 檔案，標定乳酸測試數據，進行心率、功率、核心體溫與乳酸的完美對照作圖。</div>', unsafe_allow_html=True)

# 初始化 session state 中的乳酸與血糖數據
if 'custom_lactate' not in st.session_state:
    st.session_state['custom_lactate'] = pd.DataFrame({
        '相對時間 (分鐘)': pd.Series(dtype='float'),
        '乳酸值 (mmol/L)': pd.Series(dtype='float'),
        '血糖值 (mg/dL)': pd.Series(dtype='float')
    })

# 側邊欄：檔案上傳與設定
st.sidebar.markdown("### 📁 數據源選擇")
uploaded_file = st.sidebar.file_uploader("上傳您的 FIT 檔 (.fit)", type=["fit"])

# 如果沒有上傳檔案，提供載入預設測試檔的按鈕，以方便使用者快速體驗
use_demo = False
if uploaded_file is None:
    st.sidebar.info("您可以上傳自己的 .fit 檔案，或點擊下方按鈕載入系統內建的測試檔案。")
    if st.sidebar.button("載入內建測試 FIT 檔案"):
        use_demo = True
        try:
            with open("0521/20260521060844.fit", "rb") as f:
                demo_bytes = f.read()
            st.session_state['demo_bytes'] = demo_bytes
            st.session_state['use_demo'] = True
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"無法載入測試檔案: {e}")

# 獲取實際要解析的檔案 bytes
fit_bytes = None
file_name = ""
if uploaded_file is not None:
    fit_bytes = uploaded_file.read()
    file_name = uploaded_file.name
    st.session_state['use_demo'] = False
elif st.session_state.get('use_demo', False):
    fit_bytes = st.session_state.get('demo_bytes')
    file_name = "20260521060844.fit (內建測試)"

# 檢查檔案是否切換，若是，重設乳酸資料與編輯器狀態以防資料混亂
if 'last_file' not in st.session_state:
    st.session_state['last_file'] = None

if file_name and file_name != st.session_state['last_file']:
    st.session_state['last_file'] = file_name
    # 重設為預設乳酸與血糖數據
    st.session_state['custom_lactate'] = pd.DataFrame({
        '相對時間 (分鐘)': pd.Series(dtype='float'),
        '乳酸值 (mmol/L)': pd.Series(dtype='float'),
        '血糖值 (mg/dL)': pd.Series(dtype='float')
    })
    # 清除編輯器狀態，強迫重新載入預設數據
    if 'custom_lactate_editor' in st.session_state:
        del st.session_state['custom_lactate_editor']

# 主流程
if fit_bytes is not None:
    with st.spinner("正在解析 FIT 檔案中..."):
        df, df_laps, start_time = parse_fit_file_data(fit_bytes)
        
    if df.empty:
        st.error("FIT 檔案解析失敗或無有效 Record 數據。")
    else:
        # 1. 頂部 KPI 卡片區
        duration_minutes = df['elapsed_minutes'].max()
        duration_str = f"{int(duration_minutes)} 分 {int((duration_minutes % 1)*60)} 秒"
        
        avg_power = int(df['power'].mean()) if df['power'].notna().any() else 0
        max_power = int(df['power'].max()) if df['power'].notna().any() else 0
        avg_hr = int(df['heart_rate'].mean()) if df['heart_rate'].notna().any() else 0
        max_hr = int(df['heart_rate'].max()) if df['heart_rate'].notna().any() else 0
        max_core = df['core_temp'].max() if df['core_temp'].notna().any() else None
        
        # 顯示 metadata 資訊與關鍵指標
        st.markdown(f"**📅 活動開始時間**: {start_time.strftime('%Y-%m-%d %H:%M:%S')} (在地時間/UTC) | **📄 檔案名稱**: `{file_name}`")
        
        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">⏱️ 活動時長</div><div class="metric-value" style="color: #00b0ff;">{duration_str}</div></div>', unsafe_allow_html=True)
        with kpi_cols[1]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">⚡ 平均 / 最大功率</div><div class="metric-value" style="color: #29b6f6;">{avg_power} / {max_power} W</div></div>', unsafe_allow_html=True)
        with kpi_cols[2]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">❤️ 平均 / 最大心率</div><div class="metric-value" style="color: #ff5252;">{avg_hr} / {max_hr} bpm</div></div>', unsafe_allow_html=True)
        with kpi_cols[3]:
            if max_core is not None:
                st.markdown(f'<div class="metric-card"><div class="metric-label">🔥 最大核心溫度</div><div class="metric-value" style="color: #ff9100;">{max_core:.2f} °C</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-card"><div class="metric-label">🔥 最大核心溫度</div><div class="metric-value" style="color: #8b949e;">未偵測</div></div>', unsafe_allow_html=True)
            
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # 2. 乳酸與血糖數據輸入區
        st.header("✍️ 自訂相對時間乳酸與血糖數據輸入")
        st.markdown("請在下方表格中輸入各時間點量測的乳酸與血糖數據。您可以自由新增或刪除行數，時間為相對於運動起點的累計分鐘數（支援輸入負數以代表運動前的熱身或基期測量）。")
        

        col1, col2 = st.columns([1, 1])
        with col2:
            if st.button('From Firebase Sync LA-01', use_container_width=True):
                if "firebase_uid" not in st.session_state:
                    st.error("請先在左側邊欄登入 Firebase 帳號！")
                else:
                    with st.spinner('Syncing...'):
                        cloud_records = fetch_firebase_lactate_records(start_time)
                        if cloud_records:
                            new_rows = []
                            for r in cloud_records:
                                new_rows.append({
                                    '相對時間 (分鐘)': round(r['elapsed_minutes'], 1),
                                    '乳酸值 (mmol/L)': round(r['lactate_mmol'], 2),
                                    '血糖值 (mg/dL)': np.nan
                                })
                            if new_rows:
                                st.session_state['custom_lactate'] = pd.DataFrame(new_rows)
                                st.rerun()
        edited_custom_df = st.data_editor(
            st.session_state['custom_lactate'],
            column_config={
                '相對時間 (分鐘)': st.column_config.NumberColumn("相對時間 (分鐘)", min_value=None, step=0.1, format="%.1f"),
                '乳酸值 (mmol/L)': st.column_config.NumberColumn("乳酸值 (mmol/L)", min_value=0.0, step=0.1, format="%.2f"),
                '血糖值 (mg/dL)': st.column_config.NumberColumn("血糖值 (mg/dL)", min_value=0.0, step=1.0, format="%d")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="custom_lactate_editor"
        )
        
        # 彙整 custom 乳酸與血糖點
        custom_lactate_points = []
        for idx, row in edited_custom_df.iterrows():
            t = row['相對時間 (分鐘)']
            lac = row.get('乳酸值 (mmol/L)')
            glc = row.get('血糖值 (mg/dL)')
            has_lac = pd.notna(lac) and lac > 0
            has_glc = pd.notna(glc) and glc > 0
            if pd.notna(t) and (has_lac or has_glc):
                custom_lactate_points.append({
                    'elapsed_minutes': float(t),
                    'lactate': float(lac) if has_lac else np.nan,
                    'glucose': float(glc) if has_glc else np.nan,
                    'source': '自訂時間'
                })
                
        # 合併所有的乳酸與血糖數據點
        all_lactate = pd.DataFrame(custom_lactate_points)
        if not all_lactate.empty:
            all_lactate = all_lactate.sort_values(by='elapsed_minutes').reset_index(drop=True)
            
        st.markdown("<hr>", unsafe_allow_html=True)

        
        # 3. 圖表顯示設定
        st.sidebar.markdown("### 📈 圖表顯示設定")
        smooth_power = st.sidebar.checkbox("顯示 30 秒平均功率 (平滑功率線)", value=True)
        
        # 4. 繪製圖表
        st.header("📊 數據協同分析圖表")
        
        # 檢查是否有核心溫度數據
        has_core_temp = df['core_temp'].notna().any()
        show_temp_panel = has_core_temp
        
        # 根據是否有溫度數據，動態決定子圖列數與高度比例
        if show_temp_panel:
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.06,
                row_heights=[0.4, 0.3, 0.3],
                specs=[
                    [{"secondary_y": True}],  # Row 1: Power (left) & HR (right)
                    [{"secondary_y": False}], # Row 2: Core Temp (single Y axis)
                    [{"secondary_y": True}]   # Row 3: Lactate (left) & Glucose (right)
                ]
            )
        else:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.6, 0.4],
                specs=[
                    [{"secondary_y": True}],  # Row 1: Power & HR
                    [{"secondary_y": True}]   # Row 2: Lactate (left) & Glucose (right)
                ]
            )
            
        # --- 第一層：功率與心率 ---
        # 功率 (W) - 原始數據
        fig.add_trace(
            go.Scatter(
                x=df['elapsed_minutes'],
                y=df['power'],
                name="功率 (W)",
                line=dict(color="rgba(0, 176, 255, 0.25)", width=1),
                hoverinfo="skip" if smooth_power else "all"
            ),
            row=1, col=1, secondary_y=False
        )
        
        # 功率 (W) - 30秒平滑
        if smooth_power and df['power'].notna().any():
            df['power_smoothed'] = df['power'].rolling(window=30, min_periods=1).mean()
            fig.add_trace(
                go.Scatter(
                    x=df['elapsed_minutes'],
                    y=df['power_smoothed'],
                    name="功率 (30s 平均)",
                    line=dict(color="#00b0ff", width=2),
                ),
                row=1, col=1, secondary_y=False
            )
            
        # 心率 (BPM)
        fig.add_trace(
            go.Scatter(
                x=df['elapsed_minutes'],
                y=df['heart_rate'],
                name="心率 (BPM)",
                line=dict(color="#ff2a5f", width=1.5),
            ),
            row=1, col=1, secondary_y=True
        )
        
        # --- 第二層：溫度數據 (如果有的話) ---
        if show_temp_panel:
            # 核心溫度
            if has_core_temp:
                fig.add_trace(
                    go.Scatter(
                        x=df['elapsed_minutes'],
                        y=df['core_temp'],
                        name="核心溫度 (°C)",
                        line=dict(color="#ff9100", width=2.5),
                        connectgaps=True
                    ),
                    row=2, col=1
                )
                
        # --- 第三層 / 第二層：乳酸與血糖數據 ---
        lactate_row = 3 if show_temp_panel else 2
        
        if not all_lactate.empty:
            # 繪製乳酸折線圖與點標記 (左 Y 軸)
            if 'lactate' in all_lactate.columns and all_lactate['lactate'].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=all_lactate['elapsed_minutes'],
                        y=all_lactate['lactate'],
                        name="乳酸 (mmol/L)",
                        mode="lines+markers",
                        marker=dict(size=10, color="#00e676", symbol="diamond", line=dict(color="white", width=1.5)),
                        line=dict(color="#00e676", width=2.5, dash="dash"),
                        text=all_lactate['source'],
                        hovertemplate="時間: %{x:.1f} 分<br>乳酸: %{y:.2f} mmol/L<br>來源: %{text}<extra></extra>"
                    ),
                    row=lactate_row, col=1, secondary_y=False
                )
            
            # 繪製血糖折線圖與點標記 (右 Y 軸)
            if 'glucose' in all_lactate.columns and all_lactate['glucose'].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=all_lactate['elapsed_minutes'],
                        y=all_lactate['glucose'],
                        name="血糖 (mg/dL)",
                        mode="lines+markers",
                        marker=dict(size=10, color="#d500f9", symbol="circle", line=dict(color="white", width=1.5)),
                        line=dict(color="#d500f9", width=2.5, dash="dot"),
                        text=all_lactate['source'],
                        hovertemplate="時間: %{x:.1f} 分<br>血糖: %{y:.1f} mg/dL<br>來源: %{text}<extra></extra>"
                    ),
                    row=lactate_row, col=1, secondary_y=True
                )
            
            # 在各層加上檢測點的垂直虛線 (VLine)，方便對齊
            for idx, r in all_lactate.iterrows():
                fig.add_vline(
                    x=r['elapsed_minutes'],
                    line_width=1,
                    line_dash="dash",
                    line_color="rgba(255, 255, 255, 0.35)",
                    row="all",
                    col=1
                )
                
        # --- 圖表佈局與樣式調整 ---
        
        is_dark = (theme_str == "dark")
        fig.update_layout(
            height=750,
            hovermode="x unified",
            font=dict(size=20, color="#ffffff" if is_dark else "#000000"),
            template="plotly_dark" if is_dark else "plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=60, r=60, t=40, b=40),
            plot_bgcolor='rgba(30, 30, 38, 0.4)' if is_dark else 'rgba(240, 240, 245, 0.4)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        # 坐標軸標題與格線

        fig.add_hrect(
            y0=0, y1=15, line_width=0, fillcolor="rgba(0, 255, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.add_hrect(
            y0=15, y1=30, line_width=0, fillcolor="rgba(255, 255, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.add_hrect(
            y0=30, y1=45, line_width=0, fillcolor="rgba(255, 0, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.update_xaxes(showgrid=False, ticks='outside', ticklen=6, tickwidth=1, showline=True, linewidth=1, linecolor='rgba(255,255,255,0.5)')
        fig.update_yaxes(showgrid=False, ticks='outside', ticklen=6, tickwidth=1, showline=True, linewidth=1, linecolor='rgba(255,255,255,0.5)')
        
        # 標定各軸名稱
        fig.update_xaxes(title_text="時間 (相對分鐘)", row=lactate_row, col=1)
        fig.update_yaxes(title_text="功率 (W)", row=1, col=1, secondary_y=False, title_font=dict(color="#00b0ff", size=18), tickfont=dict(size=14))
        fig.update_yaxes(title_text="心率 (BPM)", row=1, col=1, secondary_y=True, title_font=dict(color="#ff2a5f", size=18), tickfont=dict(size=14))
        
        if show_temp_panel:
            fig.update_yaxes(title_text="核心溫度 (°C)", row=2, col=1, title_font=dict(color="#ff9100", size=18), tickfont=dict(size=14))
                
        fig.update_yaxes(title_text="乳酸 (mmol/L)", row=lactate_row, col=1, secondary_y=False, range=[0, 45], title_font=dict(color="#00e676", size=18), tickfont=dict(size=14))
        fig.update_yaxes(title_text="血糖 (mg/dL)", row=lactate_row, col=1, secondary_y=True, title_font=dict(color="#d500f9", size=18), tickfont=dict(size=14))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 5. 數據彙整摘要表格與導出
        st.markdown("<hr>", unsafe_allow_html=True)
        st.header("📊 生理數據對照彙整表")
        
        if not all_lactate.empty:
            st.markdown("下表自動比對您輸入的每一個量測點，並撈取該時間點 FIT 檔中最接近的功率、心率與體溫數據，提供完整的生理指標摘要。")
            
            summary_rows = []
            for idx, r in all_lactate.iterrows():
                t = r['elapsed_minutes']
                lac = r.get('lactate')
                glc = r.get('glucose')
                source = r['source']
                
                # 尋找最接近的記錄
                diffs = (df['elapsed_minutes'] - t).abs()
                nearest_idx = diffs.idxmin()
                nearest = df.iloc[nearest_idx]
                
                calc_time = start_time + timedelta(minutes=float(t))
                is_before_start = (t < 0)
                
                summary_rows.append({
                    '量測時間 (分)': round(t, 1),
                    '乳酸值 (mmol/L)': round(lac, 2) if pd.notna(lac) else "-",
                    '血糖值 (mg/dL)': int(glc) if pd.notna(glc) else "-",
                    '量測點來源': source,
                    '對應功率 (W)': "-" if is_before_start else (str(int(nearest['power'])) if pd.notna(nearest['power']) else "-"),
                    '對應心率 (BPM)': "-" if is_before_start else (str(int(nearest['heart_rate'])) if pd.notna(nearest['heart_rate']) else "-"),
                    '對應核心溫度 (°C)': "-" if is_before_start else (f"{nearest['core_temp']:.2f}" if pd.notna(nearest['core_temp']) else "-"),
                    '實際時間 (Time)': calc_time.strftime('%H:%M:%S')
                })
                
            summary_df = pd.DataFrame(summary_rows)
            st.dataframe(summary_df, use_container_width=True)
            
            st.markdown("<hr>", unsafe_allow_html=True)
            st.header("💾 儲存與產出分析報告")
            st.markdown("您可以將包含互動式圖表、生理指標與對照表在內的**整個網頁報告**，一鍵儲存至本地專案資料夾，或下載至瀏覽器保存。")
            
            # 產生 HTML 報告內容
            html_report_data = generate_html_report(
                summary_df, 
                fig, 
                start_time, 
                file_name, 
                {
                    'duration_str': duration_str,
                    'avg_power': avg_power,
                    'max_power': max_power,
                    'avg_hr': avg_hr,
                    'max_hr': max_hr,
                    'max_core': max_core
                }
            )
            
            save_cols = st.columns(3)
            
            with save_cols[0]:
                if st.button("💾 儲存報告至本機專案資料夾", use_container_width=True):
                    try:
                        os.makedirs("saved_reports", exist_ok=True)
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        html_path = f"saved_reports/lactate_report_{timestamp_str}.html"
                        csv_path = f"saved_reports/lactate_report_{timestamp_str}.csv"
                        
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html_report_data)
                        
                        summary_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                        
                        st.success(f"✨ 報告已成功儲存至本地 `saved_reports/` 資料夾！\n\n- **HTML 網頁檔**：`{html_path}` (雙擊即可開啟)\n- **CSV 數據檔**：`{csv_path}`")
                    except Exception as e:
                        st.error(f"儲存失敗: {e}")
            
            with save_cols[1]:
                st.download_button(
                    label="📥 下載 HTML 網頁報告",
                    data=html_report_data,
                    file_name=f"lactate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    use_container_width=True
                )
                
            with save_cols[2]:
                csv_buffer = io.StringIO()
                summary_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下載生理彙整 CSV 檔",
                    data=csv_buffer.getvalue(),
                    file_name=f"lactate_physiological_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("請於上方輸入乳酸數據，此處將自動產生對照彙整表與提供報告下載。")
            
        # 額外功能：允許下載完整解析後的 FIT 檔案 CSV
        with st.expander("🛠️ 進階：下載完整解析的 FIT 軌跡 CSV"):
            csv_full_buffer = io.StringIO()
            df.to_csv(csv_full_buffer, index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載完整 FIT 軌跡資料 CSV",
                data=csv_full_buffer.getvalue(),
                file_name=f"parsed_fit_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
else:
    # 歡迎畫面
    st.info("👋 歡迎使用！請先在左側欄上傳您的 `.fit` 檔案，或是點擊載入系統內建的測試檔案來開始分析。")
    st.markdown("""
    ### 💡 本工具特色：
    1. **自動對齊**：自動將 FIT 檔時間軸轉換為運動起點開始的「相對分鐘數」，完美對齊測試時間。
    2. **自訂相對時間**：支援彈性輸入任何相對時間點（分鐘）與乳酸值（無限制上限），完美對齊生理軌跡。
    3. **核心溫度支援**：內建解析 CORE 體溫感測器的開發者欄位 (`unknown_139`)，自動縮放顯示核心與皮膚溫度。
    4. **30s 功率平滑**：可切換顯示 30s 平均功率線，避開功率跳動干擾，看清真實強度。
    5. **對應生理分析表**：自動拉取每個乳酸點對應的即時心率、功率與體溫，一鍵匯出完整生理評估報告。
    """)
