# Hướng dẫn chạy TinyML trên Yolo UNO

## 1. Chọn cách chạy

| Cách | Khi nào dùng | Nơi chạy TinyML | Đường dữ liệu lên backend |
|---|---|---|---|
| A — độc lập | Kiểm tra cảm biến và model trước | Trên mạch | USB → Python gateway → Adafruit IO → backend |
| B — tích hợp | Dùng cùng chức năng quạt, đèn, LCD của nhóm | Trên mạch, task riêng | MQTT sẵn có của firmware → Adafruit IO → backend |

**Nạp firmware sẽ thay chương trình đang chạy trên mạch.** Hai chương trình không chạy đồng thời trên cùng một mạch. Muốn giữ chức năng nhóm và thêm TinyML, chọn B. Có thể thử A trước, sau đó nạp B. Cả hai cách đều giữ nguyên các file nguồn của nhóm.

Mọi lệnh dưới đây dùng **PowerShell Windows**, Python 3.10.11 đã có sẵn của bạn. Thay `COM5` bằng cổng thực tế. Không mở hai chương trình đọc cùng một COM.

## 2. Cắm phần cứng

1. Ngắt nguồn khi nối dây.
2. Cắm module **DHT20** vào cổng **I2C** của Yolo UNO, dùng dây Grove đúng chiều. Không cắm vào cổng Digital/Analog.
3. Theo cấu hình nhóm: SDA = **GPIO11**, SCL = **GPIO12**; địa chỉ cảm biến **0x38**. Mã gọi `Wire.begin(11, 12)` rõ ràng vì board definition hiện có dùng tên chân mặc định của biến thể khác.
4. Cắm USB-C có truyền dữ liệu vào máy tính. Dây chỉ sạc có thể cấp nguồn nhưng không hiện COM.
5. Bản A không cần LCD, quạt hay còi. Cảnh báo hiện bằng LED D13 GPIO48 và USB. Nếu muốn còi ngoài, kiểm tra loại module/chân trống trước khi bật `FIRE_BUZZER_PIN` trong `firmware/include/fire_config.h`; không nối tải công suất trực tiếp vào GPIO.

Hướng dẫn hãng dùng DHT20 qua I2C: <https://docs.ohstem.vn/en/latest/yolo_uno/smart_home_uno/dht20.html>.

## 3. Chuẩn bị một lần

Giải nén ZIP. Ví dụ thư mục module là `D:\DADN\TinyML_YoloUNO\tinyml-fire`.

```powershell
cd D:\DADN\TinyML_YoloUNO\tinyml-fire
py -3.10 --version
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install platformio==6.1.18
.\.venv\Scripts\python.exe scripts\serial_gateway.py --list-ports
```

Nếu `py` không tồn tại, dùng đường dẫn đầy đủ đến `python.exe` 3.10.11 để tạo venv. Không cần activate; các lệnh đã dùng Python trong venv. Lần build đầu cần Internet để tải ESP32 toolchain và thư viện.

## 4. Cách A — nạp và chạy độc lập

### 4.1 Biên dịch và nạp

Đứng ở thư mục `tinyml-fire`:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e yolo_uno
.\.venv\Scripts\python.exe -m platformio run -d firmware -e yolo_uno -t upload --upload-port COM5
```

Nếu không kết nối được: đóng Serial Monitor/gateway, giữ **BOOT**, bấm rồi nhả **RESET**, nhả BOOT, tìm lại COM và nạp lại. Sau khi nạp, bấm RESET nếu chương trình chưa chạy. Cổng native USB có thể đổi tên sau khi chuyển từ bootloader sang chương trình.

### 4.2 Xem dữ liệu thật

```powershell
.\.venv\Scripts\python.exe scripts\serial_gateway.py --port COM5
```

Gateway chỉ đọc và ghi log CSV ở `data/captures/telemetry.csv`; **model chạy trên mạch**, không chạy trong gateway. Đầu chương trình có log quét I2C. Có thể xem riêng bằng PlatformIO monitor, sau đó đóng monitor trước khi chạy gateway:

```powershell
.\.venv\Scripts\python.exe -m platformio device monitor -d firmware -p COM5 -b 115200
```

Tiêu chí đạt cho bước này:

- Có địa chỉ I2C `0x38` lúc khởi động khi cảm biến đã cắm.
- Có frame JSON khoảng mỗi 2 giây với `type=tinyml_fire`, `v=1`.
- `valid=true`, `simulated=false`, `model=18a0faee2146` với model gốc.
- Nhiệt độ và độ ẩm thay đổi theo môi trường; `score` nằm trong [0,1].
- Rút DHT20: `valid=false`, `state=SENSOR_ERROR`, trường số là `null`; không tạo số liệu giả.
- Cắm lại: chương trình tự dò lại DHT20, không cần khởi động lại gateway.

`OK` chỉ là trạng thái không bật cảnh báo trong demo, không bảo đảm môi trường không có cháy. `inference_us` là thời gian tính model và cập nhật trạng thái trên mạch, không gồm thời gian đọc cảm biến/MQTT.

### 4.3 Kiểm tra cảnh báo có kiểm soát

Không đốt lửa, không khò nóng sát cảm biến. Dùng môi trường kiểm thử phù hợp với giới hạn của cảm biến. Với bản thật, ngưỡng nhiệt 45°C bật cảnh báo ngay ở lần đọc hợp lệ; ngưỡng ML còn yêu cầu 3 mẫu liên tiếp. Giữ riêng hai cờ `heat_alarm` và `ml_alarm` khi giải thích kết quả.

Để thử luồng cảnh báo mà không cần tạo nhiệt, có **build mô phỏng chủ động**:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d firmware -e yolo_uno_sim -t upload --upload-port COM5
.\.venv\Scripts\python.exe scripts\serial_gateway.py --port COM5 --log data\captures\SIM_ONLY.csv
```

Build này luân phiên bình thường → nóng → lỗi → phục hồi, ghi rõ `simulated=true`; gateway không gửi frame mô phỏng lên cloud. **Đây không phải kiểm thử cảm biến thật hoặc độ chính xác model.** Xong phải nạp lại `-e yolo_uno` để chạy DHT20 thật.

### 4.4 Gửi backend qua Adafruit IO — tùy chọn cho cách A

1. Tạo/kiểm tra đúng ba feed key trong cùng tài khoản backend: `yolohome-temperature`, `yolohome-humidity`, `yolohome-event`. Nếu nhóm đổi tên feed, đổi biến tương ứng trong `.env`.
2. Copy cấu hình và điền thông tin riêng:

```powershell
Copy-Item .env.example .env
notepad .env
```

3. Chạy:

```powershell
.\.venv\Scripts\python.exe scripts\serial_gateway.py --port COM5 --cloud
```

Cloud dùng TLS cổng 8883; gateway gửi nhiệt độ/độ ẩm tối đa mỗi 10 giây và event đã giới hạn tần suất. USB rớt sẽ thử mở lại cổng; mất mạng không ngăn suy luận trên mạch. Không có lưu bù cloud cho cách A; CSV vẫn giữ các frame gateway đã nhận.

**Chỉ bật một nguồn publish cho cùng cảm biến/feed**: đừng chạy thêm board/gateway khác gửi cùng feed trong buổi test. Không dùng `--cloud` khi chạy firmware cách B. Tài khoản Adafruit có quota dùng chung với các phần khác của nhóm.

## 5. Cách B — thêm vào repository và build cùng firmware nhóm

### 5.1 Chép module không ghi đè

Ví dụ repo nhóm ở `D:\DADN\YoloHome`. Đứng tại module vừa giải nén và chạy:

```powershell
.\.venv\Scripts\python.exe scripts\install_addon.py --repo D:\DADN\YoloHome
```

Lệnh chỉ tạo `D:\DADN\YoloHome\tinyml-fire`. Nếu đã có thư mục đó, lệnh dừng để tránh ghi đè. Không chép file `main.cpp`, `README.md`, `requirements.txt` của module đè lên file cùng tên của nhóm.

Build tích hợp dành cho đúng cấu trúc trong ZIP đã gửi: `firmware/src/main.cpp`, `sensor_latest()`, `cloud_post_event()`. Nếu nhóm thay các API này sau đó thì cần đối chiếu lại trước khi merge.

### 5.2 Cấu hình Wi-Fi có sẵn của nhóm

Firmware gốc lấy Wi-Fi và Adafruit từ `firmware/include/secrets.h`. Giữ cấu hình cá nhân đang dùng; kiểm tra cùng tài khoản/feed backend. Module không sửa hoặc cung cấp lại thông tin đăng nhập của nhóm. Nếu repo sạch chưa có file này, tạo file cục bộ theo mẫu biến `WIFI_SSID`, `WIFI_PASSWORD`, `AIO_USERNAME`, `AIO_KEY` mà firmware nhóm yêu cầu; không đưa khóa lên Git.

### 5.3 Build/nạp tích hợp

Vẫn dùng Python ở module giải nén bên ngoài repo:

```powershell
.\.venv\Scripts\python.exe -m platformio run -d D:\DADN\YoloHome\tinyml-fire\integration -e yolo_uno_tinyml
.\.venv\Scripts\python.exe -m platformio run -d D:\DADN\YoloHome\tinyml-fire\integration -e yolo_uno_tinyml -t upload --upload-port COM5
```

Build lấy các source của nhóm trực tiếp từ `firmware/src`, thay entry point ở **cấu hình build của module**, rồi khởi tạo thêm task suy luận. Các file gốc không bị sửa. DHT20 chỉ được task cảm biến của nhóm đọc; TinyML dùng bản chụp có mutex qua `sensor_latest()`.

Xem JSON bằng gateway **không có `--cloud`**:

```powershell
.\.venv\Scripts\python.exe scripts\serial_gateway.py --port COM5 --log data\captures\integrated.csv
```

Đầu ra firmware nhóm vẫn có các dòng `[status]`, `[ctl]`; gateway bỏ qua các dòng này và chỉ đọc JSON TinyML. Nhiệt độ/độ ẩm đi lên feed theo lịch firmware nhóm. Event `TINYML:ALERT:<score>` / `TINYML:OK:<score>` / `TINYML:SENSOR_ERROR:-1.000` dùng event feed cũ, tối đa 44 ký tự, không thêm feed.

**Hành vi điều khiển:** task TinyML mới chỉ xuất cảnh báo. Quạt, LED, relay và safety override vẫn do bộ điều khiển gốc quyết định. Vì vậy score ML cao có thể xuất event mà không đổi quạt; nhiệt độ cao vẫn kích hoạt luật quá nhiệt của firmware nhóm. Muốn ML giành quyền điều khiển cần một thay đổi riêng được nhóm thống nhất.

### 5.4 Kiểm tra backend, giữ nguyên file nhóm

Backend hiện có `adafruit_mqtt.py` dùng API paho-mqtt 2.x, nhưng `backend/requirements.txt` đang ghim 1.6.1. Nếu môi trường backend chưa được nhóm sửa, trong **venv backend riêng** cài bản phù hợp mà không sửa file nguồn:

```powershell
# Chạy trong backend, dùng đúng Python venv backend của nhóm.
python -m pip install paho-mqtt==2.1.0
```

Theo `database.py`, `DATABASE_URL` được đọc trước khi MQTT gọi `load_dotenv()`. Nếu chỉ đặt database URL trong `.env`, nên đặt biến môi trường PowerShell rõ ràng trước khi chạy backend. Ví dụ sau phải thay thông tin bằng database đã tạo của nhóm:

```powershell
$env:DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/yolohome"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Chạy backend theo hướng dẫn nhóm nếu đã có môi trường hoạt động. Không cài requirements TinyML vào venv backend. Nếu cài mới toàn bộ backend gặp gói `opencv-python==4.8.1`/face-recognition, đó là phụ thuộc trong ZIP nhóm, không phải điều kiện để TinyML trên mạch chạy; đối chiếu với người phụ trách backend trước khi sửa dependency chung.

Kiểm tra theo thứ tự:

1. Adafruit feed nhiệt độ/độ ẩm có giá trị thật mới.
2. Backend log có kết nối MQTT thành công; event TinyML xuất hiện trong log khi được gửi.
3. Trong database có dòng `lich_su_cam_bien` mới. Mỗi feed nhiệt độ/độ ẩm được lưu thành dòng riêng trong bản backend này.
4. Không dùng riêng `/api/sensors/current` để xác nhận: route đó hiện trả số mẫu cố định; `/history` cũng còn TODO. UI chưa được nối dữ liệu thật ở hai API này. Module không sửa các route đó theo yêu cầu giữ nguyên mã nhóm.
5. Event TinyML được parser và event handler của backend nhận, nhưng backend hiện chưa tự lưu event thành bảng lịch sử/cảnh báo UI. Đừng coi việc log có event là đã hoàn thành phần UI/notification.

## 6. Đưa lên GitHub

Đứng ở repository nhóm:

```powershell
git status --short
git switch -c feat/tinyml-fire
git add -- tinyml-fire
git diff --cached --name-only
git diff --cached --stat
```

Chỉ thấy đường dẫn bắt đầu `tinyml-fire/`. Không stage `.env`, `secrets.h`, `.pio`, `.venv` hoặc log thu từ môi trường cá nhân. Sau khi kiểm tra, commit và mở PR theo quy trình nhóm.

Module dùng thư mục mới nên không sửa cùng file với nhóm ở snapshot hiện tại. Không thể bảo đảm mọi merge trong tương lai đều không conflict nếu có người khác cũng sửa `tinyml-fire/` hoặc đổi API firmware.

## 7. Thu thập và train lại — sau khi đã chạy phần cứng

Model gốc đủ để kiểm tra luồng TinyML; nó chưa đủ dữ liệu để kết luận phát hiện cháy tốt. Không tự gán nhãn 1 vì score model cao. Nhãn phải do điều kiện thí nghiệm được ghi nhận độc lập quyết định. Nhãn 1 trong thí nghiệm làm ấm có nghĩa tình huống nguy cơ theo quy ước nhóm, không chứng minh đã có cháy thật.

Đóng gateway/Serial Monitor. Mỗi lần thí nghiệm độc lập dùng session id mới:

```powershell
.\.venv\Scripts\python.exe scripts\collect_data.py --port COM5 --label 0 --session room_day1 --seconds 120
# Chỉ dùng label 1 cho điều kiện thí nghiệm đã được nhóm xác định và kiểm soát.
.\.venv\Scripts\python.exe scripts\collect_data.py --port COM5 --label 1 --session controlled_warm_day1 --seconds 120
```

Công cụ từ chối ghi mẫu mô phỏng và mẫu cảm biến lỗi. Cần ít nhất 6 session độc lập, mỗi lớp có dữ liệu ở ít nhất 3 session; nên thu nhiều hơn, nhiều ngày/điều kiện để đánh giá hữu ích. Không tách một lần ghi liên tục thành nhiều session giả để vượt kiểm tra.

Tạo môi trường huấn luyện riêng, Python 3.10.11:

```powershell
py -3.10 -m venv .venv-train
.\.venv-train\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv-train\Scripts\python.exe scripts\train_model.py --csv data\labeled\readings.csv --out models\retrained
```

Script tách tập theo session, chuẩn hóa bằng tập train, ghi báo cáo validation/test. Không dùng hai CSV gốc thiếu session để tuyên bố đánh giá theo session. Đọc `models/retrained/training_report.json`, chú ý bỏ sót và báo giả ở cả ngưỡng 0,5 và 0,8. Chưa có số liệu train mới nào được tạo sẵn trong gói này.

Khi đã chấp nhận model mới, sao lưu header hiện tại rồi copy header mới và nạp lại firmware:

```powershell
Copy-Item firmware\include\model_weights.h firmware\include\model_weights.backup.txt
Copy-Item models\retrained\model_weights.h firmware\include\model_weights.h
```

Header mang theo mean/scale, không tự chuẩn hóa thêm trong firmware. Không chạy lại `export_model.py --install` sau bước này nếu muốn giữ model mới; lệnh đó mặc định xuất lại model H5 gốc. `verify_model.py` dành để kiểm tra model tham chiếu ban đầu; không dùng báo cáo của nó làm chứng cứ cho model mới.

## 8. Xử lý lỗi nhanh

| Dấu hiệu | Kiểm tra |
|---|---|
| Không có COM | Cáp dữ liệu, cổng USB, BOOT/RESET, Device Manager |
| Access denied / port busy | Đóng chương trình khác đang giữ COM |
| Không thấy 0x38 / SENSOR_ERROR | DHT20, đúng cổng I2C, dây, GPIO11/12; DHT11/DHT22 không thay trực tiếp |
| Bị kẹt boot / không có USB log | Nạp env yolo_uno, USB CDC đã bật; bấm RESET, tìm lại COM |
| JSON có simulated=true | Nạp lại env yolo_uno thật |
| MQTT không vào | Cùng username/key/feed, Wi-Fi 2.4GHz cho cách B, Internet, quota; TLS không bị chặn |
| API/UI vẫn 28.5°C/65% | Route current trong ZIP nhóm còn trả dữ liệu mẫu; kiểm tra feed/DB |
| Backend lỗi CallbackAPIVersion | Backend cần paho-mqtt 2.x, không dùng 1.6.1 |
| Build tích hợp thiếu main.cpp/API | Module chưa nằm đúng root repo, hoặc nguồn nhóm đã thay đổi |

## 9. Ghi nhận buổi test thật

Lưu CSV và ghi: board/cảm biến, ngày giờ, cổng COM, model id, env đã nạp, có/không Internet, số mẫu hợp lệ/lỗi, hành vi khi ngắt/cắm lại cảm biến. Chưa điền sẵn kết quả phần cứng trong gói. Báo cáo kiểm thử tại [docs/KIEM_THU.md](docs/KIEM_THU.md) phân biệt rõ việc đã kiểm tra và việc còn cần bạn chạy trên mạch.
