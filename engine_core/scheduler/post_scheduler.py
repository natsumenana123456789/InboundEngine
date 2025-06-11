from datetime import datetime
from typing import Optional, TypedDict

class ScheduledPost(TypedDict):
    account_id: str
    scheduled_time: datetime
    worksheet_name: Optional[str]
    # text_content_override は executor でのみ暗黙的に使われていたので、型定義からは一旦削除 