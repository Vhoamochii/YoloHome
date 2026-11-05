# TinyML Fire — Yolo UNO / DADN

Module đọc **DHT20 thật**, chạy mạng nơ-ron **2 → 8 ReLU → 1 sigmoid trực tiếp trên ESP32-S3**, và xuất kết quả qua USB. Suy luận không cần máy tính hay Internet sau khi đã nạp firmware và cấp nguồn.

Được phát triển từ `Model_AI_TinyML-master.zip`. Giữ nguyên model `.h5`, `.tflite`, `.h` và hai CSV gốc; bổ sung firmware, bộ xuất trọng số, gateway USB và công cụ thu thập/huấn luyện lại. Không sửa mã trong `YoloHome-main.zip`.

## Thành phần chính

| Thư mục | Nội dung |
|---|---|
| `firmware/` | Firmware độc lập cho Yolo UNO, PlatformIO, DHT20 I2C GPIO11/12 |
| `integration/` | Build cùng firmware YoloHome, dùng cảm biến và MQTT có sẵn |
| `models/` | Model gốc và trọng số C++ xuất từ model đã train |
| `scripts/` | USB gateway, thu thập dữ liệu thật, xuất model, train lại, cài module |
| `data/reference/` | Hai CSV gốc, chưa chứng minh đại diện cho môi trường thật |
| `tests/`, `docs/` | Kiểm tra phần mềm, báo cáo và hợp đồng tích hợp |

## TinyML nằm ở đâu?

`firmware/include/model_weights.h` chứa **33 tham số đã học** từ `TinyML.h5`. `fire_engine.h::infer()` thực hiện hai lớp Dense, ReLU và sigmoid bằng C++ float32. Đây là suy luận model đã huấn luyện trên MCU; bản chạy không dùng TensorFlow Lite Micro interpreter. File TFLite được giữ để đối chiếu. Tiền xử lý của model gốc là đầu vào thô theo thứ tự **[°C, %RH]**, không chia 100.

Ngưỡng ML: bật sau 3 mẫu liên tiếp có score ≥ 0,8; tắt sau 3 mẫu ≤ 0,5. Cảnh báo nhiệt độ ≥ 45°C, nhả ≤ 43°C là **luật độc lập**, không phải kết quả ML. Lỗi cảm biến được báo `SENSOR_ERROR` và không xóa cảnh báo đã có.

## Chạy và tích hợp

- Phần cứng mặc định: Yolo UNO ESP32-S3 + DHT20 cổng I2C + cáp USB có truyền dữ liệu.
- Công cụ: VS Code + PlatformIO hoặc Python **3.10.11** + PlatformIO Core.
- Không cần cài TensorFlow để nạp firmware hay chạy gateway. Chỉ cài khi muốn train lại.
- Bản độc lập xuất USB, bật LED D13 khi cảnh báo; còi ngoài mặc định tắt.
- Bản tích hợp dùng event feed hiện có, giữ nguyên bộ điều khiển quạt/đèn của nhóm; TinyML bổ sung cảnh báo USB/MQTT, không giành quyền điều khiển thiết bị.

Hướng dẫn đầy đủ: **[HUONG_DAN_CHAY_THUC_TE.md](HUONG_DAN_CHAY_THUC_TE.md)**.

Giao tiếp backend và giới hạn: [docs/TICH_HOP_BACKEND.md](docs/TICH_HOP_BACKEND.md).

Kết quả kiểm tra: [docs/KIEM_THU.md](docs/KIEM_THU.md).

## Giới hạn

Model/dữ liệu gốc nhỏ, có mẫu trùng và có trường hợp bỏ sót. Kết quả score chưa được hiệu chuẩn thành xác suất cháy. Gói này dùng cho học tập và kiểm thử DADN; chưa phải hệ thống báo cháy được kiểm định. Chạy được luồng cảm biến → suy luận không đồng nghĩa model phát hiện cháy đáng tin cậy trong mọi môi trường. Thông tin đã kiểm tra trên máy tính và việc chưa kiểm thử phần cứng được ghi riêng trong báo cáo.
