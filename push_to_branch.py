# -*- coding: utf-8 -*-
import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime

# 確保 Windows 主控台編碼相容
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_cmd(command, cwd=None, capture=True):
    print(f">> {command}")
    if capture:
        res = subprocess.run(command, shell=True, cwd=cwd, text=True, capture_output=True, encoding='utf-8', errors='replace')
        if res.returncode != 0:
            if res.stderr.strip():
                print(f"[提示/輸出] {res.stderr.strip()}")
            return False, res.stderr
        return True, res.stdout
    else:
        res = subprocess.run(command, shell=True, cwd=cwd)
        return res.returncode == 0, ""

def sync_from_parent(repo_dir):
    parent_dir = os.path.dirname(os.path.abspath(repo_dir))
    files_to_sync = ["fit_lactate_fire.py", "ai_weekly_report.py"]
    for fname in files_to_sync:
        parent_file = os.path.join(parent_dir, fname)
        target_file = os.path.join(repo_dir, fname)
        if os.path.exists(parent_file):
            if not os.path.exists(target_file) or os.path.getmtime(parent_file) > os.path.getmtime(target_file):
                print(f"[*] 同步最新檔案: {fname} -> fit_lactate_fire/")
                shutil.copy2(parent_file, target_file)

def main():
    parser = argparse.ArgumentParser(description="一鍵推送到 GitHub 測試分支")
    parser.add_argument("--branch", "-b", default="feature/ai-weekly-report", help="目標分支名稱")
    parser.add_argument("--message", "-m", default="", help="Commit 訊息")
    parser.add_argument("--auto", "-y", action="store_true", help="非互動自動模式")
    args = parser.parse_args()

    print("=" * 60)
    print(" [*] LA-01 系統 - 一鍵推送到 GitHub 測試分支工具")
    print("=" * 60)

    # 確定 repo 目錄
    current_dir = os.path.abspath(os.getcwd())
    if os.path.exists(os.path.join(current_dir, ".git")):
        repo_dir = current_dir
    elif os.path.exists(os.path.join(current_dir, "fit_lactate_fire", ".git")):
        repo_dir = os.path.join(current_dir, "fit_lactate_fire")
    else:
        print("[!] 找不到 .git 目錄，請確認專案路徑！")
        if not args.auto:
            input("按 Enter 鍵結束...")
        sys.exit(1)

    print(f"[*] 儲存庫路徑: {repo_dir}")

    # 同步檔案
    sync_from_parent(repo_dir)

    # 檢查 Git
    ok, _ = run_cmd("git --version", cwd=repo_dir)
    if not ok:
        print("[!] 找不到 Git，請確認已安裝 Git 並加入 PATH！")
        if not args.auto:
            input("按 Enter 鍵結束...")
        sys.exit(1)

    # 決定分支名稱
    target_branch = args.branch
    if not args.auto:
        user_branch = input(f"\n請輸入要發布的分支名稱 [預設: {target_branch}]: ").strip()
        if user_branch:
            target_branch = user_branch

    # 決定 Commit 訊息
    commit_msg = args.message
    if not commit_msg:
        default_msg = f"feat: AI生理週報與多場次分析 (分支測試版) {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if not args.auto:
            user_msg = input(f"請輸入 Commit 訊息 [預設: {default_msg}]: ").strip()
            commit_msg = user_msg if user_msg else default_msg
        else:
            commit_msg = default_msg

    print("-" * 60)
    print(f"[*] 目標分支: {target_branch}")
    print(f"[*] Commit 訊息: {commit_msg}")
    print("-" * 60)

    # 檢查當前分支
    ok, current_branch = run_cmd("git branch --show-current", cwd=repo_dir)
    current_branch = current_branch.strip() if ok else ""

    # 切換或建立分支
    if current_branch != target_branch:
        ok, branches = run_cmd("git branch --list", cwd=repo_dir)
        existing = [b.strip().replace("*", "").strip() for b in branches.splitlines()]
        if target_branch in existing:
            print(f"[*] 切換至既有分支: {target_branch}")
            run_cmd(f"git checkout {target_branch}", cwd=repo_dir)
        else:
            print(f"[*] 建立並切換至新分支: {target_branch}")
            run_cmd(f"git checkout -b {target_branch}", cwd=repo_dir)

    # 加入檔案
    print("[*] 加入變更檔案至暫存區...")
    run_cmd("git add .", cwd=repo_dir)

    # 檢查有無變更
    ok, status_out = run_cmd("git status --porcelain", cwd=repo_dir)
    if not status_out.strip():
        print("[i] 目前工作區無新的變更需要 commit。")
    else:
        print(f"[*] 正在提交 Commit...")
        run_cmd(f'git commit -m "{commit_msg}"', cwd=repo_dir)

    # 推送至遠端
    print(f"[*] 正在推送到 GitHub 遠端分支 origin/{target_branch}...")
    success, _ = run_cmd(f"git push -u origin {target_branch}", cwd=repo_dir, capture=False)

    print("=" * 60)
    if success:
        print(f"[OK] 成功推送到測試分支: {target_branch}！")
        print(f"[Link] 分支檢視: https://github.com/ReadWeng/LA-01-Analyzer/tree/{target_branch}")
        print(f"[PR]   建立 PR 比較: https://github.com/ReadWeng/LA-01-Analyzer/pull/new/{target_branch}")
    else:
        print(f"[!] 推送失敗，請確認網路連線或 GitHub 存取權限。")
        print("💡 提示：若是首次推送或需要登入，請依跳出的瀏覽器視窗指示進行授權。")

    print("=" * 60)
    if not args.auto:
        input("按 Enter 鍵結束...")

if __name__ == "__main__":
    main()
