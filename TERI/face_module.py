# face_module.py
import os
import time
import pickle
import numpy as np
import cv2
import face_recognition
from datetime import datetime
from common import capture_shared_frame
import threading

FILENAME = "/home/Izzy/face_encodings.pkl"

# Recognition state tracking
current_recognition = {
    "name": None,
    "location": None,
    "timestamp": datetime.now().timestamp()
}
recognition_lock = threading.Lock()

def update_recognition_state(name=None, location=None):
    global current_recognition
    with recognition_lock:
        current_recognition["name"] = name
        current_recognition["location"] = location
        current_recognition["timestamp"] = datetime.now().timestamp()

def get_current_recognition():
    with recognition_lock:
        return current_recognition.copy()

def collect_consistent_face_encoding(sample_count=3, delay=0.2):
    encodings = []
    attempts = 0
    max_attempts = 10
    while len(encodings) < sample_count and attempts < max_attempts:
        try:
            frame = capture_shared_frame()
            if frame is None:
                continue
                
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            
            if face_locations:
                face_encs = face_recognition.face_encodings(rgb_frame, face_locations)
                if face_encs:
                    encodings.append(face_encs[0])
                    print(f"[Face] Captured encoding {len(encodings)}/{sample_count}")
        except Exception as e:
            print("[Face] Error capturing frame:", e)
        attempts += 1
        time.sleep(delay)
        
    if len(encodings) == 0:
        return None
    avg_encoding = np.mean(encodings, axis=0)
    print("[Face] Averaged encoding computed.")
    return avg_encoding

def load_known_faces():
    try:
        with open(FILENAME, "rb") as f:
            known_faces = pickle.load(f)
        print("[Face] Loaded known faces.")
    except Exception as e:
        print("No face encoding file found. Starting fresh.")
        known_faces = {"encodings": [], "names": []}
    return known_faces

def save_known_faces(known_faces):
    with open(FILENAME, "wb") as f:
        pickle.dump(known_faces, f)
    print("[Face] Saved known faces.")

def update_known_face(known_faces, index, new_encoding):
    known_faces["encodings"][index] = np.mean([known_faces["encodings"][index], new_encoding], axis=0)
    save_known_faces(known_faces)

def handle_face_recognition(speak, recognize_command):
    known_faces = load_known_faces()
    new_encoding = collect_consistent_face_encoding()
    
    if new_encoding is None:
        update_recognition_state()
        speak("I don't see any face right now.")
        return

    frame = capture_shared_frame()
    face_locations = face_recognition.face_locations(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) if frame else []

    if known_faces["encodings"]:
        distances = face_recognition.face_distance(known_faces["encodings"], new_encoding)
        min_distance = np.min(distances)
        print(f"[Face] Minimum distance: {min_distance}")
        
        if min_distance < 0.5:
            index = np.argmin(distances)
            recognized_name = known_faces["names"][index]
            location = face_locations[0] if face_locations else None
            update_recognition_state(recognized_name, location)
            speak(f"I recognize you as {recognized_name}.")
            update_known_face(known_faces, index, new_encoding)
            return

    # New face enrollment
    update_recognition_state()
    speak("I don't recognize this face. What is your name?")
    new_name = recognize_command()
    
    if new_name:
        new_name = new_name.strip()
        speak(f"Should I remember you as {new_name}? Please say yes or no.")
        confirmation = recognize_command()
        
        if confirmation and confirmation.lower() in ["yes", "yeah", "correct"]:
            known_faces["encodings"].append(new_encoding)
            known_faces["names"].append(new_name)
            save_known_faces(known_faces)
            update_recognition_state(new_name, face_locations[0] if face_locations else None)
            speak(f"Got it. I will remember you as {new_name}.")
        else:
            speak("Okay, I won't save this face now.")
    else:
        speak("I didn't catch your name.")
