/**
 * 📱 スマホ対応複数投稿フォーム → スプレッドシート自動追加
 * 🔧 あなたの設定値で完全設定済み - そのままコピペしてください
 * 
 * ✅ 設定済み内容：
 * - スプレッドシートID: 1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA
 * - Slack通知: 有効化済み
 * - アカウント: jadiAngkat（都内メンエス）、hinataHHHHHH（都内セクキャバ）
 * - 画像・動画: そのまま投稿対応
 */

function onFormSubmit(e) {
  try {
    // 🎯 あなたの設定値（変更不要）
    const EXISTING_SHEET_ID = '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA'; // あなたのスプレッドシートID
    const SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/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'; // あなたのSlack Webhook URL
    
    // アカウントマッピング設定
    const ACCOUNT_MAPPING = {
      '🏪 都内メンエス (jadiAngkat)': 'jadiAngkat',
      '🍷 都内セクキャバ (hinataHHHHHH)': 'hinataHHHHHH'
    };
    
    const WORKSHEET_MAPPING = {
      'jadiAngkat': '都内メンエス',
      'hinataHHHHHH': '都内セクキャバ'
    };
    
    console.log('📱 フォーム送信処理開始');
    
    // フォーム回答データを取得
    const formResponse = e.values;
    console.log('📊 回答データ:', formResponse);
    
    // アカウント選択を取得
    const accountSelection = formResponse[1];
    const accountId = ACCOUNT_MAPPING[accountSelection];
    const worksheetName = WORKSHEET_MAPPING[accountId];
    
    console.log('👤 選択アカウント:', accountSelection);
    console.log('📋 ワークシート名:', worksheetName);
    
    if (!accountId || !worksheetName) {
      throw new Error(`無効なアカウント選択: ${accountSelection}`);
    }
    
    // 投稿データを解析
    const posts = parseSimplePostData(formResponse);
    console.log('📝 解析された投稿数:', posts.length);
    
    if (posts.length === 0) {
      console.log('⚠️ 投稿データがありません');
      return;
    }
    
    // 既存スプレッドシートに追加
    const addedPosts = addPostsToExistingSheet(EXISTING_SHEET_ID, worksheetName, posts, accountId);
    
    // Slack通知送信
    sendSlackNotification(SLACK_WEBHOOK_URL, worksheetName, accountId, addedPosts);
    
    console.log('✅ 処理完了 - ' + addedPosts.length + '件の投稿を追加');
    
  } catch (error) {
    console.error('❌ エラー発生:', error);
    // エラー時もSlack通知
    if (SLACK_WEBHOOK_URL) {
      sendErrorNotification(SLACK_WEBHOOK_URL, error.toString());
    }
  }
}

/**
 * フォーム回答データから投稿内容を解析
 */
function parseSimplePostData(formResponse) {
  const posts = [];
  
  // フォーム回答の構造：
  // [0] タイムスタンプ
  // [1] アカウント選択
  // [2〜] 投稿データ（本文、画像URL、続行判定の3セット）
  
  for (let i = 2; i < formResponse.length; i += 3) {
    const content = formResponse[i];
    const fileUrl = formResponse[i + 1] || '';
    const continueFlag = formResponse[i + 2];
    
    // 本文が入力されている投稿のみ処理
    if (content && content.trim() !== '') {
      posts.push({
        content: content.trim(),
        fileUrl: fileUrl.trim()
      });
      
      console.log(`📄 投稿${posts.length}: ${content.substring(0, 30)}...`);
    }
    
    // 「いいえ、送信する」が選択されたら終了
    if (continueFlag === '✅ いいえ、送信する' || continueFlag === '✅ はい、送信する') {
      break;
    }
  }
  
  return posts;
}

/**
 * 既存スプレッドシートに投稿データを追加
 */
function addPostsToExistingSheet(sheetId, worksheetName, posts, accountId) {
  try {
    const spreadsheet = SpreadsheetApp.openById(sheetId);
    const sheet = spreadsheet.getSheetByName(worksheetName);
    
    if (!sheet) {
      throw new Error(`ワークシート「${worksheetName}」が見つかりません`);
    }
    
    console.log(`📊 スプレッドシート接続成功: ${worksheetName}`);
    
    const addedPosts = [];
    
    for (let post of posts) {
      // 新しいIDを生成
      const newId = getNextId(sheet);
      const charCount = post.content.length;
      
      // メディアファイル処理（画像・動画そのまま対応）
      const processedMediaUrl = processMediaFile(post.fileUrl);
      
      // 投稿許可は初期値FALSE（後で手動チェック）
      const futureDate = '2030-01-01 00:00:00';
      
      // スプレッドシートの列構成に合わせてデータを作成
      const rowData = [
        newId,                    // A列: ID
        'フォーム投稿',           // B列: 投稿タイプ
        futureDate,               // C列: 最終投稿日時（未来日時で無効化）
        charCount,                // D列: 文字数
        post.content,             // E列: 本文
        processedMediaUrl,        // F列: 画像/動画URL
        'FALSE',                  // G列: 投稿可能（初期値FALSE）
        0                         // H列: 投稿済み回数
      ];
      
      sheet.appendRow(rowData);
      
      addedPosts.push({
        ...post,
        id: newId,
        charCount: charCount,
        processedMediaUrl: processedMediaUrl
      });
      
      console.log(`✅ 投稿追加: ID=${newId}, 文字数=${charCount}, メディア=${processedMediaUrl ? 'あり' : 'なし'}`);
    }
    
    console.log(`📊 ${addedPosts.length}件の投稿をスプレッドシートに追加完了`);
    return addedPosts;
    
  } catch (error) {
    console.error('❌ スプレッドシート追加エラー:', error);
    throw error;
  }
}

/**
 * メディアファイル処理（画像・動画そのまま対応）
 */
function processMediaFile(fileUrl) {
  if (!fileUrl || fileUrl.trim() === '') {
    return '';
  }
  
  try {
    const fileId = extractFileIdFromUrl(fileUrl);
    if (!fileId) {
      return fileUrl;
    }
    
    // Google DriveのファイルURLを公開用URLに変換
    const publicUrl = `https://drive.google.com/file/d/${fileId}/view`;
    
    console.log(`🎬 メディアファイル処理完了: ${publicUrl}`);
    
    // 📸 画像も 🎥 動画もX/Twitterで投稿可能なので、そのまま返す
    return publicUrl;
    
  } catch (error) {
    console.error('❌ メディアファイル処理エラー:', error);
    return fileUrl;
  }
}

/**
 * Google DriveのURLからファイルIDを抽出
 */
function extractFileIdFromUrl(url) {
  const regex = /\/file\/d\/([a-zA-Z0-9-_]+)/;
  const match = url.match(regex);
  return match ? match[1] : null;
}

/**
 * 次のIDを生成
 */
function getNextId(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) return 1;
  
  const idRange = sheet.getRange(2, 1, lastRow - 1, 1);
  const ids = idRange.getValues().flat().filter(id => id !== '');
  return ids.length > 0 ? Math.max(...ids) + 1 : 1;
}

/**
 * Slack通知送信（成功時）
 */
function sendSlackNotification(webhookUrl, worksheetName, accountId, addedPosts) {
  try {
    const message = {
      text: "📱 フォームから新しい投稿が追加されました！",
      attachments: [{
        color: "good",
        fields: [{
          title: "📊 対象ワークシート",
          value: `${worksheetName} (${accountId})`,
          short: true
        }, {
          title: "📝 追加投稿数",
          value: `${addedPosts.length}件`,
          short: true
        }, {
          title: "📋 投稿一覧（要確認）",
          value: addedPosts.map((post, i) => {
            const mediaIcon = post.processedMediaUrl ? '🎬' : '📝';
            const contentPreview = post.content.length > 50 
              ? post.content.substring(0, 47) + '...' 
              : post.content;
            return `${i+1}. ${mediaIcon} #${post.id} (${post.charCount}字)\n   ${contentPreview}`;
          }).join('\n'),
          short: false
        }, {
          title: "🔄 次のアクション",
          value: "📋 スプレッドシートで内容を確認し、投稿可能列にチェックを入れてください",
          short: false
        }]
      }]
    };
    
    const response = UrlFetchApp.fetch(webhookUrl, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(message)
    });
    
    console.log('📢 Slack通知送信完了:', response.getResponseCode());
    
  } catch (error) {
    console.error('❌ Slack通知エラー:', error);
    // Slack通知失敗してもメイン処理は継続
  }
}

/**
 * Slack通知送信（エラー時）
 */
function sendErrorNotification(webhookUrl, errorMessage) {
  try {
    const message = {
      text: "❌ フォーム処理でエラーが発生しました",
      attachments: [{
        color: "danger",
        fields: [{
          title: "🚨 エラー内容",
          value: errorMessage,
          short: false
        }, {
          title: "🔧 対処方法",
          value: "Google Apps Scriptの実行記録を確認してください",
          short: false
        }]
      }]
    };
    
    UrlFetchApp.fetch(webhookUrl, {
      method: 'POST',
      contentType: 'application/json',
      payload: JSON.stringify(message)
    });
    
  } catch (error) {
    console.error('❌ エラー通知送信失敗:', error);
  }
}

/**
 * 🧪 テスト用関数（手動実行でテスト可能）
 */
function testFormSubmission() {
  console.log('🧪 テスト実行開始');
  
  // テストデータを作成
  const testEvent = {
    values: [
      '2024/01/01 12:00:00',                    // タイムスタンプ
      '🏪 都内メンエス (jadiAngkat)',          // アカウント選択
      'テスト投稿です。フォームからの投稿をテストしています。', // 投稿1本文
      '',                                       // 投稿1画像URL（空）
      '✅ いいえ、送信する'                     // 続行判定
    ]
  };
  
  // テスト実行
  onFormSubmit(testEvent);
  
  console.log('🧪 テスト実行完了');
}

/**
 * 📊 スプレッドシート構造確認用関数
 */
function checkSpreadsheetStructure() {
  const SHEET_ID = '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA';
  
  try {
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    const sheets = spreadsheet.getSheets();
    
    console.log('📊 スプレッドシート構造:');
    sheets.forEach((sheet, index) => {
      console.log(`${index + 1}. ワークシート名: "${sheet.getName()}"`);
      console.log(`   最終行: ${sheet.getLastRow()}`);
      console.log(`   最終列: ${sheet.getLastColumn()}`);
    });
    
  } catch (error) {
    console.error('❌ スプレッドシート確認エラー:', error);
  }
} 