# LA-01 乳酸與生理指標分析系統 (Firebase 雲端版)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/Version-v1.0.0-success.svg)](./CHANGELOG.md)

這是一個基於 Streamlit 的網頁應用程式，能夠分析 LA-01 乳酸機資料、Garmin / COROS FIT 運動數據，並進行單期與多期的深度交叉對比，以及生成 AI 運動生理週報與下一次訓練處方。

## 執行環境準備

1. 請確認您的電腦已安裝 Python 3.9 以上版本。
2. 開啟終端機 (Terminal) 或命令提示字元 (cmd)，進入本資料夾 (`fit_lactate_fire`)。
3. 執行以下指令安裝必要的套件：
   ```bash
   pip install -r requirements.txt
   ```
4. 將 `secrets.toml.example` 複製為 `.streamlit/secrets.toml` 並填入對應雲端金鑰。

## 如何執行程式

您可以直接雙擊執行 `run.bat`，或者在終端機輸入以下指令：

```bash
streamlit run fit_lactate_fire.py
```

這會自動啟動您的瀏覽器並進入系統畫面。

## 授權條款 (License)

本專案採用 **Apache License 2.0** 授權條款開源發布。詳情請參閱 [LICENSE](./LICENSE) 與 [NOTICE](./NOTICE) 檔案。
