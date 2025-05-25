#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from notion_multi_record_analyzer import NotionMultiRecordAnalyzer
from datetime import datetime, timedelta
import json

class NotionAnalysisExamples:
    """
    Notion + AI分析の実用的な使用例集
    """
    
    def __init__(self):
        self.analyzer = NotionMultiRecordAnalyzer()
        self.db_id = self.analyzer.config['notion']['databases']['curation_main']
    
    def analyze_content_trends(self):
        """コンテンツのトレンド分析"""
        print("📊 コンテンツトレンド分析を開始...")
        
        # 過去30日のレコードを取得
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        filter_condition = {
            "property": "取得日時",
            "date": {
                "after": thirty_days_ago
            }
        }
        
        records = self.analyzer.get_database_records(
            self.db_id, 
            filter_condition=filter_condition
        )
        
        # テキストデータを抽出
        data = self.analyzer.extract_text_from_records(
            records, 
            ["ID", "画像/動画URL", "OCRテキスト", "ステータス"]
        )
        
        # AI分析実行
        prompt = """
        過去30日間のコンテンツデータを分析し、以下の項目について詳細に報告してください：
        
        1. 【トレンド分析】
           - OCRテキストから読み取れるトピックやキーワードの傾向
           - 人気のあるコンテンツタイプ
           - 時系列での変化パターン
        
        2. 【品質評価】
           - OCRの精度や内容の質
           - 不適切または改善が必要なコンテンツの特定
        
        3. 【戦略提案】
           - 今後注力すべきコンテンツの方向性
           - 効率化のための改善提案
           - KPI向上のための具体的なアクション
        
        4. 【リスク分析】
           - 問題のあるパターンや潜在的リスク
           - コンプライアンス観点での注意点
        
        分析は具体的で実行可能な提案を含めてください。
        """
        
        result = self.analyzer.analyze_with_ai(data, prompt, model="gpt-4")
        
        print("=== コンテンツトレンド分析結果 ===")
        print(result)
        print("\n" + "="*50 + "\n")
        
        return result
    
    def analyze_status_distribution(self):
        """ステータス分布と処理効率の分析"""
        print("📈 ステータス分布・処理効率分析を開始...")
        
        # 全レコードを取得
        records = self.analyzer.get_database_records(self.db_id)
        
        # データ抽出
        data = self.analyzer.extract_text_from_records(
            records, 
            ["ID", "ステータス", "取得日時"]
        )
        
        # AI分析実行
        prompt = """
        レコードのステータス分布と処理効率について分析してください：
        
        1. 【ステータス分布】
           - 各ステータスの件数と割合
           - 処理フローの効率性
        
        2. 【処理速度分析】
           - 各ステータス間の滞留時間
           - ボトルネックの特定
        
        3. 【効率化提案】
           - 処理フローの最適化案
           - 自動化可能な工程の特定
           - リソース配分の改善提案
        
        4. 【パフォーマンス指標】
           - 処理完了率
           - 平均処理時間
           - 改善余地の定量評価
        
        数値データも含めて具体的に分析してください。
        """
        
        result = self.analyzer.analyze_with_ai(data, prompt)
        
        print("=== ステータス分布・処理効率分析結果 ===")
        print(result)
        print("\n" + "="*50 + "\n")
        
        return result
    
    def analyze_url_patterns(self):
        """画像/動画URLのパターン分析とセキュリティチェック"""
        print("🔍 URL パターン・セキュリティ分析を開始...")
        
        # 全レコードを取得
        records = self.analyzer.get_database_records(self.db_id)
        
        # データ抽出
        data = self.analyzer.extract_text_from_records(
            records, 
            ["ID", "画像/動画URL", "ステータス"]
        )
        
        # AI分析実行
        prompt = """
        画像/動画URLのパターンとセキュリティ面について分析してください：
        
        1. 【URLパターン分析】
           - ドメインの分布とパターン
           - URLの構造や命名規則
           - 重複URLの検出
        
        2. 【セキュリティ評価】
           - 不審または信頼性の低いドメイン
           - HTTPSの使用状況
           - 潜在的なセキュリティリスク
        
        3. 【品質評価】
           - リンク切れの可能性
           - パフォーマンスに影響する要因
           - コンテンツ配信の最適化
        
        4. 【改善提案】
           - URL管理の標準化
           - セキュリティ向上策
           - パフォーマンス最適化
        
        セキュリティとパフォーマンスの観点から実用的な提案をしてください。
        """
        
        result = self.analyzer.analyze_with_ai(data, prompt)
        
        print("=== URLパターン・セキュリティ分析結果 ===")
        print(result)
        print("\n" + "="*50 + "\n")
        
        return result
    
    def generate_monthly_report(self):
        """月次レポートの自動生成"""
        print("📋 月次レポート生成を開始...")
        
        # 過去30日のデータを取得
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        filter_condition = {
            "property": "取得日時",
            "date": {
                "after": thirty_days_ago
            }
        }
        
        records = self.analyzer.get_database_records(
            self.db_id, 
            filter_condition=filter_condition
        )
        
        # データ抽出
        data = self.analyzer.extract_text_from_records(
            records, 
            ["ID", "画像/動画URL", "OCRテキスト", "ステータス", "取得日時"]
        )
        
        # 包括的な分析プロンプト
        prompt = f"""
        {datetime.now().strftime('%Y年%m月')}の月次レポートを作成してください。
        対象期間: {thirty_days_ago} ～ {datetime.now().isoformat()}
        
        【レポート構成】
        
        ## 1. エグゼクティブサマリー
        - 今月の主要指標
        - 前月比での変化
        - 注目すべきポイント
        
        ## 2. データ収集・処理状況
        - 総レコード数
        - ステータス別分布
        - 処理効率の評価
        
        ## 3. コンテンツ分析
        - OCRテキストの内容傾向
        - 人気トピック・キーワード
        - 品質評価
        
        ## 4. 技術・運用面
        - URLパターンの分析
        - セキュリティ状況
        - システムパフォーマンス
        
        ## 5. 課題と改善提案
        - 特定された課題
        - 優先度付きの改善提案
        - 次月の目標設定
        
        ## 6. アクションアイテム
        - 具体的な実行項目
        - 担当者・期限の提案
        - 成功指標の定義
        
        データに基づいた客観的で実用的なレポートを作成してください。
        """
        
        result = self.analyzer.analyze_with_ai(data, prompt, model="gpt-4")
        
        print(f"=== {datetime.now().strftime('%Y年%m月')}月次レポート ===")
        print(result)
        print("\n" + "="*50 + "\n")
        
        # レポートをNotionに保存
        title = f"{datetime.now().strftime('%Y年%m月')}月次レポート"
        page_id = self.analyzer.save_analysis_to_notion(result, self.db_id, title)
        
        if page_id:
            print(f"📝 月次レポートをNotion に保存しました: {page_id}")
        
        return result
    
    def custom_analysis(self, properties: list, custom_prompt: str):
        """カスタム分析の実行"""
        print(f"🔬 カスタム分析を開始... (対象プロパティ: {', '.join(properties)})")
        
        # 全レコードを取得
        records = self.analyzer.get_database_records(self.db_id)
        
        # 指定されたプロパティのデータを抽出
        data = self.analyzer.extract_text_from_records(records, properties)
        
        # カスタムプロンプトで分析
        result = self.analyzer.analyze_with_ai(data, custom_prompt)
        
        print("=== カスタム分析結果 ===")
        print(result)
        print("\n" + "="*50 + "\n")
        
        return result

def main():
    """メイン実行関数"""
    examples = NotionAnalysisExamples()
    
    # ---- ここから追加: DBスキーマ取得・表示 ----
    print("データベーススキーマ情報を取得します...")
    db_schema = examples.analyzer.get_database_schema(examples.db_id)
    if db_schema:
        print("現在のデータベーススキーマ:")
        # 整形して表示 (pprint が使えないため json.dumps で代用)
        print(json.dumps(db_schema, indent=2, ensure_ascii=False))
        print("-" * 50)
    else:
        print("スキーマ情報を取得できませんでした。DB IDやトークンを確認してください。")
        print("-" * 50)
    # ---- ここまで追加 ----
    
    print("🚀 Notion + AI 分析ツールを開始します\n")
    
    # 分析メニュー
    analyses = [
        ("コンテンツトレンド分析", examples.analyze_content_trends),
        ("ステータス分布・処理効率分析", examples.analyze_status_distribution),
        ("URLパターン・セキュリティ分析", examples.analyze_url_patterns),
        ("月次レポート生成", examples.generate_monthly_report),
    ]
    
    # 選択された分析を実行
    print("実行可能な分析:")
    for i, (name, _) in enumerate(analyses, 1):
        print(f"{i}. {name}")
    
    print(f"{len(analyses) + 1}. 全て実行")
    print("0. 終了")
    
    try:
        choice = int(input("\n実行する分析を選択してください (番号入力): "))
        
        if choice == 0:
            print("分析を終了します。")
            return
        elif choice == len(analyses) + 1:
            # 全て実行
            for name, func in analyses:
                print(f"\n{'='*20} {name} {'='*20}")
                func()
        elif 1 <= choice <= len(analyses):
            # 選択された分析を実行
            name, func = analyses[choice - 1]
            print(f"\n{'='*20} {name} {'='*20}")
            func()
        else:
            print("無効な選択です。")
            
    except ValueError:
        print("無効な入力です。数値を入力してください。")
    except KeyboardInterrupt:
        print("\n分析を中断しました。")

if __name__ == "__main__":
    main() 