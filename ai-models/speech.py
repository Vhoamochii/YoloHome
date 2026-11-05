import speech_recognition as sr

r = sr.Recognizer()

with sr.Microphone() as source:
    print("Mời bạn nói tiếng Việt...")
    r.adjust_for_ambient_noise(source, duration=1)
    audio_text = r.listen(source)

    try:
        text = r.recognize_google(audio_text, language="vi-VN")
        print("Văn bản:", text)
    except sr.UnknownValueError:
        print("Không nhận diện được giọng nói.")
    except sr.RequestError:
        print("Không thể kết nối dịch vụ nhận diện giọng nói.")