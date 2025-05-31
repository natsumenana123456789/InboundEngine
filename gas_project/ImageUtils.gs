/**
 * 画像処理ユーティリティ関数
 */

class ImageUtils {
  
  /**
   * 画像のメタデータを取得
   */
  static getImageMetadata(blob) {
    try {
      const size = blob.getSize();
      const contentType = blob.getContentType();
      const name = blob.getName();
      
      return {
        size: size,
        contentType: contentType,
        name: name,
        sizeFormatted: this.formatFileSize(size),
        isValid: this.isValidImageType(contentType)
      };
      
    } catch (error) {
      Logger.log(`❌ メタデータ取得エラー: ${error.toString()}`);
      return null;
    }
  }
  
  /**
   * 有効な画像タイプかチェック
   */
  static isValidImageType(contentType) {
    const validTypes = [
      'image/jpeg',
      'image/jpg', 
      'image/png',
      'image/gif',
      'image/webp'
    ];
    
    return validTypes.includes(contentType);
  }
  
  /**
   * ファイルサイズをフォーマット
   */
  static formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  /**
   * 画像をリサイズ（簡易版）
   * Google Apps Scriptでは画像処理に制限があるため、サムネイル作成程度
   */
  static createThumbnail(blob, maxSize = 150) {
    try {
      // Google Apps Scriptの制限により、実際のリサイズは困難
      // ここではメタデータのみ返す
      Logger.log(`📸 サムネイル作成（シミュレーション）: ${blob.getName()}`);
      
      return {
        original: blob,
        thumbnailUrl: `thumbnail_${blob.getName()}`,
        maxSize: maxSize
      };
      
    } catch (error) {
      Logger.log(`❌ サムネイル作成エラー: ${error.toString()}`);
      return null;
    }
  }
  
  /**
   * 画像の種類を判定
   */
  static detectImageFormat(blob) {
    const contentType = blob.getContentType();
    const name = blob.getName().toLowerCase();
    
    if (contentType.includes('jpeg') || name.includes('.jpg') || name.includes('.jpeg')) {
      return 'JPEG';
    } else if (contentType.includes('png') || name.includes('.png')) {
      return 'PNG';
    } else if (contentType.includes('gif') || name.includes('.gif')) {
      return 'GIF';
    } else if (contentType.includes('webp') || name.includes('.webp')) {
      return 'WEBP';
    } else {
      return 'UNKNOWN';
    }
  }
  
  /**
   * Google DriveのURLを正規化
   */
  static normalizeGoogleDriveUrl(url) {
    try {
      // ファイルIDを抽出
      const fileId = this.extractFileIdFromUrl(url);
      if (!fileId) return null;
      
      // 直接ダウンロード可能なURLに変換
      return `https://drive.google.com/uc?export=download&id=${fileId}`;
      
    } catch (error) {
      Logger.log(`❌ URL正規化エラー: ${error.toString()}`);
      return null;
    }
  }
  
  /**
   * URLからGoogle DriveファイルIDを抽出（複数パターン対応）
   */
  static extractFileIdFromUrl(url) {
    const patterns = [
      /\/file\/d\/([a-zA-Z0-9-_]+)/,
      /id=([a-zA-Z0-9-_]+)/,
      /\/open\?id=([a-zA-Z0-9-_]+)/,
      /drive\.google\.com\/.*\/([a-zA-Z0-9-_]+)/
    ];
    
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }
    
    return null;
  }
  
  /**
   * 画像の品質をチェック
   */
  static assessImageQuality(blob) {
    const metadata = this.getImageMetadata(blob);
    if (!metadata) return null;
    
    const size = metadata.size;
    const format = this.detectImageFormat(blob);
    
    let quality = 'UNKNOWN';
    let score = 0;
    
    // サイズベースの評価
    if (size > 2 * 1024 * 1024) { // 2MB以上
      score += 30;
    } else if (size > 500 * 1024) { // 500KB以上
      score += 20;
    } else if (size > 100 * 1024) { // 100KB以上
      score += 10;
    }
    
    // フォーマットベースの評価
    if (format === 'PNG') {
      score += 20;
    } else if (format === 'JPEG') {
      score += 15;
    } else if (format === 'WEBP') {
      score += 25;
    }
    
    // 総合評価
    if (score >= 40) {
      quality = 'HIGH';
    } else if (score >= 25) {
      quality = 'MEDIUM';
    } else if (score >= 10) {
      quality = 'LOW';
    } else {
      quality = 'POOR';
    }
    
    return {
      quality: quality,
      score: score,
      size: metadata.sizeFormatted,
      format: format,
      recommendations: this.getQualityRecommendations(quality, format, size)
    };
  }
  
  /**
   * 品質に基づく推奨事項
   */
  static getQualityRecommendations(quality, format, size) {
    const recommendations = [];
    
    if (quality === 'POOR') {
      recommendations.push('画像の解像度を向上させることをお勧めします');
    }
    
    if (size < 50 * 1024) { // 50KB未満
      recommendations.push('ファイルサイズが小さすぎる可能性があります');
    }
    
    if (format === 'GIF') {
      recommendations.push('動画変換にはJPEGまたはPNGが適しています');
    }
    
    if (recommendations.length === 0) {
      recommendations.push('画像品質は動画変換に適しています');
    }
    
    return recommendations;
  }
} 