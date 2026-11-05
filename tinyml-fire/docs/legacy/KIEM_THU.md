# Kiểm thử phần mềm và giới hạn xác nhận

Kết quả gắn với mã nguồn trong ZIP này và hai ZIP đầu vào, không phải kết quả đo trên mạch thật.

## Đã kiểm tra

| Hạng mục | Kết quả |
|---|---|
| Xuất trọng số từ H5 | 33 tham số đúng model 2→8→1; không tự sinh trọng số |
| TinyML.h và TinyML.tflite | Trùng từng byte |
| C++ với model tham chiếu | 525 cặp đầu vào, nhiệt độ −40..80°C, độ ẩm 0..100%; sai số tuyệt đối lớn nhất ≈8,95×10⁻⁷ |
| TFLite interpreter với phép tính tham chiếu | Cùng 525 cặp, sai số lớn nhất ≈8,65×10⁻⁷ |
| Engine cảnh báo | ML cần 3 mẫu; ngưỡng nhiệt độc lập; lỗi không xóa cảnh báo; phục hồi và hysteresis; NaN/vô cực/giá trị ngoài miền |
| Python protocol | 6 bài kiểm tra unittest, gồm frame lỗi, payload, cấm publish mô phỏng và chống ghi đè đích cài module |
| Gateway USB | Thử qua pseudo-terminal trên máy tính; nhận 3 frame mô phỏng, ghi CSV đúng, bỏ dòng log/debug và JSON hỏng |
| Parser backend gốc | Chấp nhận 3 dạng event TINYML; không khởi chạy broker/DB cho kiểm tra này |
| Bảo toàn nguồn nhóm | So sánh SHA-256 toàn bộ 83 file trong YoloHome ZIP với bản tích hợp: không đổi file nào |
| Python scripts | Qua kiểm tra cú pháp Python |
| Build ESP32-S3 độc lập | PlatformIO `yolo_uno`: SUCCESS; RAM 19.068 byte, flash ứng dụng 281.973 byte |
| Build mô phỏng trên ESP32-S3 | PlatformIO `yolo_uno_sim`: SUCCESS; chưa nạp lên thiết bị |
| Build tích hợp cùng firmware nhóm | PlatformIO `yolo_uno_tinyml`: SUCCESS; RAM 61.228 byte, flash ứng dụng 916.301 byte |

Chi tiết build ở `build_verification.json`. Khi kiểm tra tích hợp, môi trường thử chỉ cài các thư viện cần biên dịch và bỏ bước tự tải các phụ thuộc demo cho board khác của bộ Adafruit; compiler/linker ESP32-S3 và source/cấu hình build vẫn được dùng thật. Lệnh build thông thường trong hướng dẫn có thể tải thêm các phụ thuộc này ở lần đầu. Số RAM/flash ở trên là số linker cho toàn chương trình độc lập, không phải số đo riêng của model hay mức sử dụng heap khi chạy.

## Đánh giá lại các file dữ liệu tham chiếu

Đây chỉ là kiểm tra các file được cung cấp, **không phải test độc lập** vì nguồn train của model cũ chưa được chứng minh.

| File | Số mẫu | Mẫu trùng hoàn toàn | Phân loại đúng ở ngưỡng 0,5 | Phân loại đúng ở ngưỡng 0,8 |
|---|---:|---:|---:|---:|
| sensor_data.csv | 59 | 28 | 59 | 59 |
| sensor_data_test.csv | 49 | 0 | 43 | 41 |

Các tỷ lệ này là **phân loại từng mẫu bằng score**, không gồm bộ lọc 3 mẫu/hysteresis hay luật nhiệt của firmware. Không dùng để tuyên bố độ chính xác cảnh báo theo thời gian hoặc hiệu quả phát hiện cháy thật.

Ví dụ: model gốc ở 60°C/70%RH cho score xấp xỉ 1,28×10⁻⁸, tức model không cảnh báo dù nhiệt độ cao. Luật nhiệt độc lập giúp cảnh báo demo trong trường hợp này nhưng không sửa chất lượng model. Vì vậy giữ rõ `ml_alarm` và `heat_alarm` trong log.

## Chưa kiểm tra và cần chạy với thiết bị/tài khoản thật

- Chưa cắm/nạp vào Yolo UNO vật lý, đo từ DHT20 thật hoặc kiểm tra dây/cổng nguồn của người dùng.
- Chưa thử Wi-Fi, TLS với tài khoản Adafruit, quota thực tế, ACK, lưu PostgreSQL hay giao diện nhóm.
- Chưa đánh giá trên dữ liệu môi trường thật độc lập; chưa hiệu chuẩn score thành xác suất cháy.
- Script huấn luyện lại là công cụ tùy chọn, đã kiểm tra cú pháp; chưa chạy train TensorFlow trong phiên này và không có model huấn luyện mới được dựng sẵn.
- Chưa merge vào một nhánh GitHub trực tiếp. Đã chuẩn bị module chỉ thêm thư mục, kiểm tra không ghi đè source snapshot; nhóm vẫn cần review PR theo nhánh hiện tại.

## Tái hiện các kiểm tra

Đứng tại `tinyml-fire`, dùng venv riêng:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip install -r requirements-tools.txt
.\.venv\Scripts\python.exe scripts\verify_model.py
.\.venv\Scripts\python.exe scripts\verify_backend_contract.py --repo D:\DADN\YoloHome --original-zip D:\DADN\YoloHome-main.zip
```

Kiểm tra C++ trên môi trường có `g++`:

```bash
g++ -std=c++11 -Wall -Wextra -Werror -Ifirmware/include tests/host_engine.cpp -o /tmp/tinyml_host
/tmp/tinyml_host
python scripts/verify_model.py --cpp /tmp/tinyml_host --tflite
```

Cờ `--tflite` cần interpreter `ai-edge-litert` hoặc TensorFlow; không cần cài các gói này để nạp mạch/chạy USB. Phiên kiểm tra dùng LiteRT 1.2.0 trên Linux; TensorFlow 2.15.1 trong môi trường train Python 3.10 cũng cung cấp interpreter. Phiên bản gói kiểm tra thực tế nằm trong `verification_environment.json`.

Chi tiết máy đọc được: `model_verification.json`, `backend_verification.json`, `build_verification.json`. Hash hai ZIP đầu vào nằm trong `input_checksums.json`.
