import datetime as dt
import json


class DateFriendlyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt.date):
            return obj.isoformat()
        return super(DateFriendlyJSONEncoder, self).default(obj)
