import os
import sys
import subprocess
from datetime import datetime

def run_command(command, cwd=None, capture=True):
    print(f"執行指令: {command}")
    if capture:
        result = subprocess.run(command, shell=True, cwd=cwd, text=True, capture_output=True)
        if result.returncode != 0:
            print(f"錯誤: {result.stderr}")
            return False, result.stderr
        return True, result.stdout
    else:
        # 不擷取輸出，讓終端機可以直接顯示並與使用者互動 (如登入畫面)
        result = subprocess.run(command, shell=True, cwd=cwd)
        return result.returncode == 0, ""

def main():
    print("=" * 50)
    print(" 🚀 LA-01 系統 GitHub 自動發布工具")
    print("=" * 50)
    
    # Check if git is installed
    success, _ = run_command("git --version")
    if not success:
        print("❌ 找不到 Git！請確認您的電腦已經安裝 Git (https://git-scm.com/downloads) 並已加入環境變數。")
        input("按 Enter 鍵離開...")
        return

    repo_url = input("\n請輸入您的 GitHub Repository 網址 (例如 https://github.com/您的帳號/專案名稱.git):\n> ").strip()
    if not repo_url:
        print("❌ 網址不能為空！")
        return

    # Initialize git if not already initialized
    if not os.path.exists(".git"):
        print("\n📦 初始化 Git 儲存庫...")
        run_command("git init")
        run_command("git branch -M main")

    # Check remote
    success, remotes = run_command("git remote -v")
    if "origin" in remotes:
        run_command(f"git remote set-url origin {repo_url}")
    else:
        run_command(f"git remote add origin {repo_url}")

    # Add files
    print("\n📦 正在將檔案加入版本控制...")
    run_command("git add .")

    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-deploy update: {timestamp}"
    print(f"\n📦 建立 Commit: {commit_msg}")
    run_command(f'git commit -m "{commit_msg}"')

    # Push
    print("\n🚀 正在推送到 GitHub... (將跳出視窗或提示要求您登入)")
    # 這裡將 capture 設為 False，讓 Git Credential Manager 可以正常彈出視窗或讓使用者輸入
    success, _ = run_command("git push -u origin main", capture=False)
    
    if success:
        print("\n✅ 發布成功！您的程式碼已經成功上傳到 GitHub！")
        print(f"🔗 專案網址: {repo_url.replace('.git', '')}")
    else:
        print("\n❌ 發布失敗！")
        print("💡 可能的解決方法：")
        print("1. 請確認剛才彈出的瀏覽器視窗中，您有正確登入並授權 GitHub。")
        print("2. 請確認您輸入的 Repository 網址是正確的。")
        print("3. 如果要求輸入密碼，請使用 GitHub 產生的 Personal Access Token (PAT) 而不是您的登入密碼。")

    print("=" * 50)
    input("按 Enter 鍵離開...")

if __name__ == "__main__":
    main()
