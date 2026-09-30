import cv2
import face_recognition
import numpy as np

class FaceRecognizer:
    def __init__(self):
        self.known_encodings = []
        self.known_ids = []
    
    def register_face(self, image, user_id):
        """Register a new face"""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_image)
        
        if len(encodings) > 0:
            self.known_encodings.append(encodings[0])
            self.known_ids.append(user_id)
            return encodings[0]
        return None
    
    def recognize_face(self, image):
        """Recognize face from image"""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_image)
        
        if len(encodings) > 0:
            matches = face_recognition.compare_faces(self.known_encodings, encodings[0])
            if True in matches:
                match_index = matches.index(True)
                return self.known_ids[match_index]
        return None
