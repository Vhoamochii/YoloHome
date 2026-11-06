# BÁO CÁO HOÀN THÀNH TÍCH HỢP HỆ THỐNG YOLOHOME
**Dự án:** YoloHome - AI IoT Smart Home System  
**Ngày hoàn thành:** 05/11/2026  
**Mục tiêu:** Liên kết toàn bộ nội dung từ Frontend, AI vào Backend, lưu trữ Database, tinh chỉnh cơ chế cảnh báo LED quá nhiệt, đồng bộ nút bấm vật lý điều khiển quạt với Frontend và hoàn thiện hệ thống Lập lịch điều khiển.

> **Cập nhật 06/11/2026.** Các nội dung sửa sau bản báo cáo này: bộ chạy lịch (`backend/scheduler.py`), nhật ký hoạt động lưu DB (`/api/activity`), lệnh `AUTO` từ xa (cần nạp lại firmware), giao diện theo ACK của mạch.
> Ngưỡng LED thực tế của firmware là **cam từ 33°C, đỏ trên 45°C**; mục "35°C" bên dưới đã lỗi thời.
> Bảo mật chưa xử lý: API chưa kiểm tra đăng nhập, đăng ký khuôn mặt bằng email, khóa token mặc định, thông tin bí mật trong lịch sử git. Vì vậy các mục "100%" dưới đây chỉ nói về chức năng.

---

## 📌 Bảng tổng hợp công việc theo từng mảng

| Mảng / Module | Hạng mục công việc đã thực hiện | Trạng thái |
| :--- | :--- | :---: |
| **1. Database & Path Sync** | Cố định đường dẫn tuyệt đối SQLite (`backend/yolohome.db`), dọn sạch dữ liệu giả mẫu (mock seed data), hỗ trợ auto-fallback PostgreSQL / SQLite | **Hoàn thành 100%** |
| **2. Auth & Accounts** | Đăng ký, đăng nhập tài khoản lưu vào bảng `nguoi_dung`, băm mật khẩu bảo mật PBKDF2-HMAC-SHA256 | **Hoàn thành 100%** |
| **3. Face Recognition** | Trích xuất embedding 128-d, lưu bảng `face_profiles`, Face Registration & Face Login chuẩn xác qua webcam | **Hoàn thành 100%** |
| **4. Activity & CSV** | Ghi nhận hoạt động thiết bị, xuất file `.csv` tương thích Microsoft Excel (BOM UTF-8) | **Hoàn thành 100%** |
| **5. Fan Control & Hardware Sync** | Đồng bộ nút bấm phần cứng ESP32 (SW1 chuyển nấc 40% -> 70% -> 100% -> 0%, SW2 hủy lockdown về AUTO) theo thời gian thực với Web UI | **Hoàn thành 100%** |
| **6. LED Warning Alert** | Đèn RGB tinh gọn chuyên biệt báo động khi nhiệt độ > 35°C (ĐỎ `FF0000`), bình thường an toàn (XANH `00FF00` hoặc TẮT) | **Hoàn thành 100%** |
| **7. Lập lịch điều khiển (Schedule)** | Xóa bỏ lỗi 404 Not Found: xây dựng trọn bộ RESTful API CRUD `/api/schedules/` liên kết bảng `lich_trinh` | **Hoàn thành 100%** |
| **8. Frontend UI & Auto-polling** | Bổ sung polling chu kỳ 2s, các nút bấm chọn nấc tốc độ quạt trực quan, badge nhận diện trạng thái Thủ công/Tự động | **Hoàn thành 100%** |

---

## 1. Mảng Cơ sở dữ liệu (Database Layer & Clean Data)

* **Tệp chỉnh sửa:** [`backend/database.py`](backend/database.py), [`backend/routes/sensors.py`](backend/routes/sensors.py)
* **Chi tiết thực hiện:**
  * **Cố định đường dẫn cơ sở dữ liệu:** Neo cứng đường dẫn tuyệt đối `os.path.abspath(os.path.join(..., "yolohome.db"))` vào thư mục `backend/`, loại bỏ triệt để hiện tượng phân mảnh 2 file sqlite khác nhau giữa thư mục gốc và thư mục backend.
  * **Dọn dẹp dữ liệu giả (Fake Seed Data):** Đã loại bỏ hàm `ensure_initial_seed()` và xóa toàn bộ các bản ghi giả lập cũ. Khi chưa cắm phần cứng ESP32 hoặc đăng ký tài khoản mới, hệ thống phản ánh đúng thực tế: *"Chưa có dữ liệu cảm biến từ ESP32"* thay vì hiển thị dữ liệu nhiệt độ ảo 7 ngày trước.
  * Tự động khởi tạo đầy đủ 6 bảng quan hệ (`nguoi_dung`, `face_profiles`, `thiet_bi`, `trang_thai_thiet_bi`, `lich_su_cam_bien`, `lich_trinh`).

---

## 2. Mảng Xác thực & Quản lý Tài khoản (User Authentication)

* **Tệp chỉnh sửa:** [`backend/routes/auth.py`](backend/routes/auth.py)
* **Chi tiết thực hiện:**
  * **Đăng ký (`POST /api/auth/register`):** Nhận `email`, `password`, `name`. Kiểm tra trùng lặp email. Mật khẩu được băm bảo mật bằng thuật toán chuẩn hóa `PBKDF2-HMAC-SHA256` kèm chuỗi muối ngẫu nhiên (salt 16-byte). Lưu trực tiếp vào bảng `nguoi_dung`.
  * **Đăng nhập (`POST /api/auth/login`):** So khớp mật khẩu băm, cấp mã JWT session token cho phiên đăng nhập.
  * **Thông tin cá nhân (`GET /api/auth/me`):** Trả về thông tin người dùng hiện tại và cờ `has_face` cho biết tài khoản đã có khuôn mặt đăng ký trong database hay chưa.

---

## 3. Mảng Nhận diện Khuôn mặt (Face Recognition AI Integration)

* **Tệp chỉnh sửa:**
  * Backend: [`backend/routes/auth.py`](backend/routes/auth.py)
  * Frontend: [`frontend/src/pages/Login.tsx`](frontend/src/pages/Login.tsx), [`frontend/src/components/ProtectedLayout.tsx`](frontend/src/components/ProtectedLayout.tsx), [`frontend/src/services/api.ts`](frontend/src/services/api.ts)
* **Chi tiết thực hiện:**
  * **Trích xuất đặc trưng AI:** Nhận ảnh Base64 từ webcam của người dùng, giải mã và sử dụng thư viện `face_recognition` (dlib) để trích xuất vector đặc trưng 128 chiều (`np.float64`).
  * **Lưu trữ khuôn mặt (`POST /api/auth/register-face`):**
    * Tuần tự hóa vector 128 chiều thành chuỗi nhị phân (1024 bytes) và lưu vào cột `face_encoding` trong bảng `face_profiles` tương ứng với `user_id`.
  * **Đăng nhập bằng Face ID (`POST /api/auth/face-login`):**
    * Tải các hồ sơ khuôn mặt từ database, tính khoảng cách sai lệch Euclidean (`face_recognition.face_distance`), so khớp với ngưỡng `MATCH_THRESHOLD = 0.55`.
  * **Giao diện Frontend:**
    * Tại trang Login: Bổ sung 2 luồng: `👤 Đăng nhập bằng khuôn mặt` và `📸 Đăng ký Face ID cho tài khoản hiện có`.
    * Tại thanh Header của ứng dụng (`ProtectedLayout`): Bổ sung nút bấm nhanh `+ Face ID` (hoặc `Face ID ✓`), mở camera đăng ký tức thì.

---

## 4. Mảng Ghi nhận Hoạt động & Xuất dữ liệu CSV

* **Tệp chỉnh sửa:**
  * Backend: [`backend/routes/sensors.py`](backend/routes/sensors.py)
  * Frontend: [`frontend/src/pages/Logs.tsx`](frontend/src/pages/Logs.tsx), [`frontend/src/pages/Devices.tsx`](frontend/src/pages/Devices.tsx)
* **Chi tiết thực hiện:**
  * **Endpoint xuất CSV (`GET /api/sensors/export-csv`):**
    * Xuất file CSV có gắn tiền tố **UTF-8 BOM (`\ufeff`)**, tương thích hoàn hảo với Microsoft Excel và Google Sheets tiếng Việt.
  * **Giao diện Nhật ký (`Logs.tsx`):** Nút **`📥 Xuất file .CSV`**, tab hiển thị lịch sử nhiệt độ/độ ẩm Adafruit và bảng nhật ký lệnh thiết bị.
  * **Giao diện Thiết bị (`Devices.tsx`):** Bổ sung bảng *Ghi nhận hoạt động gần đây* lưu vết cục bộ các hành động điều khiển công tắc, chuyển nấc tốc độ kèm nút **`Xuất log CSV`**.

---

## 5. Mảng Đồng bộ Quạt & Nút bấm Phần cứng (Hardware Button Sync)

* **Tệp chỉnh sửa:**
  * Backend: [`backend/adafruit_mqtt.py`](backend/adafruit_mqtt.py), [`backend/routes/devices.py`](backend/routes/devices.py)
  * Frontend: [`frontend/src/pages/Devices.tsx`](frontend/src/pages/Devices.tsx), [`frontend/src/services/api.ts`](frontend/src/services/api.ts)
* **Cơ chế hoạt động:**
  * **Phía ESP32 (Firmware):**
    * Nút **SW1** gọi `controller.localFanStep()`: Chuyển tuần tự tốc độ `40% ➔ 70% ➔ 100% ➔ Tắt (0%)` và kích hoạt chế độ khóa thủ công (`MANUAL_LOCKDOWN`). Đồng thời gửi feed `yolohome-fan-state` (`<pct>`) và feed `yolohome-event` (`BTN:FAN:<pct>`).
    * Nút **SW2** gọi `controller.cancelLockdown()`: Hủy khóa thủ công, đưa hệ thống về lại chế độ `AUTO_AI`. Đồng thời gửi event `BTN:AUTO` và mode `AUTO_AI`.
  * **Phía Backend (`adafruit_mqtt.py` & `routes/devices.py`):**
    * Tích hợp hàm `sync_fan_state_to_db(fan_speed)`: Khi nhận tin từ `fan_state` hoặc event `BTN:FAN:<pct>`, tự động cập nhật ngay lập tức `speed` và `status = (speed > 0)` vào bảng `trang_thai_thiet_bi` trong database.
    * Khi nhận `BTN:AUTO`, cập nhật bộ nhớ trạng thái `mode = "AUTO_AI"`.
    * API `GET /api/devices/` tự động hòa trộn trạng thái bộ nhớ thời gian thực của MQTT client, đảm bảo trả về đúng tốc độ và trạng thái chế độ (`AUTO_AI` vs `MANUAL_LOCKDOWN`).
  * **Phía Frontend (`Devices.tsx`):**
    * Thiết lập bộ hẹn giờ tự động làm mới (**Auto-polling mỗi 2 giây**) qua `setInterval`. Người dùng bấm nút SW1/SW2 trên bo mạch ESP32 thì trong vòng 2 giây giao diện web sẽ tự động cập nhật tốc độ tương ứng.
    * Bổ sung hàng nút chọn nhanh đúng với các nấc phần cứng: **`Tắt (0%)`**, **`40%`**, **`70%`**, **`100%`** kèm viền sáng hiển thị nấc đang chạy.
    * Hiển thị badge trạng thái chế độ rõ ràng: `🤖 Tự động (AI)` hoặc `🛠️ Thủ công (MANUAL)` cùng nút bấm cho phép chuyển nhanh về AUTO.

---

## 6. Mảng Đèn LED RGB Cảnh báo Quá nhiệt (Temperature Alert LED)

* **Tệp chỉnh sửa:**
  * Backend: [`backend/routes/devices.py`](backend/routes/devices.py)
  * Frontend: [`frontend/src/pages/Devices.tsx`](frontend/src/pages/Devices.tsx), [`frontend/src/pages/Dashboard.tsx`](frontend/src/pages/Dashboard.tsx), [`frontend/src/components/VoiceModal.tsx`](frontend/src/components/VoiceModal.tsx)
* **Chi tiết thực hiện:**
  * Đèn LED RGB không còn dùng làm đèn trang trí đổi bảng màu, mà chuyên trách làm **đèn tín hiệu cảnh báo an toàn**.
  * **Ngưỡng nhiệt độ:** Khi nhiệt độ phòng vượt ngưỡng `35°C`, hoặc khi kích hoạt cảnh báo thử nghiệm:
    * Đèn phát mã màu ĐỎ (`FF0000`).
    * Giao diện hiển thị banner cảnh báo đỏ nhấp nháy: *"ĐANG CẢNH BÁO ĐỎ - Nhiệt độ phòng vượt ngưỡng an toàn (> 35°C)"*.
  * Khi nhiệt độ ở mức an toàn hoặc người dùng bấm *Hủy báo động*:
    * Đèn trở về trạng thái an toàn màu Xanh (`00FF00`) hoặc tắt (`OFF`).

---

## 7. Mảng Lập lịch điều khiển (Schedule Module - 404 Fix)

* **Tệp tạo mới / chỉnh sửa:**
  * Backend: [`backend/routes/schedules.py`](backend/routes/schedules.py), [`backend/main.py`](backend/main.py)
  * Frontend: [`frontend/src/pages/Schedule.tsx`](frontend/src/pages/Schedule.tsx)
* **Chi tiết thực hiện:**
  * **Khắc phục lỗi 404 Not Found:** Trước đây backend chưa có router cho `/api/schedules`. Đã xây dựng hoàn chỉnh router với đầy đủ các phương thức HTTP:
    * `GET /api/schedules/`: Liệt kê tất cả lịch trình kèm tên thiết bị tương ứng (`fan`, `led`).
    * `POST /api/schedules/`: Tạo lịch trình mới (thiết bị, hành động `on`/`off`/`set_speed`/`alert`, giờ chạy `HH:MM`, lặp lại `daily`/`once`/`weekly`).
    * `PATCH /api/schedules/{id}`: Bật/tắt kích hoạt lịch trình hoặc cập nhật giờ chạy.
    * `DELETE /api/schedules/{id}`: Xóa bỏ lịch trình khỏi database.
  * **Tích hợp vào `main.py`:** `app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])`.
  * **Giao diện Schedule:** Cập nhật lại các nhãn hành động cho phù hợp với vai trò cảnh báo của LED (`Kích hoạt cảnh báo` thay cho việc chọn bảng màu).

---

## 8. Hướng dẫn kiểm tra và chạy thử nghiệm (Verification)

### 1. Khởi chạy Backend:
```bash
.venv\Scripts\python.exe backend\main.py
```
*API Docs tương tác đầy đủ tại:* `http://localhost:8000/docs`

### 2. Khởi chạy Frontend:
```bash
cd frontend
npm run dev
```
*Truy cập giao diện web tại:* `http://localhost:5173`

### 3. Kịch bản kiểm thử các tính năng mới:
1. **Kiểm thử Lập lịch điều khiển:** Vào `http://localhost:5173/schedule`, chọn Quạt hoặc Đèn cảnh báo, đặt giờ `07:30`, bấm *Lưu lịch trình* -> Thêm thành công vào danh sách, không còn lỗi 404. Thử bật/tắt công tắc hoặc xóa lịch trình.
2. **Kiểm thử Đồng bộ nút quạt với ESP32:**
   - Mở trang `http://localhost:5173/devices`.
   - Bấm nút **SW1** trên mạch ESP32: Quạt đổi tốc độ (40% -> 70% -> 100% -> Tắt), trên web UI sau 1-2 giây nút tương ứng sẽ tự động sáng lên và công tắc bật/tắt chuyển trạng thái theo.
   - Bấm nút **SW2** trên mạch ESP32: Mode trên web đổi sang `Tự động (AI)`.
   - Bấm các nút nấc `40%`, `70%`, `100%`, `Tắt (0%)` trực tiếp trên web -> Lệnh được gửi chuẩn xác xuống Adafruit IO và mạch nhận lệnh thay đổi tốc độ quạt tương ứng.
3. **Kiểm thử Cảnh báo LED quá nhiệt:** Bấm *Test cảnh báo quá nhiệt (Đèn ĐỎ)* trên thẻ đèn -> Đèn phát tín hiệu đỏ báo động. Bấm *Hủy báo động* -> Đèn trở về trạng thái an toàn.
