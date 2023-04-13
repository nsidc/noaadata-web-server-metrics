import datetime as dt
import json
from typing import Any

class DateFriendlyJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, dt.date):
            return obj.isoformat()
        return super(DateFriendlyJSONEncoder, self).default(obj)
