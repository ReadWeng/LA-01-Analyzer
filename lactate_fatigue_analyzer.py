# -*- coding: utf-8 -*-
"""
lactate_fatigue_analyzer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
基於運動生理學頂級文獻之穿戴式汗乳酸 / 血乳酸疲勞動力學分析模組：
- Okawara et al. (2022) Physiological Reports: Kinetic changes in sweat lactate following fatigue during constant workload exercise (曲線左移 / 反應提前).
- Takemoto et al. (2026) Fatigue: A novel fatigue monitoring system using sweat lactate (sLT 時間與功率左移，與 48h 殘餘疲勞中度相關 r=0.64).

核心生理學鐵律：
1. 看曲線位置與提前反應，不看單點絕對濃度 (動態左移/提前為疲勞核心訊號).
2. 同人、同基準比較：與個人近五期標準化基準比對，超過 MDC95 (最小可偵測變化量) 才判定為真變化.
3. 嚴謹證據邊界：定位為「急性代謝疲勞趨勢（候選訊號）」，給予「狀態 + 原因 + 建議處方」.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


def analyze_lactate_fatigue(
    df_top5: pd.DataFrame,
    dates_chrono: List[str],
    user_mdc_pct: float = 12.0,
    min_mdc_abs: float = 0.25
) -> Dict[str, Any]:
    """
    分析近五期乳酸數據並生成基於運動生理學模型的評估結果與系統建議評語。

    :param df_top5: 包含最近五期資料之 DataFrame (欄位需包含 'date_str', 'lactate_mmol', 可含 '測試點順序')
    :param dates_chrono: 按時間先後排序的日期列表 (最早在前，最新在後)
    :param user_mdc_pct: 最小可偵測變化百分比閾值 (預設 12.0%)
    :param min_mdc_abs: 最小可偵測絕對濃度差 (預設 0.25 mmol/L)
    :return: 結構化分析結果字典
    """
    if not dates_chrono or df_top5.empty:
        return {
            "status": "NO_DATA",
            "badge": "ℹ️ 查無歷史乳酸數據",
            "latest_date": "",
            "latest_mean": 0.0,
            "prev_mean": 0.0,
            "diff": 0.0,
            "diff_pct": 0.0,
            "mdc_threshold": min_mdc_abs,
            "physio_mechanism": "目前尚無足夠的乳酸紀錄可供分析。",
            "training_prescription": "請於完成運動或乳酸檢測後記錄數據。",
            "full_advice_markdown": "尚無乳酸數據。",
            "ui_box_type": "info"
        }

    latest_date = dates_chrono[-1]
    prev_dates = dates_chrono[:-1]

    latest_rows = df_top5[df_top5['date_str'] == latest_date]
    latest_vals = latest_rows['lactate_mmol'].dropna().tolist()
    latest_mean = float(np.mean(latest_vals)) if latest_vals else 0.0

    # 1. 僅有 1 期數據：建立基準階段
    if not prev_dates:
        return {
            "status": "INSUFFICIENT_BASELINE",
            "badge": "ℹ️ 個人基準建立中（第 1 期）",
            "latest_date": latest_date,
            "latest_mean": latest_mean,
            "prev_mean": 0.0,
            "diff": 0.0,
            "diff_pct": 0.0,
            "mdc_threshold": min_mdc_abs,
            "physio_mechanism": (
                f"目前僅累積 1 期歷史紀錄（{latest_date}），平均乳酸為 {latest_mean:.2f} mmol/L。"
                "依據運動生理學疲勞監測規範（Takemoto et al. 2026），乳酸動態位移需具備至少 2 期以上"
                "之同人歷史基準，方能計算個體最小可偵測變化量（MDC₉₅）與動力學位移。"
            ),
            "training_prescription": (
                "請持續在後續常規訓練或測驗中記錄乳酸數據。待累積第 2 期以上紀錄後，"
                "系統將自動啟用「動態左移／右移疲勞動力學監測」，提供專屬運動處方與恢復建議。"
            ),
            "full_advice_markdown": (
                f"ℹ️ **個人基準建立中：** 目前僅有 1 期歷史紀錄（{latest_date}，平均 **{latest_mean:.2f} mmol/L**）。"
                "待累積第 2 期以上紀錄後，系統將自動啟動近五期乳酸動態左右移對比與訓練調整建議。"
            ),
            "ui_box_type": "info"
        }

    # 2. 歷史期數 >= 2 期，進行多點與整體動力學位移分析
    prev_rows = df_top5[df_top5['date_str'].isin(prev_dates)]
    prev_vals = prev_rows['lactate_mmol'].dropna().tolist()
    prev_mean = float(np.mean(prev_vals)) if prev_vals else 0.0

    diff = latest_mean - prev_mean
    diff_pct = (diff / prev_mean * 100.0) if prev_mean > 0 else 0.0

    # 計算歷史基準波動與 MDC95 (Minimal Detectable Change with 95% confidence)
    prev_session_means = prev_rows.groupby('date_str')['lactate_mmol'].mean()
    sd_baseline = float(prev_session_means.std(ddof=1)) if len(prev_session_means) >= 2 else 0.0
    
    # 根據文獻與統計學：MDC95 = 1.96 * sqrt(2) * SEM = 2.77 * (SD / sqrt(N))
    # 設定合理上下邊界，避免樣本少時 MDC 虛高或過窄
    statistical_mdc = (2.77 * (sd_baseline / np.sqrt(len(prev_session_means)))) if len(prev_session_means) >= 2 else min_mdc_abs
    adaptive_mdc_pct_val = prev_mean * (user_mdc_pct / 100.0)
    mdc_threshold = max(min_mdc_abs, min(0.8, max(statistical_mdc, adaptive_mdc_pct_val)))

    # 多點時序動力學檢查 (測試點順序 1, 2, 3...)
    has_stages = '測試點順序' in df_top5.columns
    early_onset_leftward = False
    early_stage_diff = 0.0
    kinetic_detail_note = ""

    if has_stages:
        common_stages = sorted(list(set(latest_rows['測試點順序']).intersection(set(prev_rows['測試點順序']))))
        if common_stages:
            stage_diffs = []
            for stg in common_stages:
                l_stg_val = latest_rows[latest_rows['測試點順序'] == stg]['lactate_mmol'].mean()
                p_stg_val = prev_rows[prev_rows['測試點順序'] == stg]['lactate_mmol'].mean()
                stage_diffs.append((stg, l_stg_val - p_stg_val))

            # 檢驗早期階段 (前 1~2 點) 是否有提早大幅爬升 (Okawara 2022 左移特徵)
            early_stages = [sd for sd in stage_diffs if sd[0] in [1, 2]]
            if early_stages:
                early_stage_diff = float(np.mean([sd[1] for sd in early_stages]))
                if early_stage_diff > mdc_threshold:
                    early_onset_leftward = True

    # 3. 生理狀態判定
    is_leftward = (diff > mdc_threshold) or (early_onset_leftward and diff > 0.1)
    is_rightward = (diff < -mdc_threshold) and not early_onset_leftward

    num_prev = len(prev_dates)

    if is_leftward:
        status = "FATIGUE_LEFTWARD_SHIFT"
        badge = "⚠️ 急性代謝疲勞累積（左移趨勢）"
        ui_box_type = "warning"
        shift_desc = "顯著左移（Leftward Shift / 反應提前）"
        
        detail_txt = f"提早上升顯著（前期各點平均位移 +{early_stage_diff:.2f} mmol/L）" if early_onset_leftward else f"整體乳酸顯著偏高（+{diff:.2f} mmol/L，超過 MDC₉₅ 閾值 {mdc_threshold:.2f} mmol/L）"

        physio_mechanism = (
            f"最新一期乳酸動力學呈現**曲線{shift_desc}**。最新平均乳酸 **{latest_mean:.2f} mmol/L**，"
            f"較前 {num_prev} 期基準（**{prev_mean:.2f} mmol/L**）高出 **+{diff:.2f} mmol/L (+{diff_pct:.1f}%)**，"
            f"{detail_txt}。\n\n"
            "**🔬 生理學機制（Okawara 2022 & Takemoto 2026 動力學模型）：**\n"
            "研究指出，疲勞的核心特徵並非單點濃度絕對值，而是**乳酸生成曲線提前或在更低負荷提早竄升**。"
            "當近期身體存在高速度跑動、高功率衝刺或高訓練量殘餘疲勞時，肌組織肝醣分解提早代償介入，"
            "且微循環血流與粒線體有氧氧化清除速率受阻，導致同輸出階段的代謝壓力提早湧現。"
        )

        training_prescription = (
            "**📋 訓練調控處方（運動生理學指引）：**\n"
            "1. **強度降階避震**：建議暫緩安排 Zone 4+ 高強度無氧間歇、大輸出衝刺或紅區力竭課表，預防自主神經與代謝過度疲勞累積。\n"
            "2. **安排主動恢復**：近期 24–48 小時內課表建議改為 45–60 分鐘 Zone 1–2 超低強度有氧輕騎或輕鬆跑，刺激微血管擴張並加速代謝產物排除。\n"
            "3. **營養與睡眠重置**：提高優質複合碳水化合物與抗氧化營養攝取，加速肌肝醣再合成，並確保 7.5–8.5 小時充足睡眠以協助代謝恢復。"
        )

    elif is_rightward:
        status = "ADAPTATION_RIGHTWARD_SHIFT"
        badge = "💪 有氧代謝適應良好（右移趨勢）"
        ui_box_type = "success"
        shift_desc = "良好右移（Rightward Shift / 延遲累積）"

        physio_mechanism = (
            f"最新一期乳酸動力學呈現**曲線{shift_desc}**。最新平均乳酸 **{latest_mean:.2f} mmol/L**，"
            f"較前 {num_prev} 期基準（**{prev_mean:.2f} mmol/L**）顯著降低 **{abs(diff):.2f} mmol/L ({diff_pct:.1f}%)**，"
            f"已突破最小可偵測變化量（MDC₉₅ = {mdc_threshold:.2f} mmol/L）。\n\n"
            "**🔬 生理學機制（有氧適應與清除率提升）：**\n"
            "在相同運動強度與測試階段下乳酸反應顯著延遲且整體值更低，代表肌纖維粒線體氧化能力顯著增強，"
            "單羧酸轉運蛋白（MCT1/4）的乳酸攝取與緩衝清除效率極佳，有氧代謝系統能承擔更高的能量輸出比例。"
        )

        training_prescription = (
            "**📋 訓練調控處方（運動生理學指引）：**\n"
            "1. **維持並推進課表**：運動員生理儲備與有氧基礎處於絕佳狀態，建議維持既定訓練計畫。\n"
            "2. **適度挑戰閾值刺激**：可依週期計畫安排 1–2 次專項閾值（sLT / LT）維持課表或漸增強度刺激，推進運動表現天花板。\n"
            "3. **維持動態平衡**：持續標準化記錄，確保高強度增量不超過每週 5–10%，維持穩定進步。"
        )

    else:
        status = "METABOLIC_STABLE"
        badge = "⚖️ 代謝狀態維持平穩（穩態基準）"
        ui_box_type = "info"

        physio_mechanism = (
            f"最新一期乳酸動力學曲線與前 {num_prev} 期歷史基準維持高度一致。最新平均乳酸 **{latest_mean:.2f} mmol/L**，"
            f"與前 {num_prev} 期平均（**{prev_mean:.2f} mmol/L**）差異僅 **{diff:+.2f} mmol/L ({diff_pct:+.1f}%)**，"
            f"變動落在個人最小可偵測變化量（MDC₉₅ = ±{mdc_threshold:.2f} mmol/L）與日常生理波動誤差線內。\n\n"
            "**🔬 生理學機制：**\n"
            "當前未見乳酸曲線提早竄升（左移）或顯著延後（右移）之動力學偏移，代表能量代謝系統與神經肌肉系統處於良好平衡，"
            "未見顯著急性代謝疲勞殘留。"
        )

        training_prescription = (
            "**📋 訓練調控處方（運動生理學指引）：**\n"
            "1. **按表操課執行**：目前代謝狀態維持良好穩態，建議依循教練原定課表步調規律執行常規週期訓練。\n"
            "2. **維持標準化監控**：建議每次量測維持相同的熱身與測試條件，持續累積高品質長期基準線。"
        )

    full_advice_markdown = (
        f"**{badge}**\n\n"
        f"{physio_mechanism}\n\n"
        f"{training_prescription}\n\n"
        f"📌 *註記：依據運動生理學研究規範，本評估以個體近五期基準線與 MDC₉₅ 誤差界線判定，作為訓練負載調節之科學參考。*"
    )

    return {
        "status": status,
        "badge": badge,
        "latest_date": latest_date,
        "latest_mean": latest_mean,
        "prev_mean": prev_mean,
        "diff": diff,
        "diff_pct": diff_pct,
        "mdc_threshold": mdc_threshold,
        "is_leftward": is_leftward,
        "is_rightward": is_rightward,
        "early_onset_leftward": early_onset_leftward,
        "physio_mechanism": physio_mechanism,
        "training_prescription": training_prescription,
        "full_advice_markdown": full_advice_markdown,
        "ui_box_type": ui_box_type
    }
