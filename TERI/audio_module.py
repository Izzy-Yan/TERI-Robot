# audio_module.py
import time
import struct
import audioop
import pyaudio
import pygame
import speech_recognition as sr
import subprocess

try:
    import pvporcupine
    WAKE_WORD_PATH = "/home/Izzy/Hey-Teri/Hey-Teri_en_raspberry-pi_v3_0_0.ppn"
    porcupine = pvporcupine.create(
        access_key="Mh37pu2XZYtcIbw+Dk6mRdHJV7KFqeNgodm2IkxE2e8cKwZQu+R5Uw==",
        keyword_paths=[WAKE_WORD_PATH]
    )
except IOError as e:
    print(f"Error initializing Porcupine: {e}")
    raise SystemExit(e)

pa = pyaudio.PyAudio()

def get_audio_stream():
    return pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

SILENCE_THRESHOLD = 300  # Adjust as needed
SILENCE_DURATION = 0.7   # Seconds required for silence

def wait_for_silence(source, silence_duration=SILENCE_DURATION, threshold=SILENCE_THRESHOLD):
    print("Waiting for a period of quiet...")
    silence_start = None
    buffer_size = 1024
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Optionally, call an exit handler here.
                pass
        try:
            data = source.stream.read(buffer_size)
        except Exception as e:
            print(f"Error reading audio stream: {e}")
            continue
        rms = audioop.rms(data, 2)
        if rms < threshold:
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start >= silence_duration:
                print("Silence detected.")
                return
        else:
            silence_start = None
        time.sleep(0.05)

def recognize_command():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening for command... Please speak after a brief pause.")
        wait_for_silence(source)
        audio = recognizer.listen(source)
    try:
        command = recognizer.recognize_google(audio).lower()
        print("You said:", command)
        return command
    except sr.UnknownValueError:
        print("Could not understand audio")
        return None
    except sr.RequestError as e:
        print(f"Could not request results: {e}")
        return None

# Add the alias function that your main.py is looking for
def listen_for_command():
    """Alias for recognize_command() to match the function call in main.py"""
    return recognize_command()

def shutdown_audio_stream(audio_stream):
    if audio_stream is not None:
        audio_stream.stop_stream()
        audio_stream.close()
    pa.terminate()
    porcupine.delete()
