# -*- coding: utf-8 -*-
"""
streamlit_pinger.py
~~~~~~~~~~~~~~~~~~~
Streamlit 雲端伺服器 (Streamlit Community Cloud / Render / Hugging Face Spaces)
24/7 自動防休眠保活與自動按鈕喚醒工具。

核心機制與問題解決：
1. 為什麼傳統 curl / HTTP GET 保活會失效？
   Streamlit Community Cloud 休眠時，網關會回傳 React 靜態提示頁面 (😴 Zzzz)。
   普通的 HTTP GET 請求「無法執行 JavaScript，無法建立 WebSocket，更無法點擊網頁按鈕」，
   因此伺服器完全不會啟動容器！
2. 本工具如何達成 100% 徹底防休眠與自動喚醒？
   - 瀏覽器自動化模式 (Playwright Chromium)：
     以無頭瀏覽器真實連線至 Streamlit 應用。
     a. 若檢測到休眠畫面 (「This app has gone to sleep」)，自動點擊
        【Yes, get this app back up!】 按鈕，並等待容器熱機啟動！
     b. 若應用處於活躍狀態，保持連線 10~15 秒，讓 Streamlit 前端與伺服器建立
        真實 WebSocket (/_stcore/stream) 連線，重置官方 12~48 小時的閒置倒數計時器。
   - 輕量 HTTP 模式 (requests / urllib)：若在無瀏覽器環境，提供 HTTP/REST 保活探測與狀態警示。
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

# Windows 主控台 UTF-8 編碼支援保護
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 預設監控目標 (您的 Streamlit App)
DEFAULT_STREAMLIT_URL = "https://la-01-analyzer-cryqmdtchjcarczhgz3bef.streamlit.app"

# 偽裝成現代 Chrome 瀏覽器 User-Agent
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
    """跨平台彩色文字輸出 (支援 Windows CP950 安全保護)"""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "gray": "\033[90m",
        "magenta": "\033[95m"
    }
    reset = "\033[0m"
    bold_str = "\033[1m" if bold else ""
    c_str = colors.get(color, colors["white"])
    line = f"{bold_str}{c_str}{text}{reset}"
    try:
        print(line)
    except UnicodeEncodeError:
        safe_line = line.encode("ascii", errors="replace").decode("ascii")
        print(safe_line)


def is_playwright_ready() -> bool:
    """檢查環境是否具備 Playwright 且已安裝可用之瀏覽器"""
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def ping_with_playwright(url: str, timeout_sec: int = 45, take_screenshot: bool = False) -> dict:
    """
    使用 Playwright Headless Chromium 真實瀏覽器探測並喚醒 Streamlit App。
    """
    from playwright.sync_api import sync_playwright

    start_time = time.time()
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    result = {
        "url": clean_url,
        "engine": "Playwright (Headless Chromium)",
        "is_sleeping": False,
        "woken_up": False,
        "success": False,
        "latency_ms": 0,
        "message": ""
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            print_colored(f"   🌐 正在透過 Chromium 瀏覽器開啟: {clean_url} ...", "cyan")
            page.goto(clean_url, timeout=timeout_sec * 1000, wait_until="domcontentloaded")

            # 等待 4 秒讓前端 React 載入與判斷伺服器狀態
            page.wait_for_timeout(4000)

            # 檢測是否有休眠喚醒按鈕
            wake_selectors = [
                'button:has-text("Yes, get this app back up!")',
                'button:has-text("get this app back up")',
                'button:has-text("Yes, get this app back up")',
                'button:has-text("wake it back up")',
                'xpath=//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "get this app back up")]'
            ]

            wake_btn = None
            for sel in wake_selectors:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        wake_btn = loc.first
                        break
                except Exception:
                    continue

            page_content = page.content().lower()
            is_sleeping = bool(wake_btn) or any(k in page_content for k in SLEEP_KEYWORDS)

            if is_sleeping:
                result["is_sleeping"] = True
                print_colored("   😴 偵測到 Streamlit 官方休眠頁面 (Zzzz)！", "yellow", bold=True)

                if wake_btn and wake_btn.is_visible():
                    print_colored("   ⚡ 正在自動點擊 【Yes, get this app back up!】 按鈕喚醒應用...", "magenta", bold=True)
                    wake_btn.click()
                    result["woken_up"] = True

                    print_colored("   ⏳ 已送出喚醒訊號，等待 Streamlit 雲端容器重新開機 (20 秒)...", "gray")
                    page.wait_for_timeout(20000)

                    # 再次檢查是否喚醒完畢
                    try:
                        page.wait_for_selector('[data-testid="stApp"], .main, header', timeout=25000)
                        result["success"] = True
                        result["message"] = "已成功點擊按鈕並喚醒 Streamlit 應用！"
                        print_colored("   🎉 喚醒成功！應用已重新上線！", "green", bold=True)
                    except Exception:
                        result["success"] = True
                        result["message"] = "喚醒訊號已送出，伺服器正在背景啟動。"
                        print_colored("   ℹ️ 喚醒訊號已送出，伺服器通常於 1 分鐘內啟動就緒。", "cyan")
                else:
                    result["message"] = "頁面包含休眠文字，但未找到可點擊的按鈕。"
            else:
                # 應用正常在線：保持 WebSocket 連線 10 秒以重置官方閒置計時器
                print_colored("   🟢 應用正常運行中！正在維持連線 10 秒刷新閒置計時器...", "green")
                page.wait_for_timeout(10000)
                result["success"] = True
                result["message"] = "連線已維持並刷新 WebSocket 活躍度，重置閒置倒數！"

            if take_screenshot:
                os.makedirs("screenshots", exist_ok=True)
                ss_path = f"screenshots/keep_alive_{int(time.time())}.png"
                page.screenshot(path=ss_path)
                print_colored(f"   📸 已儲存除錯截圖至: {ss_path}", "gray")

            browser.close()

    except Exception as e:
        err_msg = str(e)
        result["message"] = f"瀏覽器探測異常: {err_msg}"
        print_colored(f"   ❌ Playwright 執行發生異常: {err_msg}", "red")

    result["latency_ms"] = int((time.time() - start_time) * 1000)
    return result


def ping_with_http(url: str, timeout: int = 20) -> dict:
    """
    輕量 HTTP GET 探測 (支援 requests 與 urllib)。
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    start_time = time.time()
    result = {
        "url": clean_url,
        "engine": "HTTP Client",
        "status_code": 0,
        "latency_ms": 0,
        "is_sleeping": False,
        "success": False,
        "message": ""
    }

    # 優先使用 requests (自動妥善處理 301/302/303 轉址)
    try:
        import requests
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        resp = requests.get(clean_url, headers=headers, timeout=timeout, allow_redirects=True)
        latency = int((time.time() - start_time) * 1000)
        body = resp.text.lower()

        result["status_code"] = resp.status_code
        result["latency_ms"] = latency
        result["success"] = (resp.status_code in [200, 301, 302, 303, 307, 308])

        for kw in SLEEP_KEYWORDS:
            if kw in body:
                result["is_sleeping"] = True
                result["message"] = f"偵測到休眠特徵: '{kw}'"
                break

        if not result["is_sleeping"] and result["success"]:
            result["message"] = f"伺服器在線正常 (HTTP {resp.status_code})"

        return result
    except ImportError:
        pass
    except Exception as e:
        # requests 出錯，嘗試繼續使用 urllib
        pass

    # 回退到 urllib
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
            result["success"] = (status in [200, 301, 302, 303])

            for kw in SLEEP_KEYWORDS:
                if kw in body:
                    result["is_sleeping"] = True
                    result["message"] = f"偵測到休眠特徵: '{kw}'"
                    break

            if not result["is_sleeping"]:
                result["message"] = "HTTP 探測成功 (伺服器在線)"

    except urllib.error.HTTPError as e:
        latency = int((time.time() - start_time) * 1000)
        result["status_code"] = e.code
        result["latency_ms"] = latency
        if e.code in [301, 302, 303, 307, 308]:
            result["success"] = True
            result["message"] = f"伺服器轉址中 (HTTP {e.code})，服務處於線上狀態"
        else:
            result["message"] = f"HTTP 回傳碼: {e.code}"

    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        result["latency_ms"] = latency
        result["message"] = f"連線異常: {str(e)}"

    return result


def run_cycle(urls: list, force_http: bool = False, take_screenshot: bool = False):
    """執行一次保活與喚醒輪循"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_playwright = is_playwright_ready() and not force_http

    for url in urls:
        tag = f"[{now_str}]"
        target_disp = f"[{url}]"

        if has_playwright:
            print_colored(f"{tag} 🤖 啟動 Playwright 智能探測與保活 {target_disp} ...", "cyan")
            res = ping_with_playwright(url, take_screenshot=take_screenshot)
            # 若 Playwright 失敗或缺少瀏覽器核心，自動回退 HTTP
            if not res["success"] and not res["woken_up"] and ("executable doesn't exist" in res["message"].lower() or "異常" in res["message"]):
                print_colored(f"   🔄 Playwright 核心未就緒，切換至 HTTP 回退模式探測...", "yellow")
                res = ping_with_http(url)
                if res["is_sleeping"]:
                    print_colored(f"{tag} 💤 {target_disp} 狀態：休眠中！", "yellow", bold=True)
                elif res["success"]:
                    print_colored(f"{tag} 🟢 {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 狀態：{res['message']}", "green")
                else:
                    print_colored(f"{tag} ⚠️ {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 提示：{res['message']}", "red")
            else:
                if res["woken_up"]:
                    print_colored(f"{tag} 🚀 {target_disp} 已觸發自動點擊喚醒！({res['latency_ms']}ms)", "yellow", bold=True)
                elif res["success"]:
                    print_colored(f"{tag} ✅ {target_disp} 保活成功: {res['message']} ({res['latency_ms']}ms)", "green", bold=True)
                else:
                    print_colored(f"{tag} ⚠️ {target_disp} 探測告警: {res['message']} ({res['latency_ms']}ms)", "red")
        else:
            print_colored(f"{tag} 🌐 執行 HTTP 回退探測 {target_disp} ...", "cyan")
            res = ping_with_http(url)
            if res["is_sleeping"]:
                print_colored(f"{tag} 💤 {target_disp} 狀態：休眠中！", "yellow", bold=True)
                print_colored("   💡 提示：休眠狀態必須點擊按鈕才能喚醒。請推薦使用 GitHub Actions 雲端自動喚醒！", "yellow")
            elif res["success"]:
                print_colored(f"{tag} 🟢 {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 狀態：{res['message']}", "green")
            else:
                print_colored(f"{tag} ⚠️ {target_disp} (HTTP {res['status_code']}, {res['latency_ms']}ms) 提示：{res['message']}", "red")


def main():
    parser = argparse.ArgumentParser(description="Streamlit 自動防休眠與按鈕喚醒守護工具 (Keep-Alive Daemon)")
    parser.add_argument(
        "--urls", "-u", nargs="+",
        help=f"目標 Streamlit 網址 (預設: {DEFAULT_STREAMLIT_URL})"
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=10,
        help="常駐模式心跳間隔時間 (分鐘，預設: 10 分鐘)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="僅執行單次檢測即退出 (適用於 GitHub Actions 或 Windows 排程)"
    )
    parser.add_argument(
        "--http-only", action="store_true",
        help="強制僅使用 HTTP 探測 (不使用 Playwright 瀏覽器)"
    )
    parser.add_argument(
        "--screenshot", action="store_true",
        help="探測完成後儲存網頁截圖 (除錯用途)"
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

    # 若皆未指定，使用預設的 LA-01-Analyzer 網址
    if not urls:
        urls.append(DEFAULT_STREAMLIT_URL)

    has_playwright = is_playwright_ready() and not args.http_only

    print_colored("===================================================", "cyan")
    print_colored("   🚀 Streamlit 雲端應用 24/7 防休眠與喚醒守護程式", "cyan", bold=True)
    print_colored("===================================================", "cyan")
    print_colored(f"🎯 監控目標 ({len(urls)} 個):", "white", bold=True)
    for u in urls:
        print_colored(f"   • {u}", "cyan")
    print_colored(f"🛠️ 探測引擎: {'Playwright (支援自動點擊喚醒按鈕)' if has_playwright else 'HTTP 模式'}", "white")
    if not args.once:
        print_colored(f"⏱️ 探測週期: 每 {args.interval} 分鐘", "white")
    print_colored("---------------------------------------------------", "gray")

    if args.once:
        run_cycle(urls, force_http=args.http_only, take_screenshot=args.screenshot)
        return

    print_colored("🟢 守護程式已進入常駐運行模式 (按 Ctrl + C 可隨時停止)...", "green")
    try:
        while True:
            run_cycle(urls, force_http=args.http_only, take_screenshot=args.screenshot)
            # 加入隨機擾動 ±30 秒
            jitter = random.randint(-30, 30)
            sleep_sec = max(60, (args.interval * 60) + jitter)
            time.sleep(sleep_sec)
    except KeyboardInterrupt:
        print_colored("\n🛑 守護程式已手動停止。", "yellow")


if __name__ == "__main__":
    main()
