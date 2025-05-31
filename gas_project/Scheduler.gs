/**
 * スケジューラー管理
 */

class Scheduler {
  
  /**
   * トリガーを設定
   */
  static setupTriggers() {
    // 既存のトリガーを削除
    this.deleteTriggers();
    
    try {
      // 毎時実行のトリガー
      ScriptApp.newTrigger('main')
        .timeBased()
        .everyHours(1)
        .create();
      
      // 毎日午前2時実行のトリガー
      ScriptApp.newTrigger('dailyMaintenance')
        .timeBased()
        .everyDays(1)
        .atHour(2)
        .create();
      
      Logger.log('✅ トリガー設定完了');
      
    } catch (error) {
      Logger.log(`❌ トリガー設定エラー: ${error.toString()}`);
    }
  }
  
  /**
   * 既存のトリガーを削除
   */
  static deleteTriggers() {
    try {
      const triggers = ScriptApp.getProjectTriggers();
      triggers.forEach(trigger => {
        ScriptApp.deleteTrigger(trigger);
      });
      
      Logger.log(`🗑️ ${triggers.length}個のトリガーを削除`);
      
    } catch (error) {
      Logger.log(`❌ トリガー削除エラー: ${error.toString()}`);
    }
  }
  
  /**
   * 実行履歴を記録
   */
  static logExecution(functionName, status, details = '') {
    try {
      const timestamp = new Date();
      const logEntry = {
        timestamp: timestamp.toISOString(),
        function: functionName,
        status: status, // 'SUCCESS', 'ERROR', 'WARNING'
        details: details,
        executionTime: timestamp.getTime()
      };
      
      // PropertiesServiceに保存（簡易ログ）
      const existingLogs = this.getExecutionLogs();
      existingLogs.push(logEntry);
      
      // 最新100件のみ保持
      if (existingLogs.length > 100) {
        existingLogs.splice(0, existingLogs.length - 100);
      }
      
      PropertiesService.getScriptProperties().setProperty(
        'EXECUTION_LOGS',
        JSON.stringify(existingLogs)
      );
      
      Logger.log(`📝 実行ログ記録: ${functionName} - ${status}`);
      
    } catch (error) {
      Logger.log(`❌ ログ記録エラー: ${error.toString()}`);
    }
  }
  
  /**
   * 実行履歴を取得
   */
  static getExecutionLogs() {
    try {
      const logsJson = PropertiesService.getScriptProperties().getProperty('EXECUTION_LOGS');
      return logsJson ? JSON.parse(logsJson) : [];
      
    } catch (error) {
      Logger.log(`❌ ログ取得エラー: ${error.toString()}`);
      return [];
    }
  }
  
  /**
   * エラー通知
   */
  static sendErrorNotification(error, functionName) {
    try {
      const subject = `🚨 InboundEngine エラー通知: ${functionName}`;
      const body = `
エラーが発生しました:

関数: ${functionName}
時刻: ${new Date().toLocaleString('ja-JP')}
エラー: ${error.toString()}

スタックトレース:
${error.stack || 'スタックトレース不明'}

--
InboundEngine Google Apps Script
      `;
      
      // 管理者にメール送信（実際のメールアドレスに変更してください）
      const adminEmail = 'admin@example.com';
      
      if (adminEmail !== 'admin@example.com') {
        MailApp.sendEmail({
          to: adminEmail,
          subject: subject,
          body: body
        });
        
        Logger.log('📧 エラー通知メール送信完了');
      }
      
    } catch (mailError) {
      Logger.log(`❌ エラー通知送信失敗: ${mailError.toString()}`);
    }
  }
  
  /**
   * システム状態をチェック
   */
  static checkSystemHealth() {
    const healthCheck = {
      timestamp: new Date().toISOString(),
      status: 'HEALTHY',
      issues: [],
      metrics: {}
    };
    
    try {
      // スプレッドシートアクセステスト
      const spreadsheet = SpreadsheetApp.openById(CONFIG.SHEET_ID);
      const sheets = spreadsheet.getSheets();
      healthCheck.metrics.sheetsCount = sheets.length;
      
      // 実行ログ確認
      const logs = this.getExecutionLogs();
      healthCheck.metrics.logCount = logs.length;
      
      // 最近のエラー確認
      const recentErrors = logs.filter(log => 
        log.status === 'ERROR' && 
        new Date(log.timestamp) > new Date(Date.now() - 24 * 60 * 60 * 1000)
      );
      
      if (recentErrors.length > 10) {
        healthCheck.status = 'WARNING';
        healthCheck.issues.push('24時間以内に10件以上のエラーが発生');
      }
      
      // スクリプト実行時間制限チェック
      const runtime = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');
      healthCheck.metrics.lastCheck = runtime;
      
      Logger.log(`🔍 システム状態: ${healthCheck.status}`);
      
      // 状態をPropertiesServiceに保存
      PropertiesService.getScriptProperties().setProperty(
        'SYSTEM_HEALTH',
        JSON.stringify(healthCheck)
      );
      
      return healthCheck;
      
    } catch (error) {
      healthCheck.status = 'ERROR';
      healthCheck.issues.push(`システムチェックエラー: ${error.toString()}`);
      
      Logger.log(`❌ システム状態チェックエラー: ${error.toString()}`);
      return healthCheck;
    }
  }
  
  /**
   * パフォーマンス統計を記録
   */
  static recordPerformanceMetrics(functionName, startTime, endTime, recordsProcessed = 0) {
    try {
      const executionTime = endTime - startTime;
      const metrics = {
        timestamp: new Date().toISOString(),
        function: functionName,
        executionTime: executionTime,
        recordsProcessed: recordsProcessed,
        averageTimePerRecord: recordsProcessed > 0 ? executionTime / recordsProcessed : 0
      };
      
      // 既存のメトリクスを取得
      const existingMetrics = this.getPerformanceMetrics();
      existingMetrics.push(metrics);
      
      // 最新50件のみ保持
      if (existingMetrics.length > 50) {
        existingMetrics.splice(0, existingMetrics.length - 50);
      }
      
      PropertiesService.getScriptProperties().setProperty(
        'PERFORMANCE_METRICS',
        JSON.stringify(existingMetrics)
      );
      
      Logger.log(`📊 パフォーマンス記録: ${functionName} - ${executionTime}ms`);
      
    } catch (error) {
      Logger.log(`❌ パフォーマンス記録エラー: ${error.toString()}`);
    }
  }
  
  /**
   * パフォーマンス統計を取得
   */
  static getPerformanceMetrics() {
    try {
      const metricsJson = PropertiesService.getScriptProperties().getProperty('PERFORMANCE_METRICS');
      return metricsJson ? JSON.parse(metricsJson) : [];
      
    } catch (error) {
      Logger.log(`❌ パフォーマンス取得エラー: ${error.toString()}`);
      return [];
    }
  }
}

/**
 * メンテナンス用関数
 */
function dailyMaintenance() {
  Logger.log('🔧 日次メンテナンス開始');
  
  try {
    // システム状態チェック
    const healthCheck = Scheduler.checkSystemHealth();
    
    // ログのクリーンアップ
    const logs = Scheduler.getExecutionLogs();
    const metrics = Scheduler.getPerformanceMetrics();
    
    Logger.log(`📊 メンテナンス完了: ログ${logs.length}件, メトリクス${metrics.length}件`);
    
    // ヘルスチェック結果をログ記録
    Scheduler.logExecution('dailyMaintenance', 'SUCCESS', `システム状態: ${healthCheck.status}`);
    
  } catch (error) {
    Logger.log(`❌ 日次メンテナンスエラー: ${error.toString()}`);
    Scheduler.logExecution('dailyMaintenance', 'ERROR', error.toString());
    Scheduler.sendErrorNotification(error, 'dailyMaintenance');
  }
}

/**
 * 手動でトリガー設定を実行する関数
 */
function setupScheduledTriggers() {
  Scheduler.setupTriggers();
} 