# tts_module.py
import time
from gtts import gTTS
import pygame

pygame.mixer.init()
speaking_channel = None

def speak(text):
    global speaking_channel
    if speaking_channel is not None and speaking_channel.get_busy():
        speaking_channel.stop()
    time.sleep(0.1)
    temp_mp3 = "/tmp/tts.mp3"
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(temp_mp3)
        sound = pygame.mixer.Sound(temp_mp3)
        speaking_channel = sound.play()
    except Exception as e:
        print("Error generating TTS:", e)
    time.sleep(0.1)
