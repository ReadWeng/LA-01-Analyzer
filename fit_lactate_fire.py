
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
from PIL import Image
try:
    page_icon_img = Image.open("logo.jpg")
except:
    page_icon_img = "🩸"

st.set_page_config(
    page_title="FIT 檔與乳酸協同分析工具",
    page_icon=page_icon_img,
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


def upload_fit_to_firebase(df, file_name, start_time, avg_power, max_power, avg_hr, max_hr, max_core):
    uid = st.session_state.get('firebase_uid')
    token = st.session_state.get('firebase_token')
    if not uid or not token:
        st.error('請先登入 Firebase')
        return False
        
    try:
        # Downsample to 30s
        df_copy = df.copy()
        # bin size = 0.5 minutes (30s)
        df_copy['bin'] = (df_copy['elapsed_minutes'] * 2).astype(int) / 2.0
        df_res = df_copy.groupby('bin').mean(numeric_only=True).reset_index()
        
        # Prepare array data
        time_series = []
        for _, row in df_res.iterrows():
            point = {
                'mapValue': {
                    'fields': {
                        'elapsed_minutes': {'doubleValue': round(row.get('elapsed_minutes', 0), 2)}
                    }
                }
            }
            if pd.notna(row.get('heart_rate')):
                point['mapValue']['fields']['heart_rate'] = {'doubleValue': round(row['heart_rate'], 1)}
            if pd.notna(row.get('power')):
                point['mapValue']['fields']['power'] = {'doubleValue': round(row['power'], 1)}
            if pd.notna(row.get('core_temp')):
                point['mapValue']['fields']['core_temp'] = {'doubleValue': round(row['core_temp'], 2)}
            if 'cadence' in row and pd.notna(row.get('cadence')):
                point['mapValue']['fields']['cadence'] = {'doubleValue': round(row['cadence'], 1)}
            time_series.append(point)
            
        # JSON payload for Firestore
        payload = {
            'fields': {
                'file_name': {'stringValue': str(file_name)},
                'start_time': {'timestampValue': start_time.isoformat() + 'Z' if start_time.tzinfo is None else start_time.isoformat()},
                'avg_power': {'integerValue': str(int(avg_power))},
                'max_power': {'integerValue': str(int(max_power))},
                'avg_hr': {'integerValue': str(int(avg_hr))},
                'max_hr': {'integerValue': str(int(max_hr))},
                'time_series': {'arrayValue': {'values': time_series}}
            }
        }
        if max_core is not None:
            payload['fields']['max_core'] = {'doubleValue': float(max_core)}
            
        url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True
        else:
            st.error(f'Upload failed: {response.text}')
            return False
    except Exception as e:
        st.error(f'Upload error: {e}')
        return False



def fetch_firebase_lactate_records(start_time=None, duration_minutes=0.0):
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
                        # 條件: 起始時間 - 60分鐘 <= 記錄時間 <= 起始時間 + 運動時間 + 60分鐘
                        if elapsed_min < -60 or elapsed_min > (duration_minutes + 60):
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
    st.markdown('<div class="title-container" style="display: flex; align-items: center;"><img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAMKBAADASIAAhEBAxEB/8QAHQABAAICAwEBAAAAAAAAAAAAAAcIBgkBBAUDAv/EAF4QAAEDAwICBQUHEQUGAgkDBQEAAgMEBQYHERIhCBMxQVEiYXGBkRQYMlaUodEJFRYXI0JSV2JygpKTlbHS0zNDVaLBGSRTVGOyNPAlRHODo8LD4fE1N3SzJoSktP/EABwBAQACAwEBAQAAAAAAAAAAAAAFBgMEBwIBCP/EAEYRAAIBAgIECQkHAwMEAwEBAAABAgMEBREGEiExIkFRYXGBkaHRBxMUFjJTscHhFRcjM1JikkJU8ENyoiREgvE0Y9Il4v/aAAwDAQACEQMRAD8A2poiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIgCIiAIiIAiIg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lxu72PHc4eH+i51eWNzg1bXpt5cT+TL5Z31tjNLzdRLPjXzRUu1XzUjo55O6218L5LfM/ifTuJNPUt/Djd9670evuVp8B1Cx7UWzNu9iqDu3Zs8D+UkL/Aj/AFXcy/DrDm9mmsmQULKiCQeS4jy43dzmntBCqfkOJah9HbJob3aK509vlftHURg9XM0f3cze47fSCtnOhjUcnlGt3SNXKvgks1nKj3xLlosN0x1NsWptibc7a8RVcIDayjc7y4H/AOrT3Hv9IIWZKAq0p0ZunUWTRYaVWFeCqU3mmERFjMgREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQFCNYulTrVhup+R4xar3Sw0durXRQMdStcWs2BG57+RWG+/P15+MNH8iYsa6S4I12zEEbf7+P/wCmxRku6Ydg2HVbSnOVGLbiuLmPzjimkOK0b2rThcTSUnltfKTl78/Xn4w0fyJie/P15+MNH8iYoNRbn2FhvuI9iND1lxf+5n2snL35+vPxho/kTE9+frz8YaP5ExQaifYWG+4j2IesuL/3M+1k5e/P15+MNH8iYnvz9efjDR/ImKDUT7Cw33EexD1lxf8AuZ9rJy9+frz8YaP5ExXa6Od5z/JtMLflOotdHUXG7udVwtZCI+qpjsIwQO0kDi3/ACgO5a5dH8BqNTNRrJh8LHGKrqGuqnNHwIG85D5uQ238SFtioKKmt1FBb6OJsUFNG2KNjRsGtaNgB6gqDptCyslTtbanGMntbS25cXb8jpnk+qYjiEql5d1ZSguCk3sz431H3REXPTqIREQBERAEREBDfSwy/wCxXR+4wQyllTeHtoI9jz4Xc3n0cII9a15qzfTizAXDLbRh0Em8drpzUTN/6kh5f5QFWRdl0OsvRcNjN75vPq3I/PHlBxH03GJU4vg00o9e9hERWsowREQBfe30U1xrqe307S6WplbEwAb83HYfxXwUtdFzD/sv1htDZYi+mtfFcJztuB1Y8nfzF5aPWtS/uY2dtOvLdFNm/hdnLELylax3ykl3l+cGx2HEsPs+NwRhjbfSRwkD8IDyvn3Xuoi/PtSpKrNzlvbzP1bSpRo0404bkkl1BEReDIEREAREQBERAERE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R0W6cumueUlPa89q4cUv2wY81LtqKd34TJTyZ6H7eYla1UWhimDW2KxXndklua3khh+K18Of4e1PembvKOuorjTsq7fVw1MEjQ5kkTw9rgewgjkQvutM+D6q6i6cVTKrCsvuVr4XcRhimJgcfyojux3rCtLpl9UUu9DFHb9UsYbXhuzTXW4iN5Hi6M8j6j6lSb3RK7ocKg1NdjLdaaTW1bg1lqvtRfNFGOnfSQ0f1NpopMfzCjiqpCAaOseIJ2u8OF3b6t1JoIPYVWa1Crby1KsXF85YKVanXjrU5JrmOURFiMoREQBERAEREAXUqLTa6wk1duppi7t6yJrt/aF20X1Nraj40pbGYzctMtO7wHC6YTZakO+F1lFGd+W3gsVuXRk0Iub2zP0zs1PMx4kbLSQ9RIHDsPEzYqUEWxC8uKfsza62YJWlCftQXYjF8S09s2FVMsljrLk2nlj4DST1kk0QduDxgPJIdy2337ysoRFgnOVR60nmzLCnGmtWKyQREXk9hERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAEREAREQBERAFgeo2jWH6j07n3Gk9y3EDaOupwGyD87ucPMfmWeIstKtUoSU6byZirUadxDUqLNFEtRdH8x0zq+sr6d1Tb+L7jcKcHqz4cXex3mPqJXsYB0iM5wsx0ddP9eba3YGnqnHja3wZJ2j17jzK59XR0lfTSUddTRVEErSySOVgc1w8CDyIVf9TOi1Q15lu+n0raSc7udQSu+5OP5Du1voPJWa2xi3vY+Zv4rp/zcVa5wa4sZeesJPo/zecT/aQ6QEI6ucWDI3jYB4bHKXf9so9B39ChzULRLN9P3yT1tD7vte/k19KC+Pb8sdrD6eXgSsVyDGMgxSudQX611FFOw7DrGEA+dp7D6lmuFa+Z7iLG0M9aLxbgOE0tcS/yfAP7R69wpalbV7Va1nPXh+lv4MialzQunq3kNSf6kviiD8g09x6/B8pp/clS7++hG3PzjsP8fOo2v+m2RWTimhhFfTN3PWQAlwH5TO0ercedXarX6I6pgywPOFXyTta5u9JK8+jkOfhssHy7SbMcQjNbUULa62nmyuonCaFzfHdvZ61KW2LbdSpnGXI/k+M0a2Hy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" style="height: 50px; vertical-align: middle; margin-right: 15px; border-radius: 50%; object-fit: cover;">多期乳酸與生理指標整合工具</div>', unsafe_allow_html=True)
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

import base64
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 50px; vertical-align: middle; margin-right: 15px; border-radius: 50%; object-fit: cover;">'
    st.markdown(f'<div class="title-container" style="display: flex; align-items: center;">{img_tag}FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)
except:
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
fit_bytes = None
file_name = ""
if uploaded_file is not None:
    fit_bytes = uploaded_file.read()
    file_name = uploaded_file.name
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
            
        if st.session_state.get('firebase_uid'):
            if st.button('☁️ 上傳此筆 FIT 紀錄至雲端'):
                with st.spinner('上傳中...'):
                    if upload_fit_to_firebase(df, file_name, start_time, avg_power, max_power, avg_hr, max_hr, max_core):
                        st.success('✅ FIT 數據已成功上傳儲存！')

            
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
                        cloud_records = fetch_firebase_lactate_records(start_time, duration_minutes)
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
            has_lac = pd.notna(lac) and lac >= 0
            has_glc = pd.notna(glc) and glc >= 0
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
    
    if st.session_state.get('firebase_uid'):
        with st.spinner('正在載入歷史乳酸紀錄...'):
            all_records = fetch_firebase_lactate_records()
            if all_records:
                import plotly.express as px
                df_hist = pd.DataFrame(all_records)
                if not df_hist.empty and 'record_time' in df_hist.columns:
                    df_hist['date_str'] = df_hist['record_time'].dt.strftime('%Y-%m-%d')
                    top_5_dates = df_hist['date_str'].drop_duplicates().sort_values(ascending=False).head(5).values
                    df_top5 = df_hist[df_hist['date_str'].isin(top_5_dates)].copy()
                    df_top5 = df_top5.sort_values('record_time')
                    
                    # Calculate order for alignment
                    df_top5['測試點順序'] = df_top5.groupby('date_str').cumcount() + 1
                    
                    fig = px.line(df_top5, x='測試點順序', y='lactate_mmol', color='date_str', markers=True,
                                  title='📈 最近五期乳酸紀錄趨勢 (依量測順序)',
                                  labels={'測試點順序': '該期量測順序', 'lactate_mmol': '乳酸值 (mmol/L)', 'date_str': '測試日期'})
                    
                    fig.update_layout(
                        xaxis_title="量測順序",
                        yaxis_title="乳酸值 (mmol/L)",
                        xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                        hovermode="x unified",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    # Apply zero-grid style
                    fig.update_xaxes(showgrid=False, showline=True, linewidth=1, linecolor='black', ticks='outside', tickcolor='black', ticklen=5)
                    fig.update_yaxes(showgrid=False, showline=True, linewidth=1, linecolor='black', ticks='outside', tickcolor='black', ticklen=5)
                    
                    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""
    ### 💡 本工具特色：
    1. **自動對齊**：自動將 FIT 檔時間軸轉換為運動起點開始的「相對分鐘數」，完美對齊測試時間。
    2. **自訂相對時間**：支援彈性輸入任何相對時間點（分鐘）與乳酸值（無限制上限），完美對齊生理軌跡。
    3. **核心溫度支援**：內建解析 CORE 體溫感測器的開發者欄位 (`unknown_139`)，自動縮放顯示核心與皮膚溫度。
    4. **30s 功率平滑**：可切換顯示 30s 平均功率線，避開功率跳動干擾，看清真實強度。
    5. **對應生理分析表**：自動拉取每個乳酸點對應的即時心率、功率與體溫，一鍵匯出完整生理評估報告。
    """)
