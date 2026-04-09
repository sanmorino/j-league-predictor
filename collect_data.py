import pandas as pd
import os
import re
import difflib
import argparse
import logging
from typing import Dict, List, Optional, Any
from db_client import db

# ログの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class TeamIDMapper:
    """チーム名を内部IDに紐付けるクラス（キャッシュ機能付き）"""
    def __init__(self):
        self.mapping = self._load_mapping()
        self.cache: Dict[str, str] = {}

    def _load_mapping(self) -> Dict[str, str]:
        try:
            mapping_df = db.fetch_table_as_df('team_mapping')
            if not mapping_df.empty:
                return dict(zip(mapping_df['team_name'], mapping_df['team_id'].astype(str)))
        except Exception as e:
            logger.error(f"チームマッピングの取得に失敗しました: {e}")
        return {}

    def find_id(self, query_name: Any) -> Optional[str]:
        if not query_name or pd.isna(query_name) or not self.mapping:
            return None
        
        query_name = str(query_name).strip()
        if query_name in self.cache:
            return self.cache[query_name]

        # 1. 完全一致
        if query_name in self.mapping:
            res = self.mapping[query_name]
        else:
            # 2. 部分一致または類似度検索
            names = list(self.mapping.keys())
            res = None
            for name in names:
                if query_name in name or name in query_name:
                    res = self.mapping[name]
                    break
            
            if not res:
                matches = difflib.get_close_matches(query_name, names, n=1, cutoff=0.3)
                if matches:
                    res = self.mapping[matches[0]]

        if res:
            self.cache[query_name] = res
        return res

# データソースの定義
# name: ファイル名, url: Football LabのURL, team_col: チーム名が入っているカラム名
# cols_map: {新カラム名: 元カラム名}, float_cols: 数値変換する元カラム名, clean_pct: %除去が必要か
DATA_SOURCE_CONFIGS = [
    {
        'name': 'AGI,KAGI',
        'url': 'https://www.football-lab.jp/summary/team_ranking/[LEAGUE]?year=100&data=kagi',
        'team_col': 'Unnamed: 2',
        'cols_map': {'agi': 'AGI', 'goal': 'ゴール', 'shoot': 'シュート'},
        'float_cols': ['AGI', 'ゴール', 'シュート']
    },
    {
        'name': 'Attack Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=offence',
        'team_col': 'Unnamed: 2',
        'cols_map': {'attack_points': '攻撃ポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['攻撃ポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Capture Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=gain',
        'team_col': 'Unnamed: 2',
        'cols_map': {'capture_points': '奪取ポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['奪取ポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Chance Construction Rate',
        'url': 'https://www.football-lab.jp/summary/team_ranking/[LEAGUE]?year=100&data=chance',
        'team_col': 'Unnamed: 1',
        'cols_map': {
            'attacks': '攻撃回数', 'shoot': 'シュート', 'chance_construct_rate': 'チャンス 構築率', 
            'goal': 'ゴール', 'shooting_success_rate': 'シュート 成功率'
        },
        'float_cols': ['攻撃回数', 'シュート', 'チャンス 構築率', 'ゴール', 'シュート 成功率'],
        'clean_pct': True
    },
    {
        'name': 'Deffence Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=defense',
        'team_col': 'Unnamed: 2',
        'cols_map': {'deffence_points': '守備ポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['守備ポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Dribble Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=dribble',
        'team_col': 'Unnamed: 2',
        'cols_map': {'dribble_points': 'ドリブルポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['ドリブルポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Expected Goals',
        'url': 'https://www.football-lab.jp/summary/team_ranking/[LEAGUE]?year=100&data=expected',
        'team_col': 'Unnamed: 1',
        'cols_map': {'expected_goals': '期待値', 'goal': 'ゴール', 'diff': '差分'},
        'float_cols': ['期待値', 'ゴール', '差分']
    },
    {
        'name': 'Goal Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=goal',
        'team_col': 'Unnamed: 2',
        'cols_map': {'goal_points': 'ゴールポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['ゴールポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Pass Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=pass',
        'team_col': 'Unnamed: 2',
        'cols_map': {'pass_points': 'パスポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['パスポイント', '試合平均', '最近５試合']
    },
    {
        'name': 'Save Points',
        'url': 'https://www.football-lab.jp/summary/cbp_ranking/[LEAGUE]?year=100&data=save',
        'team_col': 'Unnamed: 2',
        'cols_map': {'save_points': 'セーブポイント', 'game_average': '試合平均', 'recentry5': '最近５試合'},
        'float_cols': ['セーブポイント', '試合平均', '最近５試合']
    }
]

def scrape_data(config: Dict[str, Any], site_data_path: str, force_refresh: bool) -> str:
    """WebサイトからJ1, J2のデータを取得し結合して一時ファイルに保存する"""
    file_path = os.path.join(site_data_path, f"{config['name']}.csv")
    
    if not force_refresh and os.path.exists(file_path):
        return file_path

    url_template = config['url']
    logger.info(f"取得開始: {config['name']}")
    
    try:
        # J1 (j1001), J2 (j1002) を取得
        df_j1 = pd.read_html(url_template.replace('[LEAGUE]', 'j1001'))[0]
        df_j2 = pd.read_html(url_template.replace('[LEAGUE]', 'j1002'))[0]
        
        site_df = pd.concat([df_j1, df_j2], ignore_index=True)
        site_df.to_csv(file_path, index=False)
        return file_path
    except Exception as e:
        logger.error(f"スクレイピングエラー ({config['name']}): {e}")
        raise

def process_data(file_path: str, config: Dict[str, Any], shotkey: str, mapper: TeamIDMapper) -> pd.DataFrame:
    """取得したCSVに対して、クレンジング・チームID紐付け・SHOTKEY付与を行う"""
    df_temp = pd.read_csv(file_path)
    
    # 必要に応じて '%' 記号などのクリーニング
    if config.get('clean_pct'):
        for col in config['float_cols']:
            if col in df_temp.columns and df_temp[col].dtype == object:
                df_temp[col] = df_temp[col].str.replace('%', '', regex=False)

    # 数値型へ変換
    for col in config['float_cols']:
        if col in df_temp.columns:
            df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce').fillna(0.0)

    # チームIDの紐付け
    df_temp['team_id'] = df_temp[config['team_col']].apply(lambda x: mapper.find_id(x))
    
    # 最終的なカラム構成の構築
    df = pd.DataFrame()
    df['shotkey'] = [shotkey] * len(df_temp)
    df['team_id'] = df_temp['team_id']
    
    for new_col, raw_col in config['cols_map'].items():
        df[new_col] = df_temp[raw_col]
        
    # team_idが引けなかったレコードはログ出し（任意）して除外するか検討
    missing_count = df['team_id'].isna().sum()
    if missing_count > 0:
        logger.warning(f"警告: {config['name']} において {missing_count} 件のチームIDが特定できませんでした。")

    return df

def main():
    parser = argparse.ArgumentParser(description='Jリーグ統計データ収集・加工ツール')
    parser.add_argument('shotkey', help='管理用識別子 (例: 20260402)')
    parser.add_argument('--force', '-f', action='store_true', help='キャッシュを無視して最新のWebデータを取得する')
    args = parser.parse_args()

    # フォルダの準備
    cwd = os.getcwd()
    site_data_dir = os.path.join(cwd, 'site_data')
    data_dir = os.path.join(cwd, 'data')
    
    os.makedirs(site_data_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # マッパーの初期化
    mapper = TeamIDMapper()
    
    success_count = 0
    for i, config in enumerate(DATA_SOURCE_CONFIGS, 1):
        try:
            # 1. スクレイピング
            raw_file = scrape_data(config, site_data_dir, args.force)
            
            # 2. 前処理
            processed_df = process_data(raw_file, config, args.shotkey, mapper)
            
            # 3. 保存
            output_file = os.path.join(data_dir, f"{config['name']}.csv")
            processed_df.to_csv(output_file, index=False)
            
            logger.info(f"[{i}/{len(DATA_SOURCE_CONFIGS)}] 完了: {config['name']}")
            success_count += 1
        except Exception as e:
            logger.error(f"[{i}/{len(DATA_SOURCE_CONFIGS)}] 失敗: {config['name']} - {e}")

    logger.info(f"全工程終了。成功: {success_count}/{len(DATA_SOURCE_CONFIGS)}")

if __name__ == "__main__":
    main()