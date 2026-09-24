# -*- coding: utf-8 -*-
"""
intervals_client.py - Intervals.icu API 客戶端模組
支援將 Garmin Connect、COROS 等穿戴設備透過 Intervals.icu 自動同步日常運動數據至 Firebase Firestore。
"""

import os
import re
import base64
import requests
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional


INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
INTERVALS_AUTH_URL = "https://intervals.icu/oauth/authorize"
INTERVALS_TOKEN_URL = "https://intervals.icu/api/oauth/token"


DEFAULT_INTERVALS_CLIENT_ID = "1038"
DEFAULT_INTERVALS_CLIENT_SECRET = "ebb88ff05c8240dd98143baca7764a4f"


def resolve_redirect_uri(configured_uri: str = "") -> str:
    """
    智慧解析 OAuth 回呼網址：
    1. 若已傳入或設定 (secrets 或 env)，直接使用，自動確保包含通訊協定
    2. 若處於 Streamlit 執行環境，嘗試從 st.context.headers 偵測當前 host (例如 assemzyme.com 或 streamlit.app)
    3. 否則預設使用 http://localhost:8501/
    """
    if configured_uri and str(configured_uri).strip():
        u = str(configured_uri).strip()
        if not u.startswith("http://") and not u.startswith("https://"):
            u = "https://" + u
        return u

    try:
        import streamlit as st
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers or {}
            host = headers.get("host", "")
            if host:
                proto = headers.get("x-forwarded-proto", "")
                if not proto:
                    proto = "https" if "localhost" not in host and "127.0.0.1" not in host else "http"
                return f"{proto}://{host}/"
    except Exception:
        pass

    return "http://localhost:8501/"


def get_intervals_oauth_config() -> Dict[str, str]:
    """
    讀取系統設定之 Intervals.icu OAuth Client ID, Client Secret 與 Redirect URI
    優先序: Streamlit secrets -> 環境變數 -> 官方核發之預設金鑰
    """
    client_id = ""
    client_secret = ""
    redirect_uri = ""

    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "intervals" in st.secrets:
                client_id = st.secrets["intervals"].get("client_id", "")
                client_secret = st.secrets["intervals"].get("client_secret", "")
                redirect_uri = st.secrets["intervals"].get("redirect_uri", "")
            else:
                client_id = st.secrets.get("INTERVALS_CLIENT_ID", "")
                client_secret = st.secrets.get("INTERVALS_CLIENT_SECRET", "")
                redirect_uri = st.secrets.get("INTERVALS_REDIRECT_URI", "")
    except Exception:
        pass

    if not client_id:
        client_id = os.environ.get("INTERVALS_CLIENT_ID", "")
    if not client_secret:
        client_secret = os.environ.get("INTERVALS_CLIENT_SECRET", "")
    if not redirect_uri:
        redirect_uri = os.environ.get("INTERVALS_REDIRECT_URI", "")

    # 若未在外部環境變數設定，使用官方核發之正式憑證
    if not client_id:
        client_id = DEFAULT_INTERVALS_CLIENT_ID
    if not client_secret:
        client_secret = DEFAULT_INTERVALS_CLIENT_SECRET

    return {
        "client_id": str(client_id).strip(),
        "client_secret": str(client_secret).strip(),
        "redirect_uri": str(redirect_uri).strip()
    }


def get_intervals_oauth_authorize_url(client_id: str, redirect_uri: str, state: str = "") -> str:
    """
    產生 Intervals.icu OAuth 2.0 授權跳轉網址
    包含 ACTIVITY:READ 與 WELLNESS:READ 權限
    """
    from urllib.parse import urlencode
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "ACTIVITY:READ,WELLNESS:READ",
        "response_type": "code"
    }
    if state:
        params["state"] = state
    return f"{INTERVALS_AUTH_URL}?{urlencode(params)}"


def exchange_intervals_oauth_code(client_id: str, client_secret: str, code: str, redirect_uri: str = "") -> Tuple[bool, Dict[str, Any], str]:
    """
    向 Intervals.icu 交換 OAuth 2.0 Access Token
    回傳: (成功與否, 資料字典, 訊息)
    資料字典包含: access_token, athlete: {id, name}, scope, token_type
    """
    if not client_id or not client_secret or not code:
        return False, {}, "缺少 client_id, client_secret 或 authorization code"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }
    if redirect_uri:
        data["redirect_uri"] = redirect_uri

    try:
        resp = requests.post(INTERVALS_TOKEN_URL, data=data, timeout=12)
        if resp.status_code == 200:
            res_json = resp.json()
            ath = res_json.get("athlete", {})
            ath_name = ath.get("name") or ath.get("id") or "運動員"
            return True, res_json, f"授權成功！歡迎，{ath_name}"
        else:
            err_msg = resp.text[:200]
            return False, {}, f"交換 Token 失敗 (HTTP {resp.status_code}): {err_msg}"
    except Exception as e:
        return False, {}, f"連線逾時或網路錯誤: {e}"


def get_intervals_auth_header(token_or_key: str, is_oauth: bool = False) -> Dict[str, str]:
    """
    產生 Intervals.icu 認證 Header：
    - 若為 OAuth 2.0，使用 Bearer Token：Authorization: Bearer <token>
    - 若為 API Key，使用 Basic Auth：Authorization: Basic <base64(API_KEY:key)>
    """
    t = str(token_or_key).strip() if token_or_key else ""
    if is_oauth:
        return {
            "Authorization": f"Bearer {t}",
            "Content-Type": "application/json"
        }
    token = base64.b64encode(f"API_KEY:{t}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }


def get_basic_auth_header(api_key: str) -> Dict[str, str]:
    """
    向後相容保留：產生 Intervals.icu Basic Auth Header
    """
    return get_intervals_auth_header(api_key, is_oauth=False)


def get_user_intervals_credentials(uid: str, firebase_token: str) -> Dict[str, Any]:
    """
    從 Firestore users/{uid}/settings/intervals_icu 讀取使用者的認證設定
    支援 OAuth 2.0 與傳統 API Key 雙軌
    回傳:
    {
        "configured": bool,
        "auth_type": "oauth" | "api_key" | "none",
        "token": str,
        "athlete_id": str,
        "athlete_name": str,
        "is_oauth": bool
    }
    """
    res = {
        "configured": False,
        "auth_type": "none",
        "token": "",
        "athlete_id": "0",
        "athlete_name": "",
        "is_oauth": False
    }
    if not uid or not firebase_token:
        return res

    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/settings/intervals_icu"
    headers = {"Authorization": f"Bearer {firebase_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            fields = resp.json().get("fields", {})
            auth_type = fields.get("auth_type", {}).get("stringValue", "")
            access_token = fields.get("access_token", {}).get("stringValue", "")
            api_key = fields.get("api_key", {}).get("stringValue", "")
            ath_id = fields.get("athlete_id", {}).get("stringValue", "0")
            ath_name = fields.get("athlete_name", {}).get("stringValue", "")

            if auth_type == "oauth" and access_token:
                res.update({
                    "configured": True,
                    "auth_type": "oauth",
                    "token": access_token,
                    "athlete_id": ath_id,
                    "athlete_name": ath_name,
                    "is_oauth": True
                })
            elif api_key:
                res.update({
                    "configured": True,
                    "auth_type": "api_key",
                    "token": api_key,
                    "athlete_id": ath_id,
                    "athlete_name": ath_name or "API Key 用戶",
                    "is_oauth": False
                })
    except Exception:
        pass
    return res


def save_user_intervals_oauth(
    uid: str,
    firebase_token: str,
    access_token: str,
    athlete_id: str,
    athlete_name: str = "",
    scope: str = ""
) -> bool:
    """
    將 OAuth 2.0 授權結果儲存至 Firestore
    """
    if not uid or not firebase_token or not access_token:
        return False

    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/settings/intervals_icu"
    headers = {"Authorization": f"Bearer {firebase_token}", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "auth_type": {"stringValue": "oauth"},
            "access_token": {"stringValue": access_token},
            "athlete_id": {"stringValue": athlete_id or "0"},
            "athlete_name": {"stringValue": athlete_name},
            "scope": {"stringValue": scope},
            "updated_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
        }
    }
    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=6)
        return resp.status_code in [200, 201]
    except Exception:
        return False


def save_user_intervals_apikey(
    uid: str,
    firebase_token: str,
    api_key: str,
    athlete_id: str = "0"
) -> bool:
    """
    將手動輸入之 API Key 儲存至 Firestore
    """
    if not uid or not firebase_token or not api_key:
        return False

    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/settings/intervals_icu"
    headers = {"Authorization": f"Bearer {firebase_token}", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "auth_type": {"stringValue": "api_key"},
            "api_key": {"stringValue": api_key},
            "athlete_id": {"stringValue": athlete_id or "0"},
            "athlete_name": {"stringValue": ""},
            "updated_at": {"timestampValue": datetime.utcnow().isoformat() + "Z"}
        }
    }
    try:
        resp = requests.patch(url, headers=headers, json=payload, timeout=6)
        return resp.status_code in [200, 201]
    except Exception:
        return False


def disconnect_user_intervals(uid: str, firebase_token: str) -> bool:
    """
    清除 Firestore 中 Intervals.icu 的連線紀錄
    """
    if not uid or not firebase_token:
        return False

    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/settings/intervals_icu"
    headers = {"Authorization": f"Bearer {firebase_token}"}
    try:
        resp = requests.delete(url, headers=headers, timeout=6)
        return resp.status_code in [200, 204]
    except Exception:
        return False


def test_intervals_connection(token_or_key: str, athlete_id: str = "0", is_oauth: bool = False) -> Tuple[bool, str]:
    """
    測試 Intervals.icu 連線 (支援 OAuth 2.0 Bearer 與 API Key Basic)
    回傳 (是否成功, 訊息/運動員名稱)
    """
    if not token_or_key or not str(token_or_key).strip():
        return False, "金鑰或 Token 不能為空"

    ath_id = athlete_id.strip() if athlete_id and athlete_id.strip() else "0"
    url = f"{INTERVALS_BASE_URL}/athlete/{ath_id}"
    headers = get_intervals_auth_header(token_or_key, is_oauth=is_oauth)

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ath_name = data.get("name") or data.get("id") or "運動員"
            return True, f"連線成功！歡迎，{ath_name}"
        elif resp.status_code == 401:
            return False, "授權失敗：憑證無效或已過期"
        elif resp.status_code == 404:
            return False, f"找不到 Athlete ID: {ath_id}，若為個人帳號請填入 0"
        else:
            return False, f"連線失敗 (HTTP {resp.status_code}): {resp.text[:100]}"
    except Exception as e:
        return False, f"連線逾時或網路錯誤: {str(e)}"


def calculate_lactate_surrounding_date_ranges(
    lactate_dates: Optional[List[datetime]] = None,
    lookback_days: int = 7,
    lookahead_days: int = 7,
    include_recent_days: int = 30
) -> List[Tuple[str, str]]:
    """
    根據所有乳酸採樣日期清單，計算每一天的前 N 天 (預設前 1 週 7 天) 至後 M 天 (預設後 1 週 7 天) 的完整區間，
    並預設永遠額外涵蓋「最近 include_recent_days 天 (預設 30 天) 至明天」，
    確保使用者的日常運動與當日最新上傳的運動隨時被同步納入。
    自動合併重疊或相鄰的日期區間，產生最精簡的 (oldest, newest) 清單。
    格式: YYYY-MM-DD
    """
    target_days = set()

    # 1. 涵蓋乳酸採樣日前後區間
    if lactate_dates:
        for dt in lactate_dates:
            d = dt.date() if isinstance(dt, datetime) else dt
            for i in range(-lookahead_days, lookback_days + 1):
                target_days.add(d - timedelta(days=i))

    # 2. 永遠涵蓋最近 include_recent_days 天至明天 (防止當日及近期日常手錶運動漏失)
    if include_recent_days > 0:
        today = date.today()
        # i = -1 對應明天 (today + 1)，0 對應今天，依此類推到 today - include_recent_days
        for i in range(-1, include_recent_days + 1):
            target_days.add(today - timedelta(days=i))

    sorted_days = sorted(target_days)
    if not sorted_days:
        return []

    # 3. 合併連續日期成區間 [start_date, end_date]
    ranges = []
    start_d = sorted_days[0]
    prev_d = start_d

    for current_d in sorted_days[1:]:
        if current_d == prev_d + timedelta(days=1):
            prev_d = current_d
        else:
            ranges.append((start_d.strftime("%Y-%m-%d"), prev_d.strftime("%Y-%m-%d")))
            start_d = current_d
            prev_d = current_d
    ranges.append((start_d.strftime("%Y-%m-%d"), prev_d.strftime("%Y-%m-%d")))

    return ranges


def calculate_pre_lactate_date_ranges(
    lactate_dates: Optional[List[datetime]] = None,
    lookback_days: int = 7,
    lookahead_days: int = 7,
    include_recent_days: int = 30
) -> List[Tuple[str, str]]:
    return calculate_lactate_surrounding_date_ranges(
        lactate_dates,
        lookback_days=lookback_days,
        lookahead_days=lookahead_days,
        include_recent_days=include_recent_days
    )


def fetch_intervals_activities(
    token_or_key: str,
    athlete_id: str = "0",
    oldest: str = None,
    newest: str = None,
    is_oauth: bool = False
) -> List[Dict[str, Any]]:
    """
    從 Intervals.icu 拉取指定日期區間內的活動 (支援 OAuth 2.0 與 API Key)
    oldest, newest 格式: 'YYYY-MM-DD' 或 ISO-8601
    """
    ath_id = athlete_id.strip() if athlete_id and athlete_id.strip() else "0"
    url = f"{INTERVALS_BASE_URL}/athlete/{ath_id}/activities"
    headers = get_intervals_auth_header(token_or_key, is_oauth=is_oauth)
    params = {}
    if oldest:
        params["oldest"] = oldest
    if newest:
        # 若 newest 為 YYYY-MM-DD 格式 (長度 10)，加上 T23:59:59 確保當天全天運動被完整檢索
        if len(newest) == 10:
            params["newest"] = f"{newest}T23:59:59"
        else:
            params["newest"] = newest

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Intervals.icu API Error ({resp.status_code}): {resp.text}")
            return []
    except Exception as e:
        print(f"Error fetching activities from Intervals.icu: {e}")
        return []


def fetch_intervals_wellness(
    token_or_key: str,
    athlete_id: str = "0",
    oldest: str = None,
    newest: str = None,
    is_oauth: bool = False
) -> List[Dict[str, Any]]:
    """
    從 Intervals.icu 下載指定日期區間的每日生理健康與自律神經數據 (Wellness)，包含：
    - hrv: 晨間心率變異度 rMSSD (毫秒 ms)
    - hrvSD: HRV 標準差
    - restingHR: 晨間靜息心率 (bpm)
    - readiness: 身體就緒度分數 (0-100)
    - sleepSecs: 睡眠總秒數
    - sleepScore: 睡眠品質評分
    - fatigue, soreness, stress, mood: 主觀身心疲勞程度 (1-5)
    """
    if not token_or_key:
        return []

    ath_id = athlete_id.strip() if athlete_id and athlete_id.strip() else "0"
    url = f"{INTERVALS_BASE_URL}/athlete/{ath_id}/wellness"
    headers = get_intervals_auth_header(token_or_key, is_oauth=is_oauth)
    params = {}
    if oldest:
        params["oldest"] = oldest
    if newest:
        params["newest"] = newest

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        else:
            print(f"Intervals.icu Wellness API Error ({resp.status_code}): {resp.text[:100]}")
            return []
    except Exception as e:
        print(f"Error fetching wellness from Intervals.icu: {e}")
        return []


def get_intervals_wellness_map(
    token_or_key: str,
    athlete_id: str = "0",
    oldest: str = None,
    newest: str = None,
    is_oauth: bool = False
) -> Dict[str, Dict[str, Any]]:
    """
    下載並回傳以日期字串 ('YYYY-MM-DD') 為 key 的每日 HRV 與生理狀態對照表
    """
    records = fetch_intervals_wellness(token_or_key, athlete_id=athlete_id, oldest=oldest, newest=newest, is_oauth=is_oauth)
    w_map = {}
    for r in records:
        date_k = str(r.get("id", ""))
        if date_k:
            hrv_val = r.get("hrv")
            try:
                hrv_val = round(float(hrv_val), 1) if hrv_val is not None else None
            except (ValueError, TypeError):
                hrv_val = None

            rhr_val = r.get("restingHR")
            try:
                rhr_val = round(float(rhr_val), 1) if rhr_val is not None else None
            except (ValueError, TypeError):
                rhr_val = None

            readiness_val = r.get("readiness")
            try:
                readiness_val = round(float(readiness_val), 1) if readiness_val is not None else None
            except (ValueError, TypeError):
                readiness_val = None

            w_map[date_k] = {
                "date": date_k,
                "hrv": hrv_val,
                "hrv_sd": r.get("hrvSD"),
                "resting_hr": rhr_val,
                "readiness": readiness_val,
                "sleep_hours": round(float(r.get("sleepSecs", 0)) / 3600.0, 1) if r.get("sleepSecs") else None,
                "sleep_score": r.get("sleepScore"),
                "fatigue": r.get("fatigue"),
                "soreness": r.get("soreness"),
                "stress": r.get("stress"),
                "mood": r.get("mood")
            }
    return w_map



def map_intervals_sport_type(icu_type: str) -> Tuple[str, str]:
    """
    將 Intervals.icu 的運動類型映射為 MyLactate 專項 (sport, sub_sport)
    """
    t_lower = str(icu_type).lower() if icu_type else "generic"
    if any(k in t_lower for k in ["ride", "bike", "cycling", "virtualride", "gravel"]):
        sub = "indoor_cycling" if "virtual" in t_lower or "indoor" in t_lower else "road_cycling"
        return "cycling", sub
    elif any(k in t_lower for k in ["run", "trail", "treadmill"]):
        sub = "treadmill" if "treadmill" in t_lower else "generic"
        return "running", sub
    elif any(k in t_lower for k in ["swim"]):
        return "swimming", "generic"
    elif any(k in t_lower for k in ["walk", "hike"]):
        return "walking", "generic"
    elif any(k in t_lower for k in ["row"]):
        return "rowing", "generic"
    else:
        return "generic", "generic"


def extract_intervals_power(act: Dict[str, Any]) -> Tuple[float, float]:
    """
    從 Intervals.icu 活動物件中全方位提取平均功率與最大功率，支援所有官方標準與衍生功率欄位：
    1. 官方平均功率 (average_watts, icu_average_watts)
    2. 加權平均功率 (icu_weighted_avg_watts, weighted_average_watts)
    3. 衍生功率欄位 (normalized_watts, avg_watts, power)
    4. 能量與時間換算 (P = Joules / moving_time)
    """
    if not act or not isinstance(act, dict):
        return 0.0, 0.0
        
    avg_pwr = 0.0
    max_pwr = 0.0
    
    candidates_avg = [
        act.get("average_watts"),
        act.get("icu_average_watts"),
        act.get("icu_weighted_avg_watts"),
        act.get("weighted_average_watts"),
        act.get("avg_watts"),
        act.get("power"),
        act.get("normalized_watts")
    ]
    for c in candidates_avg:
        if c is not None:
            try:
                v = float(c)
                if v > 0:
                    avg_pwr = round(v, 1)
                    break
            except (ValueError, TypeError):
                pass

    if avg_pwr <= 0:
        j_val = act.get("icu_joules") or act.get("joules")
        sec_val = act.get("moving_time") or act.get("elapsed_time")
        if j_val and sec_val:
            try:
                j = float(j_val)
                s = float(sec_val)
                if j > 0 and s > 0:
                    avg_pwr = round(j / s, 1)
            except (ValueError, TypeError):
                pass
                
    candidates_max = [
        act.get("max_watts"),
        act.get("icu_max_watts"),
        act.get("max_power")
    ]
    for c in candidates_max:
        if c is not None:
            try:
                v = float(c)
                if v > 0:
                    max_pwr = round(v, 1)
                    break
            except (ValueError, TypeError):
                pass
                
    return avg_pwr, max_pwr


def fetch_intervals_activity_streams(token_or_key: str, activity_id: str, is_oauth: bool = False) -> Dict[str, List[Any]]:
    """
    從 Intervals.icu 下載活動的詳細數據串流 (streams: time, watts, heartrate, cadence, etc.)
    """
    if not token_or_key or not activity_id:
        return {}
    url = f"{INTERVALS_BASE_URL}/activity/{activity_id}/streams"
    headers = get_intervals_auth_header(token_or_key, is_oauth=is_oauth)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            stream_dict = {}
            if isinstance(data, list):
                for item in data:
                    stype = item.get("type")
                    sdata = item.get("data")
                    if stype and sdata:
                        stream_dict[stype] = sdata
            return stream_dict
        elif resp.status_code == 404:
            alt_url = f"{INTERVALS_BASE_URL}/athlete/0/activities/{activity_id}/streams"
            r_alt = requests.get(alt_url, headers=headers, timeout=10)
            if r_alt.status_code == 200:
                data = r_alt.json()
                stream_dict = {}
                if isinstance(data, list):
                    for item in data:
                        stype = item.get("type")
                        sdata = item.get("data")
                        if stype and sdata:
                            stream_dict[stype] = sdata
                return stream_dict
    except Exception as e:
        print(f"Error fetching activity {activity_id} streams: {e}")
    return {}


def process_intervals_streams_to_30s(stream_dict: Dict[str, List[Any]]) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    將 Intervals.icu 數據串流 (time, watts, heartrate) 降採樣為 30 秒平均 (30s bins)，
    登錄為標準 Firestore time_series 點位 (含 power, power_30s, heart_rate)，
    並計算出整場運動的【總平均功率】與【最大功率】。
    """
    time_arr = stream_dict.get("time", [])
    watts_arr = stream_dict.get("watts", [])
    hr_arr = stream_dict.get("heartrate", [])
    
    if not time_arr:
        return [], 0.0, 0.0
        
    n = len(time_arr)
    bins = {}
    for i in range(n):
        t = float(time_arr[i])
        b_idx = int(t // 30)
        if b_idx not in bins:
            bins[b_idx] = {'pwrs': [], 'hrs': []}
        if i < len(watts_arr) and watts_arr[i] is not None:
            try:
                w = float(watts_arr[i])
                if w >= 0:
                    bins[b_idx]['pwrs'].append(w)
            except (ValueError, TypeError):
                pass
        if i < len(hr_arr) and hr_arr[i] is not None:
            try:
                h = float(hr_arr[i])
                if h > 0:
                    bins[b_idx]['hrs'].append(h)
            except (ValueError, TypeError):
                pass
                
    time_series_points = []
    all_30s_pwrs = []
    max_pwr = 0.0
    
    for b_idx in sorted(bins.keys()):
        b_data = bins[b_idx]
        bin_min = round((b_idx * 30.0) / 60.0, 2)
        pt_fields = {
            "elapsed_minutes": {"doubleValue": bin_min}
        }
        if b_data['pwrs']:
            mean_pwr = round(sum(b_data['pwrs']) / len(b_data['pwrs']), 1)
            pt_fields["power"] = {"doubleValue": mean_pwr}
            pt_fields["power_30s"] = {"doubleValue": mean_pwr}
            all_30s_pwrs.append(mean_pwr)
            if mean_pwr > max_pwr:
                max_pwr = mean_pwr
        if b_data['hrs']:
            mean_hr = round(sum(b_data['hrs']) / len(b_data['hrs']), 1)
            pt_fields["heart_rate"] = {"doubleValue": mean_hr}
            
        time_series_points.append({
            "mapValue": {
                "fields": pt_fields
            }
        })
        
    total_avg_pwr = round(sum(all_30s_pwrs) / len(all_30s_pwrs), 1) if all_30s_pwrs else 0.0
    return time_series_points, total_avg_pwr, max_pwr


def convert_intervals_activity_to_firebase_fit_record(
    act: Dict[str, Any],
    token_or_key: Optional[str] = None,
    is_oauth: bool = False
) -> Dict[str, Any]:
    """
    將 Intervals.icu 的單場活動轉換為標準 Firestore fit_records 格式，
    自動抓取串流並降採樣為 30 秒平均功率數列 (time_series)，計算總平均功率。
    """
    start_str = act.get("start_date_local") or act.get("start_date")
    start_dt = None
    if start_str:
        try:
            clean_ts = start_str.replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(clean_ts)
        except Exception:
            pass

    if not start_dt:
        start_dt = datetime.utcnow()

    icu_type = act.get("type", "Workout")
    sport, sub_sport = map_intervals_sport_type(icu_type)

    moving_time_s = act.get("moving_time") or act.get("elapsed_time") or 0
    duration_min = round(float(moving_time_s) / 60.0, 1)

    avg_pwr, max_pwr = extract_intervals_power(act)
    avg_hr = float(act.get("average_heartrate") or 0.0)
    max_hr = float(act.get("max_heartrate") or 0.0)
    tot_dist = float(act.get("distance") or 0.0)
    tot_elev = float(act.get("total_elevation_gain") or 0.0)
    training_load = float(act.get("icu_training_load") or act.get("trimp") or 0.0)
    intensity = float(act.get("icu_intensity") or 0.0)
    cadence = float(act.get("average_cadence") or 0.0)
    act_id = str(act.get("id", ""))
    act_name = act.get("name", f"{sport.capitalize()} Session")

    # 嘗試抓取 30 秒串流數據
    time_series_points = []
    if token_or_key and act_id:
        streams = fetch_intervals_activity_streams(token_or_key, act_id, is_oauth=is_oauth)
        if streams:
            ts_pts, stream_avg_pwr, stream_max_pwr = process_intervals_streams_to_30s(streams)
            if ts_pts:
                time_series_points = ts_pts
            if stream_avg_pwr > 0:
                avg_pwr = stream_avg_pwr
            if stream_max_pwr > max_pwr:
                max_pwr = stream_max_pwr

    clean_time = start_dt.strftime("%Y%m%d_%H%M%S")
    doc_id = f"fit_{clean_time}_icu_{act_id}"

    payload = {
        "fields": {
            "file_name": {"stringValue": f"intervals_{act_id}_{icu_type}.fit"},
            "activity_name": {"stringValue": act_name},
            "start_time": {"timestampValue": start_dt.isoformat() + "Z"},
            "sport": {"stringValue": sport},
            "sub_sport": {"stringValue": sub_sport},
            "duration_minutes": {"doubleValue": duration_min},
            "avg_power": {"integerValue": str(int(avg_pwr))},
            "max_power": {"integerValue": str(int(max_pwr))},
            "avg_hr": {"integerValue": str(int(avg_hr))},
            "max_hr": {"integerValue": str(int(max_hr))},
            "total_distance_m": {"doubleValue": round(tot_dist, 1)},
            "elevation_gain_m": {"doubleValue": round(tot_elev, 1)},
            "cadence": {"integerValue": str(int(cadence))},
            "icu_training_load": {"doubleValue": round(training_load, 1)},
            "icu_intensity": {"doubleValue": round(intensity, 2)},
            "source": {"stringValue": "intervals_icu"},
            "has_lactate": {"booleanValue": False}, # 標記為日常訓練（無採樣乳酸）
            "time_series": {"arrayValue": {"values": time_series_points}}
        }
    }

    return {
        "doc_id": doc_id,
        "start_time": start_dt,
        "payload": payload,
        "raw": act
    }


def sync_pre_lactate_activities_to_firebase(
    uid: str,
    firebase_token: str,
    intervals_api_key: str,
    athlete_id: str = "0",
    lookback_days: int = 7,
    lookahead_days: int = 7,
    is_oauth: bool = False,
    incremental_only: bool = False,
    force_overwrite: bool = False
) -> Tuple[int, int, str]:
    """
    高階整合同步主函式 (支援 OAuth 2.0 與 API Key 雙軌、增量極速模式)：
    1. 抓取 Firestore 現有 fit_records，識別已存在的活動 ID 與最新運動時間。
    2. 若啟用 incremental_only (增量模式)，僅查詢最新運動日期至明天的極小範圍；否則全量掃描。
    3. 呼叫 Intervals.icu 抓取日常運動清單。
    4. ⚡ 核心提速：若該活動 ID 已在 Firebase 且非 force_overwrite，直接跳過！不浪費頻寬下載串流與寫入。
    5. 僅針對 Firebase 尚未收錄的新運動下載串流並寫入 Firestore。
    回傳: (同步成功筆數, 跳過重疊筆數, 訊息)
    """
    if not uid or not firebase_token:
        return 0, 0, "未登入 Firebase 雲端帳號"
    if not intervals_api_key:
        return 0, 0, "未提供 Intervals.icu 認證憑證 (API Key 或 OAuth Token)"

    headers_fb = {"Authorization": f"Bearer {firebase_token}", "Content-Type": "application/json"}

    # 1. 抓取現有的 fit_records 以便精準去重與推算最新記錄日期
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records?pageSize=300"
    lactate_test_times = []
    icu_id_to_doc = {}        # 依照 Intervals 原生 activity_id 映射
    icu_time_to_doc = {}      # 依照活動時間（5分鐘窗）映射
    latest_fit_dt = None
    try:
        r_fit = requests.get(fit_url, headers=headers_fb, timeout=12)
        if r_fit.status_code == 200:
            for doc in r_fit.json().get("documents", []):
                fields = doc.get("fields", {})
                st_val = fields.get("start_time", {}).get("timestampValue")
                src = fields.get("source", {}).get("stringValue", "")
                has_la = fields.get("has_lactate", {}).get("booleanValue", False)
                doc_name = doc.get("name", "").split("/")[-1]
                
                # 提取 intervals_act_id
                icu_id = fields.get("intervals_act_id", {}).get("stringValue", "")
                if not icu_id and "_icu_" in doc_name:
                    icu_id = doc_name.split("_icu_")[-1]
                if icu_id:
                    icu_id_to_doc[str(icu_id)] = doc_name

                if st_val:
                    try:
                        clean_ts = st_val.replace("Z", "+00:00")
                        dt_obj = datetime.fromisoformat(clean_ts)
                        if latest_fit_dt is None or dt_obj > latest_fit_dt:
                            latest_fit_dt = dt_obj
                        # 若不是 intervals_icu 或者有乳酸測試，屬於不可覆蓋的原創測驗
                        if src != "intervals_icu" or has_la:
                            lactate_test_times.append(dt_obj)
                        else:
                            icu_time_to_doc[doc_name] = dt_obj
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error fetching existing fit sessions: {e}")

    # 2. 計算同步日期區間
    if incremental_only and latest_fit_dt:
        # 增量模式：Firebase 已有數據，僅查詢最新一筆運動前 2 天 (防時區差) 至明天的極窄區間
        oldest_d = (latest_fit_dt - timedelta(days=2)).date()
        newest_d = date.today() + timedelta(days=1)
        date_ranges = [(oldest_d.strftime("%Y-%m-%d"), newest_d.strftime("%Y-%m-%d"))]
    else:
        # 全量模式：讀取所有乳酸檢測日期，計算乳酸日前後 7 天並納入最近 30 天日常運動
        la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records"
        lactate_dates = []
        try:
            r_la = requests.get(la_url, headers=headers_fb, timeout=10)
            if r_la.status_code == 200:
                la_docs = r_la.json().get("documents", [])
                for doc in la_docs:
                    f = doc.get("fields", {})
                    year = int(f.get("year", {}).get("integerValue", 0))
                    month = int(f.get("month", {}).get("integerValue", 0))
                    day = int(f.get("day", {}).get("integerValue", 0))
                    if year > 0 and month > 0 and day > 0:
                        full_year = year + 2000 if year < 100 else year
                        lactate_dates.append(datetime(full_year, month, day))
        except Exception as e:
            print(f"Error fetching lactate dates: {e}")

        date_ranges = calculate_lactate_surrounding_date_ranges(
            lactate_dates,
            lookback_days=lookback_days,
            lookahead_days=lookahead_days,
            include_recent_days=30
        )

    if not date_ranges:
        return 0, 0, "未找到有效的同步日期區間"

    # 3. 依區間從 Intervals.icu 抓取活動清單 (輕量級 Summary)
    all_activities = []
    seen_act_ids = set()
    for oldest, newest in date_ranges:
        acts = fetch_intervals_activities(
            intervals_api_key, athlete_id=athlete_id, oldest=oldest, newest=newest, is_oauth=is_oauth
        )
        for a in acts:
            aid = str(a.get("id"))
            if aid not in seen_act_ids:
                seen_act_ids.add(aid)
                all_activities.append(a)

    if not all_activities:
        return 0, 0, f"在覆蓋的日期區間內，Intervals.icu 未查到任何運動紀錄"

    # 4. 轉換並寫入 Firestore (僅針對尚未收錄的新運動下載串流)
    synced_count = 0
    skipped_count = 0

    base_fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records"

    for act in all_activities:
        act_id_str = str(act.get("id", ""))

        # ⚡ 核心極速過濾：若該活動 ID 已在 Firebase 且非強制覆蓋，直接跳過！
        # 完全不呼叫 fetch_intervals_activity_streams，也不發送 PATCH 請求，0 毫秒完成！
        if not force_overwrite and act_id_str and act_id_str in icu_id_to_doc:
            skipped_count += 1
            continue

        # 只有真正缺漏的新活動才執行耗時的串流下載與特徵轉換
        rec = convert_intervals_activity_to_firebase_fit_record(act, token_or_key=intervals_api_key, is_oauth=is_oauth)
        act_start = rec["start_time"]

        # 寫入 intervals_act_id 標記以利後續 100% 精準去重
        if act_id_str:
            rec["payload"]["fields"]["intervals_act_id"] = {"stringValue": act_id_str}

        # 防覆蓋檢查：如果該時段 (前後 5 分鐘內) 有真正的原版乳酸測驗，跳過寫入，防覆蓋乳酸測驗！
        is_lactate_conflict = False
        act_start_naive = act_start.replace(tzinfo=None)
        for ex_dt in lactate_test_times:
            if abs((act_start_naive - ex_dt.replace(tzinfo=None)).total_seconds()) <= 300:
                is_lactate_conflict = True
                break

        if is_lactate_conflict:
            skipped_count += 1
            continue

        # 若是日常手錶運動，精準比對既有記錄進行 PATCH 覆蓋更新
        doc_id = rec["doc_id"]
        if act_id_str and act_id_str in icu_id_to_doc:
            doc_id = icu_id_to_doc[act_id_str]
        else:
            # 輔助比對：前後 3 分鐘內且同屬 intervals_icu 的紀錄
            for exist_name, exist_time in icu_time_to_doc.items():
                if abs((act_start_naive - exist_time.replace(tzinfo=None)).total_seconds()) <= 180:
                    doc_id = exist_name
                    break

        post_url = f"{base_fit_url}/{doc_id}"
        try:
            r_post = requests.patch(post_url, headers=headers_fb, json=rec["payload"], timeout=10)
            if r_post.status_code in [200, 201]:
                synced_count += 1
                if act_id_str:
                    icu_id_to_doc[act_id_str] = doc_id
                icu_time_to_doc[doc_id] = act_start
            else:
                print(f"Failed to upsert Intervals activity {doc_id}: {r_post.text}")
        except Exception as e:
            print(f"Error upserting activity {doc_id}: {e}")

    if synced_count > 0:
        msg = f"Intervals.icu 同步完成！已更新 {synced_count} 筆最新訓練數據，跳過 {skipped_count} 筆已存在或重疊紀錄。"
    else:
        msg = f"Intervals.icu 已檢查完成，日常運動皆已收錄於雲端（無新數據需更新）。"
    return synced_count, skipped_count, msg
