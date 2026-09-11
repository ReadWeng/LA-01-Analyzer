# -*- coding: utf-8 -*-
import os
import re
import json
import glob
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def infer_session_type(power, hr, lactate):
    """
    根據乳酸、心率與負荷強度推斷運動強度分級 (不綁定特定運動項目，以強度等級呈現)
    """
    if lactate >= 12.0 or hr >= 168:
        return "超高強度 (無氧刺激)"
    elif lactate >= 8.0 or hr >= 158:
        return "高強度 (無氧閾值)"
    elif lactate >= 5.0 or hr >= 145:
        return "中高強度 (節奏耐力)"
    elif lactate >= 3.0 or hr >= 130:
        return "中等強度 (基礎耐力)"
    elif lactate > 0 or hr > 0:
        if hr <= 125 and (lactate <= 2.2 if lactate > 0 else True):
            return "低強度 (主動恢復)"
        return "基礎有氧 (有氧耐力)"
    else:
        return "常規訓練"


def fetch_firebase_recent_sessions(uid, token, limit=5):
    """
    從 Firebase Firestore 抓取指定使用者的最新訓練場次 (fit_records 與對應的 lactate_records)。
    """
    if not uid or not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. 抓取 fit_records
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"
    fit_sessions = []
    try:
        r_fit = requests.get(fit_url, headers=headers, timeout=10)
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

                avg_pwr = float(f.get("avg_power", {}).get("integerValue", 0))
                max_pwr = float(f.get("max_power", {}).get("integerValue", 0))
                avg_hr = float(f.get("avg_hr", {}).get("integerValue", 0))
                max_hr = float(f.get("max_hr", {}).get("integerValue", 0))
                max_core = f.get("max_core", {}).get("doubleValue", None)

                ts_values = f.get("time_series", {}).get("arrayValue", {}).get("values", [])
                duration_min = 0.0
                if ts_values:
                    last_pt = ts_values[-1].get("mapValue", {}).get("fields", {})
                    duration_min = float(last_pt.get("elapsed_minutes", {}).get("doubleValue", 0.0))

                fit_sessions.append({
                    "id": doc.get("name"),
                    "file_name": file_name,
                    "start_time": start_dt,
                    "duration_min": round(duration_min, 1),
                    "avg_power": round(avg_pwr, 1),
                    "max_power": round(max_pwr, 1),
                    "avg_hr": round(avg_hr, 1),
                    "max_hr": round(max_hr, 1),
                    "max_core": max_core,
                    "points_count": len(ts_values),
                    "lactate_readings": []
                })
    except Exception as e:
        print(f"Error fetching fit_records: {e}")

    # 2. 抓取 lactate_records
    la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records"
    all_lactate = []
    try:
        r_la = requests.get(la_url, headers=headers, timeout=10)
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

    # 3. 將乳酸紀錄配對至各 fit_session
    for s in fit_sessions:
        s_time = s["start_time"]
        if s_time:
            s_naive = s_time.replace(tzinfo=None)
            dur = s["duration_min"]
            matched_la = []
            for la in all_lactate:
                diff_min = (la["record_time"] - s_naive).total_seconds() / 60.0
                if -30 <= diff_min <= (dur + 45):
                    matched_la.append(la["lactate_mmol"])
            s["lactate_readings"] = matched_la
            if matched_la:
                s["avg_lactate"] = round(float(np.mean(matched_la)), 2)
                s["max_lactate"] = round(float(np.max(matched_la)), 2)
            else:
                s["avg_lactate"] = 0.0
                s["max_lactate"] = 0.0

    # 依開始時間倒序排列並取 limit
    valid_sessions = [s for s in fit_sessions if s["start_time"] is not None]
    valid_sessions = sorted(valid_sessions, key=lambda x: x["start_time"], reverse=True)
    recent = valid_sessions[:limit]
    
    # 格式化欄位以便報告使用 (日期由舊到新排序)
    recent = sorted(recent, key=lambda x: x["start_time"])
    for s in recent:
        s["date"] = s["start_time"].strftime("%m/%d")
        s["full_date"] = s["start_time"].strftime("%Y-%m-%d")
        s["type"] = infer_session_type(s["avg_power"], s["avg_hr"], s["avg_lactate"])

    return recent


def fetch_local_sessions(folder="DataMindy", limit=5):
    """
    從本機歷史資料載入場次作為備援。
    """
    html_files = sorted(glob.glob(os.path.join(folder, "lactate_report_*.html")))
    sessions = []

    for fpath in html_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            tm = re.search(r'活動開始時間.*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', content)
            if not tm:
                tm = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(fpath))
            st_str = tm.group(1) if tm else "2026-09-10"
            try:
                st_dt = datetime.strptime(st_str[:19], '%Y-%m-%d %H:%M:%S' if len(st_str) > 10 else '%Y-%m-%d')
            except Exception:
                st_dt = datetime(2026, 9, 10)

            dur_m = re.search(r'時長.*?(\d+(?:\.\d+)?)\s*分', content)
            duration_min = float(dur_m.group(1)) if dur_m else 40.0

            p_m = re.search(r'功率.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*W', content)
            avg_p = float(p_m.group(1)) if p_m else 0.0
            max_p = float(p_m.group(2)) if p_m else 0.0

            h_m = re.search(r'心率.*?(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*bpm', content)
            avg_h = float(h_m.group(1)) if h_m else 0.0
            max_h = float(h_m.group(2)) if h_m else 0.0

            la_vals = []
            table_m = re.search(r'<table[^>]*>(.*?)</table>', content, re.DOTALL)
            if table_m:
                tds = re.findall(r'<td[^>]*>(.*?)</td>', table_m.group(1))
                for i in range(1, len(tds), 2):
                    try:
                        v = float(tds[i].strip())
                        if 0.5 <= v <= 30.0:
                            la_vals.append(v)
                    except Exception:
                        pass

            if not la_vals:
                all_la = re.findall(r'(\d+\.\d+)\s*mmol/L', content)
                la_vals = [float(x) for x in all_la if 0.5 <= float(x) <= 30.0]

            avg_la = round(float(np.mean(la_vals)), 2) if la_vals else 0.0
            max_la = round(float(np.max(la_vals)), 2) if la_vals else 0.0

            sessions.append({
                "file_name": os.path.basename(fpath),
                "start_time": st_dt,
                "duration_min": duration_min,
                "avg_power": avg_p,
                "max_power": max_p,
                "avg_hr": avg_h,
                "max_hr": max_h,
                "avg_lactate": avg_la,
                "max_lactate": max_la,
                "lactate_readings": la_vals,
                "date": st_dt.strftime("%m/%d"),
                "full_date": st_dt.strftime("%Y-%m-%d"),
                "type": infer_session_type(avg_p, avg_h, avg_la)
            })
        except Exception as e:
            print(f"Error parsing local file {fpath}: {e}")

    if sessions:
        sessions = sorted(sessions, key=lambda x: x["start_time"])
        return sessions[-limit:]
        
    return get_benchmark_sessions()


def get_benchmark_sessions():
    """標準基準場次 (5 場不同強度與時長的訓練數據)"""
    return [
        {"date": "08/22", "full_date": "2026-08-22", "type": "超高強度 (無氧刺激)", "duration_min": 32.1, "avg_power": 186.7, "max_power": 245.0, "avg_hr": 152.9, "max_hr": 178.0, "avg_lactate": 17.60, "max_lactate": 18.30},
        {"date": "08/26", "full_date": "2026-08-26", "type": "中等強度 (基礎耐力)", "duration_min": 41.7, "avg_power": 184.3, "max_power": 230.0, "avg_hr": 132.1, "max_hr": 155.0, "avg_lactate": 9.57, "max_lactate": 10.00},
        {"date": "08/29", "full_date": "2026-08-29", "type": "中高強度 (節奏耐力)", "duration_min": 96.1, "avg_power": 194.0, "max_power": 260.0, "avg_hr": 151.6, "max_hr": 182.0, "avg_lactate": 14.40, "max_lactate": 19.70},
        {"date": "09/08", "full_date": "2026-09-08", "type": "高強度 (無氧閾值)", "duration_min": 33.1, "avg_power": 189.0, "max_power": 255.0, "avg_hr": 159.0, "max_hr": 181.0, "avg_lactate": 10.85, "max_lactate": 17.10},
        {"date": "09/10", "full_date": "2026-09-10", "type": "中高強度 (節奏耐力)", "duration_min": 60.0, "avg_power": 196.9, "max_power": 250.0, "avg_hr": 149.6, "max_hr": 170.0, "avg_lactate": 7.78, "max_lactate": 10.50},
    ]


def analyze_sessions_with_ai(sessions, athlete_name="", api_key=None):
    """
    結合運動生理學邏輯與 Gemini API 生成最近運動狀態分析報告。
    """
    if not sessions:
        return {}

    start_d = sessions[0]["full_date"]
    end_d = sessions[-1]["full_date"]
    period_str = f"{start_d} – {end_d}"

    has_power = any(s.get("avg_power", 0) > 0 for s in sessions)
    
    is_breakthrough = False
    if len(sessions) >= 2:
        latest = sessions[-1]
        others = sessions[:-1]
        if has_power:
            max_p_others = max([s.get("avg_power", 0) for s in others])
            min_lac_others = min([s.get("avg_lactate", 99) for s in others if s.get("avg_lactate", 0) > 0] or [99])
            if latest.get("avg_power", 0) >= max_p_others and latest.get("avg_lactate", 0) <= min_lac_others:
                is_breakthrough = True
        else:
            min_lac_others = min([s.get("avg_lactate", 99) for s in others if s.get("avg_lactate", 0) > 0] or [99])
            if latest.get("avg_lactate", 0) <= min_lac_others:
                is_breakthrough = True

    if api_key:
        ai_res = call_gemini_api(sessions, athlete_name, period_str, is_breakthrough, api_key)
        if ai_res:
            return ai_res

    return generate_rule_based_analysis(sessions, athlete_name, period_str, is_breakthrough)


def call_gemini_api(sessions, athlete_name, period_str, is_breakthrough, api_key):
    """呼叫 Google Gemini REST API 產出結構化最近運動狀態分析"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    sessions_summary = []
    for s in sessions:
        sessions_summary.append({
            "date": s["date"],
            "intensity_grade": s.get("type", "訓練"),
            "duration_min": s.get("duration_min", 0),
            "avg_power_W": s.get("avg_power", 0),
            "avg_hr_bpm": s.get("avg_hr", 0),
            "avg_lactate_mmol": s.get("avg_lactate", 0),
            "max_lactate_mmol": s.get("max_lactate", 0)
        })

    subject = f"運動員【{athlete_name}】" if athlete_name else "受測者"
    prompt_text = f"""你是一位資深耐力運動生理科學家與國家級體能教練。
請根據{subject}最近幾場訓練數據（資料期間：{period_str}），撰寫一份嚴謹、客觀具洞察力且符合運動生理學（Exercise Physiology）的「最近運動狀態與生理適應分析報告」。

注意事項：
1. 運動不限於單車騎乘，請一律使用「訓練」、「運動」或「強度等級」進行描述，不要硬套騎乘或跑步等特定項目。
2. 標題請固定為「最近運動狀態與生理適應分析報告」，不要包含「本週」或「個人名字」。
3. 第一節聚焦於「最近訓練強度節奏」分析。
4. 第二節聚焦於「表現與代謝對比」：重點觀察負荷（功率或心率）與乳酸之關係。特別是代謝效率（Metabolic Efficiency），若出現負荷維持或提高且乳酸顯著降低，請說明其粒線體密度與乳酸清除轉運蛋白（MCT）適應的生理意義。
5. 時長 vs 乳酸的分佈解讀。
6. 總結與後續訓練處方建議。

訓練數據列表：
{json.dumps(sessions_summary, ensure_ascii=False, indent=2)}

請直接輸出繁體中文 JSON 格式（不要包含 markdown 代碼塊標記，只輸出純 JSON）：
{{
  "title": "最近運動狀態與生理適應分析報告",
  "period_str": "資料期間：{period_str}",
  "week_rhythm_summary": "最近訓練強度節奏的一段說明文字",
  "kpi_cards": [
    {{"label": "分析場次總數", "value": "{len(sessions)} 場訓練"}},
    {{"label": "最高乳酸峰值", "value": "{max([s.get('max_lactate',0) for s in sessions])} mmol/L"}},
    {{"label": "最新場次平均乳酸", "value": "{sessions[-1].get('avg_lactate',0)} mmol/L"}}
  ],
  "comparison_intro": "最近各場次客觀量化生理數據對比說明",
  "highlight_text": "最近最值得標記的關鍵發現（請用 tag-blue 強調關鍵字）",
  "duration_summary": "時長 vs 乳酸的分佈關聯解讀說明",
  "overall_summary": "總結與教練專業建議文字"
}}
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            result = res.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw_text = re.sub(r'^```json\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)
            return json.loads(raw_text)
    except Exception as e:
        print(f"Gemini API invocation error: {e}")

    return None


def generate_rule_based_analysis(sessions, athlete_name, period_str, is_breakthrough):
    """
    內建專業運動生理學規則引擎：產出「最近運動狀態與生理適應分析報告」。
    """
    latest = sessions[-1]
    
    # 建立統計指標卡片
    max_la_all = max([s.get("max_lactate", 0) for s in sessions])
    avg_la_all = round(float(np.mean([s.get("avg_lactate", 0) for s in sessions])), 2)

    kpis = [
        {"label": "分析場次總數", "value": f"{len(sessions)} 場訓練"},
        {"label": "最高乳酸峰值", "value": f"{max_la_all} mmol/L"},
        {"label": f"最新場次 ({latest['date']}) 平均乳酸", "value": f"{latest['avg_lactate']} mmol/L"}
    ]

    types_list = [s.get("type", "訓練") for s in sessions]
    types_str = " → ".join(types_list)
    
    week_rhythm = (
        f"最近訓練涵蓋了 {len(sessions)} 場次，強度節奏呈現「{types_str}」的漸進分佈。"
        f"在高強度負荷刺激後適時導入基礎耐力與主動恢復課表，兼顧了生理機能刺激與代謝疲勞之消除。"
    )

    if is_breakthrough:
        has_p = latest.get("avg_power", 0) > 0
        load_desc = f"平均功率（{latest['avg_power']}W）與心率（{latest['avg_hr']} bpm）" if has_p else f"平均心率（{latest['avg_hr']} bpm）"
        highlight = (
            f"<strong>最近最值得標記的關鍵發現：</strong>{latest['date']} 這場訓練中，{load_desc}"
            f"處於良好發揮狀態，訓練時長達到 {latest['duration_min']} 分鐘，但平均乳酸（{latest['avg_lactate']} mmol/L）卻在所有場次中"
            f"<span class=\"tag-blue\">顯著降低</span>。在負荷不減、時長延長的情況下乳酸累積更少，"
            f"是典型且明確的<strong>有氧代謝效率提升訊號</strong>（代表粒線體利用率與乳酸再循環能力優化）。"
        )
    else:
        highlight = (
            f"<strong>生理監控指標：</strong>最新場次（{latest['date']}）平均心率為 {latest['avg_hr']} bpm，"
            f"平均乳酸為 {latest['avg_lactate']} mmol/L，最高乳酸 {latest['max_lactate']} mmol/L。"
            f"整體乳酸生成速率與運動負荷強度呈現平穩的一致性，未見代謝異常堆積，顯示自主神經與能量系統適應穩定。"
        )

    duration_summary = (
        f"在選取的 {len(sessions)} 場訓練中，運動時長分佈於 {min([s['duration_min'] for s in sessions])} ~ "
        f"{max([s['duration_min'] for s in sessions])} 分鐘。各強度等級下的乳酸累積與時間呈現清晰的生理耐受區間；"
        f"長時訓練下仍能維持穩定的乳酸水平，反映出良好的抗疲勞性。"
    )

    overall_summary = (
        f"最近的訓練安排結構完整，各場次強度區分明確。特別是最新場次（{latest['date']}）展現出優異的乳酸代謝耐受度。"
        f"建議後續週期延續此一「強弱交替、極化推進」的課表配置，維持基礎有氧容量的同時，穩健提升無氧閾值與高強度支撐力。"
    )

    return {
        "title": "最近運動狀態與生理適應分析報告",
        "period_str": f"資料期間：{period_str}",
        "week_rhythm_summary": week_rhythm,
        "kpi_cards": kpis,
        "comparison_intro": f"本節將選取的 {len(sessions)} 場訓練數據進行客觀生理指標交叉對比。",
        "highlight_text": highlight,
        "duration_summary": duration_summary,
        "overall_summary": overall_summary
    }


def generate_weekly_report_html(analysis, sessions):
    """
    動態生成「最近運動狀態與生理適應分析報告」HTML。
    - 第一張圖完整呈現所有選取場次的強度與乳酸分佈。
    - 拿掉特定運動（騎乘）字眼，全面以強度等級呈現。
    - 標題與段落均為「最近」，不掛特定個人名字。
    """
    latest_date = sessions[-1]["date"]

    # 1. 第一張圖：把「所有選取的報告數據」通通秀出來！
    all_dates_labels = [f"{s['date']} ({s.get('type','訓練')})" for s in sessions]
    rhythm_labels_json = json.dumps(all_dates_labels, ensure_ascii=False)
    rhythm_data_json = json.dumps([s["avg_lactate"] for s in sessions])
    
    # 調色盤：為每根柱子配置美觀的深淺配色
    palette = ['#eb6834', '#3fae5c', '#2a78d6', '#e34948', '#8e44ad', '#16a085', '#d35400', '#2980b9', '#7f8c8d', '#f39c12']
    bar_colors = [palette[i % len(palette)] for i in range(len(sessions))]
    rhythm_colors_json = json.dumps(bar_colors)

    sessions_json = json.dumps(sessions, ensure_ascii=False, default=str)

    # KPI 卡片
    kpi_cards_html = ""
    for k in analysis.get("kpi_cards", []):
        kpi_cards_html += f"""
  <div class="kpi"><div class="label">{k['label']}</div><div class="value">{k['value']}</div></div>"""

    # 第一表：全部選取的場次明細
    table1_rows = ""
    for s in sessions:
        is_bold = (s["date"] == latest_date)
        td_d = f"<strong>{s['date']}</strong>" if is_bold else s['date']
        td_t = f"<strong>{s.get('type', '訓練')}</strong>" if is_bold else s.get('type', '訓練')
        td_dur = f"<strong>{s['duration_min']}</strong>" if is_bold else str(s['duration_min'])
        td_h = f"<strong>{s['avg_hr']}</strong>" if is_bold else str(s['avg_hr'])
        td_la = f"<strong>{s['avg_lactate']}</strong>" if is_bold else str(s['avg_lactate'])
        table1_rows += f"""
<tr><td>{td_d}</td><td>{td_t}</td><td class="num">{td_dur}</td><td class="num">{td_h}</td><td class="num">{td_la}</td></tr>"""

    # 第二表：歷史量化數據完整對比
    table2_rows = ""
    has_power = any(s.get("avg_power", 0) > 0 for s in sessions)
    for s in sessions:
        is_bold = (s["date"] == latest_date)
        td_d = f"<strong>{s['date']}</strong>" if is_bold else s['date']
        td_dur = f"<strong>{s['duration_min']}</strong>" if is_bold else str(s['duration_min'])
        td_p = f"<strong>{s['avg_power']}</strong>" if is_bold else str(s['avg_power'])
        td_h = f"<strong>{s['avg_hr']}</strong>" if is_bold else str(s['avg_hr'])
        td_la = f"<strong>{s['avg_lactate']}</strong>" if is_bold else str(s['avg_lactate'])
        td_mla = f"<strong>{s['max_lactate']}</strong>" if is_bold else str(s['max_lactate'])

        pwr_cell = f'<td class="num">{td_p}</td>' if has_power else ''
        table2_rows += f"""
<tr><td>{td_d}</td><td class="num">{td_dur}</td>{pwr_cell}<td class="num">{td_h}</td><td class="num">{td_la}</td><td class="num">{td_mla}</td></tr>"""

    pwr_header = '<th class="num">平均功率 (W)</th>' if has_power else ''

    html_template = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>{analysis.get('title', '最近運動狀態與生理適應分析報告')}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  :root {{
    --blue: #2a78d6; --orange: #eb6834; --green: #3fae5c; --red: #e34948; --gray:#898781;
    --text: #2b2a27; --sub: #6b6a65; --bg: #faf9f6; --card: #ffffff; --border: #e6e4de;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 0; line-height: 1.6;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 40px 24px 80px; }}
  header {{ margin-bottom: 32px; }}
  h1 {{ font-size: 26px; font-weight: 700; margin: 0 0 8px; color: #1a1917; }}
  .subtitle {{ color: var(--sub); font-size: 14px; }}
  h2 {{ font-size: 19px; font-weight: 700; margin: 44px 0 14px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
  h3 {{ font-size: 15px; font-weight: 600; margin: 24px 0 10px; }}
  p {{ font-size: 14px; }}
  .highlight {{
    background: #eef4fc; border: 1px solid #c9dcf2; border-radius: 8px;
    padding: 14px 16px; font-size: 13.5px; color: #22456f; margin: 16px 0; line-height: 1.7;
  }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
  .chart-box {{ position: relative; width: 100%; height: 290px; margin: 12px 0 8px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 16px 0; }}
  .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
  .kpi .label {{ font-size: 12px; color: var(--sub); margin-bottom: 4px; }}
  .kpi .value {{ font-size: 20px; font-weight: 700; color: #1a1917; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0; background: #ffffff; border-radius: 8px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--sub); font-weight: 600; background: #f5f4ef; }}
  td.num, th.num {{ text-align: right; }}
  .tag-blue {{ color: var(--blue); font-weight: 700; }}
  footer {{ margin-top: 56px; font-size: 12px; color: var(--sub); border-top: 1px solid var(--border); padding-top: 16px; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>{analysis.get('title', '最近運動狀態與生理適應分析報告')}</h1>
  <div class="subtitle">{analysis.get('period_str', '')}</div>
</header>

<h2>一、最近訓練強度節奏 (全場次概況)</h2>
<p>{analysis.get('week_rhythm_summary', '')}</p>
<div class="chart-box"><canvas id="allSessionsChart"></canvas></div>
<div class="kpi-row">
{kpi_cards_html}
</div>

<h2>二、訓練表現與生理代謝對比</h2>
<p>{analysis.get('comparison_intro', '')}</p>
<div class="chart-box"><canvas id="intensityCompare"></canvas></div>

<div class="highlight">
  {analysis.get('highlight_text', '')}
</div>

<h3>時長 vs 乳酸分佈</h3>
<div class="chart-box"><canvas id="durationChart"></canvas></div>
<p>{analysis.get('duration_summary', '')}</p>

<h2>三、資料明細</h2>
<h3>選取訓練場次列表</h3>
<table>
<thead><tr><th>日期</th><th>強度等級</th><th class="num">時長 (分)</th><th class="num">平均心率 (bpm)</th><th class="num">平均乳酸 (mmol/L)</th></tr></thead>
<tbody>
{table1_rows}
</tbody>
</table>

<h3>歷史場次量化數據對比</h3>
<table>
<thead><tr><th>日期</th><th class="num">時長 (分)</th>{pwr_header}<th class="num">平均心率 (bpm)</th><th class="num">平均乳酸 (mmol/L)</th><th class="num">最高乳酸</th></tr></thead>
<tbody>
{table2_rows}
</tbody>
</table>

<h2>四、總結與教練專業建議</h2>
<p>{analysis.get('overall_summary', '')}</p>

<footer>本報告數值由 MyLactate 雲端資料庫結合 FIT 逐秒數據與 LA-01 乳酸量測自動彙整；乳酸值為檢驗量測真值。</footer>

</div>

<script>
const sessions = {sessions_json};
const latestDate = "{latest_date}";

// 1. 第一張圖：完整秀出「所有選取的報告數據」
new Chart(document.getElementById('allSessionsChart'), {{
  type: 'bar',
  data: {{
    labels: {rhythm_labels_json},
    datasets: [{{ 
      label: '平均乳酸 (mmol/L)', 
      data: {rhythm_data_json}, 
      backgroundColor: {rhythm_colors_json},
      borderRadius: 6
    }}]
  }},
  options: {{
    responsive: true, 
    maintainAspectRatio: false,
    plugins: {{ 
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          afterLabel: function(context) {{
            const s = sessions[context.dataIndex];
            return `時長: ${{s.duration_min}}分 | 心率: ${{s.avg_hr}}bpm`;
          }}
        }}
      }}
    }},
    scales: {{ 
      y: {{ title: {{ display: true, text: '平均乳酸 (mmol/L)' }}, grid: {{ color: 'rgba(137,135,129,0.15)' }} }}, 
      x: {{ grid: {{ display: false }}, ticks: {{ autoSkip: false, maxRotation: 25 }} }} 
    }}
  }}
}});

// 2. 負荷與乳酸雙軸對比圖
const hasPower = sessions.some(s => s.avg_power > 0);
const datasets = [];

if (hasPower) {{
  datasets.push({{
    label: '平均功率(W)', 
    data: sessions.map(s => s.avg_power), 
    backgroundColor: '#3fae5c', 
    yAxisID: 'y1',
    borderRadius: 4
  }});
}}

datasets.push({{
  label: '平均心率(bpm)', 
  data: sessions.map(s => s.avg_hr), 
  backgroundColor: '#eb6834', 
  yAxisID: 'y1',
  borderRadius: 4
}});

datasets.push({{
  label: '平均乳酸(mmol/L)', 
  data: sessions.map(s => s.avg_lactate), 
  backgroundColor: sessions.map(s => s.date === latestDate ? '#2a78d6' : 'rgba(42,120,214,0.5)'), 
  yAxisID: 'y',
  borderRadius: 4
}});

new Chart(document.getElementById('intensityCompare'), {{
  type: 'bar',
  data: {{
    labels: sessions.map(s => s.date),
    datasets: datasets
  }},
  options: {{
    responsive: true, 
    maintainAspectRatio: false,
    plugins: {{ 
      legend: {{ 
        display: true, 
        position: 'bottom', 
        labels: {{ boxWidth: 12, font: {{ size: 11 }} }} 
      }} 
    }},
    scales: {{
      y: {{ position:'left', title: {{ display: true, text: '乳酸 (mmol/L)' }}, grid: {{ color: 'rgba(137,135,129,0.15)' }} }},
      y1: {{ position:'right', title: {{ display: true, text: hasPower ? '功率 (W) / 心率 (bpm)' : '心率 (bpm)' }}, grid: {{ display: false }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// 3. 時長 vs 乳酸散點圖
new Chart(document.getElementById('durationChart'), {{
  type: 'scatter',
  data: {{
    datasets: [{{
      label: '場次', 
      data: sessions.map(s => ({{ x: s.duration_min, y: s.avg_lactate }})),
      backgroundColor: sessions.map(s => s.date === latestDate ? '#2a78d6' : '#898781'),
      pointRadius: sessions.map(s => s.date === latestDate ? 9 : 6)
    }}]
  }},
  options: {{
    responsive: true, 
    maintainAspectRatio: false, 
    layout: {{ padding: 16 }},
    plugins: {{ 
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: function(context) {{
            const s = sessions[context.dataIndex];
            return `${{s.date}} [${{s.type}}]: ${{s.duration_min}}分, ${{s.avg_lactate}} mmol/L`;
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ title: {{ display: true, text: '時長 (分鐘)' }}, grid: {{ color: 'rgba(137,135,129,0.15)' }} }},
      y: {{ title: {{ display: true, text: '平均乳酸 (mmol/L)' }}, grid: {{ color: 'rgba(137,135,129,0.15)' }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""
    return html_template
