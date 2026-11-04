# Changelog

本專案遵循 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-TW/) 語意化版本規範。

## [v1.0.3] - 2026-11-04

### ✨ 使用者體驗與數值輸入優化 (Enhancements & UI)
- **RPE 體感輸入全面對齊 Android NFC 程式區間**：
  - 將逐筆表單輸入之體感／RPE 改為下拉式選單（`st.selectbox`），提供與手機端 `LA01LactateApp` 完全相同的自覺強度標籤：`運動前基期`、`輕鬆 RPE 2`、`適中 RPE 5`、`吃力 RPE 7`、`極限 RPE 9`、`無 / 未填`，並保留選填之自訂備註文字輸入框。
  - 同步將試算表編輯器（`st.data_editor`）之「體感」欄位設定為 `SelectboxColumn`，支援一鍵點選 NFC 同款區間。
- **已輸入量測數據清單清空預設占位數字**：
  - 調整 `get_default_lactate_df()` 與雲端活動載入邏輯，預設採用完全乾淨的 0 筆空白清單，杜絕預先出現 `0.0`、`15.0`、`30.0` 占位數字與「未測」狀態列。
  - 僅在使用者明確於表單中點擊「➕ 新增 / 更新此量測點」或點擊「From MyLactate Sync LA-01」同步時，才於清單中呈現真實檢測點。
  - 獨立保留「🔄 載入範本數據」按鈕供測試時一鍵載入示範數值。

## [v1.0.2] - 2026-11-04

### 🚀 雙軌輸入革新與前端極致韌性 (Features & Fixes)
- **乳酸與血糖數據「雙軌輸入機制 (Dual-Input Mode)」**：
  - **模式一：【📝 表單逐筆輸入 / 快速管理】（推薦首選）**：採用原生 HTML 數字與文字輸入框（st.number_input / st.text_input），完全不依賴前端大型動態 JS Chunk 與 Canvas，100% 免疫 Failed to fetch dynamically imported module 錯誤，在手機、平板與各類輸入法（含 Windows 注音/拼音 IME）下保證隨點即打、順暢新增、即時預覽與單鍵刪除。
  - **模式二：【📊 試算表整批編輯模式】（st.data_editor）**：保留仿 Excel 試算表表格供習慣批次複製貼上的使用者，並提供「連按兩下 (Double-Click)」明確操作指引。
  - **狀態雙向即時同步**：兩套介面無縫共享底層 custom_lactate 資料狀態，無論在表單或試算表增刪修改，皆能即時反映於圖表、生理數據對照彙整表與 Firebase 雲端綁定。
- **頂部主動式前端模組載入錯誤自動修復器**：
  - 於主文件頂部注入主動偵測器，一旦瀏覽器捕捉到 Failed to fetch dynamically imported module，自動透過帶有時間戳記的 URL 參數（?_reload=...）執行破除快取之即時重載，防止瀏覽器 V8 模組快取長期鎖定失敗狀態。

## [v1.0.1] - 2026-11-04

### 🛠️ 修復與強化 (Fixes)
- **前端動態模組（Chunk）快取自動自癒機制**：於 `streamlit_keep_alive.py` 新增內層 `/~/+/` iframe 快取版本偵測與 `Failed to fetch dynamically imported module` 自動強制刷新（`cache: 'reload'`）機制，解決雲端容器重啟或升級後瀏覽器快取舊版 JS 雜湊導致元件載入失敗的問題。
- **鎖定 Streamlit 版本**：將 `requirements.txt` 固定為 `streamlit==1.57.0`，避免雲端重啟時自動跨版本升級造成前端靜態模組雜湊變動。

## [v1.0.0] - 2026-11-04

首個正式雲端穩定版發布，涵蓋單期運動與汗乳酸協同分析、多期動力學整合儀表板（LacV5）、AI 運動生理週報與下一次處方系統，以及雲端安全架構重構。

### ✨ 核心功能 (Features)
- **單期 FIT 檔與汗乳酸／血糖協同分析**：
  - 支援解析 Garmin / COROS `.fit` 檔案（功率、心率、核心體溫、踏頻、GPS 軌跡、海拔與距離），並與 LA-01 汗乳酸（`mM`）、血糖（`mg/dL`）及體感／RPE 同步對照作圖。
  - 支援互動式雲端活動月曆（Activity Calendar）檢視、即時綁定／編輯／刪除紀錄，以及歷史 HTML 報告批次匯入還原。
- **多期數據整合儀表板 (LacV5)**：
  - 支援從 Firebase 雲端直接勾選多場歷史紀錄或上傳單期 HTML 報告進行跨期交叉比對。
  - 支援時間零點對齊、負數時間（運動前基期）呈現、跨圖表同步縮放平移，並自動於同日多筆活動中篩選具乳酸紀錄之關鍵測驗場次。
- **AI 運動生理週報與下一次訓練處方**：
  - 整合縱貫汗乳酸疲勞與有氧適應動力學模型（Okawara et al., 2022；Takemoto et al., 2026 MDC95 最小可偵測變化），自動產出個人化訓練負荷評估與下一次課表處方。
  - 支援跑步（Running）與自行車（Cycling）專項獨立篩選分析，並採用同日單一排他配對避免重複標註乳酸數值。
- **Intervals.icu 手錶雲端自動同步與教練管理模式**：
  - 支援 OAuth 2.0 一鍵授權與 API Key 綁定，登入即增量同步日常訓練與晨間生理指標。
  - 支援管理員／教練視角切換調閱多位選手雲端數據與常設選手名冊管理。

### 🔒 安全性與穩定性強化 (Security & Fixes)
- **雲端金鑰安全重構**：全面移除程式碼內硬編碼 API Key 與 Secret，改由 Streamlit Secrets（`st.secrets`）與環境變數動態讀取，並提供 `secrets.toml.example` 設定範本。
- **Google OIDC 與 Firebase 驗證韌性提升**：新增 `id_token` 逾時自動改用 `access_token` 備援交換機制與金鑰缺失明確診斷提示。
- **資料編輯器與單位標準化**：全面統一乳酸濃度單位為 `mM`，並強化手動輸入表格預設樣板列與 `float64` 型別正規化，杜絕空白表格塌陷與 `NameError` 異常。
