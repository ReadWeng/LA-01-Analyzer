import requests
import streamlit as st
import json
import base64
import time
from datetime import datetime

FIREBASE_API_KEY = "AIzaSyAhU1n_IIF7AEHXkrQCoToR3gkKe2umpuM"

def ensure_user_profile_in_firestore(uid, email, token, display_name=None):
    """
    確保 Firebase Firestore 中的 users/{uid} 根文件必定標記 email 與最後登入時間。
    使用 updateMask 進行 upsert，若文件不存在則自動建立，若已存在則安全合併欄位。
    """
    if not uid or not email or not token:
        return
    
    clean_email = str(email).strip()
    if not clean_email or "@" not in clean_email:
        return

    now_iso = datetime.utcnow().isoformat() + "Z"
    fields = {
        "email": {"stringValue": clean_email},
        "last_login": {"timestampValue": now_iso}
    }
    field_paths = ["email", "last_login"]
    
    if display_name:
        fields["display_name"] = {"stringValue": str(display_name).strip()}
        field_paths.append("display_name")
        
    mask_str = "&".join([f"updateMask.fieldPaths={fp}" for fp in field_paths])
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}?{mask_str}"
    
    payload = {
        "fields": fields
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.patch(url, headers=headers, json=payload, timeout=4)
        if r.status_code in [200, 201]:
            st.session_state["_user_email_synced_to_firestore"] = uid
        else:
            print(f"寫入 users/{uid} email 失敗 ({r.status_code}): {r.text[:100]}")
    except Exception as e:
        print(f"連線寫入 users/{uid} 失敗: {e}")

ADMIN_EMAILS = ["bigporpoise@gmail.com"]

def load_coach_roster(admin_uid, token):
    """從 Firestore 教練個人設定讀取常設自訂選手名冊"""
    if not admin_uid or not token:
        return []
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{admin_uid}/settings/coach_roster"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            fields = r.json().get("fields", {})
            roster_str = fields.get("roster_json", {}).get("stringValue", "[]")
            return json.loads(roster_str)
    except Exception:
        pass
    return []

def save_coach_roster(admin_uid, token, roster_list):
    """將常設自訂選手名冊儲存至 Firestore 教練個人設定"""
    if not admin_uid or not token:
        return
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{admin_uid}/settings/coach_roster"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "roster_json": {"stringValue": json.dumps(roster_list, ensure_ascii=False)},
            "updated_at": {"timestampValue": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
        }
    }
    try:
        requests.patch(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

def lookup_firestore_user_by_email(email_query, token):
    """透過 Firestore runQuery 尋找指定 email 的使用者文件 UID"""
    if not email_query or not token:
        return None
    url = "https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents:runQuery"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "users"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "email"},
                    "op": "EQUAL",
                    "value": {"stringValue": email_query.strip().lower()}
                }
            },
            "limit": 1
        }
    }
    try:
        r = requests.post(url, headers=headers, json=query, timeout=5)
        if r.status_code == 200:
            for item in r.json():
                doc = item.get("document", {})
                d_name = doc.get("name", "")
                if "/users/" in d_name:
                    uid = d_name.split("/users/")[1].split("/")[0]
                    fields = doc.get("fields", {})
                    disp_name = fields.get("display_name", {}).get("stringValue", "")
                    return {
                        "uid": uid,
                        "email": email_query.strip().lower(),
                        "display_name": disp_name
                    }
    except Exception:
        pass
    return None

def lookup_firestore_user_by_uid(uid_query, token):
    """直接嘗試讀取指定 UID 的使用者檔案"""
    if not uid_query or not token:
        return None
    clean_uid = uid_query.strip()
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{clean_uid}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            fields = r.json().get("fields", {})
            return {
                "uid": clean_uid,
                "email": fields.get("email", {}).get("stringValue", ""),
                "display_name": fields.get("display_name", {}).get("stringValue", "")
            }
    except Exception:
        pass
    return None

def get_all_firestore_athletes(token, admin_uid=None):
    """
    教練/管理員專用：讀取 Firestore 所有運動員清單。
    策略 1: 直接讀取 users 集合下的文件。
    策略 2: 若 users 根文件未被讀取或權限受限，透過 collectionGroup 跨用戶掃描 fit_records 與 lactate_records 發現所有運動員 UID。
    策略 3: 自動載入教練儲存的常設自訂選手名冊。
    回傳: (athletes: list, debug_msg: str)
    """
    if not token:
        return [], "未提供認證 Token"
    
    headers = {"Authorization": f"Bearer {token}"}
    athletes_dict = {}
    debug_notes = []

    # 1. 嘗試直接列舉 users 根集合
    url_users = "https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users?pageSize=300"
    try:
        r_u = requests.get(url_users, headers=headers, timeout=6)
        if r_u.status_code == 200:
            docs = r_u.json().get("documents", [])
            debug_notes.append(f"users根集合回傳 {len(docs)} 筆文件")
            for d in docs:
                doc_name = d.get("name", "")
                uid = doc_name.split("/")[-1] if doc_name else ""
                fields = d.get("fields", {})
                email = fields.get("email", {}).get("stringValue", "")
                disp_name = fields.get("display_name", {}).get("stringValue", "")
                last_login = fields.get("last_login", {}).get("timestampValue", "")
                if uid:
                    display_label = email or disp_name or f"選手 ({uid[:8]}...)"
                    if disp_name and email and disp_name != email:
                        display_label = f"{disp_name} ({email})"
                    athletes_dict[uid] = {
                        "uid": uid,
                        "email": email,
                        "display_name": disp_name,
                        "label": display_label,
                        "last_login": last_login
                    }
        else:
            debug_notes.append(f"users集合讀取受限 (HTTP {r_u.status_code})")
    except Exception as e:
        debug_notes.append(f"連線users異常: {e}")

    # 2. 補充策略：若只找到 1 筆或權限無法 list users，透過 collectionGroup 深度發現所有活躍選手
    if len(athletes_dict) <= 1:
        cg_url = "https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents:runQuery"
        found_uids = set()
        for col_name in ["fit_records", "lactate_records"]:
            cg_query = {
                "structuredQuery": {
                    "from": [{"collectionId": col_name, "allDescendants": True}],
                    "limit": 100
                }
            }
            try:
                r_cg = requests.post(cg_url, headers=headers, json=cg_query, timeout=5)
                if r_cg.status_code == 200:
                    for item in r_cg.json():
                        d_name = item.get("document", {}).get("name", "")
                        if "/users/" in d_name:
                            parts = d_name.split("/users/")[1].split("/")
                            if parts and parts[0] and parts[0] not in athletes_dict:
                                found_uids.add(parts[0])
            except Exception:
                pass
        
        if found_uids:
            debug_notes.append(f"跨集合探索發現 {len(found_uids)} 位活躍用戶")
            for u in found_uids:
                u_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{u}"
                u_email = ""
                u_disp = ""
                try:
                    r_single = requests.get(u_url, headers=headers, timeout=3)
                    if r_single.status_code == 200:
                        f_single = r_single.json().get("fields", {})
                        u_email = f_single.get("email", {}).get("stringValue", "")
                        u_disp = f_single.get("display_name", {}).get("stringValue", "")
                except Exception:
                    pass
                lbl = f"{u_disp} ({u_email})" if (u_disp and u_email) else (u_email or (f"{u_disp} ({u[:8]}...)" if u_disp else f"選手 ({u[:8]}...)"))
                athletes_dict[u] = {
                    "uid": u,
                    "email": u_email,
                    "display_name": u_disp,
                    "label": lbl,
                    "last_login": ""
                }

    # 3. 補充策略：載入教練儲存的常設自訂選手名冊
    if admin_uid:
        persisted_roster = load_coach_roster(admin_uid, token)
        if persisted_roster:
            debug_notes.append(f"載入 {len(persisted_roster)} 位常設名冊選手")
            for p in persisted_roster:
                p_uid = p.get("uid")
                if p_uid and p_uid not in athletes_dict:
                    athletes_dict[p_uid] = p

    athletes = list(athletes_dict.values())
    athletes = sorted(athletes, key=lambda x: x["label"].lower())
    return athletes, "；".join(debug_notes)

def parse_jwt_payload(token):
    """解析 JWT Payload 以取得 iat (簽發時間) 與 exp (過期時間)"""
    try:
        parts = token.split(".")
        if len(parts) == 3:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except Exception:
        pass
    return {}

def logout_firebase():
    """徹底清除所有 Firebase 登入狀態、暫存與 Streamlit OIDC Cookie，回到乾淨登入頁面"""
    keys_to_clear = [
        "firebase_uid", "firebase_email", "firebase_token", "firebase_refresh_token",
        "cached_weekly_report_html", "cached_report_key", "google_token_processed",
        "intervals_api_key", "intervals_athlete_id", "_user_email_synced_to_firestore"
    ]
    for k in list(st.session_state.keys()):
        if str(k).startswith("intervals_auto_synced_") or str(k).startswith("cal_cache_data_"):
            keys_to_clear.append(k)
    for k in keys_to_clear:
        st.session_state.pop(k, None)
    if hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
        try:
            st.logout()
        except Exception:
            pass
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()

def login_with_google_id_token(id_token):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
    payload = {
        "postBody": f"id_token={id_token}&providerId=google.com",
        "requestUri": "https://lactatecloud.firebaseapp.com",
        "returnIdpCredential": True,
        "returnSecureToken": True
    }
    try:
        res = requests.post(url, json=payload, timeout=8)
        data = res.json()
        if "localId" in data:
            u_uid = data["localId"]
            u_token = data["idToken"]
            u_email = data.get("email", "")
            st.session_state["firebase_uid"] = u_uid
            st.session_state["firebase_token"] = u_token
            st.session_state["firebase_refresh_token"] = data.get("refreshToken", "")
            st.session_state["firebase_email"] = u_email
            ensure_user_profile_in_firestore(u_uid, u_email, u_token, display_name=data.get("displayName"))
            st.session_state.pop("cached_weekly_report_html", None)
            st.session_state.pop("cached_report_key", None)
            return True, "成功"
        else:
            return False, data.get("error", {}).get("message", "未知錯誤")
    except Exception as e:
        return False, str(e)

def refresh_firebase_token():
    """當 token 過期 (401) 時自動透過 refreshToken 換取全新 idToken"""
    ref_token = st.session_state.get("firebase_refresh_token")
    if not ref_token:
        return False
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": ref_token
    }
    try:
        res = requests.post(url, data=payload, timeout=6)
        if res.status_code == 200:
            d = res.json()
            st.session_state["firebase_token"] = d.get("id_token")
            st.session_state["firebase_refresh_token"] = d.get("refresh_token", ref_token)
            return True
    except Exception:
        pass
    return False

# 檢查 Streamlit 原生 Google OIDC 登入狀態
if hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
    if "firebase_uid" not in st.session_state:
        g_token = None
        # 從 st.user.tokens 提取 token (支援 dict 或 Mapping 物件)
        tokens_obj = getattr(st.user, "tokens", None)
        if tokens_obj is not None:
            if hasattr(tokens_obj, "get"):
                g_token = tokens_obj.get("id") or tokens_obj.get("id_token") or tokens_obj.get("access") or tokens_obj.get("access_token")
            elif isinstance(tokens_obj, dict):
                g_token = tokens_obj.get("id") or tokens_obj.get("id_token") or tokens_obj.get("access") or tokens_obj.get("access_token")
        
        # 兼容性：檢查 st.user 字典屬性
        if not g_token and hasattr(st.user, "get"):
            g_token = st.user.get("id_token") or st.user.get("id") or st.user.get("access_token")

        if g_token:
            is_jwt = isinstance(g_token, str) and g_token.count(".") == 2
            
            # 若為 JWT，檢查是否為已過期憑證
            if is_jwt:
                payload_info = parse_jwt_payload(g_token)
                exp = payload_info.get("exp", 0)
                now_ts = time.time()
                # 若憑證已過期，嘗試由 refresh_token 自動換新，不主動強行登出用戶
                if exp > 0 and now_ts > exp:
                    refresh_firebase_token()

            post_body = f"id_token={g_token}&providerId=google.com" if is_jwt else f"access_token={g_token}&providerId=google.com"
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
            payload = {
                "postBody": post_body,
                "requestUri": "https://lactatecloud.firebaseapp.com",
                "returnIdpCredential": True,
                "returnSecureToken": True
            }
            try:
                res = requests.post(url, json=payload, timeout=8)
                data = res.json()
                if "localId" in data:
                    u_uid = data["localId"]
                    u_token = data["idToken"]
                    user_email = data.get("email", getattr(st.user, "email", ""))
                    st.session_state["firebase_uid"] = u_uid
                    st.session_state["firebase_token"] = u_token
                    st.session_state["firebase_refresh_token"] = data.get("refreshToken", "")
                    st.session_state["firebase_email"] = user_email
                    ensure_user_profile_in_firestore(
                        u_uid,
                        user_email,
                        u_token,
                        display_name=data.get("displayName", getattr(st.user, "name", None))
                    )
                    if "pending_intervals_oauth" in st.session_state:
                        import intervals_client as ic
                        p_data = st.session_state.pop("pending_intervals_oauth")
                        ic.save_user_intervals_oauth(
                            uid=u_uid,
                            firebase_token=u_token,
                            access_token=p_data.get("access_token", ""),
                            athlete_id=p_data.get("athlete_id", "0"),
                            athlete_name=p_data.get("athlete_name", ""),
                            scope=p_data.get("scope", "")
                        )
                    st.session_state.pop("cached_weekly_report_html", None)
                    st.session_state.pop("cached_report_key", None)
                    st.session_state.pop(f"intervals_auto_synced_{u_uid}", None)
                    st.rerun()
                else:
                    # Token 暫時無效：不調用 st.logout()，僅在畫面上提示，避免強行登出使用者
                    pass
            except Exception:
                pass

# 檢查相容 Query Params (如果有其他地方轉跳)
if "google_uid" in st.query_params:
    qp_uid = st.query_params.get("google_uid")
    qp_email = st.query_params.get("google_email", "")
    qp_token = st.query_params.get("google_token", "")
    st.session_state["firebase_uid"] = qp_uid
    st.session_state["firebase_email"] = qp_email
    st.session_state["firebase_token"] = qp_token
    ensure_user_profile_in_firestore(qp_uid, qp_email, qp_token)
    st.session_state.pop("cached_weekly_report_html", None)
    st.session_state.pop("cached_report_key", None)
    st.query_params.clear()
    st.rerun()

# 檢查 Intervals.icu OAuth 2.0 回呼跳轉 (Authorization Code Grant)
if "code" in st.query_params and str(st.query_params.get("state", "")).startswith("icu_"):
    oauth_code = st.query_params.get("code")
    target_uid = str(st.query_params.get("state", ""))[4:]
    cur_uid = st.session_state.get('firebase_uid')
    cur_token = st.session_state.get('firebase_token')

    effective_uid = cur_uid or target_uid
    if effective_uid:
        import intervals_client as ic
        oauth_cfg = ic.get_intervals_oauth_config()
        if oauth_cfg["client_id"] and oauth_cfg["client_secret"]:
            saved_redirect = st.session_state.get("intervals_active_redirect_uri")
            redirect_target = ic.resolve_redirect_uri(saved_redirect or oauth_cfg["redirect_uri"])
            ok, tok_data, msg = ic.exchange_intervals_oauth_code(
                client_id=oauth_cfg["client_id"],
                client_secret=oauth_cfg["client_secret"],
                code=oauth_code,
                redirect_uri=redirect_target
            )
            if ok:
                ath = tok_data.get("athlete", {})
                ath_id = str(ath.get("id", "0"))
                ath_name = ath.get("name") or ath_id
                acc_tok = tok_data.get("access_token", "")
                if cur_token:
                    ic.save_user_intervals_oauth(
                        uid=effective_uid,
                        firebase_token=cur_token,
                        access_token=acc_tok,
                        athlete_id=ath_id,
                        athlete_name=ath_name,
                        scope=tok_data.get("scope", "")
                    )
                else:
                    st.session_state["pending_intervals_oauth"] = {
                        "uid": effective_uid,
                        "access_token": acc_tok,
                        "athlete_id": ath_id,
                        "athlete_name": ath_name,
                        "scope": tok_data.get("scope", "")
                    }
                st.session_state["intervals_oauth_connected"] = True
                st.session_state["intervals_athlete_id"] = ath_id
                st.session_state["intervals_athlete_name"] = ath_name
                st.session_state["intervals_api_key"] = acc_tok
                st.session_state["intervals_is_oauth"] = True
                st.toast(f"🎉 Intervals.icu 授權成功！已連結運動員：{ath_name}", icon="✅")
            else:
                st.error(f"❌ Intervals.icu OAuth 授權失敗: {msg}")

    for q_param in ["code", "state", "scope"]:
        if q_param in st.query_params:
            del st.query_params[q_param]
    st.rerun()

def login_to_firebase(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email.strip(),
        "password": password,
        "returnSecureToken": True
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        data = res.json()
        if "localId" in data:
            u_uid = data["localId"]
            u_token = data["idToken"]
            st.session_state["firebase_uid"] = u_uid
            st.session_state["firebase_token"] = u_token
            st.session_state["firebase_refresh_token"] = data.get("refreshToken", "")
            st.session_state["firebase_email"] = email
            ensure_user_profile_in_firestore(
                u_uid,
                email,
                u_token,
                display_name=data.get("displayName")
            )
            if "pending_intervals_oauth" in st.session_state:
                import intervals_client as ic
                p_data = st.session_state.pop("pending_intervals_oauth")
                ic.save_user_intervals_oauth(
                    uid=u_uid,
                    firebase_token=u_token,
                    access_token=p_data.get("access_token", ""),
                    athlete_id=p_data.get("athlete_id", "0"),
                    athlete_name=p_data.get("athlete_name", ""),
                    scope=p_data.get("scope", "")
                )
            st.session_state.pop("cached_weekly_report_html", None)
            st.session_state.pop("cached_report_key", None)
            st.session_state.pop(f"intervals_auto_synced_{u_uid}", None)
            st.sidebar.success("MyLactate 雲端登入成功！")
            st.rerun()
        else:
            error_message = data.get("error", {}).get("message", "未知錯誤")
            if "INVALID_LOGIN_CREDENTIALS" in error_message or "EMAIL_NOT_FOUND" in error_message or "INVALID_PASSWORD" in error_message:
                error_message = "帳號或密碼錯誤，請重新確認或點選下方忘記密碼。"
            st.sidebar.error(f"登入失敗: {error_message}")
    except Exception as e:
        st.sidebar.error(f"網路連線失敗: {str(e)}")

def register_to_firebase(email, password):
    if not email or not password:
        st.sidebar.error("請輸入完整的電子郵件與密碼！")
        return
    if len(password) < 6:
        st.sidebar.error("密碼長度須至少為 6 位數！")
        return
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email.strip(),
        "password": password,
        "returnSecureToken": True
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        data = res.json()
        if "localId" in data:
            u_uid = data["localId"]
            u_token = data["idToken"]
            st.session_state["firebase_uid"] = u_uid
            st.session_state["firebase_token"] = u_token
            st.session_state["firebase_refresh_token"] = data.get("refreshToken", "")
            st.session_state["firebase_email"] = email
            ensure_user_profile_in_firestore(
                u_uid,
                email,
                u_token
            )
            st.session_state.pop("cached_weekly_report_html", None)
            st.session_state.pop("cached_report_key", None)
            st.sidebar.success("MyLactate 帳號註冊成功並已登入！")
            st.rerun()
        else:
            err = data.get("error", {}).get("message", "註冊失敗")
            if "EMAIL_EXISTS" in err:
                err = "此電子郵件已存在，請直接登入或使用忘記密碼。"
            st.sidebar.error(f"註冊失敗: {err}")
    except Exception as e:
        st.sidebar.error(f"網路連線失敗: {str(e)}")


def reset_firebase_password(email):
    if not email:
        st.sidebar.error("請輸入欲重設密碼的電子郵件 (Email)！")
        return
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email.strip()
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        data = res.json()
        if "email" in data:
            st.sidebar.success(f"密碼重設信件已寄出至 {email}，請查收信箱並設定新密碼！")
        else:
            err = data.get("error", {}).get("message", "未知錯誤")
            if "EMAIL_NOT_FOUND" in err:
                err = "此電子郵件尚未註冊！"
            st.sidebar.error(f"發送重設信失敗: {err}")
    except Exception as e:
        st.sidebar.error(f"連線失敗: {str(e)}")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import fitparse
from datetime import datetime, timedelta
import io
import os
import sys
import glob
import re
import streamlit.components.v1 as components

# Append LactateReport folder for importing the integration library
sys.path.append(os.path.abspath("LactateReport"))
try:
    import integrate_reports
    import importlib
    importlib.reload(integrate_reports)
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "LactateReport"))
    import integrate_reports
    import importlib
    importlib.reload(integrate_reports)

def generate_html_report(df_summary, fig, start_time, file_name, metrics):
    plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True})
    
    # Render summary table as HTML
    table_html = df_summary.to_html(index=False, classes="summary-table")
    
    # Metrics breakdown
    duration_str = metrics['duration_str']
    power_str = f"{metrics['avg_power']} / {metrics['max_power']} W"
    hr_str = f"{metrics['avg_hr']} / {metrics['max_hr']} bpm"
    core_str = f"{metrics['max_core']:.2f} °C" if metrics['max_core'] is not None else "未偵測"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FIT 檔與乳酸協同分析報告 - {file_name}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@300;400;600;700&display=swap');
        body {{
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'Outfit', 'Inter', sans-serif;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(90deg, #00e676, #00b0ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #8b949e;
            font-size: 1.1rem;
            margin-bottom: 30px;
        }}
        .metadata-bar {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 0.95rem;
            margin-bottom: 30px;
            color: #8b949e;
        }}
        .metadata-bar strong {{
            color: #ffffff;
        }}
        .kpi-container {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            text-align: center;
        }}
        .kpi-label {{
            font-size: 0.85rem;
            color: #8b949e;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .kpi-value {{
            font-size: 1.6rem;
            font-weight: 700;
        }}
        .section-title {{
            font-size: 1.8rem;
            font-weight: 600;
            margin-top: 40px;
            margin-bottom: 20px;
            border-left: 4px solid #00e676;
            padding-left: 15px;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            overflow: hidden;
        }}
        .summary-table th, .summary-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .summary-table th {{
            background-color: rgba(255, 255, 255, 0.05);
            color: #ffffff;
            font-weight: 600;
        }}
        .summary-table tr:hover {{
            background-color: rgba(255, 255, 255, 0.04);
        }}
        .chart-container {{
            background: rgba(30, 30, 38, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 40px;
        }}
        .footer {{
            text-align: center;
            color: #8b949e;
            font-size: 0.85rem;
            margin-top: 60px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🩸 FIT 檔與乳酸協同分析報告</div>
        <div class="subtitle">生理指標對照與乳酸動力學分析結果</div>
        
        <div class="metadata-bar">
            📅 <strong>活動開始時間</strong>: {start_time.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 
            📄 <strong>檔案名稱</strong>: {file_name}
        </div>
        
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">⏱️ 活動時長</div>
                <div class="kpi-value" style="color: #00b0ff;">{duration_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">⚡ 平均 / 最大功率</div>
                <div class="kpi-value" style="color: #29b6f6;">{power_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">❤️ 平均 / 最大心率</div>
                <div class="kpi-value" style="color: #ff5252;">{hr_str}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">🔥 最大核心溫度</div>
                <div class="kpi-value" style="color: #ff9100;">{core_str}</div>
            </div>
        </div>
        
        <div class="section-title">📊 數據協同分析圖表</div>
        <div class="chart-container">
            {plotly_html}
        </div>
        
        <div class="section-title">📋 生理數據對照彙整表</div>
        <div style="overflow-x: auto;">
            {table_html}
        </div>
        
        <div class="footer">
            報告產生於：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 本報告由 FIT 檔與乳酸協同分析工具產生。
        </div>
    </div>
</body>
</html>
"""
    return html_content

# 頁面配置與高級視覺主題
from PIL import Image
try:
    page_icon_img = Image.open("logo.jpg")
except:
    page_icon_img = "🩸"

st.set_page_config(
    page_title="FIT 檔與乳酸協同分析工具",
    page_icon=page_icon_img,
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入高級感 CSS 樣式
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Outfit:wght@300;400;600;700&display=swap');

/* 全域字體與背景 */
html, body, [class*="css"] {
    font-family: 'Outfit', 'Inter', sans-serif;
}

/* 漸層標題 */
.title-container {
    background: linear-gradient(90deg, #00e676, #00b0ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 2.5rem;
    margin-bottom: 0.2rem;
    letter-spacing: -0.05rem;
}

.subtitle-text {
    font-size: 1.05rem;
    color: #8b949e;
    margin-bottom: 1.8rem;
}

/* 玻璃擬態卡片 */
.metric-card {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 12px;
    padding: 15px 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    text-align: center;
    margin-bottom: 10px;
}
.metric-card:hover {
    border-color: rgba(0, 230, 118, 0.3);
    box-shadow: 0 4px 20px rgba(0, 230, 118, 0.1);
    transform: translateY(-2px);
}

.metric-label {
    font-size: 0.85rem;
    color: #8b949e;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05rem;
    margin-bottom: 5px;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
}

/* 分隔線樣式 */
hr {
    border: 0;
    height: 1px;
    background: linear-gradient(to right, rgba(255,255,255,0), rgba(255,255,255,0.1), rgba(255,255,255,0));
    margin: 20px 0;
}
</style>
""", unsafe_allow_html=True)

# ----------------- 核心解析邏輯 -----------------

@st.cache_data(show_spinner=False)




def import_historical_html_to_firebase(html_content, file_name):
    import json
    import base64
    import numpy as np
    import pandas as pd
    import re
    from datetime import datetime
    import requests

    uid = st.session_state.get('firebase_uid')
    token = st.session_state.get('firebase_token')
    if not uid or not token:
        return False, "請先登入 MyLactate 帳號"

    # 1. Metadata
    time_m = re.search(r'活動開始時間.*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', html_content, re.DOTALL)
    if not time_m:
        time_m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', html_content)
    if not time_m:
        return False, "找不到活動開始時間"
    start_time = datetime.strptime(time_m.group(1), '%Y-%m-%d %H:%M:%S')

    fn_m = re.search(r'檔案名稱.*?[:：]\s*([^&|\s\n\r<]+)', html_content)
    original_filename = fn_m.group(1).strip() if fn_m else file_name

    # 2. KPIs & 活動時長
    avg_power, max_power = 0, 0
    avg_hr, max_hr = 0, 0
    max_core = None
    duration_min = 0.0

    # 提取活動時長
    dur_m = re.search(r'活動時長.*?<div[^>]*kpi-value[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
    if not dur_m:
        dur_m = re.search(r'活動時長.*?<div[^>]*metric-value[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
    if dur_m:
        dur_txt = re.sub(r'<.*?>', '', dur_m.group(1)).strip()
        m_dur = re.search(r'(\d+(?:\.\d+)?)\s*分(?:\s*(\d+(?:\.\d+)?)\s*秒)?', dur_txt)
        if m_dur:
            duration_min = round(float(m_dur.group(1)) + (float(m_dur.group(2))/60.0 if m_dur.group(2) else 0), 1)
    if duration_min <= 0:
        plain_dur = re.search(r'時長.*?(\d+(?:\.\d+)?)\s*分(?:\s*(\d+)\s*秒)?', html_content, re.DOTALL)
        if plain_dur:
            duration_min = round(float(plain_dur.group(1)) + (float(plain_dur.group(2))/60.0 if plain_dur.group(2) else 0), 1)

    pm = re.search(r'功率.*?(\d+)\s*/\s*(\d+)\s*W', html_content, re.DOTALL)
    if pm:
        avg_power, max_power = int(pm.group(1)), int(pm.group(2))

    hm = re.search(r'心率.*?(\d+)\s*/\s*(\d+)\s*bpm', html_content, re.DOTALL)
    if hm:
        avg_hr, max_hr = int(hm.group(1)), int(hm.group(2))

    cm = re.search(r'核心溫度.*?([\d\.]+)\s*°C', html_content, re.DOTALL)
    if cm:
        max_core = float(cm.group(1))

    # 運動類型推斷 (智能整合 FIT 官方快取、檔名、踏頻與 Stryd 跑步功率計特徵)
    import weekly_physio_engine as wpe
    sport, sub_sport = wpe.resolve_sport_type(
        original_filename,
        avg_power=avg_power,
        avg_hr=avg_hr
    )
    sp_m = re.search(r'運動類型.*?([a-zA-Z\u4e00-\u9fa5]+)', html_content)
    if sp_m:
        sp_txt = sp_m.group(1).lower()
        if any(k in sp_txt for k in ['bike', 'cycling', '自行車', '騎行']):
            sport, sub_sport = 'cycling', 'indoor_cycling'
        elif any(k in sp_txt for k in ['run', '跑步', '慢跑']):
            sport, sub_sport = 'running', 'generic'

    # 3. Plotly time series (downsample to 30s bins)
    time_series_points = []
    idx = html_content.find('Plotly.newPlot(')
    if idx != -1:
        first_comma = html_content.find(',', idx)
        start_arr = html_content.find('[', first_comma)
        depth = 0
        end_arr = -1
        for i in range(start_arr, len(html_content)):
            if html_content[i] == '[':
                depth += 1
            elif html_content[i] == ']':
                depth -= 1
                if depth == 0:
                    end_arr = i + 1
                    break
        if end_arr != -1:
            try:
                traces = json.loads(html_content[start_arr:end_arr])
                x_time, y_pwr, y_hr, y_core = None, None, None, None
                for t in traces:
                    nm = str(t.get('name', '')).lower()
                    x_obj, y_obj = t.get('x', {}), t.get('y', {})
                    if isinstance(x_obj, dict) and 'bdata' in x_obj and isinstance(y_obj, dict) and 'bdata' in y_obj:
                        x_data = np.frombuffer(base64.b64decode(x_obj['bdata']), dtype=np.float64)
                        y_data = np.frombuffer(base64.b64decode(y_obj['bdata']), dtype=np.float64)
                        
                        is_pwr = any(k in nm for k in ['功率', '(w)', ' w', 'power', 'pwr', '30s'])
                        is_hr = any(k in nm for k in ['心率', '(bpm)', ' bpm', 'bpm', 'hr', 'heart'])
                        is_core = any(k in nm for k in ['核心', 'core', '°c', 'temp'])
                        
                        if is_pwr:
                            if x_time is None or ('30s' in nm):
                                x_time = x_data
                            y_pwr = y_data
                        elif is_hr:
                            if x_time is None:
                                x_time = x_data
                            y_hr = y_data
                        elif is_core:
                            if x_time is None:
                                x_time = x_data
                            y_core = y_data
                        elif x_time is None and len(x_data) > 10:
                            x_time = x_data

                if x_time is not None:
                    if duration_min <= 0:
                        duration_min = round(float(x_time.max()), 1)

                    df_ts = pd.DataFrame({'elapsed_minutes': x_time})
                    if y_pwr is not None and len(y_pwr) == len(x_time):
                        df_ts['power'] = y_pwr
                    if y_hr is not None and len(y_hr) == len(x_time):
                        df_ts['heart_rate'] = y_hr
                    if y_core is not None and len(y_core) == len(x_time):
                        df_ts['core_temp'] = y_core

                    df_ts['bin'] = (df_ts['elapsed_minutes'] * 2).astype(int) / 2.0
                    df_res = df_ts.groupby('bin').mean(numeric_only=True).reset_index()
                    for _, row in df_res.iterrows():
                        pt = {
                            'mapValue': {
                                'fields': {
                                    'elapsed_minutes': {'doubleValue': round(float(row.get('elapsed_minutes', 0)), 2)}
                                }
                            }
                        }
                        if 'power' in row and pd.notna(row['power']):
                            p_val = round(float(row['power']), 1)
                            pt['mapValue']['fields']['power'] = {'doubleValue': p_val}
                            pt['mapValue']['fields']['power_30s'] = {'doubleValue': p_val}
                        if 'heart_rate' in row and pd.notna(row['heart_rate']):
                            pt['mapValue']['fields']['heart_rate'] = {'doubleValue': round(float(row['heart_rate']), 1)}
                        if 'core_temp' in row and pd.notna(row['core_temp']):
                            pt['mapValue']['fields']['core_temp'] = {'doubleValue': round(float(row['core_temp']), 2)}
                        time_series_points.append(pt)
            except Exception as e:
                print('Error parsing plotly json in html import:', e)

    # 若 avg_power 為 0，自動由 30 秒平均功率數列計算總平均功率
    if avg_power <= 0 and time_series_points:
        pwrs = [float(p['mapValue']['fields']['power']['doubleValue']) for p in time_series_points if 'power' in p['mapValue']['fields']]
        if pwrs:
            avg_power = int(round(sum(pwrs) / len(pwrs)))
            if max_power <= 0:
                max_power = int(round(max(pwrs)))

    if duration_min <= 0:
        duration_min = 60.0

    # 4. Upload to fit_records
    fit_payload = {
        "fields": {
            "file_name": {"stringValue": str(original_filename)},
            "start_time": {"timestampValue": start_time.isoformat() + "Z"},
            "sport": {"stringValue": str(sport)},
            "sub_sport": {"stringValue": str(sub_sport)},
            "duration_minutes": {"doubleValue": float(duration_min)},
            "avg_power": {"integerValue": str(int(avg_power))},
            "max_power": {"integerValue": str(int(max_power))},
            "avg_hr": {"integerValue": str(int(avg_hr))},
            "max_hr": {"integerValue": str(int(max_hr))},
            "time_series": {"arrayValue": {"values": time_series_points}}
        }
    }
    if max_core is not None:
        fit_payload["fields"]["max_core"] = {"doubleValue": float(max_core)}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fit_doc_id = f"fit_{start_time.strftime('%Y%m%d_%H%M%S')}"
    fit_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records/{fit_doc_id}"
    try:
        r_fit = requests.patch(fit_url, headers=headers, json=fit_payload, timeout=15)
        if r_fit.status_code not in [200, 201]:
            return False, f"上傳 fit_records 失敗 ({r_fit.status_code}): {r_fit.text}"
    except Exception as e:
        return False, f"連線至 fit_records 失敗: {e}"

    # 5. Summary table -> lactate_records (使用確定性唯一 ID，防止重複登記)
    la_count = 0
    table_m = re.search(r'<table[^>]*>(.*?)</table>', html_content, re.DOTALL)
    if table_m:
        tr_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_m.group(1), re.DOTALL)
        for tr in tr_matches:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
            if len(tds) >= 2:
                try:
                    elapsed_min = float(tds[0].strip())
                    la_val = float(tds[1].strip())
                    record_time = start_time + pd.Timedelta(minutes=elapsed_min)

                    la_payload = {
                        "fields": {
                            "year": {"integerValue": str(record_time.year)},
                            "month": {"integerValue": str(record_time.month)},
                            "day": {"integerValue": str(record_time.day)},
                            "hour": {"integerValue": str(record_time.hour)},
                            "minute": {"integerValue": str(record_time.minute)},
                            "final_la_mmol": {"doubleValue": float(la_val)},
                            "source": {"stringValue": "html_import"}
                        }
                    }
                    la_doc_id = f"la_{record_time.strftime('%Y%m%d_%H%M%S')}"
                    la_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records/{la_doc_id}"
                    requests.patch(la_url, headers=headers, json=la_payload, timeout=10)
                    la_count += 1
                except Exception as e:
                    pass

    return True, f"成功匯入（包含 {len(time_series_points)} 個軌跡點，{la_count} 筆乳酸數據）"

def upload_report_to_firebase_storage(html_data, file_name):
    import urllib.parse
    uid = st.session_state.get('firebase_uid')
    token = st.session_state.get('firebase_token')
    if not uid or not token:
        return False, "請先登入 MyLactate 帳號"
    
    object_name = f"users/{uid}/reports/{file_name}"
    object_name_encoded = urllib.parse.quote(object_name, safe='')
    url = f"https://firebasestorage.googleapis.com/v0/b/lactatecloud.appspot.com/o?name={object_name_encoded}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/html"
    }
    try:
        response = requests.post(url, headers=headers, data=html_data.encode('utf-8'), timeout=15)
        if response.status_code == 200:
            return True, "成功"
        else:
            return False, f"錯誤 {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)


def upload_fit_to_firebase(df, file_name, start_time, avg_power, max_power, avg_hr, max_hr, max_core, sport='unknown', sub_sport='generic'):
    uid = st.session_state.get('firebase_uid')
    token = st.session_state.get('firebase_token')
    if not uid or not token:
        st.error('請先登入 MyLactate')
        return False
        
    try:
        # Downsample to 30s
        df_copy = df.copy()
        # bin size = 0.5 minutes (30s)
        df_copy['bin'] = (df_copy['elapsed_minutes'] * 2).astype(int) / 2.0
        df_res = df_copy.groupby('bin').mean(numeric_only=True).reset_index()
        
        # Prepare array data
        time_series = []
        for _, row in df_res.iterrows():
            point = {
                'mapValue': {
                    'fields': {
                        'elapsed_minutes': {'doubleValue': round(float(row.get('elapsed_minutes', 0)), 2)}
                    }
                }
            }
            if pd.notna(row.get('heart_rate')):
                point['mapValue']['fields']['heart_rate'] = {'doubleValue': round(float(row['heart_rate']), 1)}
            if pd.notna(row.get('power')):
                p_val = round(float(row['power']), 1)
                point['mapValue']['fields']['power'] = {'doubleValue': p_val}
                point['mapValue']['fields']['power_30s'] = {'doubleValue': p_val}
            if pd.notna(row.get('core_temp')):
                point['mapValue']['fields']['core_temp'] = {'doubleValue': round(float(row['core_temp']), 2)}
            if 'cadence' in row and pd.notna(row.get('cadence')):
                point['mapValue']['fields']['cadence'] = {'doubleValue': round(float(row['cadence']), 1)}
            # GPS 經緯度、海拔高度、累計距離
            if 'lat' in row and pd.notna(row.get('lat')) and abs(row['lat']) <= 90:
                point['mapValue']['fields']['lat'] = {'doubleValue': round(float(row['lat']), 6)}
            if 'lng' in row and pd.notna(row.get('lng')) and abs(row['lng']) <= 180:
                point['mapValue']['fields']['lng'] = {'doubleValue': round(float(row['lng']), 6)}
            if 'altitude' in row and pd.notna(row.get('altitude')):
                point['mapValue']['fields']['altitude'] = {'doubleValue': round(float(row['altitude']), 1)}
            if 'distance' in row and pd.notna(row.get('distance')):
                point['mapValue']['fields']['distance'] = {'doubleValue': round(float(row['distance']), 1)}
            time_series.append(point)
            
        # 若 avg_power 為 0，自動由 30 秒平均功率數列計算總平均功率
        if avg_power <= 0 and ('power' in df_res.columns) and df_res['power'].notna().any():
            avg_power = int(round(df_res['power'].mean()))
            if max_power <= 0:
                max_power = int(round(df_res['power'].max()))

        # JSON payload for Firestore
        has_gps = ('lat' in df.columns and df['lat'].notna().any() and
                   'lng' in df.columns and df['lng'].notna().any())
        duration_minutes = float(df['elapsed_minutes'].max()) if ('elapsed_minutes' in df.columns and df['elapsed_minutes'].notna().any()) else 0.0
        payload = {
            'fields': {
                'file_name': {'stringValue': str(file_name)},
                'start_time': {'timestampValue': start_time.isoformat() + 'Z' if start_time.tzinfo is None else start_time.isoformat()},
                'sport': {'stringValue': str(sport)},
                'sub_sport': {'stringValue': str(sub_sport)},
                'duration_minutes': {'doubleValue': round(float(duration_minutes), 1)},
                'avg_power': {'integerValue': str(int(avg_power))},
                'max_power': {'integerValue': str(int(max_power))},
                'avg_hr': {'integerValue': str(int(avg_hr))},
                'max_hr': {'integerValue': str(int(max_hr))},
                'has_gps': {'booleanValue': bool(has_gps)},
                'time_series': {'arrayValue': {'values': time_series}}
            }
        }
        if max_core is not None:
            payload['fields']['max_core'] = {'doubleValue': float(max_core)}
        if 'distance' in df.columns and df['distance'].notna().any():
            tot_dist = float(df['distance'].dropna().iloc[-1])
            if tot_dist > 0:
                payload['fields']['total_distance_m'] = {'doubleValue': round(tot_dist, 1)}
        if 'altitude' in df.columns and df['altitude'].notna().any():
            alt_series = df['altitude'].dropna()
            if len(alt_series) > 0:
                payload['fields']['min_altitude'] = {'doubleValue': round(float(alt_series.min()), 1)}
                payload['fields']['max_altitude'] = {'doubleValue': round(float(alt_series.max()), 1)}
            
        clean_fit_time = start_time.strftime('%Y%m%d_%H%M%S') if start_time else datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        doc_id = f"fit_{clean_fit_time}"
        url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/fit_records/{doc_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = requests.patch(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            return True
        else:
            st.error(f'Upload failed: {response.text}')
            return False
    except Exception as e:
        st.error(f'Upload error: {e}')
        return False



def fetch_firebase_lactate_records(start_time=None, duration_minutes=0.0, target_uid=None):
    eff_uid = target_uid or (st.session_state.get('admin_selected_athlete_uid') if st.session_state.get('firebase_email', '').lower() in [e.lower() for e in ADMIN_EMAILS] else None) or st.session_state.get('firebase_uid')
    url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{eff_uid}/lactate_records?pageSize=300"
    try:
        headers = {"Authorization": f"Bearer {st.session_state.get('firebase_token')}"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            documents = data.get("documents", [])
            
            records = []
            for doc in documents:
                fields = doc.get("fields", {})
                doc_name = doc.get("name", "")
                doc_id = doc_name.split("/")[-1] if doc_name else ""
                
                # Parse absolute time
                year = int(fields.get("year", {}).get("integerValue", 0))
                month = int(fields.get("month", {}).get("integerValue", 0))
                day = int(fields.get("day", {}).get("integerValue", 0))
                hour = int(fields.get("hour", {}).get("integerValue", 0))
                minute = int(fields.get("minute", {}).get("integerValue", 0))
                
                # Lactate value
                final_la_obj = fields.get("final_la_mmol", {})
                final_la = float(final_la_obj.get("doubleValue", final_la_obj.get("integerValue", 0)))
                
                if year > 0 and month > 0 and day > 0:
                    full_year = year + 2000 if year < 100 else year
                    try:
                        record_time = datetime(full_year, month, day, hour, minute)
                    except Exception:
                        continue
                    elapsed_min = 0.0
                    if start_time:
                        elapsed_min = (record_time - start_time).total_seconds() / 60.0
                        # 條件: 起始時間 - 60分鐘 <= 記錄時間 <= 起始時間 + 運動時間 + 60分鐘
                        if elapsed_min < -60 or elapsed_min > (duration_minutes + 60):
                            continue

                    records.append({
                        "elapsed_minutes": elapsed_min,
                        "lactate_mmol": final_la,
                        "record_time": record_time,
                        "doc_id": doc_id
                    })
                    
            # 排序：依時間由舊至新排序
            records = sorted(records, key=lambda x: x["record_time"])

            # 智慧去重與實體清理：
            # 1. 時間差 <= 120 秒（2分鐘以內）且乳酸值相同（差值 < 0.05）：判定為設備重複上傳，自動刪除後面的點並清除雲端紀錄
            # 2. 若數值有高低差別（重測）：予以保留，留給使用者自行比對與刪除判斷
            dedup_records = []
            uid = eff_uid
            token = st.session_state.get('firebase_token')
            headers_del = {"Authorization": f"Bearer {token}"} if token else None

            for r in records:
                if not dedup_records:
                    dedup_records.append(r)
                else:
                    diff_sec = (r["record_time"] - dedup_records[-1]["record_time"]).total_seconds()
                    is_same_val = abs(r["lactate_mmol"] - dedup_records[-1]["lactate_mmol"]) < 0.05
                    if diff_sec <= 120 and is_same_val:
                        # 這是「後面的數據」，且數值相同屬於重複上傳的點。從雲端 Firestore 實體刪除
                        dup_id = r.get("doc_id")
                        if dup_id and uid and headers_del:
                            try:
                                del_url = f"https://firestore.googleapis.com/v1/projects/lactatecloud/databases/(default)/documents/users/{uid}/lactate_records/{dup_id}"
                                requests.delete(del_url, headers=headers_del, timeout=5)
                            except Exception:
                                pass
                    else:
                        # 相差 > 120 秒，或相差 <= 120 秒但數值有高低差別（重測），保留給使用者自行判斷
                        dedup_records.append(r)
            records = dedup_records
            return records
        else:
            st.error(f"Firestore API Error: {response.text}")
            return []
    except Exception as e:
        st.error(f"MyLactate 連線失敗: {str(e)}")
    return []


def parse_fit_file_data(uploaded_file_bytes):
    """
    解析 FIT 檔案的 records 與 laps 數據，並提取運動類型 (sport, sub_sport)。
    傳入 bytes 物件，使用 fitparse 解析，若失敗則自動 fallback 到 fitdecode。
    """
    records = []
    laps_list = []
    use_fallback = False
    sport = 'unknown'
    sub_sport = 'generic'
    
    try:
        fit_file = fitparse.FitFile(io.BytesIO(uploaded_file_bytes))
        for record in fit_file.get_messages('record'):
            vals = {field.name: field.value for field in record.fields}
            records.append(vals)
        for i, lap in enumerate(fit_file.get_messages('lap')):
            vals = {field.name: field.value for field in lap.fields}
            laps_list.append(vals)
        for s_msg in fit_file.get_messages('sport'):
            for f in s_msg.fields:
                if f.name == 'sport' and f.value is not None:
                    sport = str(f.value).lower()
                elif f.name == 'sub_sport' and f.value is not None:
                    sub_sport = str(f.value).lower()
        if sport == 'unknown':
            for s_msg in fit_file.get_messages('session'):
                for f in s_msg.fields:
                    if f.name == 'sport' and f.value is not None:
                        sport = str(f.value).lower()
                    elif f.name == 'sub_sport' and f.value is not None:
                        sub_sport = str(f.value).lower()
    except Exception as e:
        use_fallback = True
        
    if use_fallback:
        records = []
        laps_list = []
        try:
            import fitdecode
            with fitdecode.FitReader(io.BytesIO(uploaded_file_bytes)) as fit:
                for frame in fit:
                    if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                        if frame.name == "record":
                            row = {field.name: field.value for field in frame.fields}
                            records.append(row)
                        elif frame.name == "lap":
                            row = {field.name: field.value for field in frame.fields}
                            laps_list.append(row)
                        elif frame.name in ("sport", "session"):
                            for field in frame.fields:
                                if field.name == "sport" and field.value is not None:
                                    sport = str(field.value).lower()
                                elif field.name == "sub_sport" and field.value is not None:
                                    sub_sport = str(field.value).lower()
        except Exception as fallback_err:
            return pd.DataFrame(), pd.DataFrame(), None, 'unknown', 'generic'
            
    df = pd.DataFrame(records)
    if df.empty or 'timestamp' not in df.columns:
        return pd.DataFrame(), pd.DataFrame(), None, 'unknown', 'generic'
        
    # 排序並取得開始時間 (FIT 檔時間預設為 UTC+0，加上 8 小時轉換為 UTC+8 當地時間)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 統一移除時區資訊，以防後續與其他 naive datetime 運算錯誤
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=8)
        
    start_time = df['timestamp'].iloc[0]
    df['elapsed_minutes'] = (df['timestamp'] - start_time).dt.total_seconds() / 60.0
    
    # 確保必要欄位存在
    for col in ['heart_rate', 'power', 'temperature', 'skin_temperature', 'core_temperature']:
        if col not in df.columns:
            df[col] = np.nan
            
    # 檢測替代心率欄位名稱
    if df['heart_rate'].isna().all():
        for alt_hr in ['heartrate', 'hr', 'HeartRate', 'Heart_Rate']:
            if alt_hr in df.columns and df[alt_hr].notna().any():
                df['heart_rate'] = df[alt_hr]
                break
            
    # 解析核心溫度 (優先檢測 core_temperature，若無則檢測 CORE 體溫感測器的開發者欄位 unknown_139)
    if 'core_temperature' in df.columns and df['core_temperature'].notna().any():
        df['core_temp'] = df['core_temperature'].apply(lambda x: x / 100.0 if (pd.notna(x) and x > 1000) else x)
    elif 'unknown_139' in df.columns:
        df['core_temp'] = df['unknown_139'].apply(lambda x: x / 100.0 if (pd.notna(x) and x > 1000) else x)
    else:
        df['core_temp'] = np.nan
        
    # Interpolate sparse core_temp data so the summary table can match it
    if df['core_temp'].notna().any():
        df['core_temp'] = df['core_temp'].ffill().bfill()
        
    # 解析 GPS 經緯度 (Garmin semicircles 轉 WGS84 度數)
    def _to_deg(val):
        if pd.isna(val) or val is None:
            return np.nan
        try:
            val = float(val)
            if abs(val) > 180:
                return round(val * (180.0 / 2147483648.0), 6)
            return round(val, 6)
        except Exception:
            return np.nan

    if 'position_lat' in df.columns:
        df['lat'] = df['position_lat'].apply(_to_deg)
    elif 'latitude' in df.columns:
        df['lat'] = df['latitude'].apply(_to_deg)
    else:
        df['lat'] = np.nan

    if 'position_long' in df.columns:
        df['lng'] = df['position_long'].apply(_to_deg)
    elif 'longitude' in df.columns:
        df['lng'] = df['longitude'].apply(_to_deg)
    else:
        df['lng'] = np.nan

    # 解析海拔高度 (公尺，優先 enhanced_altitude)
    if 'enhanced_altitude' in df.columns and df['enhanced_altitude'].notna().any():
        df['altitude'] = df['enhanced_altitude'].apply(lambda x: round(float(x), 1) if pd.notna(x) else np.nan)
    elif 'altitude' in df.columns and df['altitude'].notna().any():
        df['altitude'] = df['altitude'].apply(lambda x: round(float(x), 1) if pd.notna(x) else np.nan)
    else:
        df['altitude'] = np.nan

    # 解析累積距離 (公尺)
    if 'distance' in df.columns and df['distance'].notna().any():
        df['distance'] = df['distance'].apply(lambda x: round(float(x), 1) if pd.notna(x) else np.nan)
    else:
        df['distance'] = np.nan

    # 保留乾淨的欄位
    available_cols = ['timestamp', 'elapsed_minutes', 'heart_rate', 'power', 'core_temp', 'skin_temperature', 'temperature', 'lat', 'lng', 'altitude', 'distance']
    if 'cadence' in df.columns:
        available_cols.append('cadence')
    keep_cols = [c for c in available_cols if c in df.columns]
    df_clean = df[keep_cols].copy()
    
    # 2. 解析 Laps
    laps = []
    for i, lap_val in enumerate(laps_list):
        lap_start = lap_val.get('start_time')
        lap_duration = lap_val.get('total_elapsed_time') # 秒
        
        if lap_start is not None and lap_duration is not None:
            lap_start_dt = pd.to_datetime(lap_start)
            if lap_start_dt.tz is not None:
                lap_start_dt = lap_start_dt.tz_localize(None)
            lap_start_dt = lap_start_dt + pd.Timedelta(hours=8)
                
            lap_end = lap_start_dt + timedelta(seconds=float(lap_duration))
            start_el = (lap_start_dt - start_time).total_seconds() / 60.0
            end_el = (lap_end - start_time).total_seconds() / 60.0
            
            laps.append({
                'lap_index': i + 1,
                'start_time': lap_start_dt,
                'end_time': lap_end,
                'start_elapsed_minutes': start_el,
                'end_elapsed_minutes': end_el,
                'duration_sec': lap_duration,
                'avg_power': lap_val.get('avg_power'),
                'avg_heart_rate': lap_val.get('avg_heart_rate'),
                'distance_m': lap_val.get('total_distance')
            })
            
    # 若運動類型仍為未知，進行啟發式推斷
    if sport == 'unknown':
        if 'power' in df.columns and df['power'].notna().any() and (df['power'] > 0).any():
            sport = 'cycling'
        elif 'cadence' in df.columns and df['cadence'].notna().any() and df['cadence'].mean() > 130:
            sport = 'running'
        else:
            sport = 'running'
            
    df_clean.attrs['sport'] = sport
    df_clean.attrs['sub_sport'] = sub_sport
    df_laps = pd.DataFrame(laps)
    return df_clean, df_laps, start_time, sport, sub_sport

# ----------------- 應用程式介面 -----------------


# MyLactate 雲端登入區
st.sidebar.markdown("### ☁️ MyLactate 雲端帳號")
if "firebase_uid" in st.session_state and st.session_state["firebase_uid"]:
    # 確保 Firestore users/{uid} 根文件必定標記 email 與最新登入時間
    if st.session_state.get("_user_email_synced_to_firestore") != st.session_state["firebase_uid"]:
        ensure_user_profile_in_firestore(
            st.session_state["firebase_uid"],
            st.session_state.get("firebase_email", ""),
            st.session_state.get("firebase_token", "")
        )
    logged_email = str(st.session_state.get('firebase_email', '')).strip().lower()
    is_admin = logged_email in [e.lower() for e in ADMIN_EMAILS]

    if is_admin:
        st.sidebar.markdown("""
        <div style="background: linear-gradient(135deg, rgba(255, 171, 0, 0.2), rgba(255, 82, 82, 0.2)); border: 1px solid #ffab00; border-radius: 8px; padding: 8px 12px; margin-bottom: 10px;">
            <div style="color: #ffab00; font-weight: 700; font-size: 0.88rem; display: flex; align-items: center; gap: 6px;">
                <span>👑</span> <span>教練/管理員模式</span>
            </div>
            <div style="color: #cbd5e1; font-size: 0.75rem; margin-top: 2px;">登入身分：{logged_email}</div>
        </div>
        """.format(logged_email=logged_email), unsafe_allow_html=True)

        # 撈取 Firestore 全體選手名冊
        admin_uid = st.session_state.get("firebase_uid")
        admin_token = st.session_state.get("firebase_token", "")
        athletes_list, debug_msg = get_all_firestore_athletes(admin_token, admin_uid=admin_uid)

        # 檢查 session_state 自訂名冊
        if "coach_custom_athletes" in st.session_state:
            for c_ath in st.session_state["coach_custom_athletes"]:
                if not any(a["uid"] == c_ath["uid"] for a in athletes_list):
                    athletes_list.append(c_ath)

        # 確保教練自己也在名單中
        has_self = any(a["uid"] == admin_uid for a in athletes_list)
        if not has_self:
            athletes_list.insert(0, {
                "uid": admin_uid,
                "email": logged_email,
                "display_name": "教練本人",
                "label": f"👑 教練本人 ({logged_email})"
            })

        # 建立選項映射
        uid_options = [a["uid"] for a in athletes_list]
        labels_map = {a["uid"]: a["label"] for a in athletes_list}
        emails_map = {a["uid"]: a.get("email", "") for a in athletes_list}
        names_map = {a["uid"]: (a.get("display_name") or (a.get("email", "").split("@")[0] if a.get("email") else "選手")) for a in athletes_list}

        current_target_uid = st.session_state.get("admin_selected_athlete_uid", admin_uid)
        if current_target_uid not in uid_options:
            current_target_uid = admin_uid
            st.session_state["admin_selected_athlete_uid"] = admin_uid
            st.session_state["admin_selected_athlete_email"] = logged_email
            st.session_state["admin_selected_athlete_name"] = "教練本人"

        sel_idx = uid_options.index(current_target_uid) if current_target_uid in uid_options else 0

        def _on_athlete_change():
            new_uid = st.session_state.get("coach_athlete_selector")
            st.session_state["admin_selected_athlete_uid"] = new_uid
            st.session_state["admin_selected_athlete_email"] = emails_map.get(new_uid, "")
            st.session_state["admin_selected_athlete_name"] = names_map.get(new_uid, "")
            # 清除該運動員舊快取，以即時載入該運動員之活動日曆與分析報告
            st.session_state.pop("cached_weekly_report_html", None)
            st.session_state.pop("cached_report_key", None)
            st.session_state.pop("active_cloud_session", None)
            st.session_state.pop("multi_selected_cloud_sessions", None)
            # 清除所有舊日期範圍快取
            for k in list(st.session_state.keys()):
                if str(k).startswith("date_bounds_"):
                    st.session_state.pop(k, None)

        st.sidebar.markdown("#### 🏃 選手名冊管理")
        st.sidebar.selectbox(
            "切換當前分析選手",
            options=uid_options,
            index=sel_idx,
            format_func=lambda u: labels_map.get(u, u),
            key="coach_athlete_selector",
            on_change=_on_athlete_change,
            help="選擇要調閱與分析的選手資料。系統將無縫切換至該選手的乳酸記錄、FIT 檔及 AI 運動週報！"
        )
        
        # 標定當前正在分析之運動員
        sel_ath_uid = st.session_state.get("admin_selected_athlete_uid", admin_uid)
        sel_ath_label = labels_map.get(sel_ath_uid, sel_ath_uid)
        st.sidebar.caption(f"🎯 當前鎖定目標：**{sel_ath_label}**")
        if sel_ath_uid != admin_uid:
            st.sidebar.info("💡 提示：所有運動日曆、FIT 檔案與 AI 週報已切換為此選手之個人雲端數據！")

        # 選手手動新增 / 快速綁定
        with st.sidebar.expander("➕ 手動指定 / 快速綁定選手 (Email 或 UID)", expanded=False):
            st.markdown("<div style='font-size: 0.8rem; color: #cbd5e1;'>若選手尚未自動出現於上方名單，輸入選手的 Email 或 UID 即可立即調閱：</div>", unsafe_allow_html=True)
            m_input = st.text_input("選手 Email 或 UID", key="manual_ath_in", placeholder="例如: mindy@gmail.com 或 8rKj...")
            m_name = st.text_input("選手姓名/備註 (選填)", key="manual_ath_name_in", placeholder="例如: 選手 Mindy")
            col_m_add, col_m_ref = st.columns([1.2, 1])
            with col_m_add:
                if st.button("➕ 加入名冊並切換", use_container_width=True, key="btn_add_manual_ath"):
                    raw_val = m_input.strip()
                    if raw_val:
                        resolved_uid = raw_val
                        resolved_email = raw_val if "@" in raw_val else ""
                        resolved_name = m_name.strip()
                        # 嘗試聯網解析
                        if "@" in raw_val:
                            found = lookup_firestore_user_by_email(raw_val, admin_token)
                            if found:
                                resolved_uid = found["uid"]
                                resolved_email = found["email"]
                                if not resolved_name and found.get("display_name"):
                                    resolved_name = found["display_name"]
                        else:
                            found = lookup_firestore_user_by_uid(raw_val, admin_token)
                            if found:
                                resolved_email = found.get("email", "")
                                if not resolved_name and found.get("display_name"):
                                    resolved_name = found["display_name"]
                        
                        final_label = f"📌 {resolved_name} ({resolved_email or resolved_uid[:8]})" if resolved_name else (f"📌 {resolved_email}" if resolved_email else f"📌 選手 ({resolved_uid[:8]}...)")
                        new_entry = {
                            "uid": resolved_uid,
                            "email": resolved_email,
                            "display_name": resolved_name,
                            "label": final_label,
                            "custom_added": True
                        }
                        if "coach_custom_athletes" not in st.session_state:
                            st.session_state["coach_custom_athletes"] = []
                        st.session_state["coach_custom_athletes"] = [a for a in st.session_state["coach_custom_athletes"] if a.get("uid") != resolved_uid]
                        st.session_state["coach_custom_athletes"].append(new_entry)
                        
                        persisted = load_coach_roster(admin_uid, admin_token)
                        persisted = [p for p in persisted if p.get("uid") != resolved_uid]
                        persisted.append(new_entry)
                        save_coach_roster(admin_uid, admin_token, persisted)
                        
                        st.session_state["admin_selected_athlete_uid"] = resolved_uid
                        st.session_state["admin_selected_athlete_email"] = resolved_email
                        st.session_state["admin_selected_athlete_name"] = resolved_name
                        st.session_state.pop("cached_weekly_report_html", None)
                        st.session_state.pop("cached_report_key", None)
                        st.session_state.pop("active_cloud_session", None)
                        st.session_state.pop("multi_selected_cloud_sessions", None)
                        st.rerun()
            with col_m_ref:
                if st.button("🔄 重新整理", use_container_width=True, key="btn_refresh_ath_list"):
                    st.rerun()

        # 若當前選手為手動自訂選手，提供移除按鈕
        curr_is_custom = any(a.get("uid") == sel_ath_uid and a.get("custom_added") for a in athletes_list)
        if curr_is_custom:
            if st.sidebar.button("🗑️ 從常設名冊移除此選手", use_container_width=True, key="btn_remove_custom_ath"):
                if "coach_custom_athletes" in st.session_state:
                    st.session_state["coach_custom_athletes"] = [a for a in st.session_state["coach_custom_athletes"] if a.get("uid") != sel_ath_uid]
                persisted = load_coach_roster(admin_uid, admin_token)
                persisted = [p for p in persisted if p.get("uid") != sel_ath_uid]
                save_coach_roster(admin_uid, admin_token, persisted)
                st.session_state["admin_selected_athlete_uid"] = admin_uid
                st.session_state["admin_selected_athlete_email"] = logged_email
                st.session_state["admin_selected_athlete_name"] = "教練本人"
                st.rerun()

        # 最高權限與規則說明指引
        with st.sidebar.expander("🔑 如何解鎖所有選手資料庫權限？", expanded=(len(athletes_list) <= 1)):
            st.markdown(f"""
            **若下拉選單目前僅顯示您自己（共 {len(athletes_list)} 位），代表 Firebase 雲端資料庫尚未開放教練的全域讀取規則。**
            
            只需 10 秒鐘至 **[Firebase Console](https://console.firebase.google.com/)**：
            1. 點選專案 **lactatecloud**
            2. 進入 **Firestore Database** > 上方分頁 **Rules (規則)**
            3. 將內容替換為以下設定並點擊 **Publish (發布)**：
            ```javascript
            rules_version = '2';
            service cloud.firestore {{
              match /databases/{{database}}/documents {{
                // 👑 教練最高權限 (開放 bigporpoise@gmail.com 讀寫全體選手資料)
                match /{{document=**}} {{
                  allow read, write: if request.auth != null && (
                    request.auth.token.email == "bigporpoise@gmail.com"
                  );
                }}
                // 一般選手僅能讀寫個人檔案
                match /users/{{userId}}/{{document=**}} {{
                  allow read, write: if request.auth != null && request.auth.uid == userId;
                }}
              }}
            }}
            ```
            發布後回到此處點擊「🔄 重新整理」，所有選手將立刻自動全部列出！
            """)

        if st.sidebar.button("🚪 登出並清除所有紀錄", key="admin_logout_btn", use_container_width=True):
            logout_firebase()
    else:
        st.sidebar.success(f"已登入: {logged_email}")
        if st.sidebar.button("🚪 登出並清除所有紀錄", use_container_width=True):
            logout_firebase()
elif hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
    st.sidebar.warning(f"⚠️ Google 帳號已驗證 ({getattr(st.user, 'email', '')})，但尚未連結 MyLactate 雲端金鑰。")
    if st.sidebar.button("🧹 清除舊紀錄並重新登入", use_container_width=True):
        logout_firebase()
else:
    st.sidebar.info("登入與 MyLactate 相同的帳號以讀取個人數據")
    
    # 1. Google 帳號一鍵登入 (官方質感樣式與 Google 彩色四色 Logo)
    st.markdown("""
    <style>
    div.st-key-google_login_btn button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: #ffffff !important;
        color: #3c4043 !important;
        border: 1px solid #dadce0 !important;
        border-radius: 6px !important;
        padding: 6px 14px !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 2px rgba(60,64,67,0.3) !important;
        transition: all 0.2s ease !important;
    }
    div.st-key-google_login_btn button:hover {
        background-color: #f8f9fa !important;
        color: #202124 !important;
        border-color: #dadce0 !important;
        box-shadow: 0 1px 3px 1px rgba(60,64,67,0.15) !important;
    }
    div.st-key-google_login_btn button::before {
        content: "";
        display: inline-block;
        width: 18px;
        height: 18px;
        margin-right: 10px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E%3Cpath fill='%234285F4' d='M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.616z'/%3E%3Cpath fill='%2334A853' d='M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z'/%3E%3Cpath fill='%23FBBC05' d='M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.173 0 7.547 0 9s.347 2.827.957 4.039l3.007-2.332z'/%3E%3Cpath fill='%23EA4335' d='M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z'/%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        flex-shrink: 0;
    }
    div.st-key-google_login_btn button p {
        color: #3c4043 !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        margin: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    if st.sidebar.button("使用 Google 帳號登入", key="google_login_btn", use_container_width=True):
        try:
            st.login()
        except Exception as e:
            st.sidebar.error(f"Google 登入尚未設定完成: {str(e)}")
            if not hasattr(st, "secrets") or "auth" not in st.secrets:
                st.sidebar.warning("⚠️ 診斷提示：Streamlit 尚未讀取到 Secrets 中的 [auth] 設定，請確認 Secrets 已點擊 Save 並至右下角選單點選 Reboot app。")

    st.sidebar.markdown("<div style='text-align:center; color:#8b949e; font-size:12px; margin: 6px 0;'>— 或使用信箱密碼 —</div>", unsafe_allow_html=True)

    with st.sidebar.form("mylactate_login_form"):
        email = st.text_input("電子郵件 (Email)")
        password = st.text_input("密碼 (Password)", type="password")
        submitted = st.form_submit_button("登入 MyLactate", use_container_width=True)
        if submitted:
            login_to_firebase(email, password)
            
    with st.sidebar.expander("🔑 忘記密碼？點此重設"):
        reset_email_input = st.text_input("註冊信箱 (Email)", key="reset_email_input")
        if st.button("發送密碼重設信", use_container_width=True):
            reset_firebase_password(reset_email_input)
            
    with st.sidebar.expander("📝 註冊新帳號"):
        reg_email_input = st.text_input("電子郵件 (Email)", key="reg_email_input")
        reg_pwd_input = st.text_input("設定密碼 (至少6位數)", type="password", key="reg_pwd_input")
        if st.button("確認註冊並登入", use_container_width=True):
            register_to_firebase(reg_email_input, reg_pwd_input)

    st.sidebar.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    if st.sidebar.button("🧹 重設登入畫面 / 清除快取", key="reset_login_view_btn", use_container_width=True):
        logout_firebase()

def get_active_athlete_context():
    """
    動態取得當前分析目標之 (active_uid, active_email, active_name, is_coach_view)
    若登入者為管理員且已切換選取特定選手，則回傳該選手之 UID 與身分資訊；
    否則回傳一般登入者本人的 UID 與資訊。
    """
    base_uid = st.session_state.get('firebase_uid')
    base_email = str(st.session_state.get('firebase_email', '')).strip()
    is_admin = base_email.lower() in [e.lower() for e in ADMIN_EMAILS]

    if is_admin and st.session_state.get("admin_selected_athlete_uid"):
        sel_uid = st.session_state.get("admin_selected_athlete_uid")
        sel_email = st.session_state.get("admin_selected_athlete_email") or ""
        custom_name = st.session_state.get("admin_selected_athlete_name")
        sel_name = custom_name or (sel_email.split('@')[0] if sel_email else "選手")
        is_viewing_other = (sel_uid != base_uid)
        return sel_uid, sel_email, sel_name, is_viewing_other
    
    ath_name = base_email.split('@')[0] if base_email else "運動員"
    return base_uid, base_email, ath_name, False

st.sidebar.markdown("---")

# Intervals.icu / Garmin / COROS 手錶雲端綁定
if st.session_state.get('firebase_uid'):
    icu_uid = st.session_state.get('firebase_uid')
    icu_token = st.session_state.get('firebase_token')
    import intervals_client as ic
    import importlib
    importlib.reload(ic)

    # 讀取當前儲存的認證資訊 (支援 OAuth 2.0 與 API Key)
    icu_creds = ic.get_user_intervals_credentials(icu_uid, icu_token)
    oauth_cfg = ic.get_intervals_oauth_config()

    # --- 登入即自動背景同步機制 (增量極速模式：僅撈取 Firebase 尚未收錄的最新運動，毫秒級載入) ---
    auto_sync_key = f"intervals_auto_synced_{icu_uid}"
    last_sync_time = st.session_state.get(auto_sync_key, 0)
    # 冷卻時間設為 45 秒：登入時或距離上次檢查超過 45 秒時自動執行 (增量僅需 0.2 秒)
    if icu_creds["configured"] and (time.time() - last_sync_time > 45):
        st.session_state[auto_sync_key] = time.time()
        try:
            s_count, sk_count, s_msg = ic.sync_pre_lactate_activities_to_firebase(
                uid=icu_uid,
                firebase_token=icu_token,
                intervals_api_key=icu_creds["token"],
                athlete_id=icu_creds["athlete_id"],
                lookback_days=7,
                lookahead_days=7,
                is_oauth=icu_creds["is_oauth"],
                incremental_only=True,
                force_overwrite=False
            )
            # 若有同步到新數據，清除月曆快取、將焦點移至今天並觸發 rerun 立即顯示
            if s_count > 0:
                st.session_state.pop(f"cal_cache_data_{icu_uid}", None)
                st.session_state.pop("cached_weekly_report_html", None)
                st.session_state.pop(f"date_bounds_v4_{icu_uid}", None)
                today_str = date.today().strftime("%Y-%m-%d")
                st.session_state["cal_selected_date"] = today_str
                st.session_state["cal_view_year"] = date.today().year
                st.session_state["cal_view_month"] = date.today().month
                st.toast(f"⚡ 登入自動同步：已載入 {s_count} 筆今日最新手錶運動！", icon="🏃")
                st.rerun()
        except Exception as e:
            print(f"登入自動同步發生異常: {e}")

    with st.sidebar.expander("🔗 運動手錶雲端綁定 (Garmin / COROS)", expanded=False):
        st.markdown("**支援 Garmin Connect、COROS 等設備**")
        st.caption("透過 Intervals.icu 自動同步日常訓練數據至 Firebase，補齊訓練負荷與間隔，消除數據偏差。")

        if icu_creds["configured"]:
            if icu_creds["is_oauth"]:
                ath_display = icu_creds.get("athlete_name") or icu_creds.get("athlete_id") or "已認證"
                st.success(f"✅ **已透過 OAuth 2.0 連線**\n\n👤 運動員：**{ath_display}** (ID: `{icu_creds['athlete_id']}`)")
            else:
                st.info(f"🔑 **已透過 API Key 連線**\n\n🆔 Athlete ID: `{icu_creds['athlete_id']}`")

            col_a1, col_a2 = st.columns(2)
            with col_a1:
                sync_btn = st.button("🔄 同步", use_container_width=True, key="btn_sync_icu")
            with col_a2:
                if st.button("🔌 解除連結", use_container_width=True, key="btn_disconnect_icu"):
                    ic.disconnect_user_intervals(icu_uid, icu_token)
                    st.session_state.pop("intervals_api_key", None)
                    st.session_state.pop("intervals_athlete_id", None)
                    st.session_state.pop("intervals_oauth_connected", None)
                    st.session_state.pop(f"intervals_auto_synced_{icu_uid}", None)
                    st.toast("已解除 Intervals.icu 連結", icon="👋")
                    st.rerun()

            force_overwrite_sync = st.checkbox(
                "強制全量重新整理 (覆蓋已存在紀錄)",
                value=False,
                help="預設僅同步缺漏之新運動以節省時間；若手錶近期運動有重新計算負荷、修改名稱或數值異常，勾選此項可強制從 Intervals.icu 重新抓取並覆蓋雲端資料。",
                key="cb_force_sync_icu"
            )

            if sync_btn:
                with st.spinner("正在同步 Intervals.icu 數據至 Firebase..."):
                    try:
                        s_count, sk_count, s_msg = ic.sync_pre_lactate_activities_to_firebase(
                            uid=icu_uid,
                            firebase_token=icu_token,
                            intervals_api_key=icu_creds["token"],
                            athlete_id=icu_creds["athlete_id"],
                            lookback_days=7,
                            lookahead_days=7,
                            is_oauth=icu_creds["is_oauth"],
                            incremental_only=False, # 手動按鈕進行完整掃描
                            force_overwrite=force_overwrite_sync
                        )
                        # 清除月曆快取、週報快取與日期範圍快取，確保日曆重新自 Firestore 載入最新狀態
                        st.session_state[auto_sync_key] = time.time()
                        st.session_state.pop(f"cal_cache_data_{icu_uid}", None)
                        st.session_state.pop("cached_weekly_report_html", None)
                        st.session_state.pop(f"date_bounds_v4_{icu_uid}", None)
                        today_str = date.today().strftime("%Y-%m-%d")
                        st.session_state["cal_selected_date"] = today_str
                        st.session_state["cal_view_year"] = date.today().year
                        st.session_state["cal_view_month"] = date.today().month
                        if s_count > 0:
                            st.toast(s_msg, icon="✅")
                            st.success(s_msg)
                            st.rerun()
                        else:
                            st.toast(s_msg, icon="ℹ️")
                            st.info(s_msg)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ 同步過程發生異常：{str(e)}")
                        print(f"手動同步異常: {e}")
        else:
            # 未連線狀態：僅保留「一鍵授權」與「手動輸入 API Key」兩個選項
            if oauth_cfg["client_id"]:
                redirect_target = ic.resolve_redirect_uri(oauth_cfg["redirect_uri"])
                auth_url = ic.get_intervals_oauth_authorize_url(
                    client_id=oauth_cfg["client_id"],
                    redirect_uri=redirect_target,
                    state=f"icu_{icu_uid}"
                )
                st.link_button("🔗 一鍵授權連結 Intervals.icu (OAuth 2.0)", auth_url, type="primary", use_container_width=True)
            else:
                st.info("💡 **OAuth 2.0 系統端已就緒**\n\n收到官方審核之 `client_id` 與 `client_secret` 填入即可啟用一鍵授權！目前可先使用下方 API Key 連結。")

            with st.expander("🛠️ 手動輸入 API Key 與 Athlete ID", expanded=not oauth_cfg["client_id"]):
                ath_id_input = st.text_input("Intervals.icu Athlete ID", value="0", help="個人帳號請填 0，或填入如 i123456", key="input_ath_id")
                api_key_input = st.text_input("Intervals.icu API Key", type="password", help="登入 intervals.icu -> Settings (設定) 頁面最下方即可複製 API Key", key="input_api_key")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("🔌 測試連線", use_container_width=True, key="btn_test_icu"):
                        ok, msg = ic.test_intervals_connection(api_key_input, ath_id_input, is_oauth=False)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                with col_b2:
                    if st.button("💾 儲存並連線", use_container_width=True, key="btn_save_icu_key"):
                        ok, msg = ic.test_intervals_connection(api_key_input, ath_id_input, is_oauth=False)
                        if ok:
                            ic.save_user_intervals_apikey(icu_uid, icu_token, api_key_input, ath_id_input)
                            st.toast("已儲存 API Key 連線！", icon="✅")
                            st.rerun()
                        else:
                            st.error(f"連線失敗: {msg}")

    st.sidebar.markdown("---")

st.sidebar.markdown("### 介面設定")
chart_theme = st.sidebar.radio("圖表主題", ["深色模式 (Dark)", "淺色模式 (Light)"])
theme_str = "dark" if "Dark" in chart_theme else "light"
st.sidebar.markdown("---")

st.sidebar.markdown("### 🛠️ 整合分析工具模式")
MODE_OPTIONS = ["單期分析與資料登錄", "多期數據整合儀表板 (LacV5)", "AI 運動生理週報與下一次處方"]
PARAM_TO_MODE = {
    "single": "單期分析與資料登錄",
    "multi": "多期數據整合儀表板 (LacV5)",
    "ai": "AI 運動生理週報與下一次處方"
}
MODE_TO_PARAM = {v: k for k, v in PARAM_TO_MODE.items()}

# 僅在初次載入或收到來自 URL/外部跳轉且與上次同步不同的參數時，才由 query_params 更新 session_state
qp_m = st.query_params.get("app_mode")
if qp_m in PARAM_TO_MODE:
    target_mode = PARAM_TO_MODE[qp_m]
    if st.session_state.get("_last_synced_app_mode") != qp_m:
        st.session_state["app_mode_select"] = target_mode
        st.session_state["_last_synced_app_mode"] = qp_m

def _on_app_mode_change():
    sel = st.session_state.get("app_mode_select")
    new_param = MODE_TO_PARAM.get(sel, "single")
    st.query_params["app_mode"] = new_param
    st.session_state["_last_synced_app_mode"] = new_param

if "app_mode_select" not in st.session_state or st.session_state["app_mode_select"] not in MODE_OPTIONS:
    st.session_state["app_mode_select"] = MODE_OPTIONS[0]

app_mode = st.sidebar.radio(
    "功能模式選擇",
    MODE_OPTIONS,
    key="app_mode_select",
    on_change=_on_app_mode_change
)

# 保持 query_params 與 session 紀錄一致
current_param = MODE_TO_PARAM.get(app_mode, "single")
st.query_params["app_mode"] = current_param
st.session_state["_last_synced_app_mode"] = current_param

if app_mode == "多期數據整合儀表板 (LacV5)":
    st.markdown('<div class="title-container" style="display: flex; align-items: center;"><h1 style="margin: 0; color: #00f2fe;">📊 多期數據整合儀表板 (LacV5)</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-text">支援<b>從 Firebase 雲端選取歷史數據</b>，同時<b>保留上傳單期 HTML 報告</b>進行多期交叉對照與動力學分析。</div>', unsafe_allow_html=True)

    # 1. 來源選擇與設定
    tab_cloud, tab_upload = st.tabs(["☁️ 從 Firebase 雲端選取歷史數據", "📂 上傳單期 HTML 報告檔案 (.html)"])

    with tab_cloud:
        active_uid, active_email, active_name, is_coach_view = get_active_athlete_context()
        token = st.session_state.get('firebase_token', '')
        if not active_uid:
            st.info("💡 **提示**：請先於左側邊欄登入 MyLactate 雲端帳號，即可從雲端下拉選單直接勾選已儲存的手錶 FIT 與乳酸紀錄進行多期作圖。\n\n（若無雲端帳號，亦可使用右側「📂 上傳單期 HTML 報告檔案」直接分析。）")
        else:
            if is_coach_view:
                st.caption(f"👑 **教練視角**：正調閱選手 **{active_name}** ({active_email}) 之雲端活動記錄")
            import activity_calendar
            import importlib
            importlib.reload(activity_calendar)
            activity_calendar.render_activity_calendar(
                uid=active_uid,
                token=token,
                theme=theme_str,
                mode="multi"
            )

    with tab_upload:
        st.markdown("#### 📂 選擇要整合的本機 HTML 報告檔 (.html)")
        selected_html_files = st.file_uploader(
            "請點擊或拖曳選擇單期 HTML 報告檔案（可多選）",
            type=["html"],
            accept_multiple_files=True,
            key="multi_html_uploader"
        )
        if selected_html_files:
            st.success(f"已選取 {len(selected_html_files)} 個本機 HTML 報告檔案。")

    # 2. 彙整待整合之多期數據池 (Merged Session Pool)
    cloud_sessions = st.session_state.get('multi_selected_cloud_sessions', {})
    
    # 解析本機上傳之 HTML 檔案
    uploaded_sessions = {}
    if 'multi_html_uploader' in st.session_state and st.session_state['multi_html_uploader']:
        uploader_files = st.session_state['multi_html_uploader']
        for f in uploader_files:
            try:
                content_bytes = f.read()
                f.seek(0)
                date_str, s_dict = integrate_reports.parse_single_session_html(content_bytes)
                if date_str and (s_dict.get('power_30s') or s_dict.get('lactate')):
                    uploaded_sessions[f"upload_{f.name}_{date_str}"] = {
                        **s_dict,
                        'source': 'upload',
                        'activity_name': f.name,
                        'date_key': date_str
                    }
            except Exception as e:
                st.error(f"解析上傳報告 `{f.name}` 失敗: {e}")

    # 合併雲端與上傳的期數
    merged_data = {}
    preview_rows = []

    # (A) 處理雲端點選期數
    for k, s in cloud_sessions.items():
        st_time = s.get('startTime', '')
        d_str = st_time[:10] if len(st_time) >= 10 else k
        key_name = d_str
        if key_name in merged_data:
            key_name = f"{d_str} ({s.get('activity_name', '雲端活動')})"
        merged_data[key_name] = s
        preview_rows.append({
            '期數標籤': key_name,
            '來源': '☁️ Firebase 雲端',
            '活動名稱': s.get('activity_name', '-'),
            '開始時間': st_time,
            '時長': s.get('stats', {}).get('duration', '-'),
            '平均/最大功率': f"{s.get('stats', {}).get('avg_power', '-')} / {s.get('stats', {}).get('max_power', '-')} W",
            '乳酸記錄': f"💧 {len(s.get('lactate', []))} 點" if s.get('lactate') else '無',
            '血糖記錄': f"{len(s.get('glucose', []))} 點" if s.get('glucose') else '無',
        })

    # (B) 處理上傳期數
    for k, s in uploaded_sessions.items():
        st_time = s.get('startTime', '')
        d_str = s.get('date_key', st_time[:10] if len(st_time) >= 10 else k)
        key_name = d_str
        if key_name in merged_data:
            key_name = f"{d_str} ({s.get('activity_name', '上傳檔案')})"
        merged_data[key_name] = s
        preview_rows.append({
            '期數標籤': key_name,
            '來源': '📄 上傳報告',
            '活動名稱': s.get('activity_name', '-'),
            '開始時間': st_time,
            '時長': s.get('stats', {}).get('duration', '-'),
            '平均/最大功率': f"{s.get('stats', {}).get('avg_power', '-')} / {s.get('stats', {}).get('max_power', '-')} W",
            '乳酸記錄': f"💧 {len(s.get('lactate', []))} 點" if s.get('lactate') else '無',
            '血糖記錄': f"{len(s.get('glucose', []))} 點" if s.get('glucose') else '無',
        })

    st.markdown("---")
    st.markdown("### 📋 待整合之多期數據清單")
    if preview_rows:
        col_p1, col_p2 = st.columns([4, 1])
        with col_p1:
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)
        with col_p2:
            if st.button("🗑️ 清空選定清單", use_container_width=True):
                st.session_state['multi_selected_cloud_sessions'] = {}
                st.session_state.pop('latest_output_html', None)
                st.rerun()
    else:
        st.info("💡 目前尚未選取任何期數。請至上方「☁️ 從 Firebase 雲端選取歷史數據」勾選期數，或於「📂 上傳單期 HTML 報告檔案」中選取檔案。")

    output_html_path = st.text_input("輸出 HTML 報告儲存路徑", value="LactateReport/LacV5.html", help="請輸入包含檔名的完整路徑")

    if st.button("🚀 開始整合並繪製多期對照圖表 (LacV5)", type="primary", use_container_width=True):
        if not merged_data:
            st.warning("請先由雲端月曆選取或由本機上傳至少一個期數的數據！")
        else:
            with st.spinner("正在產生 Chart.js 多期數據整合儀表板..."):
                try:
                    html_content = integrate_reports.build_integrated_html(merged_data, theme=theme_str)
                    out_dir = os.path.dirname(output_html_path)
                    if out_dir:
                        os.makedirs(out_dir, exist_ok=True)
                    with open(output_html_path, 'w', encoding='utf-8') as out_f:
                        out_f.write(html_content)
                    st.success(f"✨ 多期數據整合成功！報告已儲存至：`{output_html_path}`")
                    st.session_state['latest_output_html'] = output_html_path
                except Exception as e:
                    st.error(f"整合過程中發生錯誤: {e}")

    # 如果有成功輸出的報告檔，提供預覽與下載
    latest_out = st.session_state.get('latest_output_html')
    if latest_out and os.path.exists(latest_out):
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 📊 整合報告互動預覽 (Chart.js)")

        with open(latest_out, 'r', encoding='utf-8') as out_f:
            html_report_data = out_f.read()

        st.download_button(
            label="📥 下載整合 HTML 網頁報告",
            data=html_report_data,
            file_name=os.path.basename(latest_out),
            mime="text/html",
            use_container_width=True
        )

        components.html(html_report_data, height=900, scrolling=True)

    st.stop()


if app_mode == "AI 運動生理週報與下一次處方":
    st.markdown('<div class="title-container" style="display: flex; align-items: center;"><h1 style="margin: 0; color: #00f2fe;">💧 AI 運動生理週期分析與處方（汗乳酸動態）</h1></div>', unsafe_allow_html=True)
    st.caption("以穿戴式汗乳酸動力學、真實訓練間隔天數與代謝輸出比為核心之運動科學診斷")

    active_uid, active_email, athlete_name, is_coach_view = get_active_athlete_context()
    uid = active_uid
    token = st.session_state.get('firebase_token')
    ref_token = st.session_state.get('firebase_refresh_token')

    if not uid:
        st.warning("🔒 **請先登入 MyLactate 雲端帳號**")
        st.info("系統將讀取您個人的真實汗乳酸測試紀錄與手錶日常運動進行運動生理週期分析。請於左側側邊欄輸入帳號密碼登入。")
        st.stop()

    if is_coach_view:
        st.success(f"👑 **教練模式鎖定中**：已連結選手 **{athlete_name}**（{active_email}）之個人雲端數據庫（UID: `{uid[:8]}...`）")
    else:
        st.success(f"👤 已連結個人雲端帳號：**{active_email or st.session_state.get('firebase_email')}**（數據來源：Firebase 雲端資料庫）")

    import importlib
    import weekly_physio_engine as wpe
    import ai_weekly_report as awr
    importlib.reload(wpe)
    importlib.reload(awr)
    import streamlit.components.v1 as components
    from datetime import datetime

    col_ctl1, col_ctl2, col_ctl3 = st.columns([3, 2, 1])
    with col_ctl1:
        bounds_key = f"date_bounds_v4_{uid}"
        if bounds_key not in st.session_state:
            st.session_state[bounds_key] = wpe.get_user_training_date_bounds(uid, token, ref_token)
        slider_min, slider_max, def_start, def_end = st.session_state[bounds_key]

        selected_date_range = st.slider(
            "選擇 AI 分析日期區間 (左右滑動選取區間)",
            min_value=slider_min,
            max_value=slider_max,
            value=(def_start, def_end),
            format="YYYY-MM-DD",
            help="直接拖拉起始與結束日期，系統將自動納入該區間內的所有汗乳酸關鍵測驗、日常手錶運動與 Intervals.icu 晨間 HRV 數據",
            key="ai_report_date_slider_v4"
        )
        if isinstance(selected_date_range, (list, tuple)) and len(selected_date_range) == 2:
            start_date_sel, end_date_sel = selected_date_range[0], selected_date_range[1]
        else:
            start_date_sel, end_date_sel = def_start, def_end

    with col_ctl2:
        sport_filter = st.selectbox(
            "運動專項篩選 (分開分析)",
            options=["all", "running", "cycling"],
            format_func=lambda x: {
                "all": "🌐 全部專項 (綜合交叉分析)",
                "running": "🏃 僅分析跑步訓練 (Running)",
                "cycling": "🚲 僅分析自行車騎行 (Cycling)"
            }.get(x, x),
            help="分開評估跑步（心率/配速）與自行車（瓦數/代謝效率），避免跨專項生理特徵混淆",
            key="ai_report_sport_filter"
        )
    with col_ctl3:
        st.write("")
        st.write("")
        btn_gen = st.button("⚡ 立即生成/更新 AI 運動週報", type="primary", use_container_width=True)
        if btn_gen:
            st.session_state.pop(bounds_key, None)

    # 自動快取失效機制（當調整日期區間、專項篩選、切換身分或引擎升級時自動重算，避免舊快取鎖死）
    REPORT_VERSION = "20260924_v15_long_term_adaptation"
    current_cache_key = f"{uid}_{athlete_name}_{start_date_sel}_{end_date_sel}_{sport_filter}_{REPORT_VERSION}"
    if st.session_state.get("cached_report_key") != current_cache_key:
        st.session_state.pop("cached_weekly_report_html", None)

    if btn_gen or "cached_weekly_report_html" not in st.session_state:
        with st.spinner("🧠 正在透過汗乳酸生理學引擎運算並呼叫 AI 生成處方..."):
            report_data = awr.generate_weekly_report_data(
                athlete_name=athlete_name,
                uid=uid,
                token=token,
                refresh_token=ref_token,
                start_date=start_date_sel,
                end_date=end_date_sel,
                sport_filter=sport_filter
            )

            # 若 token 有刷新，更新 session_state
            if report_data.get("new_token"):
                st.session_state["firebase_token"] = report_data["new_token"]

            # 若查無任何訓練場次，嚴格提示使用者
            if not report_data.get("sessions"):
                st.session_state.pop("cached_weekly_report_html", None)
                err_msg = report_data.get("fetch_error", "查無訓練紀錄")
                st.warning(f"⚠️ **{athlete_name} 您好**：在【{sport_filter}】專項篩選下查無足夠之運動紀錄。\n\n**詳細原因**：{err_msg}")
                st.info("""💡 **操作建議**：
1. **專項篩選**：若您進行的是跑步訓練，請確認上方篩選為 **🏃 僅分析跑步訓練 (Running)** 或 **🌐 全部專項**。
2. **上傳記錄**：若尚未上傳含有乳酸測試的 FIT 檔案，可切換至【FIT 檔與乳酸協同分析】上傳並標記乳酸。
3. **手錶日常同步**：使用左側側邊欄的【🔗 運動手錶雲端綁定 (Garmin / COROS via Intervals.icu)】一鍵同步手錶日常訓練。
""")
                st.stop()

            html_report = awr.render_modern_html_report(report_data)
            st.session_state["cached_weekly_report_html"] = html_report
            st.session_state["cached_report_key"] = current_cache_key

    if "cached_weekly_report_html" in st.session_state:
        st.download_button(
            label="💾 下載完整 HTML 報告",
            data=st.session_state["cached_weekly_report_html"],
            file_name=f"lactate_weekly_report_{datetime.now().strftime('%Y%m%d')}.html",
            mime="text/html"
        )
        components.html(st.session_state["cached_weekly_report_html"], height=950, scrolling=True)

    st.stop()



import base64
try:
    with open("logo.jpg", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    img_tag = f'<img src="data:image/jpeg;base64,{encoded_string}" style="height: 50px; vertical-align: middle; margin-right: 15px; border-radius: 50%; object-fit: cover;">'
    st.markdown(f'<div class="title-container" style="display: flex; align-items: center;">{img_tag}FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)
except:
    st.markdown('<div class="title-container">🩸 FIT 檔與乳酸協同分析工具</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">上傳運動 .fit 檔案，標定乳酸測試數據，進行心率、功率、核心體溫與乳酸的完美對照作圖。</div>', unsafe_allow_html=True)

# 初始化 session state 中的乳酸與血糖數據
if 'custom_lactate' not in st.session_state:
    st.session_state['custom_lactate'] = pd.DataFrame({
        '相對時間 (分鐘)': pd.Series(dtype='float'),
        '乳酸值 (mmol/L)': pd.Series(dtype='float'),
        '血糖值 (mg/dL)': pd.Series(dtype='float')
    })

# 側邊欄：檔案上傳與設定
st.sidebar.markdown("### 📁 數據源選擇")
uploaded_file = st.sidebar.file_uploader("上傳您的 FIT 檔 (.fit)", type=["fit"])

st.sidebar.markdown("---")
st.sidebar.markdown("### 📥 歷史報告匯入工具")
with st.sidebar.expander("匯入已分析的 HTML 報告", expanded=True):
    st.caption("將之前產生的 HTML 分析報告直接上傳還原至 MyLactate 雲端，自動轉換為 30 秒平均與乳酸紀錄。")
    uploaded_htmls = st.file_uploader("選擇 HTML 報告 (可多選)", type=["html"], accept_multiple_files=True, key="history_html_uploader")
    if uploaded_htmls:
        if not st.session_state.get('firebase_uid'):
            st.warning("⚠️ 請先在上方登入 MyLactate 帳號再進行匯入！")
        else:
            if st.button("🚀 開始批次匯入至雲端", use_container_width=True):
                success_count = 0
                fail_count = 0
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                for i, h_file in enumerate(uploaded_htmls):
                    status_text.text(f"正在處理 ({i+1}/{len(uploaded_htmls)}): {h_file.name}")
                    h_content = h_file.read().decode('utf-8', errors='ignore')
                    ok, msg = import_historical_html_to_firebase(h_content, h_file.name)
                    if ok:
                        success_count += 1
                    else:
                        fail_count += 1
                        st.error(f"❌ {h_file.name}: {msg}")
                    progress_bar.progress((i + 1) / len(uploaded_htmls))
                status_text.empty()
                progress_bar.empty()
                if success_count > 0:
                    st.success(f"🎉 成功匯入 {success_count} 筆歷史紀錄！")
                    st.rerun()

# 如果沒有上傳檔案，提供載入預設測試檔的按鈕，以方便使用者快速體驗
fit_bytes = None
file_name = ""
if uploaded_file is not None:
    fit_bytes = uploaded_file.read()
    file_name = uploaded_file.name
    # 若手動上傳新檔案，清除從雲端月曆載入的 session
    st.session_state.pop('active_cloud_session', None)

if 'last_file' not in st.session_state:
    st.session_state['last_file'] = None

if file_name and file_name != st.session_state['last_file']:
    st.session_state['last_file'] = file_name
    # 重設為預設乳酸與血糖數據
    st.session_state['custom_lactate'] = pd.DataFrame({
        '相對時間 (分鐘)': pd.Series(dtype='float'),
        '乳酸值 (mmol/L)': pd.Series(dtype='float'),
        '血糖值 (mg/dL)': pd.Series(dtype='float')
    })
    # 清除編輯器狀態，強迫重新載入預設數據
    if 'custom_lactate_editor' in st.session_state:
        del st.session_state['custom_lactate_editor']

# 檢查是否有從雲端月曆點入之活動 Session
loaded_cloud_session = st.session_state.get('active_cloud_session')

# 主流程
if fit_bytes is not None or loaded_cloud_session is not None:
    if fit_bytes is not None:
        with st.spinner("正在解析 FIT 檔案中..."):
            parsed_res = parse_fit_file_data(fit_bytes)
            if len(parsed_res) == 5:
                df, df_laps, start_time, sport, sub_sport = parsed_res
            else:
                df, df_laps, start_time = parsed_res
                sport = df.attrs.get('sport', 'unknown')
                sub_sport = df.attrs.get('sub_sport', 'generic')
    else:
        # 載入雲端選定之活動
        df = loaded_cloud_session['df']
        df_laps = loaded_cloud_session.get('df_laps', pd.DataFrame())
        start_time = loaded_cloud_session['start_time']
        sport = loaded_cloud_session.get('sport', 'running')
        sub_sport = loaded_cloud_session.get('sub_sport', 'generic')
        file_name = loaded_cloud_session.get('file_name', 'Cloud_Activity.fit')
        act_title = loaded_cloud_session.get('activity_name') or file_name

        # 頂部提示與返回月曆按鈕
        col_c_info, col_c_back = st.columns([4, 1])
        with col_c_info:
            st.info(f"☁️ **已載入雲端活動**：`{act_title}` (開始時間: {start_time.strftime('%Y-%m-%d %H:%M')})，您可以直接在下方標定或編輯乳酸與血糖數據。")
        with col_c_back:
            if st.button("📅 返回活動月曆", key="btn_back_to_cal_top", use_container_width=True):
                st.session_state.pop('active_cloud_session', None)
                st.rerun()
        
    if df.empty:
        st.error("FIT 檔案解析失敗或無有效 Record 數據。")
    else:
        # 1. 頂部 KPI 卡片區
        duration_minutes = df['elapsed_minutes'].max()
        duration_str = f"{int(duration_minutes)} 分 {int((duration_minutes % 1)*60)} 秒"
        
        avg_power = int(df['power'].mean()) if df['power'].notna().any() else 0
        max_power = int(df['power'].max()) if df['power'].notna().any() else 0
        avg_hr = int(df['heart_rate'].mean()) if df['heart_rate'].notna().any() else 0
        max_hr = int(df['heart_rate'].max()) if df['heart_rate'].notna().any() else 0
        max_core = df['core_temp'].max() if df['core_temp'].notna().any() else None
        
        # 顯示 metadata 資訊與關鍵指標
        has_gps_flag = ('lat' in df.columns and df['lat'].notna().any() and 'lng' in df.columns and df['lng'].notna().any())
        tot_dist_km = (df['distance'].dropna().iloc[-1] / 1000.0) if ('distance' in df.columns and df['distance'].notna().any()) else 0.0
        gps_badge = f" | **📍 GPS 軌跡**: 已擷取 ({tot_dist_km:.2f} km)" if has_gps_flag else ""
        
        sport_icon_map = {
            'cycling': ('🚴 自行車 (Cycling)', '#00f2fe'),
            'running': ('🏃 跑步 (Running)', '#ff5252'),
            'swimming': ('🏊 游泳 (Swimming)', '#4facfe'),
            'walking': ('🚶 健走 (Walking)', '#00e676'),
            'fitness_equipment': ('🏋️ 健身器材 (Gym)', '#ffab00'),
            'generic': ('🏅 運動訓練 (Generic)', '#ffab00'),
            'unknown': ('🎯 運動活動', '#94a3b8')
        }
        sport_text, sport_col = sport_icon_map.get(sport, (f"🏅 {sport.capitalize()}", "#ffab00"))
        sub_info = f" · {sub_sport}" if sub_sport and sub_sport != 'generic' else ""
        sport_badge = f" | **🏃 運動類型**: <span style='color:{sport_col}; font-weight:700;'>{sport_text}{sub_info}</span>"
        
        st.markdown(f"**📅 活動開始時間**: {start_time.strftime('%Y-%m-%d %H:%M:%S')} (在地時間/UTC) | **📄 檔案名稱**: `{file_name}`{sport_badge}{gps_badge}", unsafe_allow_html=True)
        
        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">⏱️ 活動時長</div><div class="metric-value" style="color: #00b0ff;">{duration_str}</div></div>', unsafe_allow_html=True)
        with kpi_cols[1]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">⚡ 平均 / 最大功率</div><div class="metric-value" style="color: #29b6f6;">{avg_power} / {max_power} W</div></div>', unsafe_allow_html=True)
        with kpi_cols[2]:
            st.markdown(f'<div class="metric-card"><div class="metric-label">❤️ 平均 / 最大心率</div><div class="metric-value" style="color: #ff5252;">{avg_hr} / {max_hr} bpm</div></div>', unsafe_allow_html=True)
        with kpi_cols[3]:
            if max_core is not None:
                st.markdown(f'<div class="metric-card"><div class="metric-label">🔥 最大核心溫度</div><div class="metric-value" style="color: #ff9100;">{max_core:.2f} °C</div></div>', unsafe_allow_html=True)
            else:
                
                st.markdown('<div class="metric-card"><div class="metric-label">🔥 最大核心溫度</div><div class="metric-value" style="color: #8b949e;">未偵測</div></div>', unsafe_allow_html=True)
            
        if st.session_state.get('firebase_uid'):
            if st.session_state.get('last_uploaded_fit_name') != file_name:
                # Automatically upload
                with st.spinner('自動同步 FIT 數據至雲端...'):
                    if upload_fit_to_firebase(df, file_name, start_time, avg_power, max_power, avg_hr, max_hr, max_core, sport=sport, sub_sport=sub_sport):
                        st.session_state['last_uploaded_fit_name'] = file_name

            
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # 2. 乳酸與血糖數據輸入區
        st.header("✍️ 自訂相對時間乳酸與血糖數據輸入")
        st.markdown("請在下方表格中輸入各時間點量測的乳酸與血糖數據。您可以自由新增或刪除行數，時間為相對於運動起點的累計分鐘數（支援輸入負數以代表運動前的熱身或基期測量）。")
        

        col1, col2 = st.columns([1, 1])
        with col2:
            if st.button('From MyLactate Sync LA-01', use_container_width=True):
                if "firebase_uid" not in st.session_state:
                    st.error("請先在左側邊欄登入 MyLactate 帳號！")
                else:
                    with st.spinner('Syncing...'):
                        cloud_records = fetch_firebase_lactate_records(start_time, duration_minutes)
                        if cloud_records:
                            new_rows = []
                            for r in cloud_records:
                                new_rows.append({
                                    '相對時間 (分鐘)': round(r['elapsed_minutes'], 1),
                                    '乳酸值 (mmol/L)': round(r['lactate_mmol'], 2),
                                    '血糖值 (mg/dL)': np.nan
                                })
                            if new_rows:
                                st.session_state['custom_lactate'] = pd.DataFrame(new_rows)
                                st.rerun()
        edited_custom_df = st.data_editor(
            st.session_state['custom_lactate'],
            column_config={
                '相對時間 (分鐘)': st.column_config.NumberColumn("相對時間 (分鐘)", min_value=None, step=0.1, format="%.1f"),
                '乳酸值 (mmol/L)': st.column_config.NumberColumn("乳酸值 (mmol/L)", min_value=0.0, step=0.1, format="%.2f"),
                '血糖值 (mg/dL)': st.column_config.NumberColumn("血糖值 (mg/dL)", min_value=0.0, step=1.0, format="%d")
            },
            num_rows="dynamic",
            use_container_width=True,
            key="custom_lactate_editor"
        )
        
        col_s1, col_s2 = st.columns([2.5, 1.5])
        with col_s2:
            if st.button("💾 儲存並綁定乳酸數據至此活動", type="primary", use_container_width=True, help="將上方編輯的乳酸數據直接綁定寫入此運動活動的 Firebase 紀錄中"):
                if not st.session_state.get('firebase_uid'):
                    st.error("請先在左側邊欄登入 MyLactate 雲端帳號！")
                else:
                    import activity_calendar
                    act_obj = st.session_state.get('active_cloud_session', {})
                    fit_doc_id = act_obj.get('doc_id') or f"fit_{start_time.strftime('%Y%m%d_%H%M%S')}"
                    with st.spinner("正在儲存並綁定乳酸數據至雲端..."):
                        ok, msg = activity_calendar.save_bound_lactate_to_firestore(
                            uid=st.session_state['firebase_uid'],
                            token=st.session_state.get('firebase_token', ''),
                            fit_doc_id=fit_doc_id,
                            start_time=start_time,
                            lactate_df=edited_custom_df
                        )
                        if ok:
                            st.toast(msg, icon="✅")
                            st.success(f"🎉 {msg}")
                        else:
                            st.error(f"儲存失敗: {msg}")

        # 彙整 custom 乳酸與血糖點
        custom_lactate_points = []
        for idx, row in edited_custom_df.iterrows():
            t = row['相對時間 (分鐘)']
            lac = row.get('乳酸值 (mmol/L)')
            glc = row.get('血糖值 (mg/dL)')
            has_lac = pd.notna(lac) and lac >= 0
            has_glc = pd.notna(glc) and glc >= 0
            if pd.notna(t) and (has_lac or has_glc):
                custom_lactate_points.append({
                    'elapsed_minutes': float(t),
                    'lactate': float(lac) if has_lac else np.nan,
                    'glucose': float(glc) if has_glc else np.nan,
                    'source': '自訂時間'
                })
                
        # 合併所有的乳酸與血糖數據點
        all_lactate = pd.DataFrame(custom_lactate_points)
        if not all_lactate.empty:
            all_lactate = all_lactate.sort_values(by='elapsed_minutes').reset_index(drop=True)
            
        st.markdown("<hr>", unsafe_allow_html=True)

        
        # 3. 圖表顯示設定
        st.sidebar.markdown("### 📈 圖表顯示設定")
        smooth_power = st.sidebar.checkbox("顯示 30 秒平均功率 (平滑功率線)", value=True)
        
        # 4. 繪製圖表
        st.header("📊 數據協同分析圖表")
        
        # 檢查是否有核心溫度數據
        has_core_temp = df['core_temp'].notna().any()
        show_temp_panel = has_core_temp
        
        # 根據是否有溫度數據，動態決定子圖列數與高度比例
        if show_temp_panel:
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.06,
                row_heights=[0.4, 0.3, 0.3],
                specs=[
                    [{"secondary_y": True}],  # Row 1: Power (left) & HR (right)
                    [{"secondary_y": False}], # Row 2: Core Temp (single Y axis)
                    [{"secondary_y": True}]   # Row 3: Lactate (left) & Glucose (right)
                ]
            )
        else:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.6, 0.4],
                specs=[
                    [{"secondary_y": True}],  # Row 1: Power & HR
                    [{"secondary_y": True}]   # Row 2: Lactate (left) & Glucose (right)
                ]
            )
            
        # --- 第一層：功率與心率 ---
        # 功率 (W) - 原始數據
        fig.add_trace(
            go.Scatter(
                x=df['elapsed_minutes'],
                y=df['power'],
                name="功率 (W)",
                line=dict(color="rgba(0, 176, 255, 0.25)", width=1),
                hoverinfo="skip" if smooth_power else "all"
            ),
            row=1, col=1, secondary_y=False
        )
        
        # 功率 (W) - 30秒平滑
        if smooth_power and df['power'].notna().any():
            df['power_smoothed'] = df['power'].rolling(window=30, min_periods=1).mean()
            fig.add_trace(
                go.Scatter(
                    x=df['elapsed_minutes'],
                    y=df['power_smoothed'],
                    name="功率 (30s 平均)",
                    line=dict(color="#00b0ff", width=2),
                ),
                row=1, col=1, secondary_y=False
            )
            
        # 心率 (BPM)
        fig.add_trace(
            go.Scatter(
                x=df['elapsed_minutes'],
                y=df['heart_rate'],
                name="心率 (BPM)",
                line=dict(color="#ff2a5f", width=1.5),
            ),
            row=1, col=1, secondary_y=True
        )
        
        # --- 第二層：溫度數據 (如果有的話) ---
        if show_temp_panel:
            # 核心溫度
            if has_core_temp:
                fig.add_trace(
                    go.Scatter(
                        x=df['elapsed_minutes'],
                        y=df['core_temp'],
                        name="核心溫度 (°C)",
                        line=dict(color="#ff9100", width=2.5),
                        connectgaps=True
                    ),
                    row=2, col=1
                )
                
        # --- 第三層 / 第二層：乳酸與血糖數據 ---
        lactate_row = 3 if show_temp_panel else 2
        
        if not all_lactate.empty:
            # 繪製乳酸折線圖與點標記 (左 Y 軸)
            if 'lactate' in all_lactate.columns and all_lactate['lactate'].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=all_lactate['elapsed_minutes'],
                        y=all_lactate['lactate'],
                        name="乳酸 (mmol/L)",
                        mode="lines+markers",
                        marker=dict(size=10, color="#00e676", symbol="diamond", line=dict(color="white", width=1.5)),
                        line=dict(color="#00e676", width=2.5, dash="dash"),
                        text=all_lactate['source'],
                        hovertemplate="時間: %{x:.1f} 分<br>乳酸: %{y:.2f} mmol/L<br>來源: %{text}<extra></extra>"
                    ),
                    row=lactate_row, col=1, secondary_y=False
                )
            
            # 繪製血糖折線圖與點標記 (右 Y 軸)
            if 'glucose' in all_lactate.columns and all_lactate['glucose'].notna().any():
                fig.add_trace(
                    go.Scatter(
                        x=all_lactate['elapsed_minutes'],
                        y=all_lactate['glucose'],
                        name="血糖 (mg/dL)",
                        mode="lines+markers",
                        marker=dict(size=10, color="#d500f9", symbol="circle", line=dict(color="white", width=1.5)),
                        line=dict(color="#d500f9", width=2.5, dash="dot"),
                        text=all_lactate['source'],
                        hovertemplate="時間: %{x:.1f} 分<br>血糖: %{y:.1f} mg/dL<br>來源: %{text}<extra></extra>"
                    ),
                    row=lactate_row, col=1, secondary_y=True
                )
            
            # 在各層加上檢測點的垂直虛線 (VLine)，方便對齊
            for idx, r in all_lactate.iterrows():
                fig.add_vline(
                    x=r['elapsed_minutes'],
                    line_width=1,
                    line_dash="dash",
                    line_color="rgba(255, 255, 255, 0.35)",
                    row="all",
                    col=1
                )
                
        # --- 圖表佈局與樣式調整 ---
        
        is_dark = (theme_str == "dark")
        fig.update_layout(
            height=750,
            hovermode="x unified",
            font=dict(size=20, color="#ffffff" if is_dark else "#000000"),
            template="plotly_dark" if is_dark else "plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=60, r=60, t=40, b=40),
            plot_bgcolor='rgba(30, 30, 38, 0.4)' if is_dark else 'rgba(240, 240, 245, 0.4)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        # 坐標軸標題與格線

        fig.add_hrect(
            y0=0, y1=15, line_width=0, fillcolor="rgba(0, 255, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.add_hrect(
            y0=15, y1=30, line_width=0, fillcolor="rgba(255, 255, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.add_hrect(
            y0=30, y1=45, line_width=0, fillcolor="rgba(255, 0, 0, 0.15)", opacity=0.3,
            row=lactate_row, col=1, secondary_y=False
        )
        fig.update_xaxes(showgrid=False, ticks='outside', ticklen=6, tickwidth=1, showline=True, linewidth=1, linecolor='rgba(255,255,255,0.5)')
        fig.update_yaxes(showgrid=False, ticks='outside', ticklen=6, tickwidth=1, showline=True, linewidth=1, linecolor='rgba(255,255,255,0.5)')
        
        # 標定各軸名稱
        fig.update_xaxes(title_text="時間 (相對分鐘)", row=lactate_row, col=1)
        fig.update_yaxes(title_text="功率 (W)", row=1, col=1, secondary_y=False, title_font=dict(color="#00b0ff", size=18), tickfont=dict(size=14))
        fig.update_yaxes(title_text="心率 (BPM)", row=1, col=1, secondary_y=True, title_font=dict(color="#ff2a5f", size=18), tickfont=dict(size=14))
        
        if show_temp_panel:
            fig.update_yaxes(title_text="核心溫度 (°C)", row=2, col=1, title_font=dict(color="#ff9100", size=18), tickfont=dict(size=14))
                
        fig.update_yaxes(title_text="乳酸 (mmol/L)", row=lactate_row, col=1, secondary_y=False, range=[0, 45], title_font=dict(color="#00e676", size=18), tickfont=dict(size=14))
        fig.update_yaxes(title_text="血糖 (mg/dL)", row=lactate_row, col=1, secondary_y=True, title_font=dict(color="#d500f9", size=18), tickfont=dict(size=14))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 5. 數據彙整摘要表格與導出
        st.markdown("<hr>", unsafe_allow_html=True)
        st.header("📊 生理數據對照彙整表")
        
        if not all_lactate.empty:
            st.markdown("下表自動比對您輸入的每一個量測點，並撈取該時間點 FIT 檔中最接近的功率、心率與體溫數據，提供完整的生理指標摘要。")
            
            summary_rows = []
            for idx, r in all_lactate.iterrows():
                t = r['elapsed_minutes']
                lac = r.get('lactate')
                glc = r.get('glucose')
                source = r['source']
                
                # 尋找最接近的記錄
                diffs = (df['elapsed_minutes'] - t).abs()
                nearest_idx = diffs.idxmin()
                nearest = df.iloc[nearest_idx]
                
                calc_time = start_time + timedelta(minutes=float(t))
                is_before_start = (t < 0)
                
                summary_rows.append({
                    '量測時間 (分)': round(t, 1),
                    '乳酸值 (mmol/L)': round(lac, 2) if pd.notna(lac) else "-",
                    '血糖值 (mg/dL)': int(glc) if pd.notna(glc) else "-",
                    '量測點來源': source,
                    '對應功率 (W)': "-" if is_before_start else (str(int(nearest['power'])) if pd.notna(nearest['power']) else "-"),
                    '對應心率 (BPM)': "-" if is_before_start else (str(int(nearest['heart_rate'])) if pd.notna(nearest['heart_rate']) else "-"),
                    '對應核心溫度 (°C)': "-" if is_before_start else (f"{nearest['core_temp']:.2f}" if pd.notna(nearest['core_temp']) else "-"),
                    '實際時間 (Time)': calc_time.strftime('%H:%M:%S')
                })
                
            summary_df = pd.DataFrame(summary_rows)
            st.dataframe(summary_df, use_container_width=True)
            
            st.markdown("<hr>", unsafe_allow_html=True)
            st.header("💾 儲存與產出分析報告")
            st.markdown("您可以將包含互動式圖表、生理指標與對照表在內的**整個網頁報告**，一鍵儲存至本地專案資料夾，或下載至瀏覽器保存。")
            
            # 產生 HTML 報告內容
            html_report_data = generate_html_report(
                summary_df, 
                fig, 
                start_time, 
                file_name, 
                {
                    'duration_str': duration_str,
                    'avg_power': avg_power,
                    'max_power': max_power,
                    'avg_hr': avg_hr,
                    'max_hr': max_hr,
                    'max_core': max_core
                }
            )
            
            save_cols = st.columns(4)
            
            with save_cols[0]:
                if st.button("💾 儲存報告至本機專案資料夾", use_container_width=True):
                    try:
                        os.makedirs("saved_reports", exist_ok=True)
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        html_path = f"saved_reports/lactate_report_{timestamp_str}.html"
                        csv_path = f"saved_reports/lactate_report_{timestamp_str}.csv"
                        
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html_report_data)
                        
                        summary_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                        
                        st.success(f"✨ 報告已成功儲存至本地 `saved_reports/` 資料夾！\n\n- **HTML 網頁檔**：`{html_path}` (雙擊即可開啟)\n- **CSV 數據檔**：`{csv_path}`")
                    except Exception as e:
                        st.error(f"儲存失敗: {e}")
            
            with save_cols[1]:
                st.download_button(
                    label="📥 下載 HTML 網頁報告",
                    data=html_report_data,
                    file_name=f"lactate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    use_container_width=True
                )
                
            with save_cols[2]:
                csv_buffer = io.StringIO()
                summary_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下載生理彙整 CSV 檔",
                    data=csv_buffer.getvalue(),
                    file_name=f"lactate_physiological_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    with save_cols[3]:
        if st.button("☁️ 備份分析報告至 MyLactate", use_container_width=True):
            if not st.session_state.get('firebase_uid'):
                st.error("請先於左側登入 MyLactate")
            else:
                with st.spinner("上傳中..."):
                    fname = f"lactate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    ok, msg = upload_report_to_firebase_storage(html_report_data, fname)
                    if ok:
                        st.success("✅ 已上傳至 MyLactate 雲端儲存空間！")
                    else:
                        st.error(f"上傳失敗: {msg}")

        else:
            st.info("請於上方輸入乳酸數據，此處將自動產生對照彙整表與提供報告下載。")
            
        # 額外功能：允許下載完整解析後的 FIT 檔案 CSV
        with st.expander("🛠️ 進階：下載完整解析的 FIT 軌跡 CSV"):
            csv_full_buffer = io.StringIO()
            df.to_csv(csv_full_buffer, index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載完整 FIT 軌跡資料 CSV",
                data=csv_full_buffer.getvalue(),
                file_name=f"parsed_fit_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
else:
    # 歡迎畫面與雲端運動活動月曆 (高對比自適應版)
    active_uid, active_email, athlete_name, is_coach_view = get_active_athlete_context()
    if active_uid:
        if is_coach_view:
            st.info(f"👑 **教練視角**：正瀏覽選手 **{athlete_name}** ({active_email}) 之活動月曆與歷史乳酸紀錄")
        import activity_calendar
        import importlib
        importlib.reload(activity_calendar)
        activity_calendar.render_activity_calendar(
            uid=active_uid,
            token=st.session_state.get('firebase_token', ''),
            theme=theme_str,
            mode="single"
        )
    else:
        st.info("👋 歡迎使用！請先在左側欄上傳您的 `.fit` 檔案，或是登入 MyLactate 雲端帳號以啟用活動月曆瀏覽手錶擷取之運動紀錄。")
    
    if active_uid:
        with st.spinner('正在載入歷史乳酸紀錄...'):
            all_records = fetch_firebase_lactate_records(target_uid=active_uid)
            if all_records:
                import plotly.express as px
                df_hist = pd.DataFrame(all_records)
                if not df_hist.empty and 'record_time' in df_hist.columns:
                    df_hist['date_str'] = df_hist['record_time'].dt.strftime('%Y-%m-%d')
                    
                    # 取出最近五個不同日期，並按時間由舊至新排序
                    unique_dates = df_hist['date_str'].drop_duplicates().sort_values(ascending=False).head(5).values
                    dates_chrono = sorted(unique_dates)
                    df_top5 = df_hist[df_hist['date_str'].isin(dates_chrono)].copy()
                    df_top5 = df_top5.sort_values('record_time')
                    
                    # 計算各期量測順序
                    df_top5['測試點順序'] = df_top5.groupby('date_str').cumcount() + 1
                    
                    # 雙色漸層色碼搭配：#D7CCC8 ➔ #4E342E
                    def generate_gradient(start_hex, end_hex, n):
                        if n <= 1:
                            return [end_hex]
                        r1, g1, b1 = int(start_hex[1:3], 16), int(start_hex[3:5], 16), int(start_hex[5:7], 16)
                        r2, g2, b2 = int(end_hex[1:3], 16), int(end_hex[3:5], 16), int(end_hex[5:7], 16)
                        colors = []
                        for i in range(n):
                            t = i / (n - 1)
                            r = int(round(r1 + (r2 - r1) * t))
                            g = int(round(g1 + (g2 - g1) * t))
                            b = int(round(b1 + (b2 - b1) * t))
                            colors.append(f"#{r:02X}{g:02X}{b:02X}")
                        return colors
                    
                    num_dates = len(dates_chrono)
                    gradient_colors = generate_gradient('#E0F7FA', '#006064', num_dates)
                    color_discrete_map = {d: c for d, c in zip(dates_chrono, gradient_colors)}
                    
                    fig = px.line(
                        df_top5,
                        x='測試點順序',
                        y='lactate_mmol',
                        color='date_str',
                        markers=True,
                        color_discrete_map=color_discrete_map,
                        category_orders={'date_str': dates_chrono},
                        title='📈 最近五期乳酸紀錄趨勢',
                        labels={'測試點順序': '該期量測順序 (點)', 'lactate_mmol': '乳酸值 (mmol/L)', 'date_str': '測試日期'}
                    )
                    
                    # 最新一期特別強調線條寬度與標記
                    latest_date = dates_chrono[-1]
                    for trace in fig.data:
                        if trace.name == latest_date:
                            trace.line.width = 3.5
                            trace.marker.size = 9
                        else:
                            trace.line.width = 2.0
                            trace.marker.size = 6
                    
                    is_dark_theme = (theme_str == "dark")
                    axis_color = '#E0E0E0' if is_dark_theme else '#000000'
                    font_color = '#FFFFFF' if is_dark_theme else '#000000'
                    
                    fig.update_layout(
                        xaxis_title="該期量測順序 (點)",
                        yaxis_title="乳酸值 (mmol/L)",
                        xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                        hovermode="x unified",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=font_color, size=14),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                            font=dict(size=12)
                        )
                    )
                    # 套用高對比無格線風格
                    fig.update_xaxes(showgrid=False, showline=True, linewidth=2, linecolor=axis_color, ticks='outside', tickcolor=axis_color, ticklen=5)
                    fig.update_yaxes(showgrid=False, showline=True, linewidth=2, linecolor=axis_color, ticks='outside', tickcolor=axis_color, ticklen=5)
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # -------------------------------------------------------------
                    # 智能計算判定：最新一期 vs 前四期差異與訓練建議
                    # -------------------------------------------------------------
                    st.markdown("#### 🧠 近五期乳酸智能評估與訓練建議")
                    
                    prev_dates = dates_chrono[:-1]
                    latest_vals = df_top5[df_top5['date_str'] == latest_date]['lactate_mmol'].dropna().tolist()
                    latest_mean = float(np.mean(latest_vals)) if latest_vals else 0.0
                    
                    if prev_dates:
                        prev_vals = df_top5[df_top5['date_str'].isin(prev_dates)]['lactate_mmol'].dropna().tolist()
                        prev_mean = float(np.mean(prev_vals)) if prev_vals else 0.0
                        diff = latest_mean - prev_mean
                        diff_pct = (diff / prev_mean * 100.0) if prev_mean > 0 else 0.0
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        with col_m1:
                            st.metric(
                                label=f"最新期 ({latest_date}) 平均乳酸",
                                value=f"{latest_mean:.2f} mmol/L"
                            )
                        with col_m2:
                            st.metric(
                                label=f"前 {len(prev_dates)} 期歷史基準平均",
                                value=f"{prev_mean:.2f} mmol/L"
                            )
                        with col_m3:
                            st.metric(
                                label="最新期 vs 前期差異",
                                value=f"{diff:+.2f} mmol/L",
                                delta=f"{diff_pct:+.1f}%",
                                delta_color="inverse"
                            )
                        
                        if diff > 0.1:
                            st.warning(
                                f"⚠️ **系統建議：** 最新一期平均乳酸為 **{latest_mean:.2f} mmol/L**，較前 {len(prev_dates)} 期平均（**{prev_mean:.2f} mmol/L**）高出 **+{diff:.2f} mmol/L (+{diff_pct:.1f}%)**，顯示疲勞累積或恢復未完全，建議安排充分休息或降低近期訓練強度。"
                            )
                        elif diff < -0.1:
                            st.success(
                                f"💪 **系統建議：** 最新一期平均乳酸為 **{latest_mean:.2f} mmol/L**，較前 {len(prev_dates)} 期平均（**{prev_mean:.2f} mmol/L**）低了 **{abs(diff):.2f} mmol/L ({diff_pct:.1f}%)**，生理與有氧代謝狀態良好，建議可維持或適度增加訓練強度。"
                            )
                        else:
                            st.info(
                                f"⚖️ **系統建議：** 最新一期平均乳酸為 **{latest_mean:.2f} mmol/L**，與前 {len(prev_dates)} 期平均（**{prev_mean:.2f} mmol/L**）差異極微（**{diff:+.2f} mmol/L**），生理狀態維持平穩，建議按原定課表規律訓練。"
                            )
                    else:
                        st.info(f"ℹ️ 目前僅有 1 期歷史紀錄（{latest_date}），平均乳酸為 **{latest_mean:.2f} mmol/L**。待累積第 2 期以上紀錄後，系統將自動啟動近五期乳酸對比與訓練調整建議。")

    st.markdown("""
    ### 💡 本工具特色：
    1. **自動對齊**：自動將 FIT 檔時間軸轉換為運動起點開始的「相對分鐘數」，完美對齊測試時間。
    2. **自訂相對時間**：支援彈性輸入任何相對時間點（分鐘）與乳酸值（無限制上限），完美對齊生理軌跡。
    3. **核心溫度支援**：內建解析 CORE 體溫感測器的開發者欄位 (`unknown_139`)，自動縮放顯示核心與皮膚溫度。
    4. **30s 功率平滑**：可切換顯示 30s 平均功率線，避開功率跳動干擾，看清真實強度。
    5. **對應生理分析表**：自動拉取每個乳酸點對應的即時心率、功率與體溫，一鍵匯出完整生理評估報告。
    """)


