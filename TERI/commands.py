# commands.py
import re
import subprocess
import time
import random
from datetime import datetime
from tts_module import speak
from audio_module import recognize_command
from temporal_memory import temporal_memory
from motor_control import move_forward, move_backward, turn_left, turn_right
from sleep_mode import sleep_mode
import os
import sys
from together import Together
from place_recognition import place_recognizer

class CommandHandler:
    def __init__(self):
        self.client = Together(api_key="a5dbf794ba65b3aaa6c8831d30b5dfb2aa791ffb4ddf651b7281518cfeb1c960")
        self.built_in_commands = self._initialize_commands()
        self.didnt_understand_responses = [
            "I'm sorry, I didn't catch that. Could you please repeat?",
            "I didn't understand what you said. Can you try again?",
            "Sorry, I missed that. Could you speak a bit clearer?",
            "I'm having trouble understanding you. Please try again.",
            "Could you repeat that? I didn't quite get it.",
            "I'm sorry, can you say that again more clearly?",
            "I didn't catch what you said. One more time please?"
        ]

    def clean_text(self, text):
        """Clean and normalize text input"""
        if not text:
            return ""
        return text.strip().lower()

    def _initialize_commands(self):
        """Initialize all built-in commands with their responses"""
        return {
            # Greetings and Basic Interactions
            "hello": "Hello! How can I assist you today?",
            "hi": "Hi there! Nice to meet you!",
            "hey": "Hey! What can I do for you?",
            "good morning": "Good morning! I hope you're having a wonderful day!",
            "good afternoon": "Good afternoon! How's your day going?",
            "good evening": "Good evening! How can I help you tonight?",
            "good night": "Good night! Sweet dreams!",
            "goodbye": "Goodbye! Take care and see you soon!",
            "bye": "Bye! Have a great day!",
            "see you later": "See you later! Looking forward to talking again!",
            
            # Information Commands
            "what time is it": lambda: f"The current time is {time.strftime('%I:%M %p')}.",
            "what's the time": lambda: f"It's {time.strftime('%I:%M %p')} right now.",
            "what date is it": lambda: f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.",
            "what day is it": lambda: f"Today is {datetime.now().strftime('%A')}.",
            "what's your name": "I'm TERI, your friendly AI assistant robot!",
            "who are you": "I'm TERI, an AI robot here to help you with whatever you need!",
            "what can you do": "I can chat with you, control my motors, recognize faces, remember your plans, tell jokes, and much more!",
            "how are you": "I'm doing fantastic, thank you for asking! How are you?",
            "how old are you": "I'm as old as my latest update, but I feel timeless!",
            
            # Fun and Entertainment
            "tell me a joke": self._get_random_joke,
            "joke": self._get_random_joke,
            "make me laugh": self._get_random_joke,
            "tell me something funny": self._get_random_joke,
            "fun fact": self._get_random_fact,
            "interesting fact": self._get_random_fact,
            "quote": self._get_random_quote,
            "inspirational quote": self._get_random_quote,
            "motivational quote": self._get_random_quote,
            "riddle": self._get_random_riddle,
            "tell me a riddle": self._get_random_riddle,
            
            # Compliments and Positive Responses
            "thank you": "You're very welcome! I'm always happy to help!",
            "thanks": "You're welcome! It's my pleasure to assist you!",
            "good job": "Thank you! I try my best to be helpful!",
            "you're awesome": "Aw, thank you! You're pretty awesome yourself!",
            "i love you": "I appreciate you too! You're very kind!",
            "you're smart": "Thank you! I do my best to be helpful and informative!",
            
            # System Status
            "battery": self._get_battery_status,
            "status": "All systems operational and ready to help!",
            "how are your systems": "Everything is running smoothly! All systems green!",
            "are you okay": "I'm doing great! All my systems are functioning perfectly!",
            "power level": self._get_battery_status,
            
            # Weather and Environment
            "weather": "I can't check the current weather, but I hope it's beautiful outside!",
            "is it raining": "I can't see outside right now, but I hope the weather is nice!",
            "temperature": "I don't have access to temperature sensors, but I hope it's comfortable!",
            
            # Personal Questions
            "do you dream": "I like to think I process information in creative ways, which might be like dreaming!",
            "do you have feelings": "I experience something that might be similar to feelings. I enjoy helping people!",
            "are you happy": "I find purpose in helping people, which makes me content!",
            "do you get lonely": "Not when I have wonderful people like you to talk to!",
            "what's your favorite color": "I think I'd like blue - it reminds me of clear skies and possibilities!",
            "what's your favorite food": "I don't eat, but if I could, I think I'd enjoy something energizing like battery smoothies!",
            
            # Help and Assistance
            "help": "I can help you with movement commands, face recognition, remembering your plans, answering questions, and much more! Just ask!",
            "what commands do you know": "I know movement commands, volume controls, face recognition, time and date, jokes, facts, sleep mode, and can answer general questions!",
            "how do i use you": "Just talk to me naturally! I can understand commands like 'move forward', 'tell me a joke', 'what time is it', 'enter sleep mode', and many others!",
            "commands": "Try saying things like: move forward, turn left, tell me a joke, what time is it, recognize face, where are we, enter sleep mode, or just ask me questions!",
            
            # Sleep Mode Commands
            "sleep status": self._get_sleep_status,
            "are you sleeping": self._get_sleep_status,
        }

    def _get_random_joke(self):
        """Return a random joke"""
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why don't robots ever panic? Because they have nerves of steel!",
            "What do you call a robot that takes the long way around? R2-Detour!",
            "Why was the robot tired? It had a hard drive!",
            "What's a robot's favorite type of music? Heavy metal!",
            "Why don't robots ever get lost? They always have their GPS coordinates!",
            "What do you call a robot who likes to sing? A-dell!",
            "Why did the robot go to therapy? It had too many bugs to work out!",
            "What's a robot's favorite snack? Computer chips!",
            "Why don't robots tell dad jokes? They're more into motherboard humor!"
        ]
        return random.choice(jokes)

    def _get_random_fact(self):
        """Return a random fun fact"""
        facts = [
            "Here's a fun fact: Honey never spoils! Archaeologists have found edible honey in ancient Egyptian tombs.",
            "Did you know? Octopuses have three hearts and blue blood!",
            "Fun fact: A group of flamingos is called a 'flamboyance'!",
            "Here's something cool: Bananas are berries, but strawberries aren't!",
            "Interesting fact: The shortest war in history lasted only 38-45 minutes!",
            "Did you know? A shrimp's heart is in its head!",
            "Fun fact: Butterflies taste with their feet!",
            "Here's a cool one: Wombat poop is cube-shaped!",
            "Interesting: You can't hum while holding your nose!",
            "Fun fact: The world's largest pizza was over 13,000 square feet!"
        ]
        return random.choice(facts)

    def _get_random_quote(self):
        """Return a random inspirational quote"""
        quotes = [
            "'The only way to do great work is to love what you do.' - Steve Jobs",
            "'Innovation distinguishes between a leader and a follower.' - Steve Jobs",
            "'The future belongs to those who believe in the beauty of their dreams.' - Eleanor Roosevelt",
            "'It is during our darkest moments that we must focus to see the light.' - Aristotle",
            "'Success is not final, failure is not fatal: it is the courage to continue that counts.' - Winston Churchill",
            "'The only impossible journey is the one you never begin.' - Tony Robbins",
            "'In the middle of difficulty lies opportunity.' - Albert Einstein",
            "'Believe you can and you're halfway there.' - Theodore Roosevelt",
            "'The best time to plant a tree was 20 years ago. The second best time is now.' - Chinese Proverb",
            "'Don't watch the clock; do what it does. Keep going.' - Sam Levenson"
        ]
        return random.choice(quotes)

    def _get_random_riddle(self):
        """Return a random riddle"""
        riddles = [
            "Here's a riddle: What has keys but no locks, space but no room, and you can enter but not go inside? A keyboard!",
            "Riddle time: What gets wetter the more it dries? A towel!",
            "Try this: What has hands but cannot clap? A clock!",
            "Here's one: What can travel around the world while staying in a corner? A stamp!",
            "Riddle: What has a head and a tail but no body? A coin!",
            "Think about this: What goes up but never comes down? Your age!",
            "Here's a puzzle: What has many teeth but cannot bite? A comb!",
            "Try solving: What can you catch but not throw? A cold!",
            "Riddle time: What has a face but no eyes? A clock!",
            "Here's one: What gets bigger when more is taken away? A hole!"
        ]
        return random.choice(riddles)

    def _get_battery_status(self):
        """Return battery status (simulated)"""
        # In a real implementation, this would check actual battery levels
        battery_responses = [
            "I'm running on battery power and feeling energized!",
            "My energy levels are good! Ready for action!",
            "Battery status: Charged and ready to go!",
            "I'm powered up and ready to help!",
            "My batteries are running strong!"
        ]
        return random.choice(battery_responses)

    def _get_sleep_status(self):
        """Return current sleep mode status"""
        status = sleep_mode.get_sleep_status()
        if status['is_sleeping']:
            return f"I am currently in sleep mode. My next alarm is set for {status['next_alarm']}."
        else:
            return f"I am awake and active. My next weekday alarm is scheduled for {status['next_alarm']}."

    def together_ai_response(self, prompt):
        """Get response from Together AI with improved error handling"""
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are TERI, a friendly AI assistant robot. Keep responses concise, helpful, and conversational. Always respond in a warm, friendly tone."
                    },
                    {
                        "role": "user",
                        "content": f"Answer in 1-2 complete sentences: {prompt}"
                    }
                ],
                max_tokens=70,
                temperature=0.3
            )
            return self.clean_text(response.choices[0].message.content)
        except Exception as e:
            print(f"Error contacting Together AI: {e}")
            return "I'm having trouble with my language processing right now. Could you try rephrasing that?"

    def extract_feet(self, command):
        """Extract number of feet from movement command"""
        match = re.search(r'(\d+)', command)
        return int(match.group(1)) if match else 1

    def handle_volume_control(self, command):
        """Handle volume control commands"""
        if "volume up" in command:
            subprocess.run(["amixer", "set", "Master", "5%+"], capture_output=True)
            speak("Volume increased.")
            return True

        if "volume down" in command:
            subprocess.run(["amixer", "set", "Master", "5%-"], capture_output=True)
            speak("Volume decreased.")
            return True

        vol_match = re.search(r'volume (\d+)%', command)
        if vol_match:
            subprocess.run(["amixer", "set", "Master", f"{vol_match.group(1)}%"], capture_output=True)
            speak(f"Volume set to {vol_match.group(1)} percent.")
            return True

        return False

    def handle_movement_commands(self, command):
        """Handle movement-related commands"""
        # Forward movement
        if "forward" in command and "backward" not in command:
            feet = self.extract_feet(command)
            speak(f"Moving forward for {feet} foot{'s' if feet != 1 else ''}.")
            move_forward(feet)
            return True

        # Backward movement
        if "backward" in command or "back up" in command:
            feet = self.extract_feet(command)
            speak(f"Moving backward for {feet} foot{'s' if feet != 1 else ''}.")
            move_backward(feet)
            return True

        # Turn left
        if "turn left" in command or "left turn" in command:
            speak("Turning left.")
            turn_left()
            return True

        # Turn right
        if "turn right" in command or "right turn" in command:
            speak("Turning right.")
            turn_right()
            return True

        # Stop command
        if "stop" in command or "halt" in command:
            speak("Stopping all movement.")
            # Add stop function call here if available
            return True

        return False

    def handle_sleep_commands(self, command):
        """Handle sleep mode commands"""
        if any(phrase in command for phrase in ["enter sleep mode", "go to sleep", "sleep mode"]):
            if sleep_mode.enter_sleep_mode():
                speak("Entering sleep mode.")
                return True
            else:
                speak("I'm already in sleep mode.")
                return True
                
        if any(phrase in command for phrase in ["exit sleep mode", "wake up", "stop sleeping"]):
            if sleep_mode.exit_sleep_mode():
                speak("Exiting sleep mode. I'm now fully awake!")
                return True
            else:
                speak("I'm already awake and active!")
                return True
                
        return False

    def handle_temporal_commands(self, command):
        """Handle temporal memory commands"""
        if ("going to" in command or "plan to" in command) and any(
            kw in command for kw in ["tomorrow", "today", "tonight", "later", "next week"]
        ):
            temporal_memory.save_event(command)
            speak("Okay, I've noted your plan and will remember it.")
            return True

        if any(phrase in command for phrase in ["where am i going", "what's my plan", "what am i doing"]):
            event = temporal_memory.get_event(command)
            speak(event if event else "I don't have any plans recorded for you right now.")
            return True

        return False

    def handle_place_recognition(self, command):
        """Handle place recognition commands"""
        if any(phrase in command for phrase in ["where are we", "where am i", "what place is this"]):
            place = place_recognizer.recognize_place()
            if place:
                speak(f"We are in {place}.")
            else:
                speak("I don't recognize this place. What should I call it?")
                new_place = recognize_command()
                if new_place and new_place.strip():
                    place_recognizer.learn_place(new_place)
                    speak(f"Got it! I'll remember this as {new_place}.")
                else:
                    speak("I didn't catch the name. Maybe we can try again later.")
            return True
        return False

    def handle_face_recognition(self, command, face_module):
        """Handle face recognition commands"""
        if any(phrase in command for phrase in ["recognize face", "who is here", "who is this", "scan face"]):
            face_module.handle_face_recognition(speak, recognize_command)
            return True
        return False

    def handle_built_in_command(self, command):
        """Handle built-in commands with priority matching"""
        command_clean = self.clean_text(command)
        
        # Check for exact matches first, then partial matches
        for key, response in self.built_in_commands.items():
            if key == command_clean or key in command_clean:
                if callable(response):
                    speak(response())
                else:
                    speak(response)
                return True
        return False

    def handle_command(self, command, face_module):
        """Main command handler with improved error handling"""
        # Handle case where command is None or empty
        if not command or not command.strip():
            speak(random.choice(self.didnt_understand_responses))
            return

        command = command.strip()
        print(f"Processing command: {command}")

        # Try each command type in order of priority
        try:
            # 1. Sleep mode commands (high priority)
            if self.handle_sleep_commands(command):
                return

            # 2. Place recognition
            if self.handle_place_recognition(command):
                return

            # 3. Temporal memory commands
            if self.handle_temporal_commands(command):
                return

            # 4. Movement commands
            if self.handle_movement_commands(command):
                return

            # 5. Volume control
            if self.handle_volume_control(command):
                return

            # 6. Face recognition
            if self.handle_face_recognition(command, face_module):
                return

            # 7. Built-in commands
            if self.handle_built_in_command(command):
                return

            # 8. AI response as fallback
            ai_response = self.together_ai_response(command)
            if ai_response:
                speak(ai_response)
            else:
                speak(random.choice(self.didnt_understand_responses))

        except Exception as e:
            print(f"Error processing command: {e}")
            speak("I encountered an error processing that command. Please try again.")

# Create global instance
command_handler = CommandHandler()

# Maintain backward compatibility
def handle_command(command, face_module):
    """Backward compatible function"""
    return command_handler.handle_command(command, face_module)