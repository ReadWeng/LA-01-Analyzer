# LA-01 乳酸與生理指標分析系統 (Firebase 雲端版)

這是一個基於 Streamlit 的網頁應用程式，能夠分析 LA-01 乳酸機資料、Garmin FIT 運動數據，並進行單期與多期的深度交叉對比。

## 執行環境準備

1. 請確認您的電腦已安裝 Python 3.9 以上版本。
2. 開啟終端機 (Terminal) 或命令提示字元 (cmd)，進入本資料夾 (`fit_lactate_fire`)。
3. 執行以下指令安裝必要的套件：
   ```bash
   pip install -r requirements.txt
   ```

## 如何執行程式

您可以直接雙擊執行 `run.bat`，或者在終端機輸入以下指令：

```bash
streamlit run fit_lactate_fire.py
```

這會自動啟動您的瀏覽器並進入系統畫面。

## Grace Imaging／中島大輔汗液乳酸研究追蹤（2026-09-10）

本次聚焦追蹤 Daisuke Nakashima 列名的汗液乳酸研究，共整理 **11 篇核心、2 篇支援、1 篇相鄰排除文章**。內容包含逐篇摘要、研究限制、利益衝突、書目勘誤、跨研究證據整合，以及 LA-01 的疲勞／恢復呈現框架。

- [交付說明](reports/grace_imaging_daisuke_nakashima_sweat_lactate_delivery_README_zhTW_2026-09-10.md)
- [繁中完整證據報告](reports/grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.md)
- [14 筆、27 欄 CSV 追蹤表](reports/grace_imaging_daisuke_nakashima_sweat_lactate_tracker_2026-09-10.csv)
- [30 頁繁中投影片](downloads/grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.pptx)
- [一次下載 ZIP](downloads/grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.zip)
- [SHA-256 完整性清單](downloads/grace_imaging_daisuke_nakashima_sweat_lactate_SHA256SUMS_2026-09-10.txt)
- [投影片產生腳本](scripts/generate_grace_imaging_sweat_lactate_review.js)

> 重點邊界：目前最可辯護的輸出是同一流程下的個人內 sLT 時間／功率／速度／心率與 `ΔsLT`。現有證據不支持把單次汗乳酸絕對濃度換成血乳酸或通用疲勞百分比。
