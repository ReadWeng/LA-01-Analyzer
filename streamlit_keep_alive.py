# -*- coding: utf-8 -*-
"""
streamlit_keep_alive.py
~~~~~~~~~~~~~~~~~~~~~~~
Streamlit 前端防休眠與連線活性維持組件。

解決問題：
1. 瀏覽器背景分頁凍結 (Tab Throttling)：使用者切換分頁後，計時器被瀏覽器暫停導致 WebSocket 斷線。
2. 閒置連線中斷 (Session Disconnect)：閒置過久出現 "Connection error" 或自動重整丟失狀態。
3. 螢幕鎖定休眠 (Screen Sleep)：長時間測試或展示時螢幕自動關閉。

核心機制：
- Web Worker 心跳：獨立執行緒定時器，繞過瀏覽器背景分頁凍結機制。
- 後端活性探測：定時 fetch 核心健康端點 (/_stcore/health)，維持 Tornado WebSocket 通道活躍。
- Screen Wake Lock API：防止作業系統螢幕進入待機休眠。
"""

import streamlit as st
import streamlit.components.v1 as components


def init_keep_alive(
    interval_seconds: int = 25,
    enable_wake_lock: bool = True,
    show_badge: bool = False,
    badge_label: str = "🟢 防休眠守護中",
    key: str = "st_keep_alive_component"
):
    """
    在 Streamlit 應用中注入防休眠與連線保活腳本。

    :param interval_seconds: 心跳發送間隔（秒，建議 20~30 秒）
    :param enable_wake_lock: 是否啟用螢幕防休眠 (Screen Wake Lock)
    :param show_badge: 是否在畫面上顯示防休眠守護徽章
    :param badge_label: 徽章文字內容
    :param key: 元件 key
    """
    interval_ms = max(5000, interval_seconds * 1000)

    badge_html = f"""
    <div id="keep-alive-badge" style="
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #10b981;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11px;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 999px;
        margin: 4px 0;
    ">
        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #10b981; animation: pulse 2s infinite;"></span>
        <span>{badge_label}</span>
        <span id="ping-count" style="color: #6ee7b7; font-size: 10px; margin-left: 4px;">(0)</span>
    </div>
    <style>
        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.85); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}
    </style>
    """ if show_badge else ""

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="margin: 0; padding: 0; background: transparent; overflow: hidden;">
        {badge_html}
        <script>
        (function() {{
            let pingCount = 0;
            const intervalMs = {interval_ms};
            const enableWakeLock = {'true' if enable_wake_lock else 'false'};

            // 1. 建立 Web Worker（利用 Blob 繞過跨域與外部檔案依賴）
            // Web Worker 執行緒不受瀏覽器背景分頁凍結 (Tab Throttling) 影響
            const workerScript = `
                let timer = null;
                self.onmessage = function(e) {{
                    if (e.data === 'start') {{
                        if (timer) clearInterval(timer);
                        timer = setInterval(function() {{
                            self.postMessage('beat');
                        }}, ${{e.data_interval || 25000}});
                    }} else if (e.data === 'stop') {{
                        if (timer) clearInterval(timer);
                    }}
                }};
            `;

            let worker = null;
            try {{
                const blob = new Blob([workerScript], {{ type: 'application/javascript' }});
                worker = new Worker(URL.createObjectURL(blob));
                worker.onmessage = function(e) {{
                    if (e.data === 'beat') {{
                        sendKeepAlivePing();
                    }}
                }};
                worker.postMessage({{ data: 'start', data_interval: intervalMs }});
            }} catch (err) {{
                console.warn('[KeepAlive] Web Worker 啟動失敗，回退至常規 setInterval:', err);
                setInterval(sendKeepAlivePing, intervalMs);
            }}

            // 2. 心跳探測函式 (發送至 Streamlit 後端健康端點)
            function sendKeepAlivePing() {{
                pingCount++;
                const countElem = document.getElementById('ping-count');
                if (countElem) {{
                    countElem.textContent = '(' + pingCount + ')';
                }}

                // 嘗試向主視窗或相對路徑探測健康端點
                const targets = [
                    '/_stcore/health',
                    '/_stcore/allowed-message-origins',
                    './_stcore/health'
                ];

                // 先嘗試透過父視窗 fetch (若同源)
                let parentFetched = false;
                try {{
                    if (window.parent && window.parent.fetch) {{
                        window.parent.fetch('/_stcore/health', {{ cache: 'no-store' }}).catch(function() {{}});
                        parentFetched = true;
                    }}
                }} catch (e) {{}}

                if (!parentFetched) {{
                    // 在 iframe 內直接發送 fetch
                    fetch(targets[0], {{ cache: 'no-store' }})
                        .catch(function() {{
                            // 若失敗則 fallback 到根路徑
                            fetch('/', {{ method: 'HEAD', cache: 'no-store' }}).catch(function() {{}});
                        }});
                }}
            }}

            // 3. 螢幕防休眠 (Screen Wake Lock API)
            let wakeLock = null;
            async function acquireWakeLock() {{
                if (!enableWakeLock || !('wakeLock' in navigator)) return;
                try {{
                    wakeLock = await navigator.wakeLock.request('screen');
                    wakeLock.addEventListener('release', function() {{
                        wakeLock = null;
                    }});
                }} catch (e) {{
                    // Wake lock 拒絕或不支援
                }}
            }}

            acquireWakeLock();

            // 當頁面可見性改變時重新申請 Wake Lock
            document.addEventListener('visibilitychange', function() {{
                if (document.visibilityState === 'visible') {{
                    acquireWakeLock();
                    sendKeepAlivePing();
                }}
            }});

            // 立即執行第一次保活
            sendKeepAlivePing();
        }})();
        </script>
    </body>
    </html>
    """

    component_height = 28 if show_badge else 0
    components.html(html_code, height=component_height, width=None)
