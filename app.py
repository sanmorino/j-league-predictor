import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import os

try:
    from predict_engine import PredictEngine
    from db_client import db
except ImportError:
    st.error("必要なモジュールが見つかりません。")
    db = None
st.write("Debug - Team Dict:", db)
# --- UI Aesthetics ---
st.set_page_config(page_title="J.League Predictor PRO", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for modern looks
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    color: #e6edf3;
}

h1, h2, h3 {
    color: #58a6ff;
    font-weight: 800;
}

div.stButton > button {
    background: linear-gradient(90deg, #1f6feb 0%, #3fb950 100%);
    color: white;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    transition: all 0.3s ease;
}

div.stButton > button:hover {
    box-shadow: 0 4px 15px rgba(63, 185, 80, 0.4);
    transform: translateY(-2px);
}

.card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 20px;
    margin: 10px 0;
    backdrop-filter: blur(10px);
}

.win-prob {
    font-size: 2.5em;
    font-weight: 800;
    text-shadow: 0 0 10px rgba(88, 166, 255, 0.5);
}

.stButton > button.team-btn {
    background: transparent;
    color: #58a6ff;
    border: 1px solid rgba(88, 166, 255, 0.3);
    padding: 2px 8px;
    font-size: 0.9em;
    font-weight: normal;
}
.stButton > button.team-btn:hover {
    background: rgba(88, 166, 255, 0.1);
    border-color: #58a6ff;
}
</style>
""", unsafe_allow_html=True)

st.title("⚽ J.League Predictor PRO")
st.markdown("AIと最新詳細スタッツによる究極の勝敗予測システム")

NO_DATA = "－"

# Initialize Engine
@st.cache_resource
def get_engine():
    return PredictEngine()

engine = get_engine()
df_teams = engine.load_team_mapping()
team_dict = dict(zip(df_teams['team_name'], df_teams['team_id']))

# --- Team Status Dialog ---
@st.dialog("チーム状況")
def show_team_status(team_name, team_id):
    st.markdown(f"### 🏟️ {team_name}")
    
    # DBからデータを取得
    status_data = db.fetch_team_status(str(team_id)) if db else None
    
    if not status_data:
        st.info("最新のチーム分析データはありません。")
        return
    
    # 分析日のチェック
    try:
        analysis_date = datetime.fromisoformat(status_data["analysis_date"])
        now = datetime.now(timezone.utc).replace(tzinfo=analysis_date.tzinfo)
        days_diff = (now - analysis_date).days
        if days_diff >= 14:
            st.info("最新のチーム分析データはありません。")
            return
        st.success(f"最終分析日: {analysis_date.strftime('%Y-%m-%d')} ({days_diff}日前)")
    except Exception:
        st.info("最新のチーム分析データはありません。")
        return
    
    # 評価を星で表示
    rating = "⭐" * int(status_data["status"])
    st.markdown(f"**現在の評価: {status_data['status']} / 5** {rating}")
    st.markdown("---")
    st.markdown(status_data["details"])

tab1, tab2 = st.tabs(["📂 一括予想 (CSV)", "📊 的中率レポート"])

# --- Tab 1: Batch Prediction ---
with tab1:
    st.markdown("### 📂 一括予想 (CSVから)")
    st.markdown("`ホームチーム名, アウェイチーム名, 試合結果(任意・0=分/1=H勝/2=A勝)` のファイル形式で一括予想を実行します。")
    
    uploaded_file = st.file_uploader("game_cards.csv を選択してください", type=["csv"])
    if uploaded_file is not None:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if 'last_file_id' not in st.session_state or st.session_state.last_file_id != file_id:
            st.session_state.last_file_id = file_id
            try:
                df_raw = pd.read_csv(uploaded_file, header=None)
                batch_data = []
                for idx, row in df_raw.iterrows():
                    if len(row) < 2: continue
                    actual_result_text = NO_DATA
                    if len(row) >= 3 and pd.notna(row[2]):
                        r_str = str(row[2]).strip()
                        if r_str in ['0', '1', '2']: actual_result_text = r_str
                        elif '分' in r_str or '引' in r_str or '0' in r_str: actual_result_text = "0"
                        elif 'ホ' in r_str or '1' in r_str: actual_result_text = "1"
                        elif 'ア' in r_str or '2' in r_str: actual_result_text = "2"
                    
                    batch_data.append({
                        "No.": idx + 1,
                        "ホーム": str(row[0]),
                        "アウェイ": str(row[1]),
                        "AI予想": NO_DATA,
                        "確率": NO_DATA,
                        "実際の結果": actual_result_text,
                        "判定": NO_DATA
                    })
                st.session_state.batch_df = pd.DataFrame(batch_data)
                for key in ['last_total', 'last_correct', 'last_saved', 'last_kuchi_text', 'batch_processed']:
                    if key in st.session_state: del st.session_state[key]
                st.rerun()
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

    if 'batch_df' in st.session_state:
        df_batch = st.session_state.batch_df
        def df_to_md_unified(df, centers):
            header = "| " + " | ".join(df.columns) + " |"
            sep = "| " + " | ".join([":---:" if c in centers else "---" for c in df.columns]) + " |"
            rows = []
            for _, r in df.iterrows():
                rows.append("| " + " | ".join([str(v) for v in r]) + " |")
            return "\n".join([header, sep] + rows)

        # --- Operation Panel ---
        with st.container():
            # Row 1: Settings
            col1, col2 = st.columns([1, 1])
            with col1:
                save_to_db = st.toggle("データベースへの学習データ登録を有効にする", value=False)
            with col2:
                margin_pct = st.slider("複数予測の許容差(%)", 0, 100, 20)
                margin_th = margin_pct / 100.0

            # Row 2: Actions and Stats
            col_btn_run, col_btn_reset, col_stats = st.columns([1.2, 0.8, 3.5])
            with col_btn_run:
                do_predict = st.button("🚀 一括予測を実行する", key="batch_pred_btn", use_container_width=True)
            with col_btn_reset:
                if st.button("🔄 リセット", use_container_width=True):
                    # 予測関連のカラムをNO_DATAにリセット（表自体は残す）
                    if 'batch_df' in st.session_state:
                        st.session_state.batch_df[['AI予想', '確率', '判定']] = NO_DATA
                    
                    # 統計情報と処理済みフラグのみを削除
                    for key in ['last_total', 'last_correct', 'last_saved', 'last_kuchi_text', 'batch_processed']:
                        if key in st.session_state: del st.session_state[key]
                    st.rerun()
            
            with col_stats:
                if st.session_state.get('batch_processed'):
                    accuracy_text = ""
                    if st.session_state.last_total > 0:
                        accuracy = st.session_state.last_correct / st.session_state.last_total * 100
                        accuracy_text = f"<span style='margin-left: 20px;'>💡 的中率: <b>{accuracy:.1f}%</b> ({st.session_state.last_correct}/{st.session_state.last_total})</span>"
                    
                    stats_html = f"""
<div style="background-color: rgba(88, 166, 255, 0.1); border: 1px solid rgba(88, 166, 255, 0.2); color: #58a6ff; padding: 8px 15px; border-radius: 8px; display: flex; align-items: center; width: 100%; font-size: 0.9em;">
    <div style="display: flex; align-items: center; width: 100%;">
        <span>{st.session_state.last_kuchi_text}</span>{accuracy_text}
    </div>
</div>
""".replace("\n", "")
                    st.markdown(stats_html, unsafe_allow_html=True)
                else:
                    st.markdown("<div style='height: 45px;'></div>", unsafe_allow_html=True)

        if do_predict:
            total_with_results = 0
            correct_predictions = 0
            total_kuchi = 1
            double_count, triple_count = 0, 0
            with st.spinner("AIによる予測を実行中..."):
                for idx, row in df_batch.iterrows():
                    h_id = engine.get_closest_team_id(df_teams, row['ホーム'])
                    a_id = engine.get_closest_team_id(df_teams, row['アウェイ'])
                    if h_id is None or a_id is None:
                        df_batch.at[idx, 'AI予想'] = "該当なし"
                        continue
                    pred_class, pred_proba, features_json = engine.predict(h_id, a_id)
                    if pred_class is None:
                        df_batch.at[idx, 'AI予想'] = "⚠️エラー"
                        continue
                    df_batch.at[idx, 'ホーム'] = df_teams[df_teams['team_id'] == h_id]['team_name'].iloc[0]
                    df_batch.at[idx, 'アウェイ'] = df_teams[df_teams['team_id'] == a_id]['team_name'].iloc[0]
                    sorted_classes = sorted(range(len(pred_proba)), key=lambda k: pred_proba[k], reverse=True)
                    c1, c2, c3 = sorted_classes[0], sorted_classes[1], sorted_classes[2]
                    p1, p2, p3 = pred_proba[c1], pred_proba[c2], pred_proba[c3]
                    selected_classes = [c1]
                    if (p1 - p2) <= margin_th:
                        selected_classes.append(c2)
                        if (p2 - p3) <= margin_th: selected_classes.append(c3)
                    total_kuchi *= len(selected_classes)
                    if len(selected_classes) == 2: double_count += 1
                    elif len(selected_classes) == 3: triple_count += 1
                    df_batch.at[idx, 'AI予想'] = ", ".join(map(str, sorted(selected_classes)))
                    df_batch.at[idx, '確率'] = ", ".join([f"{c}:{pred_proba[c]*100:.1f}%" for c in range(3)])
                    if row['実際の結果'] != NO_DATA:
                        actual_val = int(row['実際の結果'])
                        total_with_results += 1
                        if actual_val in selected_classes:
                            correct_predictions += 1
                            df_batch.at[idx, '判定'] = "🎯 的中"
                        else: df_batch.at[idx, '判定'] = "❌ 外れ"
                    if save_to_db and db is not None and db.client and row['実際の結果'] != NO_DATA:
                        try: db.insert_prediction_history(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(h_id), int(a_id), features_json, int(row['実際の結果']))
                        except: pass
            st.session_state.last_total, st.session_state.last_correct = total_with_results, correct_predictions
            st.session_state.last_kuchi_text = f"ダブル：{double_count} / トリプル：{triple_count} / 購入口数：{total_kuchi}"
            st.session_state.batch_processed = True
            st.rerun()

        st.markdown("---")
        
        # shotkeyからデータ基準日を取得
        data_date_label = engine.get_data_shotkey()
        if data_date_label:
            date_badge = f"""<span style='
                background-color: rgba(88, 166, 255, 0.15);
                border: 1px solid rgba(88, 166, 255, 0.4);
                color: #58a6ff;
                padding: 3px 12px;
                border-radius: 20px;
                font-size: 0.82em;
                font-weight: 600;
                vertical-align: middle;
                margin-left: 12px;
            '>📅 データ: {data_date_label}</span>"""
        else:
            date_badge = ""
        
        st.markdown(
            f"""<div style='display: flex; align-items: center; margin-bottom: 8px;'>
                <h3 style='margin: 0;'>🏟️ 対戦カード・予測状況</h3>
                {date_badge}
            </div>""",
            unsafe_allow_html=True
        )
        
        # テーブル表示の代わりに、チーム名をクリック可能にするためのカスタマイズ表示
        # カラムヘッダー
        cols = st.columns([0.5, 2, 2, 1, 2, 1, 1])
        headers = ["No.", "ホーム", "アウェイ", "AI予想", "確率", "結果", "判定"]
        for col, h in zip(cols, headers):
            col.write(f"**{h}**")

        st.write("Debug - Team Dict:", team_dict)
        
        for idx, row in df_batch.iterrows():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.5, 2, 2, 1, 2, 1, 1])
            c1.write(str(row["No."]))
            
            # ホームチームボタン
            h_name = str(row["ホーム"])
            h_id = team_dict.get(h_name)
            if c2.button(h_name, key=f"btn_h_{idx}", help=f"{h_name}の状況を表示", use_container_width=True):
                if h_id: show_team_status(h_name, h_id)
                else: st.error("チームIDが見つかりません。")
            
            # アウェイチームボタン
            a_name = str(row["アウェイ"])
            a_id = team_dict.get(a_name)
            if c3.button(a_name, key=f"btn_a_{idx}", help=f"{a_name}の状況を表示", use_container_width=True):
                if a_id: show_team_status(a_name, a_id)
                else: st.error("チームIDが見つかりません。")
                
            c4.write(str(row["AI予想"]))
            c5.write(str(row["確率"]))
            c6.write(str(row["実際の結果"]))
            c7.write(str(row["判定"]))

# --- Tab 2: Accuracy Report ---
with tab2:
    st.markdown("### 📊 AIモデル 成績レポート")
    if db is None or not db.client: st.error("Supabase クライアントが未設定です。")
    else:
        df_completed = db.fetch_completed_predictions()
        if df_completed.empty: st.info("評価可能な実績データがまだありません。")
        else:
            total = len(df_completed)
            st.metric("総データ件数", f"{total} 件")
            st.dataframe(df_completed.tail(10))
