# temporal_memory.py
from datetime import datetime, timedelta
import dateparser

class TemporalEventMemory:
    def __init__(self):
        self.events = {}
    
    def save_event(self, text: str):
        lower = text.lower()
        if "tomorrow" in lower:
            event_date = datetime.today() + timedelta(days=1)
        elif any(word in lower for word in ["today", "tonight", "this afternoon"]):
            event_date = datetime.today()
        else:
            parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
            event_date = parsed if parsed is not None else datetime.today()
        key = event_date.strftime("%Y-%m-%d")
        self.events.setdefault(key, []).append(text)
        print(f"[TemporalEventMemory] Saved event for {key}: {text}")
    
    def get_event(self, query: str):
        lower = query.lower()
        query_date = datetime.today() + timedelta(days=1) if "tomorrow" in lower else datetime.today()
        key = query_date.strftime("%Y-%m-%d")
        events = self.events.get(key, [])
        if events:
            events_text = "; ".join(events)
            print(f"[TemporalEventMemory] Found event(s) for {key}: {events_text}")
            return events_text
        else:
            print(f"[TemporalEventMemory] No event found for {key}.")
            return ""
    
    def clear_expired(self):
        today_str = datetime.today().strftime("%Y-%m-%d")
        for k in list(self.events.keys()):
            if k < today_str:
                del self.events[k]
                print(f"[TemporalEventMemory] Cleared event for {k}.")

# Create a module-level instance for convenience.
temporal_memory = TemporalEventMemory()
