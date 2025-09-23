from datetime import datetime, timedelta
import dateparser
import json
import os
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

class EventType(Enum):
    REMINDER = "reminder"
    APPOINTMENT = "appointment"
    TASK = "task"
    NOTE = "note"
    RECURRING = "recurring"

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class TemporalEvent:
    """Represents a temporal event with rich metadata"""
    id: str
    text: str
    event_type: EventType
    date_time: datetime
    priority: Priority = Priority.MEDIUM
    completed: bool = False
    tags: List[str] = None
    location: str = ""
    duration_minutes: int = 0
    recurring_pattern: str = ""  # e.g., "daily", "weekly", "monthly"
    created_at: datetime = None
    last_modified: datetime = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_modified is None:
            self.last_modified = datetime.now()

class TemporalEventMemory:
    def __init__(self, storage_file: str = "temporal_events.json"):
        self.storage_file = storage_file
        self.events: Dict[str, TemporalEvent] = {}
        self.load_from_file()
        
        # Enhanced date parsing patterns
        self.time_patterns = {
            r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b': self._parse_time,
            r'\bat\s+(\d{1,2})\s*(am|pm)\b': self._parse_hour_ampm,
            r'\bin\s+(\d+)\s+(minutes?|hours?|days?)\b': self._parse_relative_time,
            r'\b(morning|afternoon|evening|night)\b': self._parse_time_of_day,
        }
        
        # Priority keywords
        self.priority_keywords = {
            Priority.URGENT: ['urgent', 'asap', 'immediately', 'emergency', 'critical'],
            Priority.HIGH: ['important', 'high priority', 'soon', 'quickly'],
            Priority.MEDIUM: ['medium', 'normal', 'regular'],
            Priority.LOW: ['low', 'sometime', 'when possible', 'eventually']
        }
        
        # Event type keywords
        self.type_keywords = {
            EventType.REMINDER: ['remind', 'remember', 'don\'t forget'],
            EventType.APPOINTMENT: ['meeting', 'appointment', 'call', 'visit'],
            EventType.TASK: ['task', 'do', 'complete', 'finish', 'work on'],
            EventType.NOTE: ['note', 'write down', 'record'],
            EventType.RECURRING: ['every', 'daily', 'weekly', 'monthly', 'recurring']
        }

    def _parse_time(self, match) -> Tuple[int, int]:
        """Parse time from regex match"""
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3)
        
        if ampm:
            if ampm.lower() == 'pm' and hour != 12:
                hour += 12
            elif ampm.lower() == 'am' and hour == 12:
                hour = 0
        
        return hour, minute

    def _parse_hour_ampm(self, match) -> Tuple[int, int]:
        """Parse hour with AM/PM"""
        hour = int(match.group(1))
        ampm = match.group(2)
        
        if ampm.lower() == 'pm' and hour != 12:
            hour += 12
        elif ampm.lower() == 'am' and hour == 12:
            hour = 0
            
        return hour, 0

    def _parse_relative_time(self, match) -> timedelta:
        """Parse relative time like 'in 30 minutes'"""
        amount = int(match.group(1))
        unit = match.group(2).lower()
        
        if 'minute' in unit:
            return timedelta(minutes=amount)
        elif 'hour' in unit:
            return timedelta(hours=amount)
        elif 'day' in unit:
            return timedelta(days=amount)
        
        return timedelta()

    def _parse_time_of_day(self, match) -> Tuple[int, int]:
        """Parse general time of day"""
        time_of_day = match.group(1).lower()
        time_map = {
            'morning': (9, 0),
            'afternoon': (14, 0),
            'evening': (18, 0),
            'night': (20, 0)
        }
        return time_map.get(time_of_day, (12, 0))

    def _extract_time_from_text(self, text: str, base_date: datetime) -> datetime:
        """Enhanced time extraction from text"""
        text_lower = text.lower()
        result_datetime = base_date.replace(hour=12, minute=0, second=0, microsecond=0)
        
        # Check for specific time patterns
        for pattern, parser in self.time_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                if pattern == r'\bin\s+(\d+)\s+(minutes?|hours?|days?)\b':
                    # Relative time
                    delta = parser(match)
                    result_datetime = datetime.now() + delta
                else:
                    # Absolute time
                    hour, minute = parser(match)
                    result_datetime = result_datetime.replace(hour=hour, minute=minute)
                break
        
        return result_datetime

    def _determine_event_type(self, text: str) -> EventType:
        """Determine event type from text content"""
        text_lower = text.lower()
        
        for event_type, keywords in self.type_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return event_type
        
        return EventType.REMINDER  # Default

    def _determine_priority(self, text: str) -> Priority:
        """Determine priority from text content"""
        text_lower = text.lower()
        
        for priority, keywords in self.priority_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return priority
        
        return Priority.MEDIUM  # Default

    def _extract_tags(self, text: str) -> List[str]:
        """Extract hashtags and keywords as tags"""
        tags = []
        
        # Extract hashtags
        hashtags = re.findall(r'#(\w+)', text)
        tags.extend(hashtags)
        
        # Extract common categories
        category_keywords = {
            'work': ['work', 'office', 'meeting', 'project', 'deadline'],
            'personal': ['personal', 'family', 'friend', 'home'],
            'health': ['doctor', 'dentist', 'gym', 'exercise', 'medicine'],
            'shopping': ['buy', 'purchase', 'store', 'market', 'shopping'],
            'travel': ['flight', 'trip', 'vacation', 'travel', 'hotel']
        }
        
        text_lower = text.lower()
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                tags.append(category)
        
        return list(set(tags))  # Remove duplicates

    def _parse_enhanced_date(self, text: str) -> datetime:
        """Enhanced date parsing with multiple strategies"""
        text_lower = text.lower()
        
        # Handle relative dates first
        if "tomorrow" in text_lower:
            base_date = datetime.today() + timedelta(days=1)
        elif any(word in text_lower for word in ["today", "tonight", "this afternoon", "this morning"]):
            base_date = datetime.today()
        elif "day after tomorrow" in text_lower:
            base_date = datetime.today() + timedelta(days=2)
        elif "next week" in text_lower:
            base_date = datetime.today() + timedelta(days=7)
        elif "next month" in text_lower:
            base_date = datetime.today() + timedelta(days=30)
        else:
            # Try dateparser for more complex dates
            parsed = dateparser.parse(text, settings={
                'PREFER_DATES_FROM': 'future',
                'PREFER_DAY_OF_MONTH': 'first',
                'RETURN_AS_TIMEZONE_AWARE': False
            })
            base_date = parsed if parsed else datetime.today()
        
        # Extract specific time if mentioned
        return self._extract_time_from_text(text, base_date)

    def save_event(self, text: str, event_id: str = None) -> str:
        """Save an event with enhanced parsing and metadata extraction"""
        try:
            # Generate unique ID if not provided
            if not event_id:
                event_id = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.events)}"
            
            # Parse date and time
            event_datetime = self._parse_enhanced_date(text)
            
            # Extract metadata
            event_type = self._determine_event_type(text)
            priority = self._determine_priority(text)
            tags = self._extract_tags(text)
            
            # Extract location if mentioned
            location_match = re.search(r'\b(?:at|in|@)\s+([^,.\n]+)', text, re.IGNORECASE)
            location = location_match.group(1).strip() if location_match else ""
            
            # Extract duration if mentioned
            duration_match = re.search(r'(\d+)\s*(minutes?|hours?|hrs?)', text.lower())
            duration = 0
            if duration_match:
                amount = int(duration_match.group(1))
                unit = duration_match.group(2)
                duration = amount * (60 if 'hour' in unit or 'hr' in unit else 1)
            
            # Create event
            event = TemporalEvent(
                id=event_id,
                text=text,
                event_type=event_type,
                date_time=event_datetime,
                priority=priority,
                tags=tags,
                location=location,
                duration_minutes=duration
            )
            
            self.events[event_id] = event
            self.save_to_file()
            
            print(f"[TemporalEventMemory] Saved {event_type.value} for {event_datetime.strftime('%Y-%m-%d %H:%M')}: {text}")
            return event_id
            
        except Exception as e:
            print(f"[TemporalEventMemory] Error saving event: {e}")
            return ""

    def get_events_for_date(self, query_date: datetime = None) -> List[TemporalEvent]:
        """Get all events for a specific date"""
        if query_date is None:
            query_date = datetime.today()
        
        target_date = query_date.date()
        matching_events = []
        
        for event in self.events.values():
            if event.date_time.date() == target_date:
                matching_events.append(event)
        
        # Sort by time
        matching_events.sort(key=lambda e: e.date_time)
        return matching_events

    def get_upcoming_events(self, days_ahead: int = 7) -> List[TemporalEvent]:
        """Get upcoming events within specified days"""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)
        
        upcoming = []
        for event in self.events.values():
            if now <= event.date_time <= end_date and not event.completed:
                upcoming.append(event)
        
        # Sort by date/time and priority
        upcoming.sort(key=lambda e: (e.date_time, -e.priority.value))
        return upcoming

    def get_overdue_events(self) -> List[TemporalEvent]:
        """Get events that are overdue"""
        now = datetime.now()
        overdue = []
        
        for event in self.events.values():
            if event.date_time < now and not event.completed:
                overdue.append(event)
        
        overdue.sort(key=lambda e: e.date_time)
        return overdue

    def search_events(self, query: str) -> List[TemporalEvent]:
        """Search events by text content or tags"""
        query_lower = query.lower()
        matching_events = []
        
        for event in self.events.values():
            if (query_lower in event.text.lower() or 
                any(query_lower in tag.lower() for tag in event.tags) or
                query_lower in event.location.lower()):
                matching_events.append(event)
        
        return matching_events

    def get_events_by_type(self, event_type: EventType) -> List[TemporalEvent]:
        """Get all events of a specific type"""
        return [event for event in self.events.values() if event.event_type == event_type]

    def complete_event(self, event_id: str) -> bool:
        """Mark an event as completed"""
        if event_id in self.events:
            self.events[event_id].completed = True
            self.events[event_id].last_modified = datetime.now()
            self.save_to_file()
            print(f"[TemporalEventMemory] Marked event as completed: {event_id}")
            return True
        return False

    def delete_event(self, event_id: str) -> bool:
        """Delete an event"""
        if event_id in self.events:
            del self.events[event_id]
            self.save_to_file()
            print(f"[TemporalEventMemory] Deleted event: {event_id}")
            return True
        return False

    def update_event(self, event_id: str, **kwargs) -> bool:
        """Update event properties"""
        if event_id in self.events:
            event = self.events[event_id]
            for key, value in kwargs.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            event.last_modified = datetime.now()
            self.save_to_file()
            print(f"[TemporalEventMemory] Updated event: {event_id}")
            return True
        return False

    def get_event_summary(self, query: str = "") -> str:
        """Get a formatted summary of events"""
        if not query:
            events = self.get_upcoming_events()
        else:
            # Parse query for specific requests
            query_lower = query.lower()
            if "tomorrow" in query_lower:
                target_date = datetime.today() + timedelta(days=1)
                events = self.get_events_for_date(target_date)
            elif "today" in query_lower:
                events = self.get_events_for_date(datetime.today())
            elif "overdue" in query_lower:
                events = self.get_overdue_events()
            else:
                events = self.search_events(query)
        
        if not events:
            return "No events found."
        
        summary_lines = []
        for event in events[:10]:  # Limit to 10 events
            time_str = event.date_time.strftime('%m/%d %H:%M')
            priority_str = f"[{event.priority.name}]" if event.priority != Priority.MEDIUM else ""
            type_str = f"({event.event_type.value})"
            status_str = "✓" if event.completed else ""
            
            line = f"{time_str} {priority_str}{type_str} {event.text} {status_str}"
            if event.location:
                line += f" @ {event.location}"
            summary_lines.append(line.strip())
        
        return "\n".join(summary_lines)

    def clear_expired(self, days_old: int = 30):
        """Clear completed events older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        expired_ids = []
        
        for event_id, event in self.events.items():
            if event.completed and event.date_time < cutoff_date:
                expired_ids.append(event_id)
        
        for event_id in expired_ids:
            del self.events[event_id]
            print(f"[TemporalEventMemory] Cleared expired event: {event_id}")
        
        if expired_ids:
            self.save_to_file()

    def save_to_file(self):
        """Save events to JSON file"""
        try:
            data = {}
            for event_id, event in self.events.items():
                event_dict = asdict(event)
                # Convert datetime objects to ISO strings
                event_dict['date_time'] = event.date_time.isoformat()
                event_dict['created_at'] = event.created_at.isoformat()
                event_dict['last_modified'] = event.last_modified.isoformat()
                # Convert enums to strings
                event_dict['event_type'] = event.event_type.value
                event_dict['priority'] = event.priority.value
                data[event_id] = event_dict
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[TemporalEventMemory] Error saving to file: {e}")

    def load_from_file(self):
        """Load events from JSON file"""
        if not os.path.exists(self.storage_file):
            return
        
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
            
            for event_id, event_dict in data.items():
                # Convert ISO strings back to datetime objects
                event_dict['date_time'] = datetime.fromisoformat(event_dict['date_time'])
                event_dict['created_at'] = datetime.fromisoformat(event_dict['created_at'])
                event_dict['last_modified'] = datetime.fromisoformat(event_dict['last_modified'])
                # Convert strings back to enums
                event_dict['event_type'] = EventType(event_dict['event_type'])
                event_dict['priority'] = Priority(event_dict['priority'])
                
                self.events[event_id] = TemporalEvent(**event_dict)
            
            print(f"[TemporalEventMemory] Loaded {len(self.events)} events from file")
        except Exception as e:
            print(f"[TemporalEventMemory] Error loading from file: {e}")

    def get_stats(self) -> Dict:
        """Get statistics about stored events"""
        total_events = len(self.events)
        completed_events = sum(1 for e in self.events.values() if e.completed)
        overdue_events = len(self.get_overdue_events())
        upcoming_events = len(self.get_upcoming_events())
        
        type_counts = {}
        for event_type in EventType:
            type_counts[event_type.value] = len(self.get_events_by_type(event_type))
        
        return {
            'total_events': total_events,
            'completed_events': completed_events,
            'overdue_events': overdue_events,
            'upcoming_events': upcoming_events,
            'events_by_type': type_counts
        }

# Create a module-level instance for convenience
temporal_memory = TemporalEventMemory()