import pandas as pd
import json
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
try:
    from db_client import db
except ImportError:
    print("Warning: db_client not found. Make sure you are running from the correct directory.")
    db = None

def load_base_data(file_path="processed_data.csv"):
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return pd.DataFrame()

def load_accumulated_data():
    if db is None:
        return pd.DataFrame()
    df_history = db.fetch_completed_predictions()
    if df_history.empty:
        return pd.DataFrame()
    
    # JSONの特徴量文字列からDataFrameを再構築
    rows = []
    for _, row in df_history.iterrows():
        try:
            features = json.loads(row["features_json"])
            features["result"] = row["actual_result"]
            rows.append(features)
        except Exception as e:
            print(f"Error parsing json for row {row.get('id')}: {e}")
            
    if rows:
        df_acc = pd.DataFrame(rows)
        # 不要なカラムを取り除く、または現在のベーススキーマと不整合を起こさないようにする
        return df_acc
    return pd.DataFrame()

def train_model():
    print("Loading base training data...")
    df_base = load_base_data()
    
    print("Loading accumulated data from DB...")
    df_acc = load_accumulated_data()
    
    # データの統合
    if not df_base.empty and not df_acc.empty:
        # 古いスキーマがDBに残っている可能性があるため、ベースのスキマーに合わせる
        common_cols = [c for c in df_acc.columns if c in df_base.columns]
        df_acc = df_acc[common_cols]
        df = pd.concat([df_base, df_acc], ignore_index=True)
        print("Merged base data and accumulated data.")
    elif not df_base.empty:
        df = df_base.copy()
        print("Using only base data.")
    elif not df_acc.empty:
        df = df_acc.copy()
        print("Using only accumulated data.")
    else:
        print("No training data available.")
        return

    # メタデータなど、特徴量として不要なカラムを除外
    drop_columns = [
        'home_team_id', 'home_score', 'away_team_id', 'away_score'
    ]
    
    X = df.drop(columns=['result'] + [col for col in drop_columns if col in df.columns], errors='ignore')
    
    # NANを0などの適切な値で埋めるか、モデルに任せる（XGBoostはNANに対応している）
    # XGBoostが処理しやすいように数値型にキャスト
    X = X.apply(pd.to_numeric, errors='coerce')
    y = df['result'].astype(int)
    
    # 学習用と検証用に分割
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBClassifier...")
    model = XGBClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train)
    
    # 評価
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Validation Accuracy: {acc:.4f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred))
    
    # モデルの保存
    model_path = "xgboost_model.json"
    model.save_model(model_path)
    print(f"Model saved to {model_path}")

    # 特徴量の一覧を保存（推論時に順番をマッチさせるため）
    feature_names = list(X.columns)
    with open("feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(feature_names, f, ensure_ascii=False, indent=4)
    print("Feature columns saved to feature_columns.json")

if __name__ == "__main__":
    train_model()
