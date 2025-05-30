// 複数投稿対応Google Apps Script
// フォーム送信時に複数の投稿を一括処理

function onFormSubmit(e) {
  try {
    // 設定
    const MAIN_SHEET_ID = 'YOUR_MAIN_SPREADSHEET_ID';
    const SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL';
    
    // ワークシートマッピング
    const WORKSHEET_MAPPING = {
      '都内メンエス': 'jadiAngkat',
      '都内セクキャバ': 'hinataHHHHHH',
      '銀座キャバ': 'account3',
      '広島風俗': 'account4',
      '名古屋メンエス': 'account5',
      'w': 'account6'
    };
    
    const formResponse = e.values;
    const timestamp = formResponse[0];
    const worksheetName = formResponse[1]; // エリア/業種
    const postType = formResponse[2]; // 投稿タイプ
    
    // ワークシート検証
    if (!WORKSHEET_MAPPING[worksheetName]) {
      throw new Error('未対応のワークシート: ' + worksheetName);
    }
    
    // 投稿データを解析（3番目以降から5つずつが1セット）
    const posts = extractPostsFromResponse(formResponse.slice(3));
    
    if (posts.length === 0) {
      throw new Error('有効な投稿データが見つかりません');
    }
    
    // スプレッドシートに投稿を追加
    const addedPosts = addPostsToSheet(worksheetName, postType, posts);
    
    // Slack通知送信
    sendBatchNotification(worksheetName, postType, addedPosts, timestamp);
    
    console.log(`✅ ${addedPosts.length}件の投稿を追加しました`);
    
  } catch (error) {
    console.error('❌ フォーム処理エラー:', error);
    sendErrorNotification('複数投稿処理エラー: ' + error.toString());
  }
}

function extractPostsFromResponse(responseData) {
  const posts = [];
  
  // 5つずつのセットで解析（本文、画像URL、投稿可能、優先度、続行フラグ）
  for (let i = 0; i < responseData.length; i += 5) {
    const content = responseData[i];
    const mediaUrl = responseData[i + 1] || '';
    const isEnabled = responseData[i + 2];
    const priority = responseData[i + 3];
    const continueFlag = responseData[i + 4];
    
    // 本文が存在する場合のみ追加
    if (content && content.trim() !== '') {
      posts.push({
        content: content.trim(),
        mediaUrl: mediaUrl.trim(),
        isEnabled: isEnabled === 'はい（投稿対象に含める）' ? 'TRUE' : 'FALSE',
        priority: priority || '中（通常）'
      });
    }
    
    // 「いいえ、送信する」が選択されたら終了
    if (continueFlag === 'いいえ、送信する') {
      break;
    }
  }
  
  return posts;
}

function addPostsToSheet(worksheetName, postType, posts) {
  const MAIN_SHEET_ID = 'YOUR_MAIN_SPREADSHEET_ID';
  const spreadsheet = SpreadsheetApp.openById(MAIN_SHEET_ID);
  const targetSheet = spreadsheet.getSheetByName(worksheetName);
  
  if (!targetSheet) {
    throw new Error('ワークシートが見つかりません: ' + worksheetName);
  }
  
  const addedPosts = [];
  
  for (let post of posts) {
    // 新しいID生成
    const newId = getNextId(targetSheet);
    
    // 優先度に基づく最終投稿日時設定
    const lastPostDate = getPriorityDate(post.priority);
    
    // 文字数計算
    const charCount = post.content.length;
    
    // 行データ作成
    const rowData = [
      newId,
      postType,
      lastPostDate,
      charCount,
      post.content,
      post.mediaUrl,
      post.isEnabled,
      0 // 投稿済み回数
    ];
    
    // スプレッドシートに追加
    targetSheet.appendRow(rowData);
    
    addedPosts.push({
      ...post,
      id: newId,
      charCount: charCount,
      postType: postType
    });
    
    console.log(`✅ 投稿ID ${newId} を追加: ${post.content.substring(0, 30)}...`);
  }
  
  return addedPosts;
}

function getNextId(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    return 1;
  }
  
  const idRange = sheet.getRange(2, 1, lastRow - 1, 1);
  const ids = idRange.getValues().flat().filter(id => id !== '');
  
  return ids.length > 0 ? Math.max(...ids) + 1 : 1;
}

function getPriorityDate(priority) {
  const now = new Date();
  
  switch(priority) {
    case '高（すぐに投稿）':
      return '2020-01-01 00:00:00';
    case '中（通常）':
      const oneDayAgo = new Date(now.getTime() - 24*60*60*1000);
      return Utilities.formatDate(oneDayAgo, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
    case '低（後回し）':
      const twelveHoursAgo = new Date(now.getTime() - 12*60*60*1000);
      return Utilities.formatDate(twelveHoursAgo, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
    default:
      const defaultDate = new Date(now.getTime() - 24*60*60*1000);
      return Utilities.formatDate(defaultDate, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  }
}

function sendBatchNotification(worksheetName, postType, addedPosts, timestamp) {
  try {
    const SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL';
    
    // 統計情報
    const totalPosts = addedPosts.length;
    const enabledPosts = addedPosts.filter(p => p.isEnabled === 'TRUE').length;
    const disabledPosts = totalPosts - enabledPosts;
    const avgCharCount = Math.round(addedPosts.reduce((sum, p) => sum + p.charCount, 0) / totalPosts);
    
    // 投稿一覧
    const postList = addedPosts.map((post, index) => {
      const status = post.isEnabled === 'TRUE' ? '✅' : '❌';
      const preview = post.content.substring(0, 50) + (post.content.length > 50 ? '...' : '');
      return `${index + 1}. ${status} #${post.id} (${post.charCount}字) ${preview}`;
    }).join('\n');
    
    const message = {
      text: "📝 複数投稿がフォームから一括追加されました",
      attachments: [{
        color: "good",
        fields: [{
          title: "対象ワークシート",
          value: `📊 ${worksheetName}`,
          short: true
        }, {
          title: "投稿タイプ",
          value: postType,
          short: true
        }, {
          title: "追加投稿数",
          value: `${totalPosts}件`,
          short: true
        }, {
          title: "有効/無効",
          value: `✅${enabledPosts}件 ❌${disabledPosts}件`,
          short: true
        }, {
          title: "平均文字数",
          value: `${avgCharCount}字`,
          short: true
        }, {
          title: "送信時刻",
          value: new Date(timestamp).toLocaleString('ja-JP'),
          short: true
        }, {
          title: "投稿一覧",
          value: postList,
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
    console.log('✅ 一括Slack通知を送信しました');
    
  } catch (error) {
    console.error('❌ Slack通知エラー:', error);
  }
}

function sendErrorNotification(errorMessage) {
  try {
    const SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL';
    
    const message = {
      text: "❌ 複数投稿フォーム処理でエラーが発生しました",
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

// テスト用関数
function testMultiPostSubmit() {
  const testData = {
    values: [
      new Date(), // タイムスタンプ
      '都内メンエス', // ワークシート
      '宣伝投稿', // 投稿タイプ
      // 投稿1
      '新しいメンエス店がオープンしました！清楚系の女の子が多く、リラックスできる空間です。', // 本文1
      'https://drive.google.com/file/d/1234567890/view', // 画像URL1
      'はい（投稿対象に含める）', // 投稿可能1
      '高（すぐに投稿）', // 優先度1
      'はい、もう1つ投稿を追加する', // 続行1
      // 投稿2
      'サービス詳細：90分コース 15,000円から。初回限定で10%オフキャンペーン実施中！', // 本文2
      '', // 画像URL2（なし）
      'はい（投稿対象に含める）', // 投稿可能2
      '中（通常）', // 優先度2
      'はい、もう1つ投稿を追加する', // 続行2
      // 投稿3
      'アクセス：JR品川駅から徒歩5分。お気軽にお越しください。', // 本文3
      '', // 画像URL3（なし）
      'はい（投稿対象に含める）', // 投稿可能3
      '低（後回し）', // 優先度3
      'いいえ、送信する' // 続行3（終了）
    ]
  };
  
  onFormSubmit(testData);
}

// ワークシート一覧を取得（フォーム設定時の参考用）
function getAvailableWorksheets() {
  const MAIN_SHEET_ID = 'YOUR_MAIN_SPREADSHEET_ID';
  const spreadsheet = SpreadsheetApp.openById(MAIN_SHEET_ID);
  const sheets = spreadsheet.getSheets();
  
  console.log('利用可能なワークシート:');
  sheets.forEach(sheet => {
    console.log('- ' + sheet.getName());
  });
  
  return sheets.map(sheet => sheet.getName());
} 