# Cập nhật V2 — ưu tiên nhiệt độ, không cần đổi dây hoặc feed

## Cập nhật từ bản đang chạy

1. Dừng gateway bằng Ctrl+C. Sao lưu thư mục `firmware` hiện tại nếu muốn quay lại model cũ.
2. Chép nội dung `tinyml-fire` trong ZIP mới vào thư mục `tinyml-fire` của bạn. Gói không chứa `.env` hoặc `.venv`, nên giữ lại hai phần này của bạn. Không chép đè vào thư mục `firmware` ở root repository nhóm.
3. Nạp lại bản độc lập (thay COM5 nếu cổng đổi):

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e yolo_uno -t upload --upload-port COM5
.\.venv\Scripts\python.exe scripts\serial_gateway.py --port COM5 --cloud
```

4. Kiểm tra `model` mới là **7129a5137abe**, `valid=true`, `simulated=false`. Thông tin PeterNicolas và tên ba feed trong `.env` giữ như cũ.

Mô hình được tính ngay trên Yolo UNO. Gateway vẫn gửi nhiệt độ/độ ẩm khoảng 10 giây/lần và giới hạn event 30 giây giữa các lần gửi. Event nhắc lại sau khoảng 60 giây nếu trạng thái không đổi. Kết nối không ổn định hoặc bản tin USB bị bỏ qua có thể kéo dài thời gian cập nhật.

## Công thức score hiện tại

Đầu vào: `T` theo °C, `H` theo %RH, không phải số từ 0 đến 1.

```text
z = 3.36644578 * (T - 35)/10
  - 0.168322295 * (H - 50)/50
  + 1.30093718

score = 1 / (1 + exp(-z))
```

Đây là **logistic regression có ràng buộc**, được huấn luyện từ nhãn trong hai CSV gốc. Hệ số được học, không phải các trọng số chọn tay rồi gọi là ML. Ràng buộc do người thiết kế đặt: hệ số nhiệt độ dương, độ ẩm tác động âm yếu; toàn miền độ ẩm 0..100% chỉ dịch chuyển tương đương tối đa khoảng 1°C (có sai số làm tròn float32).

Ví dụ: độ ẩm tăng 10 điểm phần trăm chỉ bù khoảng 0,1°C. Khi giữ nguyên độ ẩm, nhiệt độ tăng luôn làm score tăng (ở vùng bão hòa số thực, có thể hiển thị bằng nhau). Nếu chỉ tăng nhiệt rất ít nhưng tăng độ ẩm rất nhiều, không bảo đảm score tăng.

| T | H | Score model mới xấp xỉ |
|---|---|---|
| 33,740°C | 51,034% | 0,7054 |
| 34,486°C | 63,831% | 0,7467 |
| 36°C | 50% | 0,8372 |
| 38°C | 50% | 0,9098 |
| 40°C | 50% | 0,9519 |

Score không được hiệu chuẩn thành xác suất cháy. Không diễn giải 0,9 là 90% khả năng có cháy. Hai CSV tham chiếu có nhãn nguy cơ ở cả nhiệt độ thấp nên thay đổi ưu tiên nhiệt độ có thể bỏ sót các nhãn đó; báo cáo ghi rõ 5/26 mẫu lớp 1 chưa được nhận diện ở ngưỡng 0,9 ngay trên dữ liệu fit. Không có tuyên bố độ chính xác trên dữ liệu thực độc lập.

## Chỗ chỉnh ngưỡng cảnh báo

Mở **firmware/include/alarm_config.h**:

```cpp
constexpr float ml_on_score = 0.90f;      // score >= mức này: đếm mẫu bật
constexpr float ml_off_score = 0.80f;     // score <= mức này: đếm mẫu tắt
constexpr unsigned consecutive_samples = 3;
constexpr float heat_on_c = 45.0f;        // luật nhiệt độc lập, không phải score ML
constexpr float heat_off_c = 43.0f;
```

Bản V2 chủ động đổi mặc định ML từ bật/tắt 0,8/0,5 sang **0,9/0,8** cho model mới. Chỉ bật khi đủ 3 mẫu liên tiếp >= ngưỡng bật. Chỉ tắt khi đủ 3 mẫu liên tiếp <= ngưỡng tắt. Mẫu nằm giữa hai ngưỡng giữ trạng thái trước đó và ngắt chuỗi đếm. Lỗi cảm biến không tự xóa cảnh báo đã có.

Ví dụ nếu muốn nhạy hơn, có thể dùng bật 0,85 và tắt 0,75; đây là lựa chọn ngưỡng cho demo, cần kiểm tra lại báo giả/bỏ sót. Luôn giữ ngưỡng tắt thấp hơn ngưỡng bật. Sau mỗi lần đổi phải build/nạp lại bằng lệnh upload ở trên. Thay `.env` không thay ngưỡng ML trên mạch.

Với mặc định 0,9 và H=50%, điểm đạt ngưỡng khoảng **37,66°C**. Đây là điểm cắt toán học của model thử nghiệm, không là ngưỡng cháy được kiểm định. Cần thêm đủ 3 mẫu, khoảng cách mẫu khoảng 2 giây. Cảnh báo Adafruit có thể đến muộn hơn vì lịch gửi event.

Theo dõi `ml_alarm` và `heat_alarm` riêng. Event `TINYML:ALERT:<score>` chỉ cho biết trạng thái tổng hợp, chưa phân biệt nguồn cảnh báo. Không dùng nhiệt độ chạm 45°C làm bằng chứng ML đã phát hiện được.

## Huấn luyện lại bằng dữ liệu của bạn

`collect_data.py` giữ cách dùng như V1. Dừng gateway trước khi thu và dùng session id riêng cho từng lần thí nghiệm độc lập. Dữ liệu thật cần header `temperature,humidity,label,session_id` (có thể có thêm cột thời gian). Nhãn do người làm thí nghiệm quyết định trước, không lấy score model làm nhãn. Nhãn 1 trong thí nghiệm làm ấm không đồng nghĩa có cháy thật.

```powershell
py -3.10 -m venv .venv-train
.\.venv-train\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv-train\Scripts\python.exe scripts\train_model.py --csv data\labeled\readings.csv --out models\retrained
```

Trainer mới yêu cầu ít nhất 6 session và tách test theo session với cả hai lớp; nên thu nhiều hơn ở nhiều điều kiện. Không còn cần TensorFlow để train model V2. Ràng buộc ưu tiên nhiệt độ vẫn được áp dụng. Đánh giá `training_report.json`, đặc biệt các ô bỏ sót và báo giả ở ngưỡng đang dùng.

Khi chấp nhận model mới:

```powershell
Copy-Item models\retrained\temperature_model.h firmware\include\temperature_model.h
```

Sau đó nạp lại. Công thức vẫn cùng dạng nhưng hệ số/ID sẽ đổi, đọc `models/retrained/model.json`; không dùng hệ số số học của model đi kèm để mô tả model bạn train mới.

Để tái tạo đúng model V2 đi kèm từ hai CSV tham chiếu:

```powershell
.\.venv-train\Scripts\python.exe scripts\train_temperature_model.py --install
```

`model_weights.h`, `.h5`, `.tflite` và `scripts/export_model.py` là tài liệu/model V1, không được dùng bởi firmware V2. `--install` của bộ xuất H5 đã bị chặn để tránh nhầm model. Kết quả kiểm tra và hướng dẫn V1 ở `docs/legacy`, không dùng làm kết quả của V2.

## Kiểm tra đã thực hiện cho V2

- C++ trên máy tính: tăng nhiệt độ, ảnh hưởng độ ẩm, trạng thái bật/tắt qua 3 mẫu, lỗi cảm biến và luật nhiệt độc lập.
- Đối chiếu 12.221 cặp đầu vào với công thức, sai số lớn nhất dưới 1e-6.
- 6 kiểm tra protocol/gateway cũ vẫn qua; định dạng JSON/API không đổi. Score xuất 8 chữ số có nghĩa để không mất các giá trị nhỏ do định dạng thập phân cố định.
- Phiên V2 này chưa biên dịch lại bằng toolchain ESP32 và chưa nạp thử lên mạch thật. File `docs/temperature_verification.json` ghi rõ phạm vi kiểm tra. Lệnh PlatformIO trên máy bạn sẽ biên dịch trước khi nạp.

Phần đọc DHT20, USB, cloud và firmware/backend gốc của nhóm không bị sửa bởi thay đổi này. Bản tích hợp dùng chung `fire_engine.h` nên cũng dùng model/ngưỡng V2 sau khi bạn build/nạp lại bằng env tích hợp; không tự cập nhật trên mạch đang chạy.
