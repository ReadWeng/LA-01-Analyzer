# Changelog

本專案遵循 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-TW/) 語意化版本規範。

## [v1.0.7] - 2026-11-04

### 🛠️ 試算表整批編輯模式 (`st.data_editor`) 輸入修復 (Spreadsheet Input Fix)
- **預留 6 列真實空白可編輯列（不含任何預設占位數字）**：
  - 解決先前因 DataFrame 為 0 列（`len == 0`）導致 `st.data_editor` 畫布內呈現的 5 列橫線皆為不可點擊之背景填充區、無法直接雙擊輸入的問題。
  - 新增 `build_editor_base_df(df, min_rows=6)`，在試算表預留 6 列真實空白儲存格（數值為 `NaN`、體感為 `None`），使用者可直接雙擊任意列輸入，同時「📋 目前已輸入之量測數據清單」仍自動過濾空白列、保持 0 筆乾淨無預設數字。
- **固定 `editor_base_df` 基底參照，杜絕連續換格輸入時被重置清空**：
  - 修復在 `st.data_editor` 輸入第 1 格（如相對時間）後點擊第 2 格（如乳酸值）時，因底層傳入的 DataFrame 在重繪時改變而觸發 Streamlit 重置 Widget 狀態、導致輸入數值消失的問題。

## [v1.0.6] - 2026-11-04

### 🚀 重新開啟網頁／冷啟動載入速度極限優化 (Cold-Start & Reopen Speed Boost)
- **雲端月曆與同步查詢欄位遮罩 (`mask.fieldPaths`)，首頁下載量縮減 99%（~20 MB ➔ ~20 KB）**：
  - 過去開啟網頁時，`fetch_user_calendar_data()` 與 `sync_pre_lactate_activities_to_firebase()` 會將使用者歷史上百場運動紀錄內部的完整 30 秒軌跡陣列（`time_series`）全數下載，單次開啟網頁需傳輸 10～20 MB 以上的 JSON 資料。
  - 現於 Firestore 查詢加入 `mask.fieldPaths` 欄位投影，首頁月曆僅下載活動摘要欄位（時間、運動類型、平均功率、平均心率、乳酸綁定狀態等，總計僅約 20 KB），並在您實際點擊「載入」或「跨期比對」某場特定運動時，才透過 `_ensure_fit_time_series()` 按需載入並快取該單場軌跡（~50 KB），徹底消除開啟網頁時的網路傳輸瓶頸。
- **跨瀏覽器重整之伺服器端記憶體快取 (`@st.cache_resource`)**：
  - 新增 `_get_server_ram_store()` 與 `_get_calendar_ram_cache()`，讓 Google OIDC 登入憑證交換結果、Intervals.icu 綁定狀態、教練選手名冊與活動月曆資料跨瀏覽器重新整理（F5 / 重新開啟分頁）常駐於伺服器 RAM 中。重新開啟網頁時達成 **0 毫秒** 直接秒開，並在新增、刪除或同步數據時自動精準更新快取。
- **消除 Google OIDC 登入時的雙重腳本執行 (`st.rerun()`) 與背景非阻塞同步**：
  - 移除 Google 帳號自動驗證成功後的強制 `st.rerun()`，避免每次重新開啟分頁時整支程式重複執行兩遍。
  - 將使用者基本資料更新（`ensure_user_profile_in_firestore`）與登入時的 Intervals.icu 增量自動同步移至背景執行緒（`threading.Thread(..., daemon=True)`）非阻塞執行，不再卡住首頁畫面渲染。

## [v1.0.5] - 2026-11-04

### ⚡ 執行與載入速度極致加速 (Performance Optimization)
- **消除每次互動之冗餘模組重編譯 (`importlib.reload`)**：
  - 移除 `fit_lactate_fire.py` 內 7 處於每次頁面重繪（Rerun）時強制重新載入與編譯子模組（`activity_calendar`、`intervals_client`、`integrate_reports`、`weekly_physio_engine`、`ai_weekly_report`、`lactate_fatigue_analyzer`）的開銷，大幅降低每次按鈕點擊的 CPU 延遲。
- **修復 `.fit` 檔案解析快取與大型 CSV 序列化快取**：
  - 修正 `@st.cache_data` 裝飾器位置至 `parse_fit_file_data()`，確保上傳 `.fit` 檔案後切換設定或新增乳酸點時直接讀取記憶體快取，免除重複解析二進位檔案。
  - 為完整 FIT 軌跡 CSV 下載新增 `@st.cache_data` 快取，避免每次重繪重複序列化數千筆軌跡列。
  - 為 `logo.jpg` 圖片與 Base64 編碼新增 `@st.cache_resource` / `@st.cache_data` 快取，消除重複磁碟 I/O。
- **消除側邊欄與首頁重複 Firestore 網路請求**：
  - 將 Intervals.icu 認證狀態（`icu_creds_cache`）與教練模式選手名冊（`coach_athletes_cache`）快取於 `st.session_state`，避免每次點擊按鈕都向 Google Firestore 發送 2～6 次同步 HTTPS 請求。
  - 首頁「最近五期乳酸紀錄趨勢」直接復用活動月曆已載入之 `cal_cache_data` 記憶體快取，省去重複抓取 `lactate_records` 的網路等待。
  - 將自動背景同步冷卻時間由 45 秒調整為 600 秒（登入時立即同步一次，並隨時支援手動點擊同步），避免操作過程中頻繁觸發背景連線卡頓。
- **雲端月曆雙執行緒平行載入 (`ThreadPoolExecutor`)**：
  - 於 `activity_calendar.py` 採用 `ThreadPoolExecutor(max_workers=2)` 與 `requests.Session()` 連線池平行抓取 `fit_records` 與 `lactate_records`，將初次載入雲端月曆的網路耗時縮減近半。

## [v1.0.4] - 2026-11-04

### 🎨 側邊欄介面與文案優化 (UI & Usability)
- **明確標示「輸出報告顏色設定」**：
  - 將側邊欄原「介面設定 / 圖表主題」重構並明確更名為「🎨 輸出報告顏色設定」，消除使用者對於設定影響範圍的疑慮，清楚傳達該深色／淺色切換係直接決定數據協同分析圖表與匯出 HTML 報告的底色與配色風格。

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
