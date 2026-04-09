import pandas as pd
import json
import os
import difflib
from xgboost import XGBClassifier
try:
    from db_client import db
except ImportError:
    db = None

class PredictEngine:
    def __init__(self, data_dir="./data", model_path="xgboost_model.json", feature_cols_path="feature_columns.json"):
        self.data_dir = data_dir
        self.model_path = model_path
        self.feature_cols_path = feature_cols_path
        self.model = None
        self.feature_columns = None
        self._load_model()
        
    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = XGBClassifier()
            self.model.load_model(self.model_path)
            
        if os.path.exists(self.feature_cols_path):
            with open(self.feature_cols_path, "r", encoding="utf-8") as f:
                self.feature_columns = json.load(f)

    def load_team_mapping(self):
        """データベースからチームのマッピングを取得する"""
        print(f'load_team_mapping:{db}')
        if db is not None:
            df = db.fetch_team_mapping()
            if not df.empty:
                return df
        # ダミーを返す（フェイルセーフ）
        return pd.DataFrame({"team_id": [1, 2, 3], "team_name": ["鹿島アントラーズ", "サガン鳥栖", "セレッソ大阪"]})

    def get_closest_team_id(self, df_mapping, input_name):
        """ファジーマッチング（曖昧検索）を用いて最も近いチーム名のIDを取得する"""
        if df_mapping is None or df_mapping.empty:
            return None
        teams = df_mapping['team_name'].tolist()
        matches = difflib.get_close_matches(input_name, teams, n=1, cutoff=0.3)
        if matches:
            best_match = matches[0]
            team_id = df_mapping[df_mapping['team_name'] == best_match]['team_id'].iloc[0]
            return team_id
        return None

    def _get_team_stats(self, df_source, team_id, prefix=""):
        """各CSVデータから指定されたチームの1行を辞書で取得し、プレフィックスをつける"""
        if df_source is None or df_source.empty:
            return {}
        
        try:
            # 型による不一致を防ぐため、int型にキャストして比較する
            target_id = int(float(team_id))
            row = df_source[df_source["team_id"].astype(float).astype(int) == target_id]
        except ValueError:
            return {}
            
        if row.empty:
            return {}
            
        row_dict = row.iloc[0].to_dict()
        # 不要なメタデータを削除
        row_dict.pop("team_id", None)
        row_dict.pop("shotkey", None)
        
        return {f"{prefix}{k}": v for k, v in row_dict.items()}

    def get_data_shotkey(self):
        """dataフォルダ内のいずれかのCSVからshotkeyを取得して日本語日付文字列に変換する"""
        try:
            df = self._load_csv("AGI,KAGI.csv")
            if df is not None and "shotkey" in df.columns and not df.empty:
                shotkey_val = str(int(df["shotkey"].iloc[0]))  # 例: "20260406"
                if len(shotkey_val) == 8:
                    year = shotkey_val[:4]
                    month = shotkey_val[4:6]
                    day = shotkey_val[6:8]
                    return f"{year}年{month}月{day}日 現在"
        except Exception:
            pass
        return None

    def _load_csv(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            return pd.read_csv(path)
        return None

    def create_features(self, home_team_id, away_team_id):
        """両チームの最新データから特徴量ベクトルを生成する"""
        
        if not os.path.exists(self.data_dir):
            return pd.DataFrame()
            
        # 1. 各ファイルからデータを読み込み
        df_goals = self._load_csv("Goal Points.csv")
        df_def = self._load_csv("Deffence Points.csv")
        df_atk = self._load_csv("Attack Points.csv")
        df_agi = self._load_csv("AGI,KAGI.csv")
        df_save = self._load_csv("Save Points.csv")
        df_ccr = self._load_csv("Chance Construction Rate.csv")
        df_cap = self._load_csv("Capture Points.csv")
        df_pass = self._load_csv("Pass Points.csv")
        df_dribble = self._load_csv("Dribble Points.csv")

        # どれか一つでもファイルが読み込めなければエラー
        required_dfs = [df_goals, df_def, df_atk, df_agi, df_save, df_ccr, df_cap, df_pass, df_dribble]
        if any(df is None for df in required_dfs):
            return pd.DataFrame()

        # ホームチームとアウェイチームのデータを取得
        h_goals = self._get_team_stats(df_goals, home_team_id)
        a_goals = self._get_team_stats(df_goals, away_team_id)
        
        # チームデータが見つからなかった場合エラー
        if not h_goals or not a_goals:
            return pd.DataFrame()
            
        
        h_def = self._get_team_stats(df_def, home_team_id)
        a_def = self._get_team_stats(df_def, away_team_id)
        
        h_atk = self._get_team_stats(df_atk, home_team_id)
        a_atk = self._get_team_stats(df_atk, away_team_id)
        
        h_agi = self._get_team_stats(df_agi, home_team_id)
        a_agi = self._get_team_stats(df_agi, away_team_id)
        
        h_save = self._get_team_stats(df_save, home_team_id)
        a_save = self._get_team_stats(df_save, away_team_id)
        
        h_ccr = self._get_team_stats(df_ccr, home_team_id)
        a_ccr = self._get_team_stats(df_ccr, away_team_id)
        
        h_cap = self._get_team_stats(df_cap, home_team_id)
        a_cap = self._get_team_stats(df_cap, away_team_id)
        
        h_pass = self._get_team_stats(df_pass, home_team_id)
        a_pass = self._get_team_stats(df_pass, away_team_id)
        
        h_dribble = self._get_team_stats(df_dribble, home_team_id)
        a_dribble = self._get_team_stats(df_dribble, away_team_id)

        # 基礎項目の構築
        base_features = {}
        
        def safe_val(d, key):
            try: return float(d.get(key, 0.0))
            except: return 0.0

        base_features['home_goal_points'] = safe_val(h_goals, 'goal_points')
        base_features['home_deffence_points'] = safe_val(h_def, 'deffence_points')
        base_features['home_attack_points'] = safe_val(h_atk, 'attack_points')
        base_features['home_agi'] = safe_val(h_agi, 'agi')
        base_features['home_save_points'] = safe_val(h_save, 'save_points')
        base_features['home_attacks'] = safe_val(h_atk, 'attacks')
        base_features['home_chance_construct_rate'] = safe_val(h_ccr, 'chance_construct_rate')
        base_features['home_shooting_success_rate'] = safe_val(h_ccr, 'shooting_success_rate')
        base_features['home_capture_points'] = safe_val(h_cap, 'capture_points')
        base_features['home_pass_points'] = safe_val(h_pass, 'pass_points')
        base_features['home_dribble_points'] = safe_val(h_dribble, 'dribble_points')

        base_features['away_goal_points'] = safe_val(a_goals, 'goal_points')
        base_features['away_deffence_points'] = safe_val(a_def, 'deffence_points')
        base_features['away_attack_points'] = safe_val(a_atk, 'attack_points')
        base_features['away_agi'] = safe_val(a_agi, 'agi')
        base_features['away_save_points'] = safe_val(a_save, 'save_points')
        base_features['away_attacks'] = safe_val(a_atk, 'attacks')
        base_features['away_chance_construct_rate'] = safe_val(a_ccr, 'chance_construct_rate')
        base_features['away_shooting_success_rate'] = safe_val(a_ccr, 'shooting_success_rate')
        base_features['away_capture_points'] = safe_val(a_cap, 'capture_points')
        base_features['away_pass_points'] = safe_val(a_pass, 'pass_points')
        base_features['away_dribble_points'] = safe_val(a_dribble, 'dribble_points')

        # 差分項目の構築
        base_features['diff_goal_points'] = base_features['home_goal_points'] - base_features['away_goal_points']
        base_features['diff_attack_points'] = base_features['home_attack_points'] - base_features['away_attack_points']
        base_features['diff_deffence_points'] = base_features['home_deffence_points'] - base_features['away_deffence_points']
        base_features['diff_agi'] = base_features['home_agi'] - base_features['away_agi']
        base_features['diff_save_points'] = base_features['home_save_points'] - base_features['away_save_points']
        base_features['diff_chance_construct_rate'] = base_features['home_chance_construct_rate'] - base_features['away_chance_construct_rate']
        base_features['diff_shooting_success_rate'] = base_features['home_shooting_success_rate'] - base_features['away_shooting_success_rate']
        base_features['diff_attacks'] = base_features['home_attacks'] - base_features['away_attacks']
        base_features['diff_capture_points'] = base_features['home_capture_points'] - base_features['away_capture_points']
        base_features['diff_pass_points'] = base_features['home_pass_points'] - base_features['away_pass_points']
        base_features['diff_dribble_points'] = base_features['home_dribble_points'] - base_features['away_dribble_points']

        # 比率項目の構築
        eps = 1e-5
        base_features['home_attack_vs_away_defense'] = base_features['home_goal_points'] / (base_features['away_deffence_points'] + eps)
        base_features['away_attack_vs_home_defense'] = base_features['away_goal_points'] / (base_features['home_deffence_points'] + eps)
        
        # 総合指標の構築
        base_features['home_overall'] = base_features['home_goal_points'] - base_features['home_deffence_points']
        base_features['away_overall'] = base_features['away_goal_points'] - base_features['away_deffence_points']
        base_features['diff_overall'] = base_features['home_overall'] - base_features['away_overall']

        # 最終的なDataFrameの構築
        df_target = pd.DataFrame([base_features])
        
        if self.feature_columns:
            for col in self.feature_columns:
                if col not in df_target.columns:
                    df_target[col] = 0.0
            df_target = df_target[self.feature_columns]
            
        return df_target

    def predict(self, home_team_id, away_team_id):
        """特徴量を生成して勝敗を予測する"""
        if self.model is None:
            return None, None, {"error": "モデルがロードされていません。先に学習を行ってください。"}
            
        df_features = self.create_features(home_team_id, away_team_id)
        if df_features.empty:
            return None, None, {"error": "必要な指標データ（CSV）または対象チームのデータが見つかりません。"}
            
        # XGBoostの入力に合わせてキャスト
        X = df_features.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # 予測 (0: Draw, 1: Home Win, 2: Away Win)
        pred_class = int(self.model.predict(X)[0])
        # 確率
        pred_proba = self.model.predict_proba(X)[0].tolist()
        
        features_json = json.dumps(df_features.iloc[0].to_dict(), ensure_ascii=False)
        return pred_class, pred_proba, features_json
