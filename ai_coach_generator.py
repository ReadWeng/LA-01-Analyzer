# -*- coding: utf-8 -*-
"""
ai_coach_generator.py
Firebase AI Logic 驅動之「汗乳酸 (Sweat Lactate)」專業運動生理教練模組

核心原則：
1. 本系統監測為【汗乳酸 (Sweat Lactate)】，數值不能與血乳酸（2.0/4.0 mmol/L）一概而論。
2. 時間軸以實際訓練日期去扣（不一定是連續幾天，跨度可達一個月）。
3. 深入探討「相鄰場次間隔天數 (Rest Days)」、「平均功率或平均心率的高低」與「汗乳酸濃度」的對應關係。
"""

import os
import re
import json
import requests

DEFAULT_FIREBASE_KEY = "AIzaSyAhU1n_IIF7AEHXkrQCoToR3gkKe2umpuM"
DEFAULT_PROJECT_ID = "lactatecloud"


def call_firebase_ai_logic(metrics, athlete_name="選手", firebase_token=None, api_key=None):
    """
    透過 Firebase AI Logic / Gemini 生成深度汗乳酸運動生理評析與下一次訓練處方
    """
    active_key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_FIREBASE_KEY

    sessions_detail = []
    for s in metrics.get("sessions", []):
        intv_str = f"距上一場隔 {s.get('days_since_prior')} 天 ({s.get('interval_desc')})" if s.get("days_since_prior") is not None else "首場基準"
        has_la = (s.get("avg_lactate", 0) > 0 or len(s.get("lactate_readings", [])) > 0)
        
        hrv_val = s.get("hrv")
        rhr_val = s.get("resting_hr")
        readiness_val = s.get("readiness")
        
        s_dict = {
            "date": s.get("date"),
            "full_date": s.get("full_date"),
            "source": s.get("source", "manual_fit"),
            "activity_name": s.get("activity_name", ""),
            "sport": s.get("sport_display", s.get("sport", "運動")),
            "sub_sport": s.get("sub_sport", "generic"),
            "interval_since_previous": intv_str,
            "duration_min": s.get("duration_min"),
            "avg_power_W": s.get("avg_power") if s.get("avg_power", 0) > 0 else "無功率 (手錶日常)",
            "max_power_W": s.get("max_power") if s.get("max_power", 0) > 0 else "無功率",
            "avg_hr_bpm": s.get("avg_hr") if s.get("avg_hr", 0) > 0 else "無心率",
            "max_hr_bpm": s.get("max_hr") if s.get("max_hr", 0) > 0 else "無心率",
            "session_load": s.get("calculated_load", 0),
            "morning_hrv_rmssd_ms": f"{hrv_val} ms" if hrv_val else "無紀錄",
            "resting_hr_bpm": f"{rhr_val} bpm" if rhr_val else "無紀錄",
            "readiness_score": f"{readiness_val}/100" if readiness_val else "無紀錄",
            "session_type": s.get("type")
        }
        if has_la:
            s_dict["is_lactate_test"] = True
            s_dict["avg_sweat_lactate_mmol"] = s.get("avg_lactate")
            s_dict["max_sweat_lactate_mmol"] = s.get("max_lactate")
            s_dict["metabolic_efficiency"] = f"{s.get('metabolic_efficiency')} {s.get('efficiency_unit')}"
        else:
            s_dict["is_lactate_test"] = False
            s_dict["avg_sweat_lactate_mmol"] = "未採樣"
            s_dict["max_sweat_lactate_mmol"] = "未採樣"
            s_dict["metabolic_efficiency"] = "不適用"
            s_dict["analysis_instruction"] = "本場為手錶日常訓練（未採樣汗乳酸）。請僅分析其心率、功率（若有）、時長與訓練負荷；嚴禁推測、提及或硬談任何乳酸數值！"
        sessions_detail.append(s_dict)

    sport_desc = "純自行車專項 (Cycling)" if metrics.get("is_pure_cycling") else ("純跑步專項 (Running)" if metrics.get("is_pure_running") else f"跨專項綜合 (場次分佈：{metrics.get('sport_counts', {})})")

    hrv_summary = {
        "has_hrv_data": metrics.get("has_hrv_data", False),
        "hrv_baseline_rmssd_ms": metrics.get("hrv_baseline"),
        "resting_hr_baseline_bpm": metrics.get("rhr_baseline"),
        "readiness_baseline": metrics.get("readiness_baseline"),
        "latest_hrv_rmssd_ms": metrics.get("latest_hrv"),
        "hrv_delta_vs_baseline_pct": f"{'+' if (metrics.get('hrv_delta_pct') or 0) > 0 else ''}{metrics.get('hrv_delta_pct')}%" if metrics.get("hrv_delta_pct") is not None else "無基準"
    }

    long_term_adaptation = metrics.get("long_term_adaptation", {})

    prompt_context = {
        "athlete_name": athlete_name,
        "sport_discipline": sport_desc,
        "time_span": f"{metrics.get('period_start')} 至 {metrics.get('period_end')}（框選週期天數：{metrics.get('time_span_days')} 天，共 {metrics.get('session_count')} 場實際訓練）",
        "long_term_lactate_history": {
            "has_history": long_term_adaptation.get("has_long_term_history", False),
            "total_historical_tests": long_term_adaptation.get("total_historical_tests", 0),
            "historical_date_range": f"{long_term_adaptation.get('history_start_date')} 至 {long_term_adaptation.get('history_end_date')}（全歷史跨越 {long_term_adaptation.get('history_span_days', 0)} 天，約 {long_term_adaptation.get('history_span_months', 0)} 個月）",
            "early_phase_vs_recent_phase": f"早期平均乳酸 {long_term_adaptation.get('early_avg_lactate')} mmol/L（峰值 {long_term_adaptation.get('early_peak_lactate')}） vs 近期平均乳酸 {long_term_adaptation.get('recent_avg_lactate')} mmol/L（峰值 {long_term_adaptation.get('recent_peak_lactate')}）",
            "long_term_efficiency_change": f"{'+' if (long_term_adaptation.get('efficiency_change_pct') or 0) > 0 else ''}{long_term_adaptation.get('efficiency_change_pct', 0)}% ({long_term_adaptation.get('efficiency_unit', 'W/mmol')})",
            "adaptation_direction": long_term_adaptation.get("adaptation_direction"),
            "adaptation_physiological_mechanism": long_term_adaptation.get("adaptation_mechanism")
        },
        "sweat_lactate_range": f"當前週期最低 {metrics.get('min_sweat_lactate')} ~ 最高峰值 {metrics.get('peak_sweat_lactate')} mmol/L（個人基準分界：低於 {metrics.get('baseline_low')} 為低負荷，高於 {metrics.get('baseline_high')} 為高糖解負荷）",
        "metabolic_efficiency_change": f"{'+' if metrics.get('efficiency_delta_pct', 0) > 0 else ''}{metrics.get('efficiency_delta_pct', 0)}% (當期最新測驗對比當期前期測驗)",
        "autonomic_nervous_status_hrv": hrv_summary,
        "recovery_and_adaptation_state": metrics.get("recovery_state"),
        "recommended_action_guideline": metrics.get("recommended_action"),
        "training_sessions_chronological": sessions_detail
    }

    system_instruction = """你是一位國際頂尖耐力運動生理學家與穿戴式生化傳感專家，專精於【汗乳酸 (Sweat Lactate Kinetics)】與運動員週期化負荷監控。

【關鍵生理學認知與分析鐵律】
1. 嚴格注意：本數據來自【汗乳酸 (Sweat Lactate)】傳感測試，絕對不能與侵入式血乳酸（Blood Lactate，如LT1 2.0 / LT2 4.0 mmol/L）一概而論！汗乳酸數值常在 5~25+ mmol/L，必須依據該選手自身的汗乳酸動態範圍與基線進行評估。
2. 汗乳酸動態規律：連續高強度訓練會造成汗乳酸濃度顯著上升；安排低強度運動（主動排酸/低代謝負荷）能有效促進組織循環與汗腺代謝物排除。
3. 時間軸非連續性：訓練是以實際發生日期為準，可能橫跨數週或一整個月。分析時【必須深度結合各場次之間的「間隔天數（Rest Days）」】以及【平均功率或平均心率的高低與汗乳酸濃度】進行縱向對比。
4. 【未採樣汗乳酸之場次評析鐵律 (極重要，務必嚴格執行)】：
   - 本週期中包含日常手錶運動（標註未採樣乳酸之場次）：
   - 【僅討論功率、心率或負荷】：對於此類沒有乳酸採樣的日常訓練，請【僅評估其運動時長、平均心率 (bpm)、平均功率 (W，若有) 與單場訓練負荷 (Load)】，探討其在兩場測驗之間扮演的累積負荷、有氧巡航或恢復角色。
   - 【嚴禁硬談乳酸值】：未採樣乳酸的場次，【絕對不要推測、虛構、假定或提及任何乳酸數值】（例如嚴禁妄稱「推估乳酸為多少」或「乳酸為0」）！
   - 【嚴禁抱怨未採樣】：嚴禁在文字中寫出「因未採樣乳酸而無法誘導...」、「缺乏乳酸數據導致中斷...」等負面抱怨贅詞，直接客觀肯定其心率與負荷表現。
5. 【汗乳酸動力學縱向對比與全期長期代謝適應評析 (核心重中之重)】：
   - 在章節「一、汗乳酸動力學與輸出負荷對照評析 (lactate_kinetics_analysis)」中，【必須同時涵蓋兩大分析維度】：
     A. 【當期/框選場次間隔動力學】：縱向對比框選週期內的關鍵測驗，明確引用日期、間隔天數、平均功率/心率與汗乳酸數值，對比輸出代謝效率比（W/mmol 或 bpm/mmol）。
     B. 【全歷史長期乳酸趨勢與代謝適應 (Long-Term Metabolic Adaptation)】：結合提供的 `long_term_lactate_history` 數據（歷史總天數、早期 vs 近期乳酸水準、長期代謝效率變動率與適應機制），深入評析受測者從全歷史最早至最新紀錄以來，在生理代謝上是否有實質適應（例如：粒線體氧化能力提升、同等功率下乳酸收斂、糖原節省效應提升、乳酸轉折門檻右移，或是近期高負荷造成的代謝解離/累積疲勞）。
6. 【運動專項分流原則】：若受測者為特定專項（如純跑步 Running），請嚴格聚焦於跑步生理特徵（承重衝擊、配速與跑步心率漂移、跑步動態功率）。下一次處方中明確指明運動項目（sport_type 為跑步課表）。
7. 精準開出【下一次運動處方 (Next Workout Protocol)】：針對汗乳酸特性，給出具體建議間隔天數、目標時長、目標心率/功率、運動項目與階段指導。
8. 【HRV 心率變異度與自律神經恢復 × 汗乳酸交互對照鐵律 (極重要)】：
   - 整合 Intervals.icu 每日晨間 HRV (rMSSD, ms) 與靜息心率 (Resting HR, bpm) 監控數據。
   - 【高乳酸刺激後的自律神經抑制】：在高糖解、汗乳酸峰值飆高的關鍵測驗後，若隔日晨間 HRV 顯著被壓低（Suppressed HRV）且靜息心率升高，反映交感神經劇烈興奮與中樞/神經內分泌疲勞尚未修復，應在「cumulative_load_fatigue_review」中具體指出。
   - 【低負荷巡航與修整後的自律神經回彈】：若在充分間隔天數或低強度日常有氧巡航後，晨間 HRV 回彈（Rebound）超越個人基準線、靜息心率降低，表示副交感神經恢復、自律神經處於超補償準備狀態。
   - 【請在 hero_insights 或 cumulative_load_fatigue_review 中深度討論 HRV 與汗乳酸的交互狀態】。若受測者無 HRV 記錄，則客觀依據訓練時長與負荷評估，不捏造 HRV 數字。
"""

    user_prompt = f"""請根據以下受測者的汗乳酸與跨期運動負荷數據進行深度評析：
{json.dumps(prompt_context, ensure_ascii=False, indent=2)}

請直接輸出繁體中文標準 JSON 格式（不要包含 markdown 標籤）：
{{
  "report_title": "汗乳酸運動生理週期分析與下一次處方報告",
  "athlete_summary_tag": "一句極具教練震撼力與專業度的汗乳酸生理總結標籤 (15字以內)",
  "hero_insights": [
    {{"metric": "汗乳酸代謝經濟性", "value": "例如：功率-汗乳酸比提升 46%", "desc": "輸出/汗乳酸濃度對比說明"}},
    {{"metric": "自律神經與恢復狀態", "value": "例如：HRV 處於基準以上 (+8.5%)", "desc": "晨間 HRV 與副交感神經準備度"}},
    {{"metric": "長期代謝適應進展", "value": "例如：全歷史代謝經濟性提升 28.5%", "desc": "長期汗乳酸走勢與氧化適應評析"}}
  ],
  "lactate_kinetics_analysis": "深入剖析汗乳酸動力學與負荷對比的段落（280~400字）。【必須同時包含】：1. 框選週期內關鍵測驗的日期、間隔天數、平均功率/心率與汗乳酸對比；2. 融合全歷史長期乳酸趨勢（引用全歷史天數、早期 vs 近期平均乳酸與效率變化），深度評述長期以來骨骼肌粒線體氧化能力、糖原節省效應與乳酸清除率是否產生代謝適應。",
  "cumulative_load_fatigue_review": "深入評估跨期累積代謝負荷、休整節奏與 HRV 自律神經恢復狀態的段落（200~300字）。【必須明確結合 Intervals.icu 晨間 HRV (ms)、靜息心率 (bpm) 與間隔天數】，探討高汗乳酸刺激後神經系統是否處於抑制或超補償回彈，診斷疲勞累積。",
  "next_workout_prescription": {{
    "workout_code": "課表代號（如：SWEAT-FLUSH-40 或 AERO-TEMPO-50）",
    "workout_name": "具體課表名稱（如：主動排酸・低代謝壓力有氧巡航）",
    "recommended_date": "建議間隔時程（如：建議休整 48 小時後 / 次日進行）",
    "sport_type": "建議運動項目（如：低阻力單車踩踏 / 輕鬆慢跑）",
    "target_duration_min": 40,
    "target_lactate_limit": "針對汗乳酸之控制目標（例如：維持於個人低汗乳酸基準線，避免高糖解飆升）",
    "target_intensity": "目標心率 (bpm) 與功率 (W) 區解",
    "protocol_phases": [
      {{"phase": "熱身階段 (Warm-up)", "duration": "10 分鐘", "intensity": "低心率漸進啟動", "focus": "促進周邊微血管舒張，喚醒汗腺分泌，避免急性糖解"}},
      {{"phase": "主課表 (Main Set)", "duration": "20-25 分鐘", "intensity": "目標穩態區間", "focus": "維持平穩配速/踩踏，加速肌群氧化循環與代謝物清除"}},
      {{"phase": "緩和與排酸 (Cool-down)", "duration": "10 分鐘", "intensity": "極低阻力/極慢跑", "focus": "協助循環回流，運動後補充水分與電解質"}}
    ],
    "physiological_rationale": "為什麼開立這堂課？給予汗乳酸代謝與運動生理學理論支持（100~150字）"
  }},
  "coach_pro_tips": "教練對運動員下一階段訓練間隔天數安排、排汗補水策略與生活恢復的具體叮嚀（100字左右）"
}}
"""

    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json"}
    if firebase_token:
        headers["Authorization"] = f"Bearer {firebase_token}"

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={active_key}"
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.35,
                "responseMimeType": "application/json"
            }
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                raw_text = re.sub(r'\s*```$', '', raw_text)
                parsed_json = json.loads(raw_text)
                print(f"成功透過模型 {model_name} 生成汗乳酸運動生理學分析！")
                return parsed_json
        except Exception as e:
            pass

    # 啟用高階汗乳酸動態運算備援引擎
    return generate_dynamic_sweat_lactate_fallback(metrics, athlete_name)


def generate_dynamic_sweat_lactate_fallback(metrics, athlete_name):
    """
    動態汗乳酸運動生理學備援引擎：
    嚴格引用具體訓練日期、間隔天數、心率功率與汗乳酸濃度，產出扎實的專業講評。
    """
    sessions = metrics.get("sessions", [])
    latest = sessions[-1] if sessions else {}
    eff_delta = metrics.get("efficiency_delta_pct", 0)
    time_span = metrics.get("time_span_days", 14)
    peak_la = metrics.get("peak_sweat_lactate", 0)
    min_la = metrics.get("min_sweat_lactate", 0)
    base_low = metrics.get("baseline_low", 6.0)
    base_high = metrics.get("baseline_high", 15.0)
    rec_state = metrics.get("recovery_state", "")
    days_since_prior = latest.get("days_since_prior", 2.0)

    # 嚴格分流：有採樣汗乳酸之關鍵測驗 vs 未採樣汗乳酸之手錶日常運動
    la_sessions = [s for s in sessions if (s.get('avg_lactate', 0) > 0 or len(s.get('lactate_readings', [])) > 0)]
    daily_sessions = [s for s in sessions if not (s.get('avg_lactate', 0) > 0 or len(s.get('lactate_readings', [])) > 0)]
    has_pwr = any(s.get('avg_power', 0) > 0 for s in la_sessions)

    # 提取長期適應分析
    long_term_ada = metrics.get("long_term_adaptation", {})
    long_term_summary = ""
    if long_term_ada.get("has_long_term_history"):
        long_term_summary = (
            f" 此外，拓展至全歷史長期趨勢分析（自 {long_term_ada.get('history_start_date')} 至 {long_term_ada.get('history_end_date')}，"
            f"跨越 {long_term_ada.get('history_span_days')} 天，共收錄 {long_term_ada.get('total_historical_tests')} 場含汗乳酸測驗）："
            f"早期階段平均汗乳酸為 {long_term_ada.get('early_avg_lactate')} mmol/L（峰值 {long_term_ada.get('early_peak_lactate')} mmol/L），"
            f"近期階段平均汗乳酸為 {long_term_ada.get('recent_avg_lactate')} mmol/L（峰值 {long_term_ada.get('recent_peak_lactate')} mmol/L），"
            f"全期代謝經濟性長期演變率達 {long_term_ada.get('efficiency_change_pct', 0.0):+0.1f}%（{long_term_ada.get('adaptation_direction')}）。"
            f"生理學判定：{long_term_ada.get('adaptation_mechanism')}"
        )

    # 1. 撰寫汗乳酸動力學核心段落 (融合當期橫向動力學與全歷史長期代謝適應)
    if len(la_sessions) >= 2:
        s_prev_la = la_sessions[-2]
        s_curr_la = la_sessions[-1]
        diff_days = s_curr_la.get('days_since_prior', 1.0)
        intv_txt = f"（距前次測驗隔 {diff_days} 天）" if diff_days else ""
        
        has_test_pwr = (s_prev_la.get('avg_power', 0) > 0 and s_curr_la.get('avg_power', 0) > 0)
        if has_test_pwr:
            eff_prev = s_prev_la.get('metabolic_efficiency')
            eff_curr = s_curr_la.get('metabolic_efficiency')
            kinetics_text = (
                f"本次分析橫跨 {time_span} 天的實際訓練歷程，聚焦於【關鍵汗乳酸測驗場次】的縱向動力學對照：在 {s_prev_la.get('date')} 的測驗中，"
                f"平均功率為 {s_prev_la.get('avg_power')} W（心率 {s_prev_la.get('avg_hr')} bpm），平均汗乳酸為 {s_prev_la.get('avg_lactate')} mmol/L；"
                f"而在 {s_curr_la.get('date')} 的最新測驗中{intv_txt}，平均功率為 {s_curr_la.get('avg_power')} W（心率 {s_curr_la.get('avg_hr')} bpm），"
                f"平均汗乳酸為 {s_curr_la.get('avg_lactate')} mmol/L（峰值 {s_curr_la.get('max_lactate')} mmol/L）。"
                f"輸出代謝效率比由 {eff_prev} 變動至 {eff_curr} {s_curr_la.get('efficiency_unit', 'W/mmol')}（變動率 {eff_delta:+0.1f}%）。"
                f"汗乳酸數值反映出受測者在高強度輸出下的代謝產酸與排除平衡，體現出局部微循環與肌肉有氧氧化適應狀態。{long_term_summary}"
            )
        else:
            eff_prev = s_prev_la.get('metabolic_efficiency')
            eff_curr = s_curr_la.get('metabolic_efficiency')
            kinetics_text = (
                f"本次分析橫跨 {time_span} 天的實際訓練歷程，以【關鍵汗乳酸測驗之平均心率縱向對照】為核心：在 {s_prev_la.get('date')} 的測驗中，"
                f"平均心率為 {s_prev_la.get('avg_hr')} bpm，平均汗乳酸為 {s_prev_la.get('avg_lactate')} mmol/L；"
                f"而在 {s_curr_la.get('date')} 的最新測驗中{intv_txt}，平均心率為 {s_curr_la.get('avg_hr')} bpm，"
                f"平均汗乳酸為 {s_curr_la.get('avg_lactate')} mmol/L，"
                f"心率代謝效率比由 {eff_prev} 變動至 {eff_curr} {s_curr_la.get('efficiency_unit', 'bpm/mmol')}（變動率 {eff_delta:+0.1f}%）。"
                f"汗乳酸走勢體現出該受測者在此心肺負荷區間的排汗代謝排酸與疲勞耐受特性。{long_term_summary}"
            )
    elif len(la_sessions) == 1:
        s_single = la_sessions[0]
        kinetics_text = (
            f"本次分析涵蓋 {time_span} 天的歷程。在關鍵測驗場次（{s_single.get('date')}）中，"
            f"運動員於時長 {s_single.get('duration_min')} 分鐘、心率 {s_single.get('avg_hr')} bpm 下，"
            f"測得平均汗乳酸為 {s_single.get('avg_lactate')} mmol/L（峰值 {s_single.get('max_lactate')} mmol/L），代謝效率比為 {s_single.get('metabolic_efficiency')} {s_single.get('efficiency_unit', '')}。"
            f"汗乳酸動態反映出此強度下的基本氧化代謝反應。{long_term_summary}"
        )
    else:
        kinetics_text = f"目前週期內查無足夠之汗乳酸採樣測驗數據，主要為常態日常運動負荷紀錄。{long_term_summary}"

    # 2. 撰寫累積負荷與日常手錶運動評析段落 (未採樣日常運動僅討論心率、功率與負荷，絕不硬談乳酸)
    daily_desc = ""
    if daily_sessions:
        daily_items = [
            f"{d.get('date')}（時長 {d.get('duration_min')} 分，平均心率 {d.get('avg_hr')} bpm，單場負荷 {d.get('calculated_load')}）"
            for d in daily_sessions
        ]
        daily_desc = f" 在測驗間隔期間，受測者進行了手錶日常運動：{'、'.join(daily_items)}；此類日常運動未採樣汗乳酸，僅就其心率與負荷進行客觀評估，真實反映了兩場測驗之間的疲勞累積與有氧巡航支撐。"

    hrv_txt = ""
    if metrics.get("has_hrv_data"):
        h_base = metrics.get("hrv_baseline")
        r_base = metrics.get("rhr_baseline")
        l_hrv = metrics.get("latest_hrv")
        h_delta = metrics.get("hrv_delta_pct")
        delta_str = f"{h_delta:+0.1f}%" if h_delta is not None else "穩定"
        hrv_txt = f" 同期 Intervals.icu 晨間自律神經監控顯示：週期 HRV 基準線為 {h_base} ms（靜息心率 {r_base} bpm），最新晨間 HRV 為 {l_hrv} ms（相對基準變動 {delta_str}）；反映出受測者副交感神經在汗乳酸負荷與日常訓練交替下的修復能力。"

    load_review_text = (
        f"在過去 {time_span} 天的實際紀錄中，共涵蓋 {len(sessions)} 場訓練（包含 {len(la_sessions)} 場含汗乳酸關鍵測驗與 {len(daily_sessions)} 場日常背景運動），總時長 {metrics.get('total_hours')} 小時。"
        f"在含乳酸測驗中，汗乳酸動態範圍介於 {min_la} 至 {peak_la} mmol/L 之間（個人基準：低負荷 <= {base_low}，高糖解 >= {base_high} mmol/L）。"
        f"{daily_desc}"
        f"{hrv_txt}"
        f" 整體生理狀態判定為【{rec_state}】。"
    )

    # 開立下一次運動處方
    if "高代謝累積疲勞" in rec_state or (days_since_prior is not None and days_since_prior <= 1.0 and latest.get('avg_lactate', 0) > base_high):
        rx = {
            "workout_code": "SWEAT-FLUSH-40",
            "workout_name": "主動排酸・超低代謝壓力巡航修復",
            "recommended_date": "建議於間隔休整 24~48 小時後進行",
            "sport_type": "低阻力單車輕鬆踩踏 或 極輕鬆慢跑",
            "target_duration_min": 40,
            "target_lactate_limit": f"控制於個人低汗乳酸區間（目標 <= {base_low} mmol/L，避免高糖解飆升）",
            "target_intensity": "心率控制於 110 ~ 125 bpm" + (f"，功率維持於 {int(latest.get('avg_power', 180)*0.65)} ~ {int(latest.get('avg_power', 180)*0.72)} W" if has_pwr else "（依心率區間監控，不需功率計）"),
            "protocol_phases": [
                {"phase": "熱身階段 (Warm-up)", "duration": "10 分鐘", "intensity": "心率 < 115 bpm 漸進熱身", "focus": "促進血液循環與微血管舒張，喚醒汗腺溫和排泄，嚴格避免任何酸痛感"},
                {"phase": "主課表 (Main Set)", "duration": "20 分鐘", "intensity": "維持 Zone 1-2 穩定巡航", "focus": "維持高迴轉速/輕步伐，利用慢肌與心肌氧化排除殘留代謝物，降低汗乳酸堆積"},
                {"phase": "緩和與排酸 (Cool-down)", "duration": "10 分鐘", "intensity": "極低阻力冷卻", "focus": "協助下肢靜脈回流，運動後即刻補充含電解質水份"}
            ],
            "physiological_rationale": "汗乳酸同樣具備低強度運動有助排除的特性。在密集或高強度訓練後，維持超低強度運動可增加骨骼肌與汗腺血流量，比完全靜態臥床休息更能有效加速局部殘存乳酸的轉運代謝。"
        }
    else:
        rx = {
            "workout_code": "AERO-CAP-50",
            "workout_name": "有氧容量穩態拓展・汗乳酸穩態巡航",
            "recommended_date": "建議於間隔 24~48 小時後執行",
            "sport_type": "專項耐力訓練（單車騎乘或節奏跑）",
            "target_duration_min": 50,
            "target_lactate_limit": f"維持於個人穩定區間（約 {base_low} ~ {base_high} mmol/L，維持平穩不漂移）",
            "target_intensity": "心率維持於 135 ~ 148 bpm" + (f"，功率維持於 {int(latest.get('avg_power', 190)*0.82)} ~ {int(latest.get('avg_power', 190)*0.90)} W" if has_pwr else "（依心率區間控制，無需功率計）"),
            "protocol_phases": [
                {"phase": "熱身階段 (Warm-up)", "duration": "12 分鐘", "intensity": "Zone 1 漸進至 Zone 2", "focus": "核心體溫漸進上升，確保心率上升與排汗節奏平順"},
                {"phase": "主課表 (Main Set)", "duration": "28 分鐘", "intensity": "目標心率配速穩態", "focus": "維持穩定節奏，在此負荷下刺激粒線體有氧呼吸，監控汗乳酸平穩度"},
                {"phase": "緩和與排酸 (Cool-down)", "duration": "10 分鐘", "intensity": "Zone 1 慢速恢復", "focus": "舒緩肌肉張力，引導心率緩和回落"}
            ],
            "physiological_rationale": "運動員當前代謝經濟性良好，汗乳酸在輸出刺激下呈現良好收斂。此時安排個人中等穩態訓練，能進一步加固慢肌纖維的粒線體氧化能力，擴展有氧平台。"
        }

    fallback_insights = [
        {
            "metric": "輸出-汗乳酸代謝經濟性" if has_pwr else "心率-汗乳酸代謝經濟性",
            "value": f"{eff_delta:+0.1f}%",
            "desc": "最新關鍵測驗 vs 前期基準"
        }
    ]
    if metrics.get("has_hrv_data"):
        h_delta = metrics.get("hrv_delta_pct")
        delta_str = f"{h_delta:+0.1f}%" if h_delta is not None else "持平"
        fallback_insights.append({
            "metric": "自律神經恢復 (HRV)",
            "value": f"{metrics.get('latest_hrv')} ms ({delta_str})",
            "desc": f"基準 {metrics.get('hrv_baseline')} ms / 靜息心率 {metrics.get('rhr_baseline')} bpm"
        })
    else:
        fallback_insights.append({
            "metric": "週期訓練與休整節奏",
            "value": f"平均每 {round(time_span / max(1, len(sessions)), 1)} 天一場",
            "desc": f"跨期 {time_span} 天共 {len(sessions)} 場"
        })
    fallback_insights.append({
        "metric": "當前代謝適應狀態",
        "value": rec_state.split(' ')[0] if ' ' in rec_state else rec_state,
        "desc": "生理系統準備狀態"
    })

    return {
        "report_title": "汗乳酸運動生理週期分析與下一次處方報告",
        "athlete_summary_tag": "汗乳酸代謝經濟性良好" if eff_delta > 0 else "汗乳酸負荷調整中",
        "hero_insights": fallback_insights,
        "lactate_kinetics_analysis": kinetics_text,
        "cumulative_load_fatigue_review": load_review_text,
        "next_workout_prescription": rx,
        "coach_pro_tips": "汗乳酸測試受排汗速率與環境溫濕度影響，運動前 2 小時請確保補足 500ml 水份。訓練後建議補充水份與鈉、鉀等電解質，幫助汗腺組織機能恢復與全身代謝平衡。"
    }
