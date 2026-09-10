# Grace Imaging／中島大輔汗液乳酸研究追蹤交付說明

**版本：** 2026-09-10<br>
**語言：** 繁體中文<br>
**用途：** 研究追蹤、LA-01 產品規劃與內部簡報；不是醫療診斷或臨床處方。

## 交付內容

| 檔案 | 用途 |
|---|---|
| `grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.md` | 完整證據報告：搜尋方法、11 篇核心逐篇摘要、2 篇支援文章、1 篇相鄰排除文章、跨研究整合、COI 與產品建議 |
| `grace_imaging_daisuke_nakashima_sweat_lactate_tracker_2026-09-10.csv` | 27 欄、14 筆的可排序更新追蹤表；保留 online／issue date、樣本、分析人數、統計、限制、COI 與全文連結 |
| `grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.pptx` | 30 頁繁中簡報：證據時間軸、逐篇圖卡、疲勞證據、品質閘門、LA-01 畫面與驗證路線 |
| `generate_grace_imaging_sweat_lactate_review.js` | PptxGenJS 投影片產生腳本，可重製與更新簡報 |
| `SHA256SUMS.txt` | 上述來源檔與成品的 SHA-256 完整性雜湊 |

GitHub 儲存庫中的原始位置為：

- 報告與 CSV：`reports/`
- 投影片與 ZIP：`downloads/`
- 產生腳本：`scripts/`

## 一分鐘判讀

1. 本次辨識 **11 篇核心汗乳酸研究、2 篇支援文章、1 篇相鄰排除文章**。
2. 目前最穩健的用途是：在有足夠出汗時，從曲線找 **sLT／第一轉折**，再顯示當下時間、功率、速度或心率。
3. 直接疲勞證據只有兩篇小型男性研究（`n=17`、`n=18`）；只能支持「較早／較低 sLT 可能反映恢復降低」的初步方向，不能建立通用濃度切點或 0–100 疲勞分數。
4. LA-01 建議採 **資料品質 → 同流程 → 個人基準 → 個人 MDC → 第二指標複核** 的判讀順序。
5. 11/11 核心研究皆揭露中島大輔與 Grace Imaging 的公司或股權關係；目前集合不能證明獨立外部重現。

## 重要書目 QA

- 手搖車研究正確 DOI：`10.14814/phy2.71002`（Grace 官網文字曾寫成 `phy2.17002`）。
- 游泳研究正確 DOI：`10.1002/ejsc.12179`（Grace 官網文字曾寫成 `10.10002`）。
- 足球疲勞研究為 2025-09-07 online、2026 正式卷期；追蹤表分欄保存，不重複計數。
- 2026 健康女性研究在本次查核的 Grace Paper 清單中未列出，因此正式追蹤不能只看公司官網。

## 更新投影片

需先安裝 Node.js 與 PptxGenJS 3.12：

```bash
npm install pptxgenjs@3.12.0
node scripts/generate_grace_imaging_sweat_lactate_review.js
```

產生器會覆寫：

```text
downloads/grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.pptx
```

更新文獻後，應同步修改 Markdown、CSV 與投影片腳本，並重新執行 CSV、Open XML、ZIP 與版面邊界 QA。
