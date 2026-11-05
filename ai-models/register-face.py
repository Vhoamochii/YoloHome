import cv2
import face_recognition
import pickle
import os
import time

print("=== Face Registration ===")
name = input("Enter your name: ")

# Lower camera resolution for better performance
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print(f"\nHi {name}! Position your face in the camera.")
print("Press SPACE to capture your face")
print("Press 'q' to quit")

face_captured = False
frame_skip = 3
frame_count = 0

while True:
    ret, frame = video_capture.read()
    frame_count += 1
    
    if frame_count % frame_skip != 0:
        cv2.imshow('Registration - Press SPACE to capture', frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' ') or key == ord('q'):
            frame_count = 0  # Reset to process immediately
        continue
    
    # Resize frame for faster processing (0.5x scale)
    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    # Detect faces on small frame
    face_locations = face_recognition.face_locations(rgb_frame, model="hog")  # "hog" is faster than "cnn"
    
    # Scale back face locations to original frame size
    face_locations = [(top*2, right*2, bottom*2, left*2) for (top, right, bottom, left) in face_locations]

    # Draw rectangles on original frame
    for (top, right, bottom, left) in face_locations:
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(frame, "Press SPACE to capture", (left, top - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    cv2.imshow('Registration - Press SPACE to capture', frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord(' '):
        if len(face_locations) == 0:
            print("No face detected! Try again.")
        elif len(face_locations) > 1:
            print("Multiple faces detected! Make sure only you are in frame.")
        else:
            print("Encoding face... Please wait.")
            
            face_encoding = face_recognition.face_encodings(rgb_frame)[0]
            
            data_file = "faces_data.pkl"
            if os.path.exists(data_file):
                with open(data_file, "rb") as f:
                    data = pickle.load(f)
            else:
                data = {"encodings": [], "names": []}
            
            data["encodings"].append(face_encoding)
            data["names"].append(name)
            
            with open(data_file, "wb") as f:
                pickle.dump(data, f)
            
            encoding_str = ",".join(map(str, face_encoding))
            
            web_data_file = f"face_encodings/{name.replace(' ', '_')}.txt"
            os.makedirs("face_encodings", exist_ok=True)
            
            with open(web_data_file, "w") as f:
                f.write(f"{name}\n")
                f.write(encoding_str)
            
            print(f"Face registered successfully for {name}!")
            print(f"Saved to: {data_file}")
            print(f"Web data saved to: {web_data_file}")
            print(f"Total faces registered: {len(data['names'])}")
            print("To use in web backend:")
            print(f"   1. Copy {web_data_file} to backend/face_data/")
            print(f"   2. Backend will load encoding on startup")
            
            face_captured = True
            break
    
    elif key == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()

if face_captured:
    print("Registration complete!")
    print("You can now use face login on the web dashboard")
