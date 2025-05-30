/**
 * 📱 スマホ対応複数投稿フォーム → スプレッドシート自動追加（最新版）
 * 🔧 Git管理版 - 動画変換ロジック統合済み
 * 
 * ✅ 機能：
 * - フォーム送信時の自動処理
 * - スプレッドシート自動追加
 * - Slack通知
 * - 画像・動画対応
 * - GitHub Actions動画変換連携
 * 
 * 📊 対象スプレッドシート: 1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA
 */

/**
 * フォーム送信時のメイン処理
 * @param {Object} e - フォーム送信イベント
 */
function onFormSubmit(e) {
  try {
    console.log('📱 フォーム送信処理開始:', new Date());
    
    // 🎯 設定値
    const config = getConfig();
    
    // フォーム回答データを取得
    const formResponse = e.values;
    console.log('📊 回答データ:', formResponse);
    
    // アカウント選択を取得・検証
    const accountInfo = parseAccountSelection(formResponse[1], config);
    if (!accountInfo) {
      throw new Error('無効なアカウント選択');
    }
    
    // 投稿データを解析
    const posts = parsePostData(formResponse);
    console.log('📝 解析された投稿数:', posts.length);
    
    if (posts.length === 0) {
      console.log('⚠️ 投稿データがありません');
      return;
    }
    
    // 既存スプレッドシートに追加
    const addedPosts = addPostsToSpreadsheet(
      config.SPREADSHEET_ID, 
      accountInfo.worksheet, 
      posts, 
      accountInfo.accountId
    );
    
    // Slack通知送信
    if (config.SLACK_WEBHOOK_URL) {
      sendSlackNotification(
        config.SLACK_WEBHOOK_URL, 
        accountInfo.worksheet, 
        accountInfo.accountId, 
        addedPosts
      );
    }
    
    // 動画変換処理をGitHub Actionsに委任（非同期）
    triggerVideoConversionIfNeeded(addedPosts);
    
    console.log('✅ 処理完了 - ' + addedPosts.length + '件の投稿を追加');
    
  } catch (error) {
    console.error('❌ エラー発生:', error);
    handleError(error);
  }
}

/**
 * 設定値を取得
 * @returns {Object} 設定オブジェクト
 */
function getConfig() {
  return {
    // あなたの設定値（Git管理）
    SPREADSHEET_ID: '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA',
    SLACK_WEBHOOK_URL: 'https://hooks.slack.com/services/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',
    
    // アカウントマッピング
    ACCOUNT_MAPPING: {
      '🏪 都内メンエス (jadiAngkat)': 'jadiAngkat',
      '🍷 都内セクキャバ (hinataHHHHHH)': 'hinataHHHHHH'
    },
    
    WORKSHEET_MAPPING: {
      'jadiAngkat': '都内メンエス',
      'hinataHHHHHH': '都内セクキャバ'
    }
  };
}

/**
 * アカウント選択を解析
 * @param {string} accountSelection - 選択されたアカウント
 * @param {Object} config - 設定オブジェクト
 * @returns {Object|null} アカウント情報
 */
function parseAccountSelection(accountSelection, config) {
  const accountId = config.ACCOUNT_MAPPING[accountSelection];
  const worksheet = config.WORKSHEET_MAPPING[accountId];
  
  if (!accountId || !worksheet) {
    console.error('❌ 無効なアカウント選択:', accountSelection);
    return null;
  }
  
  console.log('👤 選択アカウント:', accountSelection);
  console.log('📋 ワークシート名:', worksheet);
  
  return {
    accountId: accountId,
    worksheet: worksheet,
    selection: accountSelection
  };
}

/**
 * フォーム回答データから投稿内容を解析
 * @param {Array} formResponse - フォーム回答配列
 * @returns {Array} 投稿データ配列
 */
function parsePostData(formResponse) {
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
      const post = {
        content: content.trim(),
        fileUrl: fileUrl.trim(),
        charCount: content.trim().length,
        hasMedia: !!(fileUrl && fileUrl.trim())
      };
      
      posts.push(post);
      console.log(`📄 投稿${posts.length}: ${post.content.substring(0, 30)}... (${post.charCount}字, メディア: ${post.hasMedia ? 'あり' : 'なし'})`);
    }
    
    // 「いいえ、送信する」が選択されたら終了
    if (continueFlag === '✅ いいえ、送信する' || continueFlag === '✅ はい、送信する') {
      break;
    }
  }
  
  return posts;
}

/**
 * スプレッドシートに投稿データを追加
 * @param {string} sheetId - スプレッドシートID
 * @param {string} worksheetName - ワークシート名
 * @param {Array} posts - 投稿データ配列
 * @param {string} accountId - アカウントID
 * @returns {Array} 追加された投稿データ
 */
function addPostsToSpreadsheet(sheetId, worksheetName, posts, accountId) {
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
      
      // メディアファイル処理
      const processedMediaUrl = processMediaFile(post.fileUrl);
      
      // 投稿許可は初期値FALSE（後で手動チェック）
      const futureDate = '2030-01-01 00:00:00';
      
      // スプレッドシートの列構成に合わせてデータを作成
      const rowData = [
        newId,                    // A列: ID
        'フォーム投稿',           // B列: 投稿タイプ
        futureDate,               // C列: 最終投稿日時（未来日時で無効化）
        post.charCount,           // D列: 文字数
        post.content,             // E列: 本文
        processedMediaUrl,        // F列: 画像/動画URL
        'FALSE',                  // G列: 投稿可能（初期値FALSE）
        0                         // H列: 投稿済み回数
      ];
      
      sheet.appendRow(rowData);
      
      const addedPost = {
        ...post,
        id: newId,
        processedMediaUrl: processedMediaUrl,
        needsVideoConversion: isImageFile(processedMediaUrl)
      };
      
      addedPosts.push(addedPost);
      
      console.log(`✅ 投稿追加: ID=${newId}, 文字数=${post.charCount}, メディア=${processedMediaUrl ? 'あり' : 'なし'}`);
    }
    
    console.log(`📊 ${addedPosts.length}件の投稿をスプレッドシートに追加完了`);
    return addedPosts;
    
  } catch (error) {
    console.error('❌ スプレッドシート追加エラー:', error);
    throw error;
  }
}

/**
 * メディアファイル処理
 * @param {string} fileUrl - ファイルURL
 * @returns {string} 処理済みURL
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
    
    return publicUrl;
    
  } catch (error) {
    console.error('❌ メディアファイル処理エラー:', error);
    return fileUrl;
  }
}

/**
 * Google DriveのURLからファイルIDを抽出
 * @param {string} url - Google Drive URL
 * @returns {string|null} ファイルID
 */
function extractFileIdFromUrl(url) {
  const patterns = [
    /\/file\/d\/([a-zA-Z0-9-_]+)/,
    /id=([a-zA-Z0-9-_]+)/,
    /\/open\?id=([a-zA-Z0-9-_]+)/
  ];
  
  for (let pattern of patterns) {
    const match = url.match(pattern);
    if (match) {
      return match[1];
    }
  }
  
  return null;
}

/**
 * 画像ファイルかどうか判定
 * @param {string} url - ファイルURL
 * @returns {boolean} 画像ファイルかどうか
 */
function isImageFile(url) {
  if (!url) return false;
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
  const urlLower = url.toLowerCase();
  return imageExtensions.some(ext => urlLower.includes(ext)) || url.includes('drive.google.com');
}

/**
 * 次のIDを生成
 * @param {Object} sheet - スプレッドシートオブジェクト
 * @returns {number} 次のID
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
 * @param {string} webhookUrl - Slack Webhook URL
 * @param {string} worksheetName - ワークシート名
 * @param {string} accountId - アカウントID
 * @param {Array} addedPosts - 追加された投稿
 */
function sendSlackNotification(webhookUrl, worksheetName, accountId, addedPosts) {
  try {
    const imageCount = addedPosts.filter(post => post.needsVideoConversion).length;
    const videoNote = imageCount > 0 ? `\n🎬 ${imageCount}件の画像を動画変換予定` : '';
    
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
            const mediaIcon = post.processedMediaUrl ? (post.needsVideoConversion ? '📸→🎥' : '🎬') : '📝';
            const contentPreview = post.content.length > 50 
              ? post.content.substring(0, 47) + '...' 
              : post.content;
            return `${i+1}. ${mediaIcon} #${post.id} (${post.charCount}字)\n   ${contentPreview}`;
          }).join('\n') + videoNote,
          short: false
        }, {
          title: "🔄 次のアクション",
          value: "📋 スプレッドシートで内容を確認し、投稿可能列にチェックを入れてください" + 
                 (imageCount > 0 ? "\n🤖 GitHub Actionsが30分以内に画像を動画変換します" : ""),
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
 * 動画変換が必要な場合の処理（GitHub Actions連携）
 * @param {Array} addedPosts - 追加された投稿
 */
function triggerVideoConversionIfNeeded(addedPosts) {
  try {
    const imageCount = addedPosts.filter(post => post.needsVideoConversion).length;
    
    if (imageCount > 0) {
      console.log(`🎬 動画変換対象: ${imageCount}件`);
      console.log('🤖 GitHub Actionsが30分以内に動画変換を実行します');
      
      // GitHub Actions APIを直接呼び出すことも可能だが、
      // 定期実行の方が安定しているため、ここではログのみ
      // 実際の変換はGitHub Actionsの定期実行に委任
    }
    
  } catch (error) {
    console.error('❌ 動画変換処理エラー:', error);
  }
}

/**
 * エラーハンドリング
 * @param {Error} error - エラーオブジェクト
 */
function handleError(error) {
  const config = getConfig();
  
  if (config.SLACK_WEBHOOK_URL) {
    try {
      const errorMessage = {
        text: "❌ フォーム処理でエラーが発生しました",
        attachments: [{
          color: "danger",
          fields: [{
            title: "🚨 エラー内容",
            value: error.toString(),
            short: false
          }, {
            title: "🔧 対処方法",
            value: "Google Apps Scriptの実行記録を確認してください",
            short: false
          }]
        }]
      };
      
      UrlFetchApp.fetch(config.SLACK_WEBHOOK_URL, {
        method: 'POST',
        contentType: 'application/json',
        payload: JSON.stringify(errorMessage)
      });
      
    } catch (slackError) {
      console.error('❌ エラー通知送信失敗:', slackError);
    }
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
      new Date().toISOString(),                 // タイムスタンプ
      '🏪 都内メンエス (jadiAngkat)',          // アカウント選択
      'テスト投稿です。フォームからの投稿をテストしています。Git管理版での動作確認。', // 投稿1本文
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
  const config = getConfig();
  
  try {
    const spreadsheet = SpreadsheetApp.openById(config.SPREADSHEET_ID);
    const sheets = spreadsheet.getSheets();
    
    console.log('📊 スプレッドシート構造:');
    sheets.forEach((sheet, index) => {
      console.log(`${index + 1}. ワークシート名: "${sheet.getName()}"`);
      console.log(`   最終行: ${sheet.getLastRow()}`);
      console.log(`   最終列: ${sheet.getLastColumn()}`);
      
      // ヘッダー行の確認
      if (sheet.getLastRow() >= 1) {
        const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
        console.log(`   ヘッダー: ${headers.join(', ')}`);
      }
    });
    
  } catch (error) {
    console.error('❌ スプレッドシート確認エラー:', error);
  }
}

/**
 * 🔄 GitHub Actions動画変換を手動実行（テスト用）
 */
function manualTriggerVideoConversion() {
  console.log('🎬 GitHub Actions動画変換を手動でトリガー');
  
  // 実際のGitHub Actions APIを使用する場合の例
  // const githubToken = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  // const repoOwner = 'your-username';
  // const repoName = 'your-repo';
  
  console.log('🤖 定期実行により自動で処理されます');
} 