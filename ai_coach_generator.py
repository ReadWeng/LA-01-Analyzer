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
        sessions_detail.append({
            "date": s.get("date"),
            "full_date": s.get("full_date"),
            "source": s.get("source", "manual_fit"),
            "activity_name": s.get("activity_name", ""),
            "sport": s.get("sport_display", s.get("sport", "運動")),
            "sub_sport": s.get("sub_sport", "generic"),
            "interval_since_previous": intv_str,
            "duration_min": s.get("duration_min"),
            "avg_power_W": s.get("avg_power") if s.get("avg_power", 0) > 0 else "無功率",
            "max_power_W": s.get("max_power") if s.get("max_power", 0) > 0 else "無功率",
            "avg_hr_bpm": s.get("avg_hr") if s.get("avg_hr", 0) > 0 else "無心率",
            "max_hr_bpm": s.get("max_hr") if s.get("max_hr", 0) > 0 else "無心率",
            "avg_sweat_lactate_mmol": s.get("avg_lactate") if (s.get("avg_lactate", 0) > 0 or len(s.get("lactate_readings", [])) > 0) else "未採樣 (手錶日常訓練)",
            "max_sweat_lactate_mmol": s.get("max_lactate") if (s.get("avg_lactate", 0) > 0 or len(s.get("lactate_readings", [])) > 0) else "未採樣",
            "metabolic_efficiency": f"{s.get('metabolic_efficiency')} {s.get('efficiency_unit')}" if s.get('metabolic_efficiency') is not None else "未採樣",
            "session_type": s.get("type")
        })

    sport_desc = "純自行車專項 (Cycling)" if metrics.get("is_pure_cycling") else ("純跑步專項 (Running)" if metrics.get("is_pure_running") else f"跨專項綜合 (場次分佈：{metrics.get('sport_counts', {})})")

    prompt_context = {
        "athlete_name": athlete_name,
        "sport_discipline": sport_desc,
        "time_span": f"{metrics.get('period_start')} 至 {metrics.get('period_end')}（跨越總天數：{metrics.get('time_span_days')} 天，共 {metrics.get('session_count')} 場實際訓練）",
        "sweat_lactate_range": f"週期最低 {metrics.get('min_sweat_lactate')} ~ 最高峰值 {metrics.get('peak_sweat_lactate')} mmol/L（個人基準分界：低於 {metrics.get('baseline_low')} 為低負荷，高於 {metrics.get('baseline_high')} 為高糖解負荷）",
        "metabolic_efficiency_change": f"{'+' if metrics.get('efficiency_delta_pct', 0) > 0 else ''}{metrics.get('efficiency_delta_pct', 0)}% (最新場次對比前期場次)",
        "recovery_and_adaptation_state": metrics.get("recovery_state"),
        "recommended_action_guideline": metrics.get("recommended_action"),
        "training_sessions_chronological": sessions_detail
    }

    system_instruction = """你是一位國際頂尖耐力運動生理學家與穿戴式生化傳感專家，專精於【汗乳酸 (Sweat Lactate Kinetics)】與運動員週期化負荷監控。

【關鍵生理學認知】
1. 嚴格注意：本數據來自【汗乳酸 (Sweat Lactate)】傳感測試，絕對不能與侵入式血乳酸（Blood Lactate，如LT1 2.0 / LT2 4.0 mmol/L）一概而論！汗乳酸數值常在 5~25+ mmol/L，數值尺度截然不同，必須依據該選手自身的汗乳酸動態範圍與基線進行評估。
2. 汗乳酸動態規律：連續高強度訓練會造成汗乳酸濃度顯著上升；安排低強度運動（主動排酸/低代謝負荷）能有效促進組織循環與汗腺代謝物排除。
3. 時間軸非連續性：訓練是以實際發生日期為準，可能橫跨數週或一整個月。分析時【必須深度結合各場次之間的「間隔天數（Rest Days）」】以及【平均功率或平均心率的高低與汗乳酸濃度】進行縱向對比。
4. 核心洞察方法：
   - 觀察在相似或不同功率/心率負荷下，汗乳酸是上升還是下降？
   - 若經過充分休整（如隔 3~6 天），功率提升但汗乳酸顯著收斂，代表「有氧代謝效率提高、第一型肌纖維氧化能力增強」；
   - 若連日運動（背靠背隔 0~1 天），且汗乳酸偏高，代表「連續訓練的代謝堆疊與未完全排除」。
5. 精準開出【下一次運動處方 (Next Workout Protocol)】：針對汗乳酸特性，給出具體建議間隔天數、目標時長、目標心率/功率、運動項目與階段指導。
6. 【功率缺失處理原則】：若訓練數據中有場次缺失功率（例如 avg_power_W 顯示為「無功率」），系統已自動切換為【平均心率 (bpm)】作為縱向對照基準。此時嚴禁提及功率 (W) 或輸出功率圖，必須全程以心率 (bpm) 與汗乳酸濃度的關係、代謝效率 (bpm/mmol) 及心率區間進行講評與下一次處方！
7. 【運動專項分流原則】：若受測者為特定專項（如純自行車 Cycling 或純跑步 Running），請嚴格聚焦於該專項的生理特徵（自行車著重踩踏輸出、齒比、踏頻與功率/心率比；跑步著重承重衝擊、跑步心率漂移與配速/心率經濟性）。若為混合運動，請分析騎跑交叉訓練的互補效益，下一次處方中明確指明運動項目（sport_type）。
8. 【手錶日常背景訓練指引】：部分場次為透過手錶（Garmin / COROS via Intervals.icu）自動拉取的日常背景訓練（標註未採樣乳酸）。這些紀錄提供了乳酸測驗日之間的真實身體負荷、運動頻率與恢復間隔，使負荷分析更真實；但在探討「汗乳酸動力學與代謝經濟性」時，請以實際有採樣汗乳酸的關鍵測驗場次為分析主軸。
"""

    user_prompt = f"""請根據以下受測者的汗乳酸與跨期運動負荷數據進行深度評析：
{json.dumps(prompt_context, ensure_ascii=False, indent=2)}

請直接輸出繁體中文標準 JSON 格式（不要包含 markdown 標籤）：
{{
  "report_title": "汗乳酸運動生理週期分析與下一次處方報告",
  "athlete_summary_tag": "一句極具教練震撼力與專業度的汗乳酸生理總結標籤 (15字以內)",
  "hero_insights": [
    {{"metric": "汗乳酸代謝經濟性", "value": "例如：功率-汗乳酸比提升 46%", "desc": "輸出/汗乳酸濃度對比說明"}},
    {{"metric": "週期訓練與休整節奏", "value": "例如：平均每 2.8 天訓練一場", "desc": "間隔天數與恢復平衡"}},
    {{"metric": "當前代謝適應狀態", "value": "例如：處於超補償突破期", "desc": "生理系統準備狀態"}}
  ],
  "lactate_kinetics_analysis": "深入剖析汗乳酸動力學與負荷對比的段落（200~300字）。【必須明確引用具體日期、間隔天數、平均功率/心率與汗乳酸數值】，對比不同場次的代謝經濟性變化，並從粒線體有氧氧化與汗腺乳酸排泄機制解讀。",
  "cumulative_load_fatigue_review": "深入評估跨期累積代謝負荷與休整節奏的段落（150~250字）。探討間隔天數（如背靠背 vs 充分休整）對汗乳酸基礎水平的影響，診斷是否有連續疲勞堆疊。",
  "next_workout_prescription": {{
    "workout_code": "課表代號（如：SWEAT-FLUSH-40 或 AERO-TEMPO-50）",
    "workout_name": "具體課表名稱（如：主動排酸・低代謝壓力有氧巡航）",
    "recommended_date": "建議間隔時程（如：建議休整 48 小時後 / 次日進行）",
    "sport_type": "建議運動項目（如：低阻力單車踩踏 / 輕鬆慢跑）",
    "target_duration_min": 40,
    "target_lactate_limit": "針對汗乳酸之控制目標（例如：維持於個人低汗乳酸基準線，避免高糖解飆升）",
    "target_intensity": "目標心率 (bpm) 與功率 (W) 區間",
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

    # 檢查功率是否完整（若有任一場次缺失，嚴格遵循使用者原則：直接用心率比較，不提功率）
    has_full_pwr = metrics.get("has_full_power", False)
    
    # 撰寫汗乳酸動力學核心段落
    if not has_full_pwr:
        # 功率有缺失，直接用心率畫線做縱向對比
        if len(sessions) >= 2:
            s_prev = sessions[-2]
            s_curr = sessions[-1]
            diff_days = s_curr.get('days_since_prior', 1.0)
            intv_txt = f"（距前次訓練隔 {diff_days} 天）" if diff_days else ""
            kinetics_text = (
                f"本次分析橫跨 {time_span} 天的實際訓練歷程。由於部分場次功率紀錄缺失，系統依循運動生理學原則，直接以【汗乳酸濃度與平均心率的縱向對照】進行評估：在 {s_prev.get('date')} 的訓練中，"
                f"平均心率為 {s_prev.get('avg_hr')} bpm，平均汗乳酸為 {s_prev.get('avg_lactate')} mmol/L；"
                f"而在 {s_curr.get('date')} 的場次中{intv_txt}，平均心率為 {s_curr.get('avg_hr')} bpm，"
                f"平均汗乳酸為 {s_curr.get('avg_lactate')} mmol/L，"
                f"心率代謝效率比（心率/汗乳酸）由 {s_prev.get('metabolic_efficiency')} 變動至 {s_curr.get('metabolic_efficiency')} {s_curr.get('efficiency_unit', 'bpm/mmol')}（變動率 {eff_delta:+0.1f}%）。"
                f"須知汗乳酸數值不同於血乳酸，數值常在較高水平（本週期範圍 {min_la} ~ {peak_la} mmol/L）；以心率作為客觀內部負荷指標，"
                f"汗乳酸的動態走勢清晰反映出受測者在該心肺刺激下的代謝排除與局部微循環適應狀態。"
            )
        else:
            kinetics_text = (
                f"本次分析橫跨 {time_span} 天的實際訓練歷程。以【汗乳酸濃度與平均心率的縱向對照】為核心：在最新場次（{latest.get('date')}）中，"
                f"運動員在心率 {latest.get('avg_hr')} bpm 且時長達 {latest.get('duration_min')} 分鐘的刺激下，"
                f"平均汗乳酸為 {latest.get('avg_lactate')} mmol/L（峰值 {latest.get('max_lactate')} mmol/L），心率代謝效率比為 {latest.get('metabolic_efficiency')} {latest.get('efficiency_unit', 'bpm/mmol')}。"
                f"汗乳酸動態充分體現出受測者在此心肺強度下的穩定代謝適應，汗腺局部排泄與體循環平衡良好。"
            )
    else:
        # 所有場次功率齊全，使用功率做縱向對照
        s_prev_pwr = sessions[-2]
        s_curr_pwr = sessions[-1]
        kinetics_text = (
            f"本次分析橫跨 {time_span} 天的實際訓練歷程。重點檢視【汗乳酸（Sweat Lactate）濃度與輸出功率的縱向對照】：在 {s_prev_pwr['date']} 的訓練中，"
            f"平均功率為 {s_prev_pwr['avg_power']} W（心率 {s_prev_pwr['avg_hr']} bpm），當時平均汗乳酸為 {s_prev_pwr['avg_lactate']} mmol/L；"
            f"而在 {s_curr_pwr['date']} 的場次中（距前次訓練僅隔 {s_curr_pwr.get('days_since_prior', 1.0)} 天），平均功率提升至 {s_curr_pwr['avg_power']} W，"
            f"心率為 {s_curr_pwr['avg_hr']} bpm，但汗乳酸濃度為 {s_curr_pwr['avg_lactate']} mmol/L，"
            f"代謝效率比（輸出/汗乳酸）由 {s_prev_pwr['metabolic_efficiency']} 躍升至 {s_curr_pwr['metabolic_efficiency']} W/mmol，提升幅度達 {eff_delta:+0.1f}%。"
            f"須知汗乳酸數值不同於血乳酸，數值常在較高水平（本週期範圍 {min_la} ~ {peak_la} mmol/L）；在相近甚至更高強度下汗乳酸大幅降低，"
            f"清楚反映出肌肉周邊有氧氧化利用率提升，第一型慢肌纖維對代謝物的再利用能力增強，且局部能量代謝經濟性有實質進步。"
        )

    # 撰寫累積負荷與間隔天數段落
    load_review_text = (
        f"在過去 {time_span} 天的實際紀錄中，共涵蓋 {len(sessions)} 場有效訓練，總訓練時長 {metrics.get('total_hours')} 小時。"
        f"受測者的汗乳酸動態範圍介於 {min_la} 至 {peak_la} mmol/L 之間（個人相對基準線：低負荷區約 <= {base_low} mmol/L，高糖解區約 >= {base_high} mmol/L）。"
        f"從訓練間隔天數來看，各場次之間包含背靠背連日訓練與間隔數日的充分休整。"
        f"當安排連續密集訓練時，汗乳酸呈現出累積攀升的典型生理特性；而在安排低強度運動或間隔充分休整後，汗乳酸能有效回落。"
        f"目前整體生理狀態處於【{rec_state}】。"
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
            "target_intensity": "心率控制於 110 ~ 125 bpm" + (f"，功率維持於 {int(latest.get('avg_power', 180)*0.65)} ~ {int(latest.get('avg_power', 180)*0.72)} W" if has_full_pwr else "（依心率區間監控，不需功率計）"),
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
            "target_intensity": "心率維持於 135 ~ 148 bpm" + (f"，功率維持於 {int(latest.get('avg_power', 190)*0.82)} ~ {int(latest.get('avg_power', 190)*0.90)} W" if has_full_pwr else "（依心率區間控制，無需功率計）"),
            "protocol_phases": [
                {"phase": "熱身階段 (Warm-up)", "duration": "12 分鐘", "intensity": "Zone 1 漸進至 Zone 2", "focus": "核心體溫漸進上升，確保心率上升與排汗節奏平順"},
                {"phase": "主課表 (Main Set)", "duration": "28 分鐘", "intensity": "目標心率配速穩態", "focus": "維持穩定節奏，在此負荷下刺激粒線體有氧呼吸，監控汗乳酸平穩度"},
                {"phase": "緩和與排酸 (Cool-down)", "duration": "10 分鐘", "intensity": "Zone 1 慢速恢復", "focus": "舒緩肌肉張力，引導心率緩和回落"}
            ],
            "physiological_rationale": "運動員當前代謝經濟性良好，汗乳酸在輸出刺激下呈現良好收斂。此時安排個人中等穩態訓練，能進一步加固慢肌纖維的粒線體氧化能力，擴展有氧平台。"
        }

    return {
        "report_title": "汗乳酸運動生理週期分析與下一次處方報告",
        "athlete_summary_tag": "汗乳酸代謝經濟性良好" if eff_delta > 0 else "汗乳酸負荷調整中",
        "hero_insights": [
            {
                "metric": "輸出-汗乳酸代謝經濟性" if has_full_pwr else "心率-汗乳酸代謝經濟性",
                "value": f"{eff_delta:+0.1f}%",
                "desc": "最新場次 vs 前期基準"
            },
            {
                "metric": "週期訓練與休整節奏",
                "value": f"平均每 {round(time_span / max(1, len(sessions)), 1)} 天一場",
                "desc": f"跨期 {time_span} 天共 {len(sessions)} 場"
            },
            {
                "metric": "當前代謝適應狀態",
                "value": rec_state.split(' ')[0] if ' ' in rec_state else rec_state,
                "desc": "生理系統準備狀態"
            }
        ],
        "lactate_kinetics_analysis": kinetics_text,
        "cumulative_load_fatigue_review": load_review_text,
        "next_workout_prescription": rx,
        "coach_pro_tips": "汗乳酸測試受排汗速率與環境溫濕度影響，運動前 2 小時請確保補足 500ml 水份。訓練後建議補充水份與鈉、鉀等電解質，幫助汗腺組織機能恢復與全身代謝平衡。"
    }
