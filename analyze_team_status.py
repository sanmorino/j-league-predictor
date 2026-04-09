import sys
import os
import time
import pandas as pd
from google import genai
from dotenv import load_dotenv
from db_client import db
from predict_engine import PredictEngine

# .envファイルを読み込む
load_dotenv()

# 設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL_NAME = "gemini-2.0-flash"

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY is not set in .env")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_and_register_team_status(team_name, team_id=None):
    """チームの最新状況を分析し、DBに登録する"""
    print(f"--- Analyzing team: {team_name} ---")
    
    from datetime import datetime
    current_date = datetime.now().strftime("%Y年%m月%d日")
    
    # プロンプトの生成
    # 依頼内容に基づいたプロンプト
    prompt = f"""
あなたは、サッカーJリーグの非常に優秀で情報通な戦術アナリストです。
{team_name}の**本日（{current_date}）時点での最新のチーム状況**を、以下の観点で鋭く分析してください。

【重要：最新情報の優先】
過去の栄光や昨シーズンのデータ、一般的な解説ではなく、**直近2週間以内（できれば最新数日）**の具体的なニュース、負傷者情報、監督・選手の最新コメント、直近2〜3試合のパフォーマンスにのみ焦点を当ててください。

【分析観点】
  ・直近で主力選手の故障、出場停止、コンディション不良、移籍関連の噂、クラブ内部の問題など、次節の試合に直接影響のある「具体的なマイナス要素」が存在するか。
  - 最近2〜3試合の勝ち方・負け方、試合内容から見える「戦術的な浸透度」や「チームとしての勢い」はどうか。
  - 直近の会見やインタビューでの監督・選手の言葉から、チームの結束力やポジティブな変化、あるいは焦りや閉塞感が感じられるか。

【評価方法】
  分析観点による最新状況の分析に基づき、現在のチーム状況を以下の５段階で評価してください。
  1：低迷（出口が見えず、次節も勝てる要素が極めて薄い）
  2：低迷だが上向き傾向（結果は出ていないが、内容は改善しており光が見える）
  3：安定（波がなく、実力通りの戦いができている）
  4：勢いがある（主力の好調や戦術の浸透で勝ちを重ねているが、微細な不安要素もある）
  5：絶好調（攻守に隙がなく、圧倒的な勢いと自信に満ちている）

最後に、取得した内容を以下のJSON形式で出力してください。それ以外の挨拶や説明テキストは一切含めないでください。
{{
  "status": [評価値(1-5)],
  "details": "[分析結果テキスト（具体的かつ直近の事実に即した内容で記述してください）]"
}}
"""

    # リトライ設定
    max_retries = 3
    retry_delay = 5  # 秒

    for attempt in range(max_retries):
        try:
            # 検索機能を使用するかどうか（リトライ時は負荷軽減のためオフにする場合も考慮）
            tools = [{'google_search_retrieval': {}}] if attempt == 0 else []
            
            import json, re
            
            # google_search_retrieval使用時は response_mime_typeと併用不可のため、テキストからJSONを抽出
            if tools:
                response = client.models.generate_content(
                    model=LLM_MODEL_NAME,
                    contents=prompt,
                    config={'tools': tools}
                )
                raw_text = response.text
                # テキスト中のJSONブロックを抽出
                json_match = re.search(r'\{[\s\S]*?"status"[\s\S]*?\}', raw_text)
                if json_match:
                    result_json = json.loads(json_match.group())
                else:
                    result_json = json.loads(raw_text)
            else:
                response = client.models.generate_content(
                    model=LLM_MODEL_NAME,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
                result_json = json.loads(response.text)
            status = result_json.get("status")
            details = result_json.get("details")
            
            print(f"Status Rating: {status}")
            print(f"Analysis Summary: {details[:100]}...")

            # データベースに登録
            analysis_date = None
            if team_id:
                analysis_date = db.upsert_team_status(str(team_id), status, details)
                if analysis_date:
                    print(f"Success: Registered to database for team_id {team_id}.")
                else:
                    print(f"Error: Failed to register to database.")
            else:
                print(f"Warning: No team_id provided, skipped DB registration.")
            
            # 成功したら結果を返す
            return {
                "status": status,
                "details": details,
                "analysis_date": analysis_date or "N/A"
            }

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"Quota exceeded (429). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    if attempt == 0:
                        print("Next attempt will run WITHOUT google_search_retrieval to save quota.")
                    time.sleep(wait_time)
                    continue
            
            print(f"Error during analysis for {team_name}: {e}")
            break
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_team_status.py \"TeamA,TeamB\"")
        print("Example: python analyze_team_status.py \"浦和レッズ,川崎フロンターレ\"")
        sys.exit(1)

    cards_input = sys.argv[1]
    # "浦和レッズ,川崎フロンターレ" 形式をパース
    # 複数カードがカンマ区切りで重なっている場合も考慮（将来的に）
    teams_to_analyze = [t.strip() for t in cards_input.split(",")]
    
    # 試合結果が含まれる場合は無視（最初の2つだけ取る）
    if len(teams_to_analyze) > 2:
        teams_to_analyze = teams_to_analyze[:2]
    
    engine = PredictEngine()
    df_mapping = engine.load_team_mapping()
    
    for team_name in teams_to_analyze:
        # チームIDを曖昧一致で取得
        team_id = engine.get_closest_team_id(df_mapping, team_name)
        if team_id is None:
            print(f"Warning: Could not find team_id for '{team_name}'. Searching by exact name...")
            # 部分一致でのマッチングを試みる
            matches = df_mapping[df_mapping['team_name'].str.contains(team_name, na=False)]
            if not matches.empty:
                team_id = matches.iloc[0]['team_id']
                print(f"Found: {matches.iloc[0]['team_name']} (ID: {team_id})")

        if team_id is not None:
            analyze_and_register_team_status(team_name, team_id)
        else:
            print(f"Error: Team '{team_name}' not found in team_mapping table.")

if __name__ == "__main__":
    main()
