import os
import pandas as pd
import hashlib
from supabase import create_client, Client
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
load_dotenv()

class SupabaseDB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key or url == "your_supabase_project_url":
            self.client = None
        else:
            self.client: Client = create_client(str(url), str(key))

    def fetch_table_as_df(self, table_name: str) -> pd.DataFrame:
        """指定されたテーブルの全データを取得して DataFrame で返す"""
        if not self.client:
            print(f"Warning: Supabase client not initialized. Cannot fetch '{table_name}'.")
            return pd.DataFrame()
        
        # 簡易的に全件取得（件数が多い場合はページネーションが必要だが、Jリーグデータなら一度に取得可能と想定）
        response = self.client.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)

    def _hash_password(self, password: str) -> str:
        """パスワードのハッシュ化（簡易版）"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def sign_up(self, username, password):
        """新規ユーザー登録"""
        if not self.client: return False, "DB接続エラー"
        hashed = self._hash_password(password)
        try:
            # 既存チェック
            res = self.client.table("app_users").select("*").eq("username", username).execute()
            if res.data and len(res.data) > 0:
                return False, "そのユーザー名は既に使われています"
            
            self.client.table("app_users").insert({"username": username, "password_hash": hashed}).execute()
            return True, "登録が完了しました"
        except Exception as e:
            return False, f"登録エラー: {str(e)}"

    def sign_in(self, username, password):
        """ログイン処理"""
        if not self.client: return False, "DB接続エラー", None
        hashed = self._hash_password(password)
        res = self.client.table("app_users").select("*").eq("username", username).eq("password_hash", hashed).execute()
        if res.data and len(res.data) > 0:
            return True, "ログイン成功", res.data[0]["id"]
        return False, "ユーザー名またはパスワードが間違っています", None

    def upsert_user_team_stats(self, user_id, team_id, data_json):
        """ユーザーごとのカスタムチーム指標を保存"""
        if not self.client: return None
        from datetime import datetime
        import json
        # JSON文字列で渡された場合 dict に変換する（JSONBカラムの型不一致エラー回避）
        if isinstance(data_json, str):
            try:
                data_dict = json.loads(data_json)
            except Exception:
                data_dict = {}
        else:
            data_dict = data_json

        now = datetime.now().isoformat()
        return self.client.table("user_team_stats").upsert({
            "user_id": user_id,
            "team_id": team_id,
            "data": data_dict,
            "updated_at": now
        }, on_conflict="user_id, team_id").execute()

    def fetch_user_team_stats(self, user_id, team_id):
        """特定のユーザー・チームのカスタム指標を取得"""
        if not self.client: return None
        response = self.client.table("user_team_stats").select("data").eq("user_id", user_id).eq("team_id", team_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["data"]
        return None

    def upsert_custom_stats(self, team_id: str, data_json: str):
        """カスタム指標を保存（存在すれば更新、なければ挿入）"""
        if not self.client: return None
        from datetime import datetime
        now = datetime.now().isoformat()
        return self.client.table("custom_team_stats").upsert({
            "team_id": team_id,
            "data": data_json,
            "update": now
        }).execute()

    def fetch_custom_stats(self, team_id: str):
        """特定のチームのカスタム指標を取得"""
        if not self.client: return None
        response = self.client.table("custom_team_stats").select("data").eq("team_id", team_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["data"]
        return None

    def insert_prediction_history(self, match_date: str, home_team_id: int, away_team_id: int, features_json: str, actual_result: int):
        """試合の予測結果と使用した特徴量セットを履歴テーブルに保存"""
        if not self.client: return None
        return self.client.table("prediction_history").insert({
            "match_date": match_date,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "features_json": features_json,
            "actual_result": actual_result
        }).execute()

    def update_prediction_actual_result(self, history_id: int, actual_result: int):
        """試合終了後に実際の結果（0:引き分け, 1:ホーム勝ち, 2:アウェイ勝ち）を更新"""
        if not self.client: return None
        return self.client.table("prediction_history").update({
            "actual_result": actual_result
        }).eq("id", history_id).execute()

    def fetch_completed_predictions(self) -> pd.DataFrame:
        """結果が判明している（実際の試合結果が入力済みの）蓄積データを取得"""
        if not self.client: return pd.DataFrame()
        response = self.client.table("prediction_history").select("*").not_.is_("actual_result", "null").execute()
        return pd.DataFrame(response.data)

    def fetch_pending_predictions(self) -> pd.DataFrame:
        """まだ実際の試合結果が入力されていない予測履歴を取得"""
        if not self.client: return pd.DataFrame()
        response = self.client.table("prediction_history").select("*").is_("actual_result", "null").execute()
        return pd.DataFrame(response.data)

    def upsert_team_status(self, team_id: str, status: int, details: str):
        """最新のチーム状況を保存・更新する"""
        if not self.client: return None
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.client.table("latest_team_status").upsert({
            "team_id": team_id,
            "analysis_date": now,
            "status": status,
            "details": details
        }, on_conflict="team_id").execute()
        return now

    def fetch_team_status(self, team_id: str):
        """特定のチームの最新ステータスを取得"""
        if not self.client: return None
        response = self.client.table("latest_team_status").select("*").eq("team_id", team_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    def fetch_team_mapping(self) -> pd.DataFrame:
        """Supabase の team_mapping テーブルからチームのマスターデータを取得"""
        if not self.client: return pd.DataFrame()
        response = self.client.table("team_mapping").select("*").execute()
        return pd.DataFrame(response.data)

db = SupabaseDB()
