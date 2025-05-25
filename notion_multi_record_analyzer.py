import os
import json
from typing import List, Dict, Any, Optional
from notion_client import Client
import openai
import yaml
from datetime import datetime

class NotionMultiRecordAnalyzer:
    """
    Notion APIで複数レコードを取得し、外部AI APIで分析を行うクラス
    """
    
    def __init__(self, config_path: str = "config/config.yml"):
        """
        設定ファイルから認証情報を読み込み、クライアントを初期化
        """
        self.config = self._load_config(config_path)
        
        # Notion Client初期化
        self.notion = Client(auth=self.config['notion']['token'])
        
        # OpenAI Client初期化
        openai.api_key = self.config['openai_api']['api_key']
        self.openai_client = openai
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    
    def get_database_records(self, 
                           database_id: str, 
                           filter_condition: Optional[Dict] = None,
                           sorts: Optional[List[Dict]] = None,
                           page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Notionデータベースから複数レコードを取得
        
        Args:
            database_id: データベースID
            filter_condition: フィルター条件
            sorts: ソート条件
            page_size: 一度に取得するレコード数
            
        Returns:
            レコードのリスト
        """
        records = []
        has_more = True
        start_cursor = None
        
        while has_more:
            query_params = {
                "database_id": database_id,
                "page_size": page_size
            }
            
            if filter_condition:
                query_params["filter"] = filter_condition
            if sorts:
                query_params["sorts"] = sorts
            if start_cursor:
                query_params["start_cursor"] = start_cursor
                
            response = self.notion.databases.query(**query_params)
            records.extend(response["results"])
            
            has_more = response["has_more"]
            start_cursor = response.get("next_cursor")
            
        return records
    
    def get_database_schema(self, database_id: str) -> Dict[str, Any]:
        """
        Notionデータベースのスキーマ（プロパティ情報）を取得

        Args:
            database_id: データベースID

        Returns:
            データベースのプロパティ情報
        """
        try:
            response = self.notion.databases.retrieve(database_id=database_id)
            return response.get("properties", {})
        except Exception as e:
            print(f"データベーススキーマの取得中にエラーが発生しました: {str(e)}")
            return {}
    
    def extract_text_from_records(self, 
                                records: List[Dict[str, Any]], 
                                text_properties: List[str]) -> List[Dict[str, str]]:
        """
        レコードから指定されたテキストプロパティを抽出
        
        Args:
            records: Notionレコードのリスト
            text_properties: 抽出したいプロパティ名のリスト
            
        Returns:
            抽出されたテキストデータのリスト
        """
        extracted_data = []
        
        for record in records:
            record_data = {"id": record["id"]}
            properties = record.get("properties", {})
            
            for prop_name in text_properties:
                if prop_name in properties:
                    prop_data = properties[prop_name]
                    
                    # プロパティタイプに応じてテキストを抽出
                    text_value = self._extract_text_from_property(prop_data)
                    record_data[prop_name] = text_value
                    
            extracted_data.append(record_data)
            
        return extracted_data
    
    def _extract_text_from_property(self, property_data: Dict[str, Any]) -> str:
        """プロパティからテキストを抽出"""
        prop_type = property_data.get("type")
        
        if prop_type == "title":
            return "".join([t["plain_text"] for t in property_data["title"]])
        elif prop_type == "rich_text":
            return "".join([t["plain_text"] for t in property_data["rich_text"]])
        elif prop_type == "select":
            return property_data["select"]["name"] if property_data["select"] else ""
        elif prop_type == "multi_select":
            return ", ".join([s["name"] for s in property_data["multi_select"]])
        elif prop_type == "url":
            return property_data["url"] or ""
        elif prop_type == "email":
            return property_data["email"] or ""
        elif prop_type == "phone_number":
            return property_data["phone_number"] or ""
        elif prop_type == "number":
            return str(property_data["number"]) if property_data["number"] is not None else ""
        elif prop_type == "date":
            date_info = property_data["date"]
            if date_info:
                return f"{date_info['start']} - {date_info.get('end', '')}"
            return ""
        else:
            return str(property_data.get(prop_type, ""))
    
    def analyze_with_ai(self, 
                       data: List[Dict[str, str]], 
                       analysis_prompt: str,
                       model: str = "gpt-4") -> str:
        """
        AIを使用してデータを分析
        
        Args:
            data: 分析対象のデータ
            analysis_prompt: 分析用のプロンプト
            model: 使用するAIモデル
            
        Returns:
            AI分析結果
        """
        # データを読みやすい形式に整形
        formatted_data = self._format_data_for_ai(data)
        
        # プロンプトを作成
        full_prompt = f"""
以下のNotionデータベースから取得したデータを分析してください。

{analysis_prompt}

データ:
{formatted_data}

分析結果を詳細に回答してください。
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "あなたはデータ分析の専門家です。与えられたデータを詳細に分析し、有用な洞察を提供してください。"},
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"AI分析中にエラーが発生しました: {str(e)}"
    
    def _format_data_for_ai(self, data: List[Dict[str, str]]) -> str:
        """AIが読みやすい形式にデータを整形"""
        formatted_lines = []
        
        for i, record in enumerate(data, 1):
            formatted_lines.append(f"レコード {i}:")
            for key, value in record.items():
                if key != "id":  # IDは表示しない
                    formatted_lines.append(f"  {key}: {value}")
            formatted_lines.append("")  # 空行で区切り
            
        return "\n".join(formatted_lines)
    
    def save_analysis_to_notion(self, 
                              analysis_result: str, 
                              database_id: str,
                              title: str = None) -> str:
        """
        分析結果をNotionの新しいページに保存
        
        Args:
            analysis_result: 分析結果
            database_id: 保存先データベースID
            title: ページタイトル
            
        Returns:
            作成されたページのID
        """
        if not title:
            title = f"AI分析結果 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
        try:
            new_page = self.notion.pages.create(
                parent={"database_id": database_id},
                properties={
                    "名前": {  # タイトルプロパティ名は実際のDBに合わせて調整
                        "title": [
                            {
                                "text": {
                                    "content": title
                                }
                            }
                        ]
                    }
                },
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": analysis_result
                                    }
                                }
                            ]
                        }
                    }
                ]
            )
            
            return new_page["id"]
            
        except Exception as e:
            print(f"Notionへの保存中にエラーが発生しました: {str(e)}")
            return None

# 使用例のサンプル関数
def example_analysis():
    """使用例: 特定のプロパティを分析"""
    analyzer = NotionMultiRecordAnalyzer()
    
    # 設定から主要なデータベースIDを取得
    database_id = analyzer.config['notion']['databases']['curation_main']
    
    # データベースからレコードを取得
    records = analyzer.get_database_records(database_id)
    
    # 特定のプロパティからテキストを抽出
    text_data = analyzer.extract_text_from_records(
        records, 
        ["ID", "画像/動画URL", "OCRテキスト", "ステータス"]
    )
    
    # AI分析を実行
    analysis_prompt = """
    このデータから以下の観点で分析してください:
    1. OCRテキストの内容の傾向
    2. 画像/動画URLのパターン
    3. ステータスの分布
    4. 改善提案
    """
    
    result = analyzer.analyze_with_ai(text_data, analysis_prompt)
    
    print("=== AI分析結果 ===")
    print(result)
    
    # 結果をNotionに保存（オプション）
    # page_id = analyzer.save_analysis_to_notion(result, database_id)
    # print(f"分析結果をページID: {page_id} に保存しました")

if __name__ == "__main__":
    example_analysis() 