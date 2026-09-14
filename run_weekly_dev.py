# -*- coding: utf-8 -*-
"""
run_weekly_dev.py
獨立開發與即時預覽工具：AI 運動生理週報與下一次處方
執行方式：
    streamlit run run_weekly_dev.py
功能：
1. 完全獨立運行，不干擾主系統
2. 支援選擇本地真實資料夾 (DataMindy, DataRead 等) 或 Firebase 線上登入
3. 呈現客觀生理學指標計算（乳酸加權總負荷、代謝效率變化、高乳酸暴露面積）
4. 一鍵呼叫 Firebase AI Logic / Gemini 產出深度洞察與下一次運動處方
5. 即時於畫面預覽現代科技感 HTML 儀表板
"""

import os
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

import weekly_physio_engine as wpe
import ai_coach_generator as acg
import ai_weekly_report as awr

st.set_page_config(
    page_title="AI 運動生理週報開發預覽器",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Streamlit UI
st.markdown("""
<style>
    .main { background-color: #090d16; }
    .stApp { background-color: #090d16; color: #f1f5f9; }
    .css-1d391kg, .css-1lcbmhc { background-color: #121826; }
    h1, h2, h3 { color: #ffffff !important; }
    .stat-box {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .stat-val { font-size: 1.8rem; font-weight: 800; color: #00f2fe; }
    .stat-lbl { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

st.title("🩸 AI 運動生理週報與下一次處方 — 獨立開發實驗室")
st.caption("基於血乳酸動力學 (Lactate Kinetics)、5~7 天累積負荷與 Firebase AI Logic 架構")

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ 數據來源與設定")
    
    data_mode = st.radio("選擇測試模式", ["📁 本地真實數據資料夾", "☁️ Firebase 線上帳號 (Firestore)"], index=0)
    
    athlete_name = st.text_input("運動員名稱", value="Mindy")
    days_limit = st.slider("分析天數範圍 (天)", min_value=3, max_value=14, value=5)
    
    selected_folder = "DataMindy"
    firebase_uid = None
    firebase_token = None
    
    if data_mode == "📁 本地真實數據資料夾":
        local_dirs = [d for d in os.listdir(".") if os.path.isdir(d) and ("Data" in d or "Run" in d or "bike" in d)]
        default_idx = local_dirs.index("DataMindy") if "DataMindy" in local_dirs else 0
        selected_folder = st.selectbox("選擇測試資料夾", local_dirs, index=default_idx)
    else:
        st.subheader("Firebase 驗證")
        fb_email = st.text_input("Email", value="")
        fb_pwd = st.text_input("Password", type="password", value="")
        if st.button("登入 Firebase"):
            import requests
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={acg.DEFAULT_FIREBASE_KEY}"
            try:
                res = requests.post(url, json={"email": fb_email, "password": fb_pwd, "returnSecureToken": True}, timeout=10)
                data = res.json()
                if "idToken" in data:
                    st.session_state["dev_uid"] = data["localId"]
                    st.session_state["dev_token"] = data["idToken"]
                    st.success("Firebase 登入成功！")
                else:
                    st.error(f"登入失敗: {data.get('error', {}).get('message')}")
            except Exception as e:
                st.error(f"連線錯誤: {e}")
        firebase_uid = st.session_state.get("dev_uid")
        firebase_token = st.session_state.get("dev_token")

    st.markdown("---")
    st.subheader("🤖 Firebase AI Logic 設定")
    st.markdown("**預設專案**：`lactatecloud`")
    api_key_input = st.text_input("Gemini API Key (選填，若啟用專案 API 可直接呼叫)", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

# Main Data Pipeline
col1, col2 = st.columns([1, 1])

with st.spinner("正在解析運動數據與生理指標..."):
    if data_mode == "📁 本地真實數據資料夾":
        sessions = wpe.fetch_local_dataset(selected_folder, days_limit=days_limit)
    else:
        if firebase_uid and firebase_token:
            sessions = wpe.fetch_firestore_dataset(firebase_uid, firebase_token, days_limit=days_limit)
        else:
            st.info("請於側邊欄輸入 Firebase 帳號密碼登入，或切換為「本地真實數據資料夾」。目前載入標準測試數據。")
            sessions = wpe.get_benchmark_dataset()

metrics = wpe.calculate_comprehensive_load(sessions)

# Display Key Physio Metrics
st.subheader("📊 運動生理學核心運算指標 (客觀數據層)")
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f'<div class="stat-box"><div class="stat-lbl">分析場次</div><div class="stat-val">{metrics.get("session_count")}</div><div style="font-size:0.8rem; color:#94a3b8;">總計 {metrics.get("total_hours")} 小時</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="stat-box"><div class="stat-lbl">乳酸加權總負荷</div><div class="stat-val" style="color:#ffab00;">{metrics.get("total_lactate_load")}</div><div style="font-size:0.8rem; color:#94a3b8;">Lactate Load Score</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="stat-box"><div class="stat-lbl">最高乳酸峰值</div><div class="stat-val" style="color:#ff5252;">{metrics.get("peak_lactate_week")}</div><div style="font-size:0.8rem; color:#94a3b8;">mmol/L</div></div>', unsafe_allow_html=True)
with m4:
    delta = metrics.get("efficiency_delta_pct", 0)
    delta_color = "#00e676" if delta >= 0 else "#ff5252"
    st.markdown(f'<div class="stat-box"><div class="stat-lbl">代謝效率變化</div><div class="stat-val" style="color:{delta_color};">{"+" if delta>0 else ""}{delta}%</div><div style="font-size:0.8rem; color:#94a3b8;">最新 vs 前期</div></div>', unsafe_allow_html=True)
with m5:
    st.markdown(f'<div class="stat-box"><div class="stat-lbl">疲勞與恢復狀態</div><div class="stat-val" style="color:{metrics.get("state_color")}; font-size:1.2rem; padding:8px 0;">{metrics.get("recovery_state").split(" ")[0]}</div><div style="font-size:0.75rem; color:#94a3b8;">急慢性負荷評估</div></div>', unsafe_allow_html=True)

st.markdown("---")

# Generate AI Weekly Report
if st.button("⚡ 生成全新 AI 運動生理週報與下一次處方", type="primary", use_container_width=True):
    with st.spinner("🧠 正在透過 Firebase AI Logic 深度分析血乳酸動力學與開立運動處方..."):
        ai_res = acg.call_firebase_ai_logic(
            metrics,
            athlete_name=athlete_name,
            firebase_token=firebase_token,
            api_key=api_key_input
        )
        report_data = {
            "athlete_name": athlete_name,
            "metrics": metrics,
            "ai_analysis": ai_res,
            "sessions": sessions
        }
        st.session_state["latest_report_data"] = report_data
        html_out = awr.render_modern_html_report(report_data)
        st.session_state["latest_html"] = html_out
        awr.save_report_html(report_data, "modern_weekly_report.html")
        st.success("🎉 報告已生成完畢！")

if "latest_html" in st.session_state:
    st.subheader("📱 現代科技感週報與處方即時預覽")
    
    # Download Button
    st.download_button(
        label="💾 下載完整 HTML 報告檔案",
        data=st.session_state["latest_html"],
        file_name=f"lactate_weekly_report_{athlete_name}_{datetime.now().strftime('%Y%m%d')}.html",
        mime="text/html"
    )

    # Iframe Preview
    components.html(st.session_state["latest_html"], height=950, scrolling=True)
