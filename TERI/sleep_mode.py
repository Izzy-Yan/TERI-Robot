# sleep_mode.py
import time
import threading
from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger('Teri.SleepMode')

class SleepMode:
    def __init__(self):
        self.is_sleeping = False
        self.alarm_thread = None
        self.alarm_time = (5, 30)  # 5:30 AM
        self.weekdays = [0, 1, 2, 3, 4]  # Monday to Friday (0=Monday, 6=Sunday)
        self.los_angeles_tz = pytz.timezone('America/Los_Angeles')
        self.alarm_active = False
        
    def enter_sleep_mode(self):
        """Enter sleep mode and set up alarm"""
        if self.is_sleeping:
            return False
            
        logger.info("Entering sleep mode")
        self.is_sleeping = True
        self.alarm_active = True
        
        # Start alarm monitoring thread
        self.alarm_thread = threading.Thread(target=self._alarm_monitor, daemon=True)
        self.alarm_thread.start()
        
        return True
    
    def exit_sleep_mode(self):
        """Exit sleep mode"""
        if not self.is_sleeping:
            return False
            
        logger.info("Exiting sleep mode")
        self.is_sleeping = False
        self.alarm_active = False
        
        return True
    
    def _alarm_monitor(self):
        """Monitor for alarm time on weekdays"""
        while self.alarm_active:
            try:
                # Get current time in Los Angeles timezone
                now = datetime.now(self.los_angeles_tz)
                current_weekday = now.weekday()
                current_time = (now.hour, now.minute)
                
                # Check if it's a weekday and alarm time
                if (current_weekday in self.weekdays and 
                    current_time == self.alarm_time and
                    self.is_sleeping):
                    
                    logger.info("Alarm triggered - time to wake up!")
                    self._trigger_alarm()
                    break
                
                # Sleep for 60 seconds before checking again
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in alarm monitor: {e}")
                time.sleep(60)
    
    def _trigger_alarm(self):
        """Trigger the alarm and wake up"""
        from tts_module import speak
        
        # Exit sleep mode
        self.exit_sleep_mode()
        
        # Wake up message at full volume
        speak("Time to wake up, good morning!")
        
    def get_sleep_status(self):
        """Get current sleep mode status"""
        return {
            'is_sleeping': self.is_sleeping,
            'alarm_time': f"{self.alarm_time[0]:02d}:{self.alarm_time[1]:02d}",
            'next_alarm': self._get_next_alarm_time()
        }
    
    def _get_next_alarm_time(self):
        """Calculate the next alarm time"""
        try:
            now = datetime.now(self.los_angeles_tz)
            
            # Find the next weekday alarm
            for i in range(8):  # Check next 7 days
                check_date = now + timedelta(days=i)
                if check_date.weekday() in self.weekdays:
                    alarm_datetime = check_date.replace(
                        hour=self.alarm_time[0], 
                        minute=self.alarm_time[1], 
                        second=0, 
                        microsecond=0
                    )
                    
                    # If it's today, make sure alarm time hasn't passed
                    if i == 0 and now >= alarm_datetime:
                        continue
                        
                    return alarm_datetime.strftime('%A, %B %d at %I:%M %p')
            
            return "No upcoming alarms"
            
        except Exception as e:
            logger.error(f"Error calculating next alarm: {e}")
            return "Unable to calculate next alarm"

# Global sleep mode instance
sleep_mode = SleepMode()