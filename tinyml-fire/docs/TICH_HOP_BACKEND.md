# Hợp đồng tích hợp — snapshot YoloHome-main.zip được cung cấp

## Quyền sở hữu và dữ liệu

| Phần | Module làm gì | File nhóm có bị sửa? |
|---|---|---|
| DHT20, cách A | Tự đọc I2C GPIO11/12, suy luận trên chip | Không |
| DHT20, cách B | Đọc `sensor_latest(SensorReading&)`, kiểm tra độ mới ≤6 giây | Không |
| MQTT, cách A | Python gateway gửi 3 feed hiện có, TLS 8883 | Không |
| MQTT, cách B | `cloud_post_event("TINYML", ...)` qua hàng đợi firmware nhóm | Không |
| Control, cách B | Giữ nguyên Controller của nhóm; task mới không viết actuator | Không |
| Backend | Dùng parser event có sẵn; không thêm route, bảng hay handler | Không |

Cách B không đọc DHT20 lần hai, không gọi Wire.begin lần hai, không tạo MQTT client thứ hai. Event có thể chậm do hàng đợi/quota và không được xem là đường báo động thời gian thực.

## Bản tin

- USB: một JSON mỗi mẫu, `type=tinyml_fire`, `v=1`, cờ `valid`, `simulated`, `ml_alarm`, `heat_alarm`, `alarm`; `score=null` khi lỗi.
- Nhiệt độ/độ ẩm: chuỗi số ở feed `yolohome-temperature` và `yolohome-humidity`.
- Event: `TINYML:ALERT:0.824`, `TINYML:OK:0.001`, `TINYML:SENSOR_ERROR:-1.000`.
- Bản tin feed ≤44 ký tự, không dấu phẩy, dấu ngoặc kép hay ký tự điều khiển. USB JSON không bị giới hạn 44 vì không đưa nguyên JSON lên feed.
- Khi lỗi sau cảnh báo, JSON vẫn giữ cờ alarm; state SENSOR_ERROR báo tình trạng dữ liệu. Event lỗi dùng score -1, không coi là suy luận âm.
- Cách A gửi giá trị mới nhất định kỳ, không gửi bù mẫu offline. Cách B dùng cơ chế telemetry/backlog vốn có của nhóm; event TinyML không có lịch sử bền riêng.

## Những chỗ chưa hoàn tất trong backend gốc

1. `backend/requirements.txt` ghim paho-mqtt 1.6.1, trái với import `CallbackAPIVersion` và callback VERSION2 trong `adafruit_mqtt.py`. Gateway module dùng venv riêng. Backend cần môi trường paho 2.x để chạy mã đang có.
2. `routes/sensors.py` còn TODO, current trả 28.5/65.0, history trả mảng trống. Điều này không phản ánh việc MQTT có nhận dữ liệu thật hay chưa.
3. Parser event chấp nhận TYPE tự do; `TINYML` được nhận và phát qua `_emit("event", ...)`. Mặc định chưa có route/lưu bảng/phát notification cho TinyML.
4. Database URL phải có trước khi import `database.py`; đặt qua biến môi trường nếu quy trình khởi động nhóm chưa load `.env` trước.

Đây là ghi nhận để kiểm thử đúng phạm vi; ZIP module không vá các file trên theo yêu cầu người dùng.

## Chống ghi đè và giới hạn merge

Đích duy nhất khi cài là `<repo>/tinyml-fire/`. `install_addon.py` dừng nếu đích đã tồn tại. Cấu hình build tích hợp chỉ đọc source nhóm ở `../../firmware/src`, loại main/demo rồi thêm entry point của module. Không sao chép một phiên bản backend/firmware nhóm vào ZIP mới để tránh có hai bản nguồn trôi lệch.

Tính tương thích được đối chiếu với ZIP đã cung cấp. Nếu API `sensor_latest`, cấu trúc `SensorReading`, `cloud_post_event` hoặc layout thư mục đổi thì phải kiểm tra lại. Việc thêm thư mục mới giảm khả năng conflict, không là bảo đảm cho mọi nhánh GitHub tương lai.

## Nguồn kỹ thuật

- Nguồn người dùng: `YoloHome-main.zip`, `Model_AI_TinyML-master.zip`.
- [OhStem — Yolo UNO](https://docs.ohstem.vn/en/latest/yolo_uno/yolo_uno_khoi_lenh/gioi_thieu_yolo_uno.html).
- [OhStem — DHT20 qua I2C](https://docs.ohstem.vn/en/latest/yolo_uno/smart_home_uno/dht20.html).
- [RobTillaart/DHT20 — Wire.begin trước begin, read/getTemperature/getHumidity](https://github.com/RobTillaart/DHT20).
- [PlatformIO — src_dir và build_src_filter](https://docs.platformio.org/en/latest/projectconf/sections/platformio/options/directory/src_dir.html).

Thông số dung lượng flash trên các trang OhStem có chỗ không thống nhất. Gói dùng đúng board definition 8MB từ firmware nhóm, không suy đoán thêm về revision phần cứng. Nếu mạch thật báo dung lượng khác, cần xác nhận revision trước khi thay board config.
