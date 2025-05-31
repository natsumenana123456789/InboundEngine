import re
import unicodedata

class TextProcessor:
    MAX_LENGTH = 280
    MAX_LINE_BREAKS = 8

    def normalize(self, text: str) -> str:
        """テキストを正規化する"""
        if not text:
            return ""

        # 全角文字を半角に変換
        text = unicodedata.normalize('NFKC', text)

        # 制御文字を除去（絵文字と改行は保持）
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or ord(char) > 0x1F or char == '\n')

        # 改行の正規化（最初の処理）
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 連続改行を最大2つまでに制限
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 各行を処理
        lines = []
        current_line = ""
        for char in text:
            if char == '\n':
                # 行末の空白を除去して追加
                lines.append(current_line.rstrip())
                current_line = ""
            else:
                current_line += char
        # 最後の行を追加
        if current_line:
            lines.append(current_line.rstrip())

        # 各行の空白を正規化
        normalized_lines = []
        for line in lines:
            if not line:  # 空行はそのまま追加
                normalized_lines.append(line)
                continue
            
            # 行内の空白を正規化（URLは保持）
            parts = []
            for part in line.split():
                if part.startswith(('http://', 'https://')):
                    parts.append(part)
                else:
                    parts.append(part.strip())
            normalized_lines.append(' '.join(parts))

        # 改行数を制限
        if len(normalized_lines) > self.MAX_LINE_BREAKS + 1:
            normalized_lines = normalized_lines[:self.MAX_LINE_BREAKS + 1]

        # 行を結合
        text = '\n'.join(normalized_lines)

        # 最大文字数を超える場合は切り詰め
        if len(text) > self.MAX_LENGTH:
            text = text[:self.MAX_LENGTH-3] + "..."

        return text 