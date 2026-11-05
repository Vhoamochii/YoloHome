import cv2
import face_recognition
import numpy as np
import pickle
import os
import speech_recognition as sr
import threading
import time

# Load registered faces
data_file = "faces_data.pkl"
if not os.path.exists(data_file):
    print("No registered faces found!")
    print("Please run: python register-face.py")
    exit()

with open(data_file, "rb") as f:
    data = pickle.load(f)

known_face_encodings = data["encodings"]
known_face_names = data["names"]

print(f"Loaded {len(known_face_names)} registered face(s)")
print("Controls:")
print("  - Press 'q' to quit")
print("  - Press 'v' to activate voice command")
print("  - Say: 'turn on light', 'turn off fan', etc.\n")

recognizer = sr.Recognizer()
microphone = sr.Microphone()

voice_active = False
last_command = "Waiting for voice command..."

def listen_for_voice():
    global last_command, voice_active
    with microphone as source:
        print("🎤 Listening... (Say your command)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            print("Processing voice...")
            
            try:
                text = recognizer.recognize_google(audio, language='en-US').lower()
                print(f"🇺🇸 Heard (English): {text}")
            except:
                text = recognizer.recognize_google(audio, language='vi-VN').lower()
                print(f"🇻🇳 Heard (Vietnamese): {text}")
            
            if "light" in text or "đèn" in text:
                if "on" in text or "bật" in text:
                    last_command = "✅ Command: TURN ON LIGHT"
                    print("💡 Action: Turn on light")
                elif "off" in text or "tắt" in text:
                    last_command = "✅ Command: TURN OFF LIGHT"
                    print("💡 Action: Turn off light")
            
            elif "fan" in text or "quạt" in text:
                if "on" in text or "bật" in text:
                    last_command = "✅ Command: TURN ON FAN"
                    print("🌀 Action: Turn on fan")
                elif "off" in text or "tắt" in text:
                    last_command = "✅ Command: TURN OFF FAN"
                    print("🌀 Action: Turn off fan")
            
            elif "door" in text or "cửa" in text:
                if "open" in text or "mở" in text:
                    last_command = "✅ Command: OPEN DOOR"
                    print("🚪 Action: Open door")
                elif "close" in text or "đóng" in text:
                    last_command = "✅ Command: CLOSE DOOR"
                    print("🚪 Action: Close door")
            
            else:
                last_command = f"❓ Unknown command: {text}"
                print(f"❓ Unknown command: {text}")
        
        except sr.WaitTimeoutError:
            last_command = "⏱️ Timeout - No speech detected"
            print("⏱️ Timeout - No speech detected")
        except sr.UnknownValueError:
            last_command = "❓ Could not understand audio"
            print("❓ Could not understand audio")
        except sr.RequestError as e:
            last_command = f"❌ Error: {e}"
            print(f"❌ Speech service error: {e}")
        
        voice_active = False

video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

frame_skip = 3
frame_count = 0
last_recognized_name = "Unknown"

while True:
    # Capture frame
    ret, frame = video_capture.read()
    frame_count += 1
    
    # Skip frames for better performance
    if frame_count % frame_skip == 0:
        # Resize frame for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Find faces in frame (using faster "hog" model)
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        # Check each face
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            name = "Unknown"
            confidence = 0
            
            if known_face_encodings:
                # Compare faces
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                
                if matches[best_match_index]:
                    name = known_face_names[best_match_index]
                    confidence = (1 - face_distances[best_match_index]) * 100
                    last_recognized_name = f"{name} ({confidence:.1f}%)"
            
            # Scale back coordinates to original frame
            top *= 2
            right *= 2
            bottom *= 2
            left *= 2
            
            # Draw rectangle and name
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            
            label = f"{name}" if name != "Unknown" else "Unknown"
            cv2.putText(frame, label, (left + 6, bottom - 6), 
                       cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
    
    # Display voice command status
    cv2.putText(frame, f"Face: {last_recognized_name}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, last_command, (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    if voice_active:
        cv2.putText(frame, "🎤 LISTENING...", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    # Display frame
    cv2.imshow('YoloHome - Face + Voice Recognition', frame)
    
    # Handle keypresses
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        break
    elif key == ord('v') and not voice_active:
        # Start voice recognition in background thread
        voice_active = True
        voice_thread = threading.Thread(target=listen_for_voice)
        voice_thread.daemon = True
        voice_thread.start()

video_capture.release()
cv2.destroyAllWindows()

print("\n✅ YoloHome closed. Goodbye!")
