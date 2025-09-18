# place_recognition.py
import cv2
import numpy as np
import pickle
import os
from datetime import datetime
from common import capture_shared_frame

PLACES_FILE = "/home/Izzy/place_encodings.pkl"

class PlaceRecognizer:
    def __init__(self):
        self.known_places = self.load_places()
        self.current_place = None
        
    def load_places(self):
        try:
            with open(PLACES_FILE, "rb") as f:
                return pickle.load(f)
        except:
            return {"names": [], "encodings": []}
            
    def save_places(self):
        with open(PLACES_FILE, "wb") as f:
            pickle.dump(self.known_places, f)
            
    def extract_features(self, frame):
        """Lightweight scene features using color + edge histograms"""
        # Resize for faster processing
        small = cv2.resize(frame, (160, 120))
        
        # Color histogram (HSV space)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist_color = cv2.calcHist([hsv], [0,1], None, [8,8], [0,180,0,256])
        hist_color = cv2.normalize(hist_color, hist_color).flatten()
        
        # Edge density
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        hist_edges = cv2.calcHist([edges], [0], None, [4], [0,256]).flatten()
        
        return np.hstack([hist_color, hist_edges])
        
    def recognize_place(self):
        frame = capture_shared_frame()
        if frame is None:
            return None
            
        current_encoding = self.extract_features(frame)
        
        # Compare to known places
        if self.known_places["encodings"]:
            distances = [np.linalg.norm(enc - current_encoding) 
                        for enc in self.known_places["encodings"]]
            min_idx = np.argmin(distances)
            if distances[min_idx] < 0.4:  # Threshold adjustable per environment
                self.current_place = self.known_places["names"][min_idx]
                return self.current_place
                
        return None
        
    def learn_place(self, name):
        frame = capture_shared_frame()
        if frame is None:
            return False
            
        encoding = self.extract_features(frame)
        self.known_places["names"].append(name)
        self.known_places["encodings"].append(encoding)
        self.save_places()
        self.current_place = name
        return True

# Global instance
place_recognizer = PlaceRecognizer()
