"""
Google Calendar OAuth初回認証スクリプト

使い方:
  1. Google Cloud ConsoleでOAuth 2.0クライアントIDを作成
  2. credentials.json（クライアントシークレット）をこのスクリプトと同じ場所に配置
  3. python scripts/authorize_google.py を実行
  4. ブラウザでGoogleアカウントにログインして許可
  5. 出力されたJSONをコピーして環境変数に設定:
       GOOGLE_CALENDAR_CREDENTIALS_JSON=<出力されたJSON>

Google Cloud Consoleの設定:
  - APIとサービス → 認証情報 → OAuth 2.0クライアントID
  - アプリケーションの種類: デスクトップアプリ
  - Google Calendar API を有効化すること
"""

import json
import os
import sys

# スクリプトからsrcをimportできるようにパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")


def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ {CREDENTIALS_FILE} が見つかりません。")
        print()
        print("Google Cloud Console から OAuth 2.0 クライアントIDをダウンロードして")
        print(f"  {CREDENTIALS_FILE}")
        print("として保存してください。")
        sys.exit(1)

    print("🔑 Google Calendar OAuth認証を開始します...")
    print("ブラウザが開くので、Googleアカウントでログインして許可してください。")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    token_json = json.dumps(token_data, ensure_ascii=False)

    print("✅ 認証成功！")
    print()
    print("以下のJSONを環境変数 GOOGLE_CALENDAR_CREDENTIALS_JSON に設定してください:")
    print()
    print(token_json)
    print()
    print("【Railwayへの設定方法】")
    print("  Railway ダッシュボード → Variables → 新規追加")
    print("  Name: GOOGLE_CALENDAR_CREDENTIALS_JSON")
    print("  Value: 上記のJSON文字列")
    print()
    print("【.envファイルへの設定方法】")
    print("  GOOGLE_CALENDAR_CREDENTIALS_JSON='上記のJSON文字列'")


if __name__ == "__main__":
    main()
