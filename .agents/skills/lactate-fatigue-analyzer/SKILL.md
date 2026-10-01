---
name: lactate-fatigue-analyzer
description: Analyze longitudinal multi-session lactate kinetics to assess acute metabolic fatigue trends and aerobic adaptation based on Okawara et al. (2022) and Takemoto et al. (2026) models. Evaluates leftward/rightward curve shifts, early onset accumulation, and minimal detectable change (MDC95) to produce physiological rationales and personalized training prescriptions.
---

# Lactate Fatigue Analyzer (汗乳酸/血乳酸疲勞動力學分析器)

基於運動生理學頂級文獻（*Okawara et al. 2022, Physiol Rep* 與 *Takemoto et al. 2026, Fatigue*）之穿戴式汗乳酸與血乳酸疲勞動力學分析引擎。

## 核心生理學判定鐵律 (Physiological Principles)
1. **看曲線位置與提前反應，不看單點絕對濃度**：
   - 疲勞特徵主要為動力學曲線「左移（Leftward shift）」與「提前上升（Sooner observation of rise/peak）」，並非跨人的單一絕對濃度高低。
2. **同人、同基準比較（超過 MDC₉₅ 才算真變化）**：
   - 比較限於同一運動員在標準化或相似測試條件下的前四期歷史基準。
   - 導入最小可偵測變化量（MDC₉₅，預設閾值約 12-15% 變異量或 0.25~0.3 mmol/L）。唯有突破此雜訊邊界，才判定為真實生理動態位移。
3. **客觀科學宣稱邊界**：
   - 用語規範為「急性代謝疲勞趨勢（候選訊號）」，結合「狀態等級 + 生理機制 + 具體訓練處方」，避免跨人絕對病理診斷。

## 評估狀態分類
1. **⚠️ 急性代謝疲勞累積（左移趨勢）**：
   - 最新期乳酸上升提早、同負荷/同點數乳酸累積速率顯著增快（高於基準線超過 MDC₉₅）。
   - 生理機制：前期高負荷後糖解作用提前代償介入，粒線體有氧氧化清除速率或微循環恢復尚未完全。
   - 處方建議：暫緩 Zone 4+ 高強度間歇，改排 Zone 1-2 低強度主動恢復（45-60分鐘），補充醣類與維持充份睡眠。
2. **💪 有氧代謝適應良好（右移趨勢）**：
   - 最新期乳酸累積延遲，同輸出階段乳酸低於基準（低於基準線超過 MDC₉₅）。
   - 生理機制：粒線體氧化能力與乳酸轉運效率提升，能量供能更仰賴有氧系統。
   - 處方建議：生理狀態佳，可維持現行課表，或依週期進度適度增加 5-10% 專項負荷或閾值維持刺激。
3. **⚖️ 代謝狀態維持平穩（穩態基準）**：
   - 最新期動力學位於基準波動 MDC 範圍內。
   - 處方建議：維持既定訓練週期計畫與常規恢復。
4. **ℹ️ 個人基準建立中**：
   - 歷史期數 < 2 期，持續標準化累積。
