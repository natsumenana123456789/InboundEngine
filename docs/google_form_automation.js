// Google Apps Script: フォーム送信時の自動処理（全ワークシート対応版）
// このスクリプトをGoogle Apps Scriptエディタに貼り付けて使用

function onFormSubmit(e) {
  try {
    // 設定
    const MAIN_SHEET_ID = 'YOUR_MAIN_SPREADSHEET_ID'; // メインのスプレッドシートID
    
    // ワークシートとアカウントのマッピング
    const WORKSHEET_MAPPING = {
      '都内メンエス': 'jadiAngkat',
      '都内セクキャバ': 'hinataHHHHHH',
      '銀座キャバ': 'account3', // 必要に応じて実際のアカウント名に変更
      '広島風俗': 'account4', // 必要に応じて実際のアカウント名に変更
      '名古屋メンエス': 'account5', // 必要に応じて実際のアカウント名に変更
      'w': 'account6' // 必要に応じて実際のアカウント名に変更
    };
    
    // フォーム回答データを取得
    const formResponse = e.values;
    const timestamp = formResponse[0]; // タイムスタンプ
    const worksheetName = formResponse[1]; // 対象ワークシート
    const postType = formResponse[2]; // 投稿タイプ
    const content = formResponse[3]; // 本文
    const mediaUrl = formResponse[4] || ''; // 画像/動画URL
    const isEnabled = formResponse[5] === 'はい' ? 'TRUE' : 'FALSE'; // 投稿可能
    const priority = formResponse[6]; // 優先度
    
    // 文字数計算
    const charCount = content ? content.length : 0;
    
    // 優先度に基づく最終投稿日時の設定
    const now = new Date();
    let lastPostDate;
    
    switch(priority) {
      case '高（すぐに投稿）':
        lastPostDate = new Date('2020-01-01 00:00:00');
        break;
      case '中（通常）':
        lastPostDate = new Date(now.getTime() - 24*60*60*1000); // 1日前
        break;
      case '低（後回し）':
        lastPostDate = new Date(now.getTime() - 12*60*60*1000); // 12時間前
        break;
      default:
        lastPostDate = new Date(now.getTime() - 24*60*60*1000);
    }
    
    // ワークシート名の検証
    if (!WORKSHEET_MAPPING[worksheetName]) {
      console.error('未対応のワークシート:', worksheetName);
      sendErrorNotification('未対応のワークシート: ' + worksheetName);
      return;
    }
    
    // メインスプレッドシートを開く
    const mainSpreadsheet = SpreadsheetApp.openById(MAIN_SHEET_ID);
    const targetSheet = mainSpreadsheet.getSheetByName(worksheetName);
    
    if (!targetSheet) {
      console.error('ワークシートが見つかりません:', worksheetName);
      sendErrorNotification('ワークシートが見つかりません: ' + worksheetName);
      return;
    }
    
    // 新しいIDを生成（最大ID + 1）
    const lastRow = targetSheet.getLastRow();
    let newId = 1;
    if (lastRow > 1) {
      const idRange = targetSheet.getRange(2, 1, lastRow - 1, 1);
      const ids = idRange.getValues().flat().filter(id => id !== '');
      if (ids.length > 0) {
        newId = Math.max(...ids) + 1;
      }
    }
    
    // 新しい行データを作成
    const newRowData = [
      newId, // ID
      postType, // 投稿タイプ
      Utilities.formatDate(lastPostDate, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss'), // 最終投稿日時
      charCount, // 文字数
      content, // 本文
      mediaUrl, // 画像/動画URL
      isEnabled, // 投稿可能
      0 // 投稿済み回数
    ];
    
    // スプレッドシートに行を追加
    targetSheet.appendRow(newRowData);
    
    // 成功通知
    sendSuccessNotification(worksheetName, postType, content, priority, newId);
    
    console.log('✅ 新しい投稿データを追加しました:', {
      worksheet: worksheetName,
      id: newId,
      content: content.substring(0, 50) + '...'
    });
    
  } catch (error) {
    console.error('❌ フォーム処理中にエラー:', error);
    sendErrorNotification('処理エラー: ' + error.toString());
  }
}

function sendSuccessNotification(worksheetName, postType, content, priority, newId) {
  try {
    const SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL'; // SlackのWebhook URL
    
    const message = {
      text: "📝 新しい投稿がフォームから追加されました",
      attachments: [{
        color: "good",
        fields: [{
          title: "対象ワークシート",
          value: `📊 ${worksheetName}`,
          short: true
        }, {
          title: "投稿ID",
          value: `#${newId}`,
          short: true
        }, {
          title: "投稿タイプ",
          value: postType,
          short: true
        }, {
          title: "優先度",
          value: priority,
          short: true
        }, {
          title: "文字数",
          value: content.length + "字",
          short: true
        }, {
          title: "投稿可能",
          value: "✅ 有効",
          short: true
        }, {
          title: "本文（抜粋）",
          value: content.substring(0, 100) + (content.length > 100 ? "..." : ""),
          short: false
        }]
      }]
    };
    
    const options = {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(message)
    };
    
    UrlFetchApp.fetch(SLACK_WEBHOOK_URL, options);
    console.log('✅ Slack通知を送信しました');
    
  } catch (error) {
    console.error('❌ Slack通知エラー:', error);
  }
}

function sendErrorNotification(errorMessage) {
  try {
    const SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL';
    
    const message = {
      text: "❌ フォーム処理でエラーが発生しました",
      attachments: [{
        color: "danger",
        fields: [{
          title: "エラー内容",
          value: errorMessage,
          short: false
        }, {
          title: "発生時刻",
          value: new Date().toLocaleString('ja-JP'),
          short: true
        }]
      }]
    };
    
    const options = {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(message)
    };
    
    UrlFetchApp.fetch(SLACK_WEBHOOK_URL, options);
    
  } catch (error) {
    console.error('❌ エラー通知の送信に失敗:', error);
  }
}

// 手動実行用のテスト関数
function testFormSubmit() {
  const testData = {
    values: [
      new Date(), // タイムスタンプ
      '都内メンエス', // 対象ワークシート
      '通常投稿', // 投稿タイプ
      'テスト投稿です。Google Formから自動で追加されました。', // 本文
      'https://drive.google.com/test', // 画像/動画URL
      'はい', // 投稿可能
      '中（通常）' // 優先度
    ]
  };
  
  onFormSubmit(testData);
}

// ワークシート一覧を取得する関数（フォーム設定時の参考用）
function getWorksheetList() {
  const MAIN_SHEET_ID = 'YOUR_MAIN_SPREADSHEET_ID';
  const spreadsheet = SpreadsheetApp.openById(MAIN_SHEET_ID);
  const sheets = spreadsheet.getSheets();
  
  console.log('利用可能なワークシート:');
  sheets.forEach(sheet => {
    console.log('- ' + sheet.getName());
  });
  
  return sheets.map(sheet => sheet.getName());
} 