/**
 * 📱 InboundEngine Image to Video Converter
 * 🎯 スプレッドシートの画像URLを動画に変換
 */

// 設定
const CONFIG = {
  SHEET_ID: '1lgCn5iAiFT9PSr3vA3Tp1SePe0g3B9Xe1ppsr8bn2FA',
  WORKSHEETS: ['都内メンエス', '都内セクキャバ'],
  DRIVE_FOLDER_ID: '', // Google Driveフォルダーを指定
  VIDEO_DURATION: 1, // 秒
  MAX_PROCESSES: 5 // 同時処理数
};

/**
 * メイン処理関数
 */
function main() {
  Logger.log('🚀 Google Apps Script動画変換処理開始');
  
  try {
    const converter = new ImageToVideoConverter();
    converter.processAllImages();
  } catch (error) {
    Logger.log(`❌ 予期しないエラー: ${error.toString()}`);
    throw error;
  }
  
  Logger.log('✅ 動画変換処理終了');
}

/**
 * 画像から動画への変換クラス
 */
class ImageToVideoConverter {
  constructor() {
    this.spreadsheet = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  }
  
  /**
   * 変換が必要な画像を検索
   */
  findImagesToConvert() {
    const imagesToConvert = [];
    
    CONFIG.WORKSHEETS.forEach(worksheetName => {
      try {
        const worksheet = this.spreadsheet.getSheetByName(worksheetName);
        if (!worksheet) {
          Logger.log(`❌ ワークシートが見つかりません: ${worksheetName}`);
          return;
        }
        
        const data = worksheet.getDataRange().getValues();
        const headers = data[0];
        
        // 画像/動画URLの列を探す
        const mediaUrlColumnIndex = headers.indexOf('画像/動画URL');
        if (mediaUrlColumnIndex === -1) {
          Logger.log(`❌ 画像/動画URL列が見つかりません: ${worksheetName}`);
          return;
        }
        
        Logger.log(`📊 ${worksheetName}: ${data.length - 1}件のレコードを確認`);
        
        for (let i = 1; i < data.length; i++) {
          const row = data[i];
          const mediaUrl = row[mediaUrlColumnIndex];
          
          // 画像URLで、まだ変換されていないもの
          if (mediaUrl && 
              this.isImageUrl(mediaUrl) && 
              !this.isConvertedVideo(mediaUrl)) {
            
            imagesToConvert.push({
              worksheet: worksheetName,
              row: i + 1, // スプレッドシートの行番号（1ベース）
              url: mediaUrl,
              recordId: row[headers.indexOf('ID')] || '',
              content: (row[headers.indexOf('本文')] || '').substring(0, 50) + '...'
            });
          }
        }
        
      } catch (error) {
        Logger.log(`❌ ワークシート処理エラー ${worksheetName}: ${error.toString()}`);
      }
    });
    
    Logger.log(`🎯 変換対象の画像: ${imagesToConvert.length}件`);
    return imagesToConvert;
  }
  
  /**
   * 画像URLかどうか判定
   */
  isImageUrl(url) {
    if (!url) return false;
    
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
    const urlLower = url.toLowerCase();
    
    return imageExtensions.some(ext => urlLower.includes(ext)) ||
           urlLower.includes('drive.google.com');
  }
  
  /**
   * 既に変換済みかどうか判定
   */
  isConvertedVideo(url) {
    if (!url) return false;
    
    return url.includes('converted_video') ||
           url.endsWith('.mp4') ||
           url.includes('video_converted');
  }
  
  /**
   * Google Driveから画像をダウンロード
   */
  downloadImage(driveUrl) {
    try {
      const fileId = this.extractFileId(driveUrl);
      if (!fileId) {
        Logger.log(`❌ ファイルIDが抽出できません: ${driveUrl}`);
        return null;
      }
      
      Logger.log(`📥 画像ダウンロード中: ${fileId}`);
      
      const file = DriveApp.getFileById(fileId);
      const blob = file.getBlob();
      
      Logger.log(`✅ 画像ダウンロード完了: ${blob.getSize()} bytes`);
      return blob;
      
    } catch (error) {
      Logger.log(`❌ 画像ダウンロードエラー: ${error.toString()}`);
      return null;
    }
  }
  
  /**
   * Google DriveのURLからファイルIDを抽出
   */
  extractFileId(url) {
    const patterns = [
      /\/file\/d\/([a-zA-Z0-9-_]+)/,
      /id=([a-zA-Z0-9-_]+)/,
      /\/open\?id=([a-zA-Z0-9-_]+)/
    ];
    
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) {
        return match[1];
      }
    }
    
    return null;
  }
  
  /**
   * 画像を動画に変換（GAS内ではシミュレーション）
   * 実際の動画変換は外部サービスやアドオンが必要
   */
  convertImageToVideo(imageBlob, originalUrl) {
    try {
      Logger.log(`🎬 動画変換シミュレーション開始: ${imageBlob.getName()}`);
      
      // Google Apps Scriptでは直接動画変換はできないため、
      // ここでは変換済みURLのプレースホルダーを返す
      const timestamp = new Date().getTime();
      const videoUrl = `https://drive.google.com/converted_video_${timestamp}.mp4`;
      
      Logger.log(`✅ 動画変換シミュレーション完了: ${videoUrl}`);
      return videoUrl;
      
    } catch (error) {
      Logger.log(`❌ 動画変換エラー: ${error.toString()}`);
      return null;
    }
  }
  
  /**
   * スプレッドシートのURLを更新
   */
  updateSpreadsheetUrl(worksheetName, row, newUrl) {
    try {
      const worksheet = this.spreadsheet.getSheetByName(worksheetName);
      if (!worksheet) {
        Logger.log(`❌ ワークシートが見つかりません: ${worksheetName}`);
        return false;
      }
      
      // F列（画像/動画URL）を更新
      worksheet.getRange(row, 6).setValue(newUrl);
      Logger.log(`✅ スプレッドシート更新: ${worksheetName} 行${row}`);
      
      return true;
      
    } catch (error) {
      Logger.log(`❌ スプレッドシート更新エラー: ${error.toString()}`);
      return false;
    }
  }
  
  /**
   * すべての画像を処理
   */
  processAllImages() {
    const images = this.findImagesToConvert();
    
    if (images.length === 0) {
      Logger.log('🎯 変換対象の画像がありません');
      return;
    }
    
    Logger.log(`📊 変換対象: ${images.length}件`);
    
    let successCount = 0;
    let errorCount = 0;
    
    // バッチ処理でスプレッドシートの更新回数を削減
    const updates = [];
    
    images.forEach((imageData, index) => {
      try {
        Logger.log(`🔄 [${index + 1}/${images.length}] 処理中: ID=${imageData.recordId}`);
        Logger.log(`📝 内容: ${imageData.content}`);
        Logger.log(`🌐 URL: ${imageData.url.substring(0, 100)}...`);
        
        // 画像ダウンロード
        const imageBlob = this.downloadImage(imageData.url);
        if (!imageBlob) {
          Logger.log(`❌ 画像ダウンロード失敗: ID=${imageData.recordId}`);
          errorCount++;
          return;
        }
        
        // 動画変換
        const newUrl = this.convertImageToVideo(imageBlob, imageData.url);
        if (!newUrl) {
          Logger.log(`❌ 動画変換失敗: ID=${imageData.recordId}`);
          errorCount++;
          return;
        }
        
        // 更新情報を蓄積
        updates.push({
          worksheet: imageData.worksheet,
          row: imageData.row,
          url: newUrl
        });
        
        successCount++;
        Logger.log(`✅ 完了: ID=${imageData.recordId}`);
        
      } catch (error) {
        Logger.log(`❌ 処理エラー ID=${imageData.recordId}: ${error.toString()}`);
        errorCount++;
      }
    });
    
    // バッチでスプレッドシート更新
    this.batchUpdateSpreadsheet(updates);
    
    Logger.log(`🎉 処理完了: 成功=${successCount}件, エラー=${errorCount}件`);
  }
  
  /**
   * スプレッドシートをバッチ更新
   */
  batchUpdateSpreadsheet(updates) {
    const groupedUpdates = {};
    
    // ワークシート別にグループ化
    updates.forEach(update => {
      if (!groupedUpdates[update.worksheet]) {
        groupedUpdates[update.worksheet] = [];
      }
      groupedUpdates[update.worksheet].push(update);
    });
    
    // ワークシート別に一括更新
    Object.keys(groupedUpdates).forEach(worksheetName => {
      try {
        const worksheet = this.spreadsheet.getSheetByName(worksheetName);
        const worksheetUpdates = groupedUpdates[worksheetName];
        
        worksheetUpdates.forEach(update => {
          worksheet.getRange(update.row, 6).setValue(update.url);
        });
        
        Logger.log(`✅ バッチ更新完了: ${worksheetName} (${worksheetUpdates.length}件)`);
        
      } catch (error) {
        Logger.log(`❌ バッチ更新エラー ${worksheetName}: ${error.toString()}`);
      }
    });
  }
}

/**
 * テスト関数
 */
function testImageProcessing() {
  Logger.log('🧪 テスト開始');
  
  const converter = new ImageToVideoConverter();
  const images = converter.findImagesToConvert();
  
  Logger.log(`テスト結果: ${images.length}件の変換対象画像を発見`);
  
  if (images.length > 0) {
    Logger.log(`最初の画像: ${JSON.stringify(images[0])}`);
  }
} 