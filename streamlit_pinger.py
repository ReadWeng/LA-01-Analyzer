# -*- coding: utf-8 -*-
"""
streamlit_pinger.py
~~~~~~~~~~~~~~~~~~~
Streamlit 雲端伺服器 (Streamlit Community Cloud / Render) 24/7 自動防休眠與定時喚醒工具。

功能特點：
1. 定時自動保活：每隔 5~10 分鐘自動向目標網址發送探測請求，防止伺服器因閒置休眠。
2. 智慧休眠偵測：若檢測到 "This app has gone to sleep" 或休眠頁面，自動觸發喚醒機制。
3. 支援多目標監控：可同時守護多個 Streamlit / 網頁應用。
4. 彈性執行模式：支援本機背景持續運行 (常駐模式) 或單次執行 (--once，適用於排程任務/GitHub Actions)。
5. 隨機擾動機制 (Jitter)：隨機微調間隔時間，避免固定頻率被 CDN 判定為惡意機器人。
"""

import sys
import os
import time
import random
import argparse
from datetime import datetime
import urllib.request
import urllib.error
import ssl

# 預設使用者代理 (偽裝成現代 Chrome 瀏覽器)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# 常見休眠關鍵字
SLEEP_KEYWORDS = [
    "this app has gone to sleep",
    "yes, get this app back up",
    "get this app back up",
    "wake up this app",
    "app is sleeping"
]


def print_colored(text: str, color: str = "white", bold: bool = False):
    """跨平台彩色文字輸出"""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "gray": "\033[90m"
    }
    reset = "\033[0m"
    bold_str = "\033[1m" if bold else ""
    c_str = colors.get(color, colors["white"])
    print(f"{bold_str}{c_str}{text}{reset}")


def ping_url(url: str, timeout: int = 15) -> dict:
    """
    發送 HTTP 請求並檢測目標狀態與是否休眠。
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    start_time = time.time()
    result = {
        "url": clean_url,
        "status_code": 0,
        "latency_ms": 0,
        "is_sleeping": False,
        "success": False,
        "message": ""
    }

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            latency = int((time.time() - start_time) * 1000)
            status = response.getcode()
            body = response.read(65536).decode("utf-8", errors="ignore").lower()

            result["status_code"] = status
            result["latency_ms"] = latency
            result["success"] = (status in [200, 301, 302])

            for kw in SLEEP_KEYWORDS:
                if kw in body:
                    result["is_sleeping"] = True
                    result["message"] = f"偵測到休眠特徵: '{kw}'"
                    break

            if not result["is_sleeping"]:
                result["message"] = "正常運行中"

    except urllib.error.HTTPError as e:
        latency = int((time.time() - start_time) * 1000)
        result["status_code"] = e.code
        result["latency_ms"] = latency
        error_body = ""
        try:
            error_body = e.read(16384).decode("utf-8", errors="ignore").lower()
        except Exception:
            pass

        for kw in SLEEP_KEYWORDS:
            if kw in error_body:
                result["is_sleeping"] = True
                result["message"] = f"偵測到休眠特徵: '{kw}'"
                break
        if not result["is_sleeping"]:
            result["message"] = f"HTTP 錯誤碼: {e.code}"

    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        result["latency_ms"] = latency
        result["message"] = f"連線異常: {str(e)}"

    return result


def trigger_wake_up(url: str, timeout: int = 20) -> bool:
    """
    發送多次激活用戶請求嘗試喚醒 Streamlit Cloud 容器。
    """
    clean_url = url.rstrip('/')
    wake_endpoints = [
        clean_url + '/',
        clean_url + '/_stcore/health',
        clean_url + '/_stcore/stream'
    ]

    print_colored(f"   ⚡ 正在嘗試激活動態喚醒程序...", "yellow")
    for ep in wake_endpoints:
        try:
            req = urllib.request.Request(
                ep,
                headers={"User-Agent": DEFAULT_USER_AGENT, "Cache-Control": "no-cache"}
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                pass
            time.sleep(1.5)
        except Exception:
            pass

    return True


def run_cycle(urls: list, auto_wake: bool = True):
    """執行一次完整的 Ping 檢測流程"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for url in urls:
        res = ping_url(url)
        tag = f"[{now_str}]"
        target_disp = f"[{res['url']}]"

        if res["is_sleeping"]:
            print_colored(f"{tag} 💤 {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 狀態：休眠中！", "yellow", bold=True)
            if auto_wake:
                trigger_wake_up(url)
                print_colored(f"   ⏳ 等待 10 秒後重新複檢...", "gray")
                time.sleep(10)
                re_check = ping_url(url)
                if not re_check["is_sleeping"] and re_check["success"]:
                    print_colored(f"   ✅ 喚醒成功！應用已重新啟動 (HTTP {re_check['status_code']}, {re_check['latency_ms']}ms)", "green", bold=True)
                else:
                    print_colored(f"   ℹ️ 容器已收到喚醒訊號，通常需 1~2 分鐘熱機完畢。", "cyan")
        elif res["success"]:
            print_colored(f"{tag} 🟢 {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 狀態：{res['message']}", "green")
        else:
            print_colored(f"{tag} ⚠️ {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 提示：{res['message']}", "red")


def main():
    parser = argparse.ArgumentParser(description="Streamlit 自動防休眠保活工具 (Keep-Alive Pinger)")
    parser.add_argument(
        "--urls", "-u", nargs="+",
        help="目標 Streamlit 網址 (可指定多個，例如: https://myapp.streamlit.app)"
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=8,
        help="心跳保活間隔時間 (分鐘，預設: 8 分鐘)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="僅執行單次檢測即退出 (適用於排程任務或 GitHub Actions)"
    )
    parser.add_argument(
        "--no-wake", action="store_true",
        help="停用自動喚醒觸發"
    )

    args = parser.parse_args()

    # 1. 取得目標網址清單
    urls = []
    if args.urls:
        urls.extend(args.urls)

    # 亦可從環境變數 STREAMLIT_APP_URL 取得
    env_url = os.environ.get("STREAMLIT_APP_URL")
    if env_url and env_url not in urls:
        urls.append(env_url)

    # 若尚未指定，提供互動式輸入或讀取預設
    if not urls:
        print_colored("===================================================", "cyan")
        print_colored("   🚀 Streamlit 雲端應用防休眠保活守護工具", "cyan", bold=True)
        print_colored("===================================================", "cyan")
        input_url = input("請輸入您的 Streamlit 網址 (例如: https://my-app.streamlit.app): ").strip()
        if input_url:
            urls.append(input_url)
        else:
            print_colored("❌ 未提供任何網址，程序退出。", "red")
            sys.exit(1)

    print_colored(f"🎯 監控目標 ({len(urls)} 個):", "white", bold=True)
    for u in urls:
        print_colored(f"   • {u}", "cyan")
    print_colored(f"⏱️ 探測週期: 每 {args.interval} 分鐘", "white")
    print_colored("---------------------------------------------------", "gray")

    if args.once:
        run_cycle(urls, auto_wake=not args.no_wake)
        return

    print_colored("🟢 守護程式已進入常駐運行模式 (按 Ctrl + C 可隨時停止)...", "green")
    try:
        while True:
            run_cycle(urls, auto_wake=not args.no_wake)
            # 加入隨機擾動 ±20 秒
            jitter = random.randint(-20, 20)
            sleep_sec = max(60, (args.interval * 60) + jitter)
            time.sleep(sleep_sec)
    except KeyboardInterrupt:
        print_colored("\n🛑 守護程式已手動停止。", "yellow")


if __name__ == "__main__":
    main()
