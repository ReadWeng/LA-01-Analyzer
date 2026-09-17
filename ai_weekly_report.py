# -*- coding: utf-8 -*-
"""
ai_weekly_report.py
以「汗乳酸 (Sweat Lactate)」為核心的現代化運動生理週期分析與下一次處方報告

領域認知整合：
1. 汗乳酸動態具有高強度刺激上升、低強度有助排出的特性，但數值不能與血乳酸一概而論。
2. 跨期分析以實際訓練日期為準（可橫跨一整個月，計算相鄰場次間隔天數）。
3. 縱向探討平均功率或平均心率與汗乳酸濃度的對照（代謝經濟性與疲勞累積）。
"""

import os
import re
import json
from datetime import datetime
import numpy as np

import weekly_physio_engine as wpe
import ai_coach_generator as acg


def generate_weekly_report_data(
    athlete_name="選手",
    uid=None,
    token=None,
    api_key=None,
    days_limit=5,
    sport_filter="all",
    refresh_token=None,
    start_date=None,
    end_date=None
):
    """
    抓取真實用戶雲端數據（支援指定日期區間拉桿或指定關鍵測驗場次，並納入期間所有手錶日常運動與 HRV）、進行運動專項分流、汗乳酸動力學與跨期負荷運算，並呼叫 Firebase AI Logic
    """
    if not uid or not token:
        return {
            "athlete_name": athlete_name,
            "metrics": {},
            "ai_analysis": None,
            "sessions": [],
            "sport_filter": sport_filter,
            "fetch_error": "尚未登入 MyLactate 帳號，請先於側邊欄登入以讀取您的雲端紀錄",
            "new_token": token
        }

    sessions, new_token, fetch_error = wpe.fetch_firestore_dataset_with_status(
        uid, token, session_limit=days_limit, sport_filter=sport_filter, refresh_token=refresh_token,
        start_date=start_date, end_date=end_date
    )

    if not sessions:
        return {
            "athlete_name": athlete_name,
            "metrics": {},
            "ai_analysis": None,
            "sessions": [],
            "sport_filter": sport_filter,
            "fetch_error": fetch_error or f"在【{sport_filter}】專項篩選下查無足夠之運動紀錄",
            "new_token": new_token
        }

    # 1. 運動生理學與跨期負荷運算 (包含手錶日常負荷與乳酸動力學)
    metrics = wpe.calculate_comprehensive_load(sessions)

    # 2. 透過 Firebase AI Logic 產出深度汗乳酸評析與處方
    ai_analysis = acg.call_firebase_ai_logic(metrics, athlete_name=athlete_name, firebase_token=new_token or token, api_key=api_key)

    return {
        "athlete_name": athlete_name,
        "metrics": metrics,
        "ai_analysis": ai_analysis,
        "sessions": sessions,
        "sport_filter": sport_filter,
        "new_token": new_token
    }


def render_modern_html_report(report_data):
    """
    將汗乳酸運算數據與 AI 處方渲染為現代科技感 HTML 儀表板
    """
    athlete = report_data.get("athlete_name", "選手")
    metrics = report_data.get("metrics", {})
    ai = report_data.get("ai_analysis", {})
    sessions = report_data.get("sessions", [])

    rx = ai.get("next_workout_prescription", {})
    hero_insights = ai.get("hero_insights", [])

    source_banner_html = f"""<div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; padding: 10px 16px; border-radius: 10px; font-size: 0.88rem; margin-bottom: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px;"><span>✅</span> <span><strong>【個人專屬紀錄】</strong>已成功連結運動員 <strong>{athlete}</strong> 之個人雲端真實訓練數據庫（包含關鍵乳酸測驗與日常背景運動）。</span></div>"""

    # 圖表資料準備
    dates_labels = [s["date"] for s in sessions]
    # 若某場次為手錶日常（無乳酸採樣），在乳酸數值填入 None (JSON null)，避免繪出 0 mmol/L 的突兀柱狀
    avg_lactates = [(s.get("avg_lactate") if (s.get("avg_lactate", 0) > 0 or len(s.get("lactate_readings", [])) > 0) else None) for s in sessions]
    max_lactates = [(s.get("max_lactate") if (s.get("avg_lactate", 0) > 0 or len(s.get("lactate_readings", [])) > 0) else None) for s in sessions]
    powers = [s.get("avg_power", 0) for s in sessions]
    hrs = [s.get("avg_hr", 0) for s in sessions]
    durations = [s.get("duration_min", 0) for s in sessions]

    # 嚴格遵循原則：若功率有任何缺失（任一場次無功率或完全無功率），直接用心率畫線做比較，不秀功率圖
    has_full_power = (
        len(sessions) > 0
        and all(
            s.get("avg_power") is not None
            and float(s.get("avg_power", 0)) > 0
            and not np.isnan(float(s.get("avg_power", 0)))
            for s in sessions
        )
    )
    if has_full_power:
        secondary_intensity = powers
        secondary_label = "平均功率 (W)"
        secondary_color = "#00f2fe"
        chart_title_metric = "平均功率"
        chart_subtitle = "縱向汗乳酸 vs 平均功率 (W) 代謝經濟性對照"
    else:
        secondary_intensity = hrs
        secondary_label = "平均心率 (bpm)"
        secondary_color = "#ff5252"
        chart_title_metric = "平均心率"
        chart_subtitle = "縱向汗乳酸 vs 平均心率 (bpm) 對照（功率缺失，直接用心率畫線比較）"

    zone_pct = metrics.get("zone_percentage", {})
    polar_labels = [
        f"低代謝負荷 (主動排酸 <= {metrics.get('baseline_low', 6.0)} mmol/L)",
        f"中等代謝負荷 (節奏穩態 {metrics.get('baseline_low', 6.0)}-{metrics.get('baseline_high', 15.0)})",
        f"高代謝負荷 (高糖解輸出 > {metrics.get('baseline_high', 15.0)})"
    ]
    polar_values = [
        zone_pct.get("Low_Recovery", 0),
        zone_pct.get("Tempo_Aerobic", 0),
        zone_pct.get("High_Glycolytic", 0)
    ]

    # 專項範圍識別標籤 (精確反映使用者篩選意圖與專項分佈)
    sport_filter = report_data.get("sport_filter", "all")
    counts = metrics.get("sport_counts", {})
    
    if sport_filter == "cycling" or (sport_filter != "all" and metrics.get("is_pure_cycling")):
        sport_scope_badge = "<span style='display:inline-flex; align-items:center; background:rgba(0,242,254,0.12); border:1px solid rgba(0,242,254,0.3); color:#00f2fe; padding:4px 12px; border-radius:999px; font-size:0.8rem; font-weight:700;'>🚲 自行車專項分析</span>"
    elif sport_filter == "running" or (sport_filter != "all" and metrics.get("is_pure_running")):
        sport_scope_badge = "<span style='display:inline-flex; align-items:center; background:rgba(255,82,82,0.12); border:1px solid rgba(255,82,82,0.3); color:#ff5252; padding:4px 12px; border-radius:999px; font-size:0.8rem; font-weight:700;'>🏃 跑步專項分析</span>"
    else:
        c_items = []
        if counts.get('cycling', 0) > 0:
            c_items.append(f"🚲 騎行 {counts.get('cycling')} 場")
        if counts.get('running', 0) > 0:
            c_items.append(f"🏃 跑步 {counts.get('running')} 場")
        for k, v in counts.items():
            if k not in ['cycling', 'running'] and v > 0:
                c_items.append(f"🏅 {k} {v} 場")
        detail_desc = f" ({' / '.join(c_items)})" if c_items else ""
        sport_scope_badge = f"<span style='display:inline-flex; align-items:center; background:rgba(255,171,0,0.12); border:1px solid rgba(255,171,0,0.3); color:#ffab00; padding:4px 12px; border-radius:999px; font-size:0.8rem; font-weight:700;'>🌐 全部專項 (綜合交叉分析){detail_desc}</span>"

    # 處方階段 HTML
    phases_html = ""
    for idx, p in enumerate(rx.get("protocol_phases", [])):
        phases_html += f"""
        <div class="phase-card">
            <div class="phase-header">
                <span class="phase-step">PHASE 0{idx+1}</span>
                <span class="phase-name">{p.get('phase', '')}</span>
                <span class="phase-dur">⏱️ {p.get('duration', '')}</span>
            </div>
            <div class="phase-intensity">🎯 <strong>目標強度：</strong>{p.get('intensity', '')}</div>
            <div class="phase-focus">💡 <strong>生理焦點：</strong>{p.get('focus', '')}</div>
        </div>
        """

    # 場次明細表格
    table_rows_html = ""
    for s in sessions:
        is_icu = s.get('source') == 'intervals_icu'
        has_la = (s.get('avg_lactate', 0) > 0) or (len(s.get('lactate_readings', [])) > 0)
        
        eff_str = f"{s.get('metabolic_efficiency', 0)} {s.get('efficiency_unit', '')}" if (s.get('metabolic_efficiency') is not None and s.get('metabolic_efficiency', 0) > 0) else "<span style='color:#64748b;'>—</span>"
        pwr_val = float(s.get('avg_power', 0)) if s.get('avg_power') is not None else 0.0
        pwr_str = f"{pwr_val:.1f} W" if pwr_val > 0 else "<span style='color:#64748b;'>—</span>"
        hr_str = f"{s.get('avg_hr', 0)} bpm" if s.get('avg_hr', 0) > 0 else "<span style='color:#64748b;'>—</span>"
        intv_badge = f"<span class='intv-pill'>{s.get('interval_desc')}</span>"
        sport_disp = s.get('sport_display', '🏅 運動')
        sport_color = s.get('sport_color', '#ffab00')
        sub_info = f"<br><span style='font-size:0.68rem; color:#94a3b8;'>{s.get('sub_sport', '')}</span>" if s.get('sub_sport') and s.get('sub_sport') != 'generic' else ""
        
        # 標註手錶日常訓練來源
        source_badge = "<br><span style='font-size:0.68rem; color:#38bdf8; background:rgba(56,189,248,0.12); padding:1px 6px; border-radius:4px;'>⌚ 手錶日常</span>" if is_icu else ""
        sport_badge = f"<span style='display:inline-block; padding:2px 8px; border-radius:10px; font-size:0.75rem; font-weight:700; background:rgba(255,255,255,0.06); color:{sport_color}'>{sport_disp}{sub_info}</span>{source_badge}"
        
        hrv_val = s.get('hrv')
        rhr_val = s.get('resting_hr')
        if hrv_val and hrv_val > 0:
            rhr_txt = f"<br><span style='font-size:0.72rem; color:#94a3b8;'>靜息 {int(rhr_val)} bpm</span>" if (rhr_val and rhr_val > 0) else ""
            hrv_html = f"<span style='color: #a78bfa; font-weight: 700;'>{hrv_val} ms</span>{rhr_txt}"
        else:
            hrv_html = "<span style='color:#64748b; font-size:0.8rem;'>—</span>"

        if has_la:
            avg_la_html = f"<span style='color: #ffab00; font-weight: 700;'>{s.get('avg_lactate')}</span>"
            max_la_html = f"<span style='color: #ff5252; font-weight: 700;'>{s.get('max_lactate')}</span>"
        else:
            avg_la_html = "<span style='color:#64748b; font-size:0.8rem;'>未採樣</span>"
            max_la_html = "<span style='color:#64748b; font-size:0.8rem;'>未採樣</span>"

        table_rows_html += f"""
        <tr>
            <td style="font-weight: 700; color: #ffffff;">{s.get('date')}</td>
            <td>{intv_badge}</td>
            <td>{sport_badge}</td>
            <td><span class="type-pill">{s.get('type')}</span></td>
            <td class="num">{s.get('duration_min')} 分</td>
            <td class="num" style="color: #00f2fe; font-weight: 600;">{pwr_str}</td>
            <td class="num" style="color: #ff5252; font-weight: 600;">{hr_str}</td>
            <td class="num">{avg_la_html}</td>
            <td class="num">{max_la_html}</td>
            <td class="num" style="color: #00e676; font-weight: 700;">{eff_str}</td>
            <td class="num">{hrv_html}</td>
            <td class="num" style="color: #64b5f6;">{s.get('calculated_load')}</td>
        </tr>
        """

    # HRV KPI 卡片 HTML
    hrv_kpi_card_html = ""
    if metrics.get("has_hrv_data"):
        d_pct = metrics.get('hrv_delta_pct')
        delta_str = f"{'+' if (d_pct or 0) > 0 else ''}{d_pct}%" if d_pct is not None else "持平"
        hrv_kpi_card_html = f"""
            <div class="kpi-card">
                <div class="kpi-label">💓 自律神經恢復基準 (HRV)</div>
                <div class="kpi-value" style="color: #a78bfa;">{metrics.get('latest_hrv', '—')} <span style="font-size: 1rem; color: var(--text-secondary);">ms</span></div>
                <div class="kpi-sub">週期基準 {metrics.get('hrv_baseline')} ms（偏離 {delta_str}），靜息心率 {metrics.get('rhr_baseline')} bpm</div>
            </div>
        """

    # Hero Insight 卡片 HTML
    hero_cards_html = ""
    for h in hero_insights:
        hero_cards_html += f"""
        <div class="insight-pill">
            <div class="insight-label">{h.get('metric')}</div>
            <div class="insight-val">{h.get('value')}</div>
            <div class="insight-desc">{h.get('desc')}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{athlete}：{ai.get('report_title', '汗乳酸運動生理週期分析與處方報告')}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-card: rgba(18, 24, 38, 0.75);
            --bg-card-hover: rgba(25, 33, 52, 0.85);
            --border: rgba(255, 255, 255, 0.08);
            --border-highlight: rgba(0, 242, 254, 0.3);
            --neon-cyan: #00f2fe;
            --neon-blue: #4facfe;
            --neon-emerald: #00e676;
            --neon-amber: #ffab00;
            --neon-crimson: #ff5252;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
            line-height: 1.6;
            padding: 30px 16px 80px;
        }}
        .container {{
            max-width: 1180px;
            margin: 0 auto;
        }}

        /* Header */
        header {{
            background: linear-gradient(180deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.2) 100%);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 32px 36px;
            margin-bottom: 28px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(12px);
        }}
        header::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--neon-cyan), var(--neon-emerald), var(--neon-amber));
        }}
        .top-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 12px;
        }}
        .athlete-tag {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 242, 254, 0.1);
            border: 1px solid rgba(0, 242, 254, 0.25);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--neon-cyan);
            letter-spacing: 0.5px;
        }}
        .recovery-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {metrics.get('state_color')};
            color: {metrics.get('state_color')};
        }}
        h1 {{
            font-size: 2.1rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.5px;
            margin-bottom: 8px;
        }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .summary-banner {{
            margin-top: 18px;
            padding: 14px 18px;
            background: rgba(0, 230, 118, 0.08);
            border-left: 4px solid var(--neon-emerald);
            border-radius: 8px;
            font-size: 0.95rem;
            color: #e2e8f0;
            font-weight: 500;
            line-height: 1.6;
        }}

        /* Hero KPIs */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 22px;
            backdrop-filter: blur(10px);
            transition: all 0.2s ease;
        }}
        .kpi-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-highlight);
            transform: translateY(-2px);
        }}
        .kpi-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 6px;
            font-weight: 600;
        }}
        .kpi-value {{
            font-size: 1.9rem;
            font-weight: 800;
            color: #ffffff;
            line-height: 1.2;
            margin-bottom: 4px;
        }}
        .kpi-sub {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        /* Next Workout Prescription Card */
        .rx-card {{
            background: linear-gradient(135deg, rgba(20, 30, 48, 0.95) 0%, rgba(10, 20, 35, 0.95) 100%);
            border: 2px solid var(--neon-cyan);
            box-shadow: 0 0 30px rgba(0, 242, 254, 0.15);
            border-radius: 20px;
            padding: 32px;
            margin-bottom: 32px;
            position: relative;
        }}
        .rx-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: linear-gradient(90deg, #ff0844, #ffb199);
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            padding: 4px 12px;
            border-radius: 6px;
            margin-bottom: 14px;
        }}
        .rx-title {{
            font-size: 1.7rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .rx-meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            margin: 18px 0 24px;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--border);
        }}
        .rx-meta-item {{
            flex: 1;
            min-width: 160px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 12px 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .rx-meta-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .rx-meta-val {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--neon-cyan);
        }}
        .phase-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 14px;
            margin: 20px 0;
        }}
        .phase-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 16px;
        }}
        .phase-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .phase-step {{
            font-size: 0.7rem;
            font-weight: 800;
            color: var(--neon-cyan);
            background: rgba(0, 242, 254, 0.1);
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .phase-name {{
            font-weight: 700;
            font-size: 0.95rem;
            color: #ffffff;
        }}
        .phase-dur {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        .phase-intensity {{
            font-size: 0.85rem;
            color: #e2e8f0;
            margin-bottom: 6px;
        }}
        .phase-focus {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        .rx-rationale {{
            background: rgba(0, 242, 254, 0.05);
            border-left: 3px solid var(--neon-cyan);
            padding: 14px 18px;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #cbd5e1;
            margin-top: 18px;
            line-height: 1.6;
        }}

        /* Analysis Sections */
        .section-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 28px;
            margin-bottom: 28px;
            backdrop-filter: blur(10px);
        }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 18px;
        }}
        .section-icon {{
            font-size: 1.4rem;
        }}
        .section-title {{
            font-size: 1.3rem;
            font-weight: 700;
            color: #ffffff;
        }}
        .prose {{
            font-size: 0.95rem;
            color: #cbd5e1;
            line-height: 1.75;
            margin-bottom: 16px;
        }}

        /* Hero Insights Horizontal Grid */
        .insights-bar {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
            margin: 20px 0;
        }}
        .insight-pill {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 12px;
            padding: 14px 18px;
        }}
        .insight-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
        }}
        .insight-val {{
            font-size: 1.25rem;
            font-weight: 800;
            color: var(--neon-emerald);
            margin: 4px 0 2px;
        }}
        .insight-desc {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        /* Charts Grid */
        .charts-row {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 28px;
        }}
        @media (max-width: 900px) {{
            .charts-row {{ grid-template-columns: 1fr; }}
        }}
        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 24px;
        }}
        .chart-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .chart-container {{
            position: relative;
            height: 310px;
            width: 100%;
        }}

        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            margin-top: 12px;
        }}
        th, td {{
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            background: rgba(255, 255, 255, 0.02);
        }}
        td.num, th.num {{ text-align: right; }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.03);
        }}
        .type-pill {{
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.06);
            padding: 3px 8px;
            border-radius: 6px;
            color: #e2e8f0;
        }}
        .intv-pill {{
            font-size: 0.75rem;
            background: rgba(0, 242, 254, 0.1);
            color: var(--neon-cyan);
            border: 1px solid rgba(0, 242, 254, 0.2);
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}

        /* Footer */
        footer {{
            margin-top: 50px;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
            border-top: 1px solid var(--border);
            padding-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            {source_banner_html}
            <div class="top-meta">
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <div class="athlete-tag">💧 汗乳酸動態監控 &nbsp;|&nbsp; 選手：{athlete} &nbsp;|&nbsp; 週期：{metrics.get('period_start')} – {metrics.get('period_end')}</div>
                    {sport_scope_badge}
                </div>
                <div class="recovery-pill">● {metrics.get('recovery_state')}</div>
            </div>
            <h1>💧 {ai.get('report_title', '汗乳酸運動生理週期分析與處方報告')}</h1>
            <div class="subtitle">以非侵入式汗乳酸動力學 (Sweat Lactate)、跨期實際間隔天數與輸出負荷（功率/心率）對比為核心之運動科學診斷</div>
            <div class="summary-banner">
                💡 <strong>週期核心生理洞察：</strong>{ai.get('athlete_summary_tag', '汗乳酸代謝經濟性突破')} &nbsp;—&nbsp; {metrics.get('recommended_action')}
            </div>
        </header>

        <!-- Hero KPIs -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">⏱️ 週期實際跨度與訓練量</div>
                <div class="kpi-value" style="color: var(--neon-cyan);">{metrics.get('total_hours')} <span style="font-size: 1rem; color: var(--text-secondary);">小時</span></div>
                <div class="kpi-sub">跨越 {metrics.get('time_span_days')} 天，共 {metrics.get('session_count')} 場實際訓練</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">💧 汗乳酸動態範圍</div>
                <div class="kpi-value" style="color: var(--neon-amber);">{metrics.get('min_sweat_lactate')} ~ {metrics.get('peak_sweat_lactate')} <span style="font-size: 0.95rem; color: var(--text-secondary);">mmol/L</span></div>
                <div class="kpi-sub">平均濃度 {metrics.get('avg_sweat_lactate')} mmol/L（非血乳酸標準）</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">📈 輸出/汗乳酸代謝經濟性</div>
                <div class="kpi-value" style="color: var(--neon-emerald);">{'+' if metrics.get('efficiency_delta_pct', 0) > 0 else ''}{metrics.get('efficiency_delta_pct', 0)}%</div>
                <div class="kpi-sub">最新輸出效率：{metrics.get('latest_efficiency')} {metrics.get('efficiency_unit')}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">⚡ 汗乳酸加權累積負荷</div>
                <div class="kpi-value" style="color: #64b5f6;">{metrics.get('total_sweat_load')} <span style="font-size: 1rem; color: var(--text-secondary);">分</span></div>
                <div class="kpi-sub">距上一場隔 {metrics.get('days_since_prior', 0)} 天休整</div>
            </div>
            {hrv_kpi_card_html}
        </div>

        <!-- Hero Insights Bar -->
        <div class="insights-bar">
            {hero_cards_html}
        </div>

        <!-- 🔥 NEXT WORKOUT PROTOCOL (下一次運動處方卡片) -->
        <div class="rx-card">
            <div class="rx-badge">⚡ NEXT WORKOUT PROTOCOL ・ 下一次訓練處方</div>
            <div class="rx-title">{rx.get('workout_code', 'SWEAT-RX')} : {rx.get('workout_name', '汗乳酸巡航處方')}</div>
            
            <div class="rx-meta-row">
                <div class="rx-meta-item">
                    <div class="rx-meta-label">🎯 汗乳酸目標控制</div>
                    <div class="rx-meta-val" style="color: var(--neon-amber); font-size: 0.95rem;">{rx.get('target_lactate_limit', '維持於個人低汗乳酸基準線')}</div>
                </div>
                <div class="rx-meta-item">
                    <div class="rx-meta-label">⏱️ 目標時長</div>
                    <div class="rx-meta-val">{rx.get('target_duration_min', 40)} 分鐘</div>
                </div>
                <div class="rx-meta-item">
                    <div class="rx-meta-label">⚡ 強度指引 (心率/功率)</div>
                    <div class="rx-meta-val" style="font-size: 0.95rem;">{rx.get('target_intensity', 'Zone 1-2')}</div>
                </div>
                <div class="rx-meta-item">
                    <div class="rx-meta-label">🏃 建議項目與休整時程</div>
                    <div class="rx-meta-val" style="font-size: 0.95rem; color: var(--neon-emerald);">{rx.get('sport_type', '耐力運動')} ({rx.get('recommended_date', '次日')})</div>
                </div>
            </div>

            <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 8px;">
                📋 課表結構與階段指引 (Protocol Phases)
            </div>
            <div class="phase-grid">
                {phases_html}
            </div>

            <div class="rx-rationale">
                <strong>🧬 運動生理學處方依據：</strong>{rx.get('physiological_rationale', '')}
            </div>
        </div>

        <!-- Deep Physiological Insights -->
        <div class="section-box">
            <div class="section-header">
                <span class="section-icon">🔬</span>
                <span class="section-title">一、汗乳酸動力學與輸出負荷對照評析</span>
            </div>
            <div class="prose">
                {ai.get('lactate_kinetics_analysis', '')}
            </div>

            <div class="section-header" style="margin-top: 24px;">
                <span class="section-icon">⚖️</span>
                <span class="section-title">二、跨期實際間隔天數與代謝累積負荷平衡</span>
            </div>
            <div class="prose">
                {ai.get('cumulative_load_fatigue_review', '')}
            </div>

            <div class="section-header" style="margin-top: 24px;">
                <span class="section-icon">🩺</span>
                <span class="section-title">三、教練專業叮嚀 (Recovery & Hydration Tips)</span>
            </div>
            <div class="prose" style="color: #93c5fd; background: rgba(59, 130, 246, 0.08); padding: 14px 18px; border-radius: 10px; border-left: 3px solid #3b82f6;">
                {ai.get('coach_pro_tips', '')}
            </div>
        </div>

        <!-- Interactive Visualizations -->
        <div class="charts-row">
            <div class="chart-card">
                <div class="chart-title">
                    <span>📊 跨期汗乳酸趨勢 vs 運動負荷 ({chart_title_metric})</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted);">{chart_subtitle}</span>
                </div>
                <div class="chart-container">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-title">
                    <span>🧭 汗乳酸代謝負荷分佈 (%)</span>
                    <span style="font-size: 0.75rem; color: var(--text-muted);">時長佔比</span>
                </div>
                <div class="chart-container">
                    <canvas id="polarChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Session Matrix Table -->
        <div class="section-box">
            <div class="section-header">
                <span class="section-icon">📋</span>
                <span class="section-title">四、跨期實際訓練場次與汗乳酸數據矩陣</span>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>訓練日期</th>
                            <th>距前次間隔</th>
                            <th>運動專項</th>
                            <th>強度層級</th>
                            <th class="num">時長</th>
                            <th class="num">平均功率</th>
                            <th class="num">平均心率</th>
                            <th class="num">平均汗乳酸</th>
                            <th class="num">峰值汗乳酸</th>
                            <th class="num">代謝效率比</th>
                            <th class="num">晨間 HRV / 靜息心率</th>
                            <th class="num">單場負荷</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <footer>
            💧 Powered by Sweat Lactate Kinetics Engine & Firebase AI Logic &nbsp;|&nbsp; LactateCloud Sports System &nbsp;|&nbsp; 報告產出時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </footer>
    </div>

    <!-- Chart.js Scripts -->
    <script>
        const dates = {json.dumps(dates_labels)};
        const avgLa = {json.dumps(avg_lactates)};
        const maxLa = {json.dumps(max_lactates)};
        const intensityVals = {json.dumps(secondary_intensity)};
        const polarLabels = {json.dumps(polar_labels, ensure_ascii=False)};
        const polarValues = {json.dumps(polar_values)};

        // 1. 雙軸趨勢圖
        new Chart(document.getElementById('trendChart'), {{
            type: 'bar',
            data: {{
                labels: dates,
                datasets: [
                    {{
                        type: 'line',
                        label: '峰值汗乳酸 (mmol/L)',
                        data: maxLa,
                        borderColor: '#ff5252',
                        backgroundColor: '#ff5252',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 5,
                        spanGaps: true,
                        yAxisID: 'yLactate'
                    }},
                    {{
                        type: 'bar',
                        label: '平均汗乳酸 (mmol/L)',
                        data: avgLa,
                        backgroundColor: 'rgba(255, 171, 0, 0.7)',
                        borderRadius: 6,
                        yAxisID: 'yLactate'
                    }},
                    {{
                        type: 'line',
                        label: '{secondary_label}',
                        data: intensityVals,
                        borderColor: '{secondary_color}',
                        borderDash: [5, 5],
                        borderWidth: 2,
                        pointRadius: 4,
                        spanGaps: true,
                        yAxisID: 'yIntensity'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                        labels: {{ color: '#94a3b8', boxWidth: 12, font: {{ size: 11 }} }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    yLactate: {{
                        type: 'linear',
                        position: 'left',
                        title: {{ display: true, text: '汗乳酸 (mmol/L)', color: '#ffab00' }},
                        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                        ticks: {{ color: '#ffab00' }}
                    }},
                    yIntensity: {{
                        type: 'linear',
                        position: 'right',
                        title: {{ display: true, text: '{secondary_label}', color: '{secondary_color}' }},
                        grid: {{ display: false }},
                        ticks: {{ color: '{secondary_color}' }},
                        suggestedMin: { '0' if has_full_power else '60' }
                    }}
                }}
            }}
        }});

        // 2. 極化分佈環形圖
        new Chart(document.getElementById('polarChart'), {{
            type: 'doughnut',
            data: {{
                labels: polarLabels,
                datasets: [{{
                    data: polarValues,
                    backgroundColor: [
                        '#00e676', // Low
                        '#00f2fe', // Tempo
                        '#ff5252'  // High
                    ],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ color: '#94a3b8', font: {{ size: 10 }}, boxWidth: 10 }}
                    }}
                }},
                cutout: '65%'
            }}
        }});
    </script>
</body>
</html>
"""
    return html


def save_report_html(report_data, output_path="modern_weekly_report.html"):
    """將生成的現代化 HTML 儲存至本機檔案"""
    html_content = render_modern_html_report(report_data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"現代化汗乳酸運動週報已儲存至：{output_path}")
    return output_path


if __name__ == "__main__":
    print("正在生成汗乳酸運動生理分析週報...")
    data = generate_weekly_report_data(source="DataMindy", athlete_name="Mindy", days_limit=6)
    save_report_html(data, "modern_weekly_report.html")
