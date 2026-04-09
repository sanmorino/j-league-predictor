import sys
from predict_engine import PredictEngine
import pandas as pd

try:
    engine = PredictEngine()
    df_teams = engine.load_team_mapping()
    print("Team Mappings:", df_teams.head())
    
    h_id = engine.get_closest_team_id(df_teams, "鹿島アントラーズ")
    a_id = engine.get_closest_team_id(df_teams, "セレッソ大阪")
    print(f"Testing predicted features for Home: {h_id}, Away: {a_id}")
    
    df_feat = engine.create_features(h_id, a_id)
    print("Features extracted shape:", df_feat.shape)
    print("Features:")
    for col in df_feat.columns:
        print(f"  {col}: {df_feat[col].iloc[0]}")
    
    pred_class, pred_proba, json_f = engine.predict(h_id, a_id)
    print(f"Prediction: class={pred_class}, proba={pred_proba}")
except Exception as e:
    import traceback
    traceback.print_exc()
