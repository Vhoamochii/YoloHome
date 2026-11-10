# BÁO CÁO HOÀN THÀNH TÍCH HỢP HỆ THỐNG YOLOHOME
**Dự án:** YoloHome - AI IoT Smart Home System  
**Ngày hoàn thành:** 05/11/2026  
**Mục tiêu:** Liên kết toàn bộ nội dung từ Frontend, AI vào Backend, lưu trữ Database, tinh chỉnh cơ chế cảnh báo LED quá nhiệt, đồng bộ nút bấm vật lý điều khiển quạt với Frontend và hoàn thiện hệ thống Lập lịch điều khiển.

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
| **9. Tốc độ lập lịch & Fix Refused LOCK** | Bổ sung ô/slider đặt % tốc độ quạt khi lập lịch; Firmware và Backend ưu tiên lịch trình, hủy lockdown không bị từ chối | **Hoàn thành 100%** |
| **10. UI Tinh gọn & Cài đặt** | Đổi logo nút Cài đặt sang bánh răng ⚙️, loại bỏ thanh đăng ký khuôn mặt thừa trong modal ngưỡng, xóa icon rườm rà | **Hoàn thành 100%** |
| **11. Nhật ký lệnh & thiết bị** | Kết nối bảng Nhật ký sự kiện với database thời gian thực, lưu vết trạng thái OK/REJECTED, RTT và xuất file CSV | **Hoàn thành 100%** |
| **12. Tinh chỉnh Trợ lý Giọng nói (Voice AI)** | Loại bỏ toàn bộ icon emoji rườm rà, thay bằng vector SVG hiện đại; thêm cơ chế nhận diện micro và hướng dẫn xử lý khi cắm tai nghe | **Hoàn thành 100%** |

---

## 1. Mảng Cơ sở dữ liệu (Database Layer & Clean Data)

* **Tệp chỉnh sửa:** [`backend/database.py`](file:///d:/Hoc/Y3/261/dadn/backend/database.py), [`backend/routes/sensors.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/sensors.py)
* **Chi tiết thực hiện:**
  * **Cố định đường dẫn cơ sở dữ liệu:** Neo cứng đường dẫn tuyệt đối `os.path.abspath(os.path.join(..., "yolohome.db"))` vào thư mục `backend/`, loại bỏ triệt để hiện tượng phân mảnh 2 file sqlite khác nhau giữa thư mục gốc và thư mục backend.
  * **Dọn dẹp dữ liệu giả (Fake Seed Data):** Đã loại bỏ hàm `ensure_initial_seed()` và xóa toàn bộ các bản ghi giả lập cũ. Khi chưa cắm phần cứng ESP32 hoặc đăng ký tài khoản mới, hệ thống phản ánh đúng thực tế: *"Chưa có dữ liệu cảm biến từ ESP32"* thay vì hiển thị dữ liệu nhiệt độ ảo 7 ngày trước.
  * Tự động khởi tạo đầy đủ 6 bảng quan hệ (`nguoi_dung`, `face_profiles`, `thiet_bi`, `trang_thai_thiet_bi`, `lich_su_cam_bien`, `lich_trinh`).

---

## 2. Mảng Xác thực & Quản lý Tài khoản (User Authentication)

* **Tệp chỉnh sửa:** [`backend/routes/auth.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/auth.py)
* **Chi tiết thực hiện:**
  * **Đăng ký (`POST /api/auth/register`):** Nhận `email`, `password`, `name`. Kiểm tra trùng lặp email. Mật khẩu được băm bảo mật bằng thuật toán chuẩn hóa `PBKDF2-HMAC-SHA256` kèm chuỗi muối ngẫu nhiên (salt 16-byte). Lưu trực tiếp vào bảng `nguoi_dung`.
  * **Đăng nhập (`POST /api/auth/login`):** So khớp mật khẩu băm, cấp mã JWT session token cho phiên đăng nhập.
  * **Thông tin cá nhân (`GET /api/auth/me`):** Trả về thông tin người dùng hiện tại và cờ `has_face` cho biết tài khoản đã có khuôn mặt đăng ký trong database hay chưa.

---

## 3. Mảng Nhận diện Khuôn mặt (Face Recognition AI Integration)

* **Tệp chỉnh sửa:**
  * Backend: [`backend/routes/auth.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/auth.py)
  * Frontend: [`frontend/src/pages/Login.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Login.tsx), [`frontend/src/components/ProtectedLayout.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/components/ProtectedLayout.tsx), [`frontend/src/services/api.ts`](file:///d:/Hoc/Y3/261/dadn/frontend/src/services/api.ts)
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
  * Backend: [`backend/routes/sensors.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/sensors.py)
  * Frontend: [`frontend/src/pages/Logs.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Logs.tsx), [`frontend/src/pages/Devices.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Devices.tsx)
* **Chi tiết thực hiện:**
  * **Endpoint xuất CSV (`GET /api/sensors/export-csv`):**
    * Xuất file CSV có gắn tiền tố **UTF-8 BOM (`\ufeff`)**, tương thích hoàn hảo với Microsoft Excel và Google Sheets tiếng Việt.
  * **Giao diện Nhật ký (`Logs.tsx`):** Nút **`📥 Xuất file .CSV`**, tab hiển thị lịch sử nhiệt độ/độ ẩm Adafruit và bảng nhật ký lệnh thiết bị.
  * **Giao diện Thiết bị (`Devices.tsx`):** Bổ sung bảng *Ghi nhận hoạt động gần đây* lưu vết cục bộ các hành động điều khiển công tắc, chuyển nấc tốc độ kèm nút **`Xuất log CSV`**.

---

## 5. Mảng Đồng bộ Quạt & Nút bấm Phần cứng (Hardware Button Sync)

* **Tệp chỉnh sửa:**
  * Backend: [`backend/adafruit_mqtt.py`](file:///d:/Hoc/Y3/261/dadn/backend/adafruit_mqtt.py), [`backend/routes/devices.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/devices.py)
  * Frontend: [`frontend/src/pages/Devices.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Devices.tsx), [`frontend/src/services/api.ts`](file:///d:/Hoc/Y3/261/dadn/frontend/src/services/api.ts)
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
  * Backend: [`backend/routes/devices.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/devices.py)
  * Frontend: [`frontend/src/pages/Devices.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Devices.tsx), [`frontend/src/pages/Dashboard.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Dashboard.tsx), [`frontend/src/components/VoiceModal.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/components/VoiceModal.tsx)
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
  * Backend: [`backend/routes/schedules.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/schedules.py), [`backend/main.py`](file:///d:/Hoc/Y3/261/dadn/backend/main.py)
  * Frontend: [`frontend/src/pages/Schedule.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Schedule.tsx)
* **Chi tiết thực hiện:**
  * **Khắc phục lỗi 404 Not Found:** Trước đây backend chưa có router cho `/api/schedules`. Đã xây dựng hoàn chỉnh router với đầy đủ các phương thức HTTP:
    * `GET /api/schedules/`: Liệt kê tất cả lịch trình kèm tên thiết bị tương ứng (`fan`, `led`).
    * `POST /api/schedules/`: Tạo lịch trình mới (thiết bị, hành động `on`/`off`/`set_speed`/`alert`, giờ chạy `HH:MM`, lặp lại `daily`/`once`/`weekly`).
    * `PATCH /api/schedules/{id}`: Bật/tắt kích hoạt lịch trình hoặc cập nhật giờ chạy.
    * `DELETE /api/schedules/{id}`: Xóa bỏ lịch trình khỏi database.
  * **Tích hợp vào `main.py`:** `app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])`.
  * **Giao diện Schedule:** Cập nhật lại các nhãn hành động cho phù hợp với vai trò cảnh báo của LED (`Kích hoạt cảnh báo` thay cho việc chọn bảng màu).

---

## 9. Tinh chỉnh Lập lịch quạt & Khắc phục lỗi lệnh bị từ chối (Refused: LOCK)

* **Tệp chỉnh sửa:**
  * Frontend: [`frontend/src/pages/Schedule.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Schedule.tsx)
  * Backend: [`backend/scheduler.py`](file:///d:/Hoc/Y3/261/dadn/backend/scheduler.py), [`backend/routes/schedules.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/schedules.py), [`backend/models.py`](file:///d:/Hoc/Y3/261/dadn/backend/models.py), [`backend/database.py`](file:///d:/Hoc/Y3/261/dadn/backend/database.py)
  * Firmware: [`firmware/src/control.cpp`](file:///d:/Hoc/Y3/261/dadn/firmware/src/control.cpp), [`firmware/src/tasks/adafruitio_task.cpp`](file:///d:/Hoc/Y3/261/dadn/firmware/src/tasks/adafruitio_task.cpp)
* **Nguyên nhân lỗi Refused `LOCK`:**
  * Khi người dùng thao tác quạt thủ công (qua Web UI, phím cứng SW1 hoặc Voice), ESP32 tự động kích hoạt chế độ khóa thủ công `ManualLockdown` trong 30 phút (`c_.lockdownMin = 30`).
  * Trong thời gian 30 phút này, trước đây firmware kiểm tra `if (cmd.actor == Actor::Schedule) { if (lockdownActive(nowMs)) return {false, "LOCK"}; }` dẫn đến lệnh lập lịch bị từ chối với lý do `LOCK`.
  * Đồng thời, backend cố gắng gửi `"AUTO"` để giải phóng lockdown trước khi gửi lịch, nhưng firmware trước đây chưa nhận diện chuỗi `"AUTO"` trên feed quạt (`parseNumber` thất bại -> `BAD_VAL`).
* **Giải pháp khắc phục:**
  * **Phía Frontend (`Schedule.tsx`):** Khi chọn hành động *"Đặt tốc độ quạt"*, giao diện hiển thị ngay ô nhập tốc độ số nguyên (10 - 100%), thanh kéo slider liên tục và 3 nút chọn nhanh (`40%`, `70%`, `100%`). Bảng lịch trình hiển thị rõ ràng tốc độ đã đặt.
  * **Phía Firmware (`control.cpp` & `adafruitio_task.cpp`):**
    * Cập nhật logic: Lệnh từ bộ lập lịch (`Actor::Schedule`) là chủ ý đã định trước của người dùng nên được ưu tiên thực thi ngay lập tức, tự động hủy `lockActive_` thủ công cũ và kích hoạt `holdMin` tạm hoãn AI điều chỉnh đè lên.
    * Hỗ trợ lệnh `"AUTO"` trên feed `fan`: Cho phép hủy `ManualLockdown` an toàn mà không báo lỗi `BAD_VAL`.
  * **Phía Backend (`scheduler.py` & `database.py`):**
    * Tự động migration thêm cột `speed` và `last_run_at` vào bảng `lich_trinh`.
    * Quá trình kích hoạt lịch trình diễn ra atomic, mượt mà và ghi nhận nhật ký chuẩn xác.

---

## 10. Tinh gọn Giao diện & Modal Cài đặt

* **Tệp chỉnh sửa:**
  * [`frontend/src/components/ProtectedLayout.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/components/ProtectedLayout.tsx)
  * [`frontend/src/components/ThresholdModal.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/components/ThresholdModal.tsx)
* **Chi tiết thực hiện:**
  * **Biểu tượng Cài đặt:** Đổi biểu tượng trên thanh Header sang icon Bánh răng chuẩn (`⚙️ Settings`), trực quan và đúng chuẩn UX.
  * **Loại bỏ Đăng ký khuôn mặt thừa:** Đã xóa bỏ thanh/nút *"Đăng ký khuôn mặt"* trong modal Cài đặt ngưỡng, tập trung modal này đúng vai trò cấu hình nhiệt độ, độ ẩm và các thông số giám sát. (Tính năng khuôn mặt đã có nút chuyên biệt trên Header và trang Login).
  * **Dọn dẹp biểu tượng:** Tinh chỉnh các icon rườm rà trên giao diện các trang, tạo khoảng trống thoáng và hiện đại.

---

## 11. Hoàn thiện Nhật ký lệnh & thiết bị (Activity Logs)

* **Tệp chỉnh sửa:**
  * Frontend: [`frontend/src/pages/Logs.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/pages/Logs.tsx)
  * Backend: [`backend/device_control.py`](file:///d:/Hoc/Y3/261/dadn/backend/device_control.py), [`backend/routes/activity.py`](file:///d:/Hoc/Y3/261/dadn/backend/routes/activity.py), [`backend/models.py`](file:///d:/Hoc/Y3/261/dadn/backend/models.py)
* **Chi tiết thực hiện:**
  * Kết nối bảng *Nhật ký lệnh & thiết bị* với API `GET /api/activity/` hiển thị 100 sự kiện gần nhất từ bảng `nhat_ky_hoat_dong`.
  * Ghi nhận đầy đủ: Thiết bị, Lệnh thực hiện, Tác nhân (`USER`, `VOICE`, `SCHEDULE`, `AI`), Thời gian thực thi, Trạng thái phản hồi (`OK`, `REJECTED`, `PENDING`), thời gian phản hồi (RTT ms) và lý do từ chối nếu có.
  * Hỗ trợ xuất file CSV riêng cho Nhật ký sự kiện lệnh với UTF-8 BOM.

---

## 12. Tinh chỉnh Trợ lý Giọng nói (Voice AI) & Xử lý sự cố Micro khi cắm tai nghe

* **Tệp chỉnh sửa:** [`frontend/src/components/VoiceModal.tsx`](file:///d:/Hoc/Y3/261/dadn/frontend/src/components/VoiceModal.tsx)
* **Chi tiết thực hiện:**
  * **Loại bỏ icon emoji rườm rà:** Xoá sạch toàn bộ các icon emoji như 🎙️, 🎤, 💡, 🔄; thay thế bằng thiết kế tối giản, biểu tượng vector SVG hiện đại và hiệu ứng sóng âm pulsing mềm mại khi đang thu âm.
  * **Nhận diện thiết bị âm thanh thời gian thực:** Tích hợp `navigator.mediaDevices.enumerateDevices()` và lắng nghe sự kiện `devicechange`. Hiển thị nhãn tên micro đang hoạt động ngay trên giao diện (`Mic: [Tên thiết bị]`).
  * **Chẩn đoán sự cố cắm tai nghe:** Khi xảy ra lỗi `no-speech` hoặc `audio-capture`, giao diện cung cấp chỉ dẫn khắc phục cụ thể: giải thích hiện tượng ngắt mic tích hợp của máy khi cắm tai nghe không mic, hoặc kiểm tra quyền truy cập và mức âm lượng micro trên Windows.
  * **Sửa lỗi thứ tự nhận dạng khẩu lệnh Tắt cảnh báo:** Khắc phục lỗi kiểm tra chuỗi `command.includes('cảnh báo')` đứng trước, khiến câu lệnh *"tắt cảnh báo"* bị hiểu nhầm thành *"kích hoạt cảnh báo đỏ"*. Đã ưu tiên toàn bộ các biến thể phủ định (`tắt cảnh báo`, `hủy cảnh báo`, `tắt đèn đỏ`, `dừng báo động`, `an toàn`, `đèn xanh`...) thực thi lệnh `safe` đưa hệ thống và đèn LED về màu an toàn/tắt ngay lập tức.

---

## 13. Hướng dẫn kiểm tra và chạy thử nghiệm (Verification)

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
