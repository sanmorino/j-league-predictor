import sys
import pandas as pd
from predict_engine import PredictEngine

try:
    engine = PredictEngine(data_dir=r'c:\dev\Google Antigravity\J-LeaguePrediction\data')
    df_teams = engine.load_team_mapping()
    
    with open('output.txt', 'w', encoding='utf-8') as f:
        f.write("--- df_teams ---\n")
        f.write(df_teams.to_string())
        
        h_id = engine.get_closest_team_id(df_teams, "鹿島アントラーズ")
        a_id = engine.get_closest_team_id(df_teams, "セレッソ大阪")
        f.write(f"\nh_id: {h_id}, a_id: {a_id}\n")
        
        df_feat = engine.create_features(h_id, a_id)
        f.write("--- features ---\n")
        for col in df_feat.columns:
            f.write(f"{col}: {df_feat[col].iloc[0]}\n")
            
except Exception as e:
    with open('output.txt', 'w') as f:
        f.write(str(e))
