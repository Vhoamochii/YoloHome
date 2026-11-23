# YoloHome: hướng dẫn thuyết trình và luồng logic

File này dùng để thuyết trình YoloHome theo thứ tự:
1. Tổng quan hệ thống.
2. 5 module chức năng.
3. Các tính năng AI: Face ID, giọng nói, TinyML.
4. Chi tiết mạch, giao thức, backend, kiểm thử, cách chạy và một kịch bản demo.
5. Đối chiếu với yêu cầu 3 hướng chuyên môn: AI, CNPM, HTTT (mục 10).

Tài liệu khác:
- **`LICH_SU_THAY_DOI.md`:** lịch sử thay đổi.
- **`HUONG_FACE_ID.md`:** chi tiết thiết kế và số liệu Face ID.
- **`tinyml-fire/HUONG_DAN_CHAY_THUC_TE.md`:** chi tiết mô hình TinyML và cách train lại.
- **`CLAUDE.md`:** lệnh build và test.

---

## 1. Bức tranh tổng thể

```
┌────────────────────────┐   MQTT/TLS   ┌──────────────┐   MQTT    ┌───────────────────────┐   HTTP /api   ┌──────────────┐
│ Board ESP32 (Yolo Uno) │ ───────────► │ Adafruit IO  │ ────────► │ Backend FastAPI       │ ◄──────────── │ Web React    │
│ cảm biến, quạt, LED,   │ ◄─────────── │ (10 feed)    │ ◄──────── │ SQLite, scheduler,    │ ────────────► │ (Vite)       │
│ LCD, nút, TinyML       │              └──────────────┘           │ Face ID (OpenCV)      │               │ webcam, mic  │
└────────────────────────┘                                         └───────────────────────┘               └──────────────┘
```

- **Board và backend không nói chuyện trực tiếp.** Mọi dữ liệu đi qua các feed của Adafruit IO. Board vẫn tự điều khiển được khi mất mạng.
- **Board là nơi quyết định cuối cùng:** an toàn nhiệt, khoá tay, AI làm mát đều chạy trên board. Backend chỉ gửi lệnh, ghi nhật ký và phục vụ web.
- **Web không bao giờ gọi Adafruit IO.** Web chỉ gọi backend qua `/api` (khi dev, Vite chuyển tiếp sang cổng 8000).

---

## 2. Năm module chức năng

Mỗi module đều đi qua đủ các tầng: mạch → Adafruit IO → backend → web.

| Module | Trên mạch ESP32 | Ở backend | Trên web |
|---|---|---|---|
| 1. Nhận và hiển thị dữ liệu | Đọc DHT20 mỗi 2 s, gửi trung bình 30 s, hiện lên LCD | Gộp nhiệt độ + độ ẩm, lưu lịch sử | Dashboard, trang Nhật ký |
| 2. Kiểm tra vượt ngưỡng | An toàn 45 °C, cảnh báo nóng 33 °C, TinyML, bất thường | Nhận sự kiện, giữ mức cảnh báo hiện tại | Dòng cảnh báo theo ngưỡng tự đặt, thẻ đèn cảnh báo |
| 3. Điều khiển thiết bị | Xét thứ tự ưu tiên, chạy hoặc từ chối, luôn ACK | Gửi lệnh, chờ ACK tối đa 30 s | Nút, thanh trượt, giọng nói, lịch hẹn giờ |
| 4. Ghi nhận hoạt động | Gửi ACK, sự kiện, gửi bù khi có mạng lại | Bảng nhật ký, lịch sử cảm biến, lịch sử báo cháy | Trang Nhật ký, xuất CSV |
| 5. Ứng dụng Web/Mobile | — | REST API, đăng nhập | React, chạy trên trình duyệt máy tính và điện thoại |

### Module 1: Nhận và hiển thị dữ liệu từ thiết bị

```
DHT20 ──(mỗi 2 s)──► tác vụ sensor ──► tác vụ display: LCD 16x2
                          │
                          └──► tác vụ cloud: trung bình 30 s ──► feed yolohome-temperature, yolohome-humidity
                                                                      │ MQTT
backend (luồng MQTT): gộp nhiệt độ + độ ẩm về cách nhau ≤ 5 s ──► bảng lich_su_cam_bien
web: Dashboard gọi GET /api/sensors/current mỗi 5 s; trang Nhật ký gọi /api/sensors/history mỗi 3 s
```

- **Đọc 2 s, gửi 30 s:**
  - Mạch đọc cảm biến mỗi 2 giây để phản ứng nhanh: LCD, ngưỡng an toàn và TinyML đều dùng số đo này.
  - Lên cloud, mạch chỉ gửi giá trị trung bình 30 giây một lần. Lý do: gói Adafruit IO miễn phí chỉ cho 30 lần gửi mỗi phút cho cả tài khoản, tính cả lệnh và ACK.
  - Ánh sáng và chuyển động (nếu có lắp) gửi mỗi 60 giây.
- **Màn LCD trên mạch:**
  - Dòng 1: nhiệt độ, độ ẩm, % quạt.
  - Dòng 2: chế độ và nhiệt độ dự báo 15 phút, ví dụ `AUTO t15 31.2C`. Khi có chuyện, dòng 2 đổi thành `FIRE!`, `SAFETY!`, `HOT!` hoặc `LOCK 25m left`.
- **Backend gộp hai tin nhắn:** nhiệt độ và độ ẩm của cùng một lần đo đến bằng hai tin MQTT riêng. Backend gộp thành một dòng nếu hai tin cách nhau không quá 5 giây.
- **Web:**
  - Dashboard hiện nhiệt độ, độ ẩm hiện tại, trạng thái thiết bị, 6 lần đo gần nhất, và hai biểu đồ đường nhiệt độ, độ ẩm 24 giờ qua.
  - Trang Nhật ký có bảng lịch sử theo số giờ chọn và nút xuất CSV.
- **Khi mất mạng:** mạch giữ số liệu từng phút (tối đa 1000 phút, khoảng 16,7 giờ) và gửi bù khi có mạng lại.

### Module 2: Kiểm tra dữ liệu vượt quá ngưỡng cho phép

Việc kiểm tra ngưỡng chạy ở hai nơi: trên mạch (có hành động thật) và trên web (chỉ hiển thị).

| Kiểm tra | Ở đâu | Ngưỡng | Hành động |
|---|---|---|---|
| An toàn nhiệt | Mạch, `control.cpp` | Bật khi > 45 °C, tắt khi < 43 °C | Quạt 100%, LED đỏ, từ chối lệnh giảm quạt (lý do `SAFE`), gửi sự kiện `SAFETY:46.2` |
| Cảnh báo nóng | Mạch, `control.cpp` | Bật khi ≥ 33 °C, tắt khi < 32,5 °C | LED cam, gửi sự kiện `HOT` |
| Báo cháy TinyML | Mạch, `fire_engine.h` | Điểm ≥ 0,80 trong 3 lần đo liên tiếp; nhả khi ≤ 0,75 trong 3 lần liên tiếp | Gửi `TINYML:ALERT:0.952`, LCD hiện `FIRE!` |
| Bất thường | Mạch, `control.cpp` | Nhiệt độ thật lệch dự báo quá 2,5 độ lệch chuẩn, 3 phút liên tiếp | Gửi sự kiện `ANOM:+3.1` |
| Ngưỡng hiển thị | Web, `ThresholdModal` | Người dùng tự đặt nhiệt độ và độ ẩm tối đa | Dashboard hiện dòng cảnh báo |

- **Mạch tự quyết, không cần mạng:** ngưỡng an toàn và báo cháy chạy ngay trên chip. Mất Wi-Fi hay backend tắt thì quạt vẫn bật.
- **Có khoảng trễ:** ngưỡng bật cao hơn ngưỡng tắt, nên LED và quạt không bật tắt liên tục khi nhiệt độ dao động quanh ngưỡng.
- **Backend:**
  - Nhận sự kiện, ghi vào nhật ký.
  - Giữ mức cảnh báo hiện tại (`SAFETY`, `HOT`) để web hiện đèn cảnh báo.
  - Lưu kết quả TinyML vào bảng `lich_su_canh_bao_chay`.
- **Ngưỡng trên web chỉ để hiển thị:** lưu trong trình duyệt, không gửi xuống mạch.

### Module 3: Điều khiển thiết bị

Hai thiết bị: **quạt** (0–100%) và **đèn LED RGB cảnh báo**. Lệnh đến từ năm nguồn:
- nút bấm và thanh trượt trên web (`U`);
- giọng nói (`V`);
- lịch hẹn giờ (`S`);
- AI trên mạch (`A`);
- nút SW1, SW2 trên mạch.

```
Web: POST /api/devices/{id}/control
  └─ device_control.dispatch(): ghi dòng PENDING (kèm người bấm) và COMMIT trước
       └─ gửi "70:a1b2c3d4:U" lên feed yolohome-fan
            └─ mạch (tác vụ control) xét thứ tự ưu tiên ──► chạy hoặc từ chối
                 └─ mạch gửi ACK "fan:a1b2c3d4:1:70:U" lên feed yolohome-ack
backend: PENDING → OK hoặc REJECTED (kèm lý do); 30 s không ACK → TIMEOUT; backend mất kết nối → OFFLINE
web: chỉ đổi trạng thái khi mạch báo về, không tự đoán
```

**Thứ tự ưu tiên trên mạch:** An toàn nhiệt → Khoá tay → Lịch hẹn giờ → AI.
- **Khoá tay:** người dùng chỉnh quạt (web, giọng nói, nút SW1) thì mạch giữ mức đó 30 phút. Trong lúc đó, lệnh AI bị từ chối với lý do `LOCK`.
- **Lịch hẹn giờ:** vẫn chạy kể cả khi đang khoá tay, vì người dùng đã hẹn trước.
- **Nút SW2:** huỷ khoá tay, quạt về chế độ tự động.

Chi tiết từng bước ở mục 4.3 và 6.2.

### Module 4: Ghi nhận hoạt động

| Dữ liệu | Lưu ở đâu | Ghi khi nào |
|---|---|---|
| Lệnh điều khiển | Bảng `nhat_ky_hoat_dong` | Lúc gửi (PENDING), cập nhật khi có ACK hoặc hết hạn. Có người thực hiện, nguồn lệnh, lý do từ chối, thời gian phản hồi (RTT) |
| Sự kiện từ mạch | Bảng `nhat_ky_hoat_dong`, nguồn `BOARD` | Nút SW1/SW2, an toàn, cảnh báo nóng, bất thường, AI đổi quạt; TinyML chỉ khi đổi trạng thái (OK ↔ ALERT), để tin nhắc lại mỗi phút không lấn các lệnh của người dùng |
| Số đo cảm biến | Bảng `lich_su_cam_bien` | Mỗi 30 s |
| Kết quả TinyML | Bảng `lich_su_canh_bao_chay` | Ngay khi trạng thái đổi, nhắc lại mỗi 60 s |
| Độ trễ lệnh | File `backend/data/command_latency.csv` | Mỗi lần có ACK |

- **Trang Nhật ký:**
  - Có hai tab: cảm biến và sự kiện.
  - Có cột **Người thực hiện**.
  - Xuất được CSV (UTF-8 có BOM, mở bằng Excel không lỗi font).
- **Trang Thiết bị:** hiện 10 thao tác gần nhất.
- **Nhật ký dùng chung cho mọi tài khoản,** vì cả nhà dùng chung một mạch. Cột "Người thực hiện" cho biết ai đã bấm. Dòng do mạch, lịch hoặc AI tạo ra để trống cột này.
- **Giờ:** lưu theo UTC, hiển thị theo giờ Việt Nam.

### Module 5: Ứng dụng Web/Mobile

- **Công nghệ:**
  - Web: React 18 + TypeScript + Vite + Tailwind. Web gọi backend FastAPI qua REST (`/api`, thư viện axios).
  - Backend nói chuyện với mạch qua Adafruit IO.
- **Đăng nhập:** bằng email + mật khẩu, hoặc bằng khuôn mặt. Quy tắc chi tiết ở cuối module này.
- **Cập nhật dữ liệu:** web hỏi backend định kỳ: Dashboard 5 s, Thiết bị 2 s, Nhật ký 3 s.
- **Mobile:** chưa có app di động riêng. Giao diện web có thẻ viewport và dùng Tailwind, nên mở được trên trình duyệt điện thoại.

| Trang hoặc thành phần | Việc |
|---|---|
| `Login` | Đăng nhập hoặc đăng ký bằng email và mật khẩu, hoặc đăng nhập bằng khuôn mặt (3 khung) |
| `Dashboard` | Nhiệt độ, độ ẩm hiện tại, cảnh báo theo ngưỡng tự đặt, trạng thái thiết bị, 6 lần đo gần nhất, biểu đồ nhiệt độ và độ ẩm 24 giờ |
| `Devices` | Bật/tắt và chỉnh tốc độ quạt (cập nhật ngay trên giao diện, gộp các lần bấm liên tục), thử LED, 10 thao tác gần nhất, xuất CSV |
| `Schedule` | Tạo, sửa, xoá lịch hẹn giờ (một lần, hằng ngày, hằng tuần), có chọn % tốc độ quạt |
| `Logs` | Lịch sử cảm biến và nhật ký sự kiện, xuất CSV |
| `VoiceModal` | Trợ lý giọng nói tiếng Việt (mục 3.2) |
| `ThresholdModal` | Ngưỡng cảnh báo hiển thị, lưu trong trình duyệt |
| `FaceSetup`, `FaceCapture` | Đăng ký và quản lý Face ID, chụp nhiều khung từ webcam |

Lúc vừa bấm, web tạm hiện giá trị người dùng chọn khoảng 1,5 giây cho đỡ giật. Sau đó web hiện lại trạng thái do mạch báo về.

#### Quy tắc đăng ký và đăng nhập

Code nằm ở `backend/routes/auth.py` (backend), `frontend/src/pages/Login.tsx` và `frontend/src/components/ProtectedLayout.tsx` (web).

**Đăng ký** (`POST /api/auth/register`):

| Kiểm tra | Quy tắc | Câu báo lỗi |
|---|---|---|
| Email | Bỏ khoảng trắng hai đầu, đổi về chữ thường; phải có dấu `@` | "Email không hợp lệ." |
| Mật khẩu | Ít nhất 4 ký tự | "Mật khẩu phải có ít nhất 4 ký tự." |
| Trùng email | Mỗi email chỉ được một tài khoản | "Email này đã được đăng ký." |
| Tên hiển thị | Không bắt buộc; bỏ trống thì lấy phần trước `@` của email | — |

- **Không lưu mật khẩu gốc:**
  - Backend tạo một chuỗi muối ngẫu nhiên 16 byte, rồi băm mật khẩu bằng PBKDF2-HMAC-SHA256 với 100.000 vòng.
  - Bảng `nguoi_dung` chỉ lưu `muối:mã băm`.
  - Lộ database cũng không đọc ra được mật khẩu.
- **Đăng ký xong là vào luôn:** backend trả token ngay, không phải đăng nhập lại. Web mở sẵn hộp đăng ký Face ID; người dùng có thể bỏ qua.

**Đăng nhập bằng mật khẩu** (`POST /api/auth/login`):
- Email được chuẩn hoá giống lúc đăng ký, nên gõ chữ hoa hay thường đều được.
- Backend băm mật khẩu vừa nhập với đúng chuỗi muối đã lưu, rồi so với mã băm. Phép so sánh mất thời gian như nhau dù sai ở ký tự nào (`hmac.compare_digest`), nên không đoán dần được mật khẩu qua thời gian phản hồi.
- Sai email hay sai mật khẩu đều báo cùng một câu: "Email hoặc mật khẩu không chính xác." Câu báo lỗi không cho biết sai ở đâu.

**Đăng nhập bằng khuôn mặt** (`POST /api/auth/face-login`):
- Web chụp 3 khung, cách nhau 300 ms. Quy tắc chấp nhận hay từ chối ở mục 3.1.
- Thành công thì nhận token giống hệt đăng nhập bằng mật khẩu.
- Muốn dùng Face ID, người dùng phải đăng nhập bằng mật khẩu trước rồi mới đăng ký khuôn mặt (`POST /api/auth/face/enroll` cần token).

**Token và phiên đăng nhập:**

```
token = base64( user_id : hạn_dùng : HMAC-SHA256(SECRET_KEY, "user_id:hạn_dùng") )
```

- **Hạn dùng:** 7 ngày kể từ lúc đăng nhập.
- **Gửi kèm:** web lưu token trong `localStorage` và tự gắn vào mọi request (`Authorization: Bearer <token>`).
- **Backend kiểm ở mỗi request:** chữ ký đúng, chưa hết hạn, tài khoản còn tồn tại. Sai một điều là trả 401 "Chưa đăng nhập hoặc phiên đã hết hạn."
- **Không giả mạo được:** sửa `user_id` hay hạn dùng trong token thì chữ ký không còn khớp. Muốn ký lại phải có `SECRET_KEY`, mà khoá này chỉ nằm trên server.

**Bảo vệ trang trên web:**
- Chưa có token thì mọi trang, trừ `/login`, chuyển về trang đăng nhập.
- API trả 401 (token hết hạn hoặc sai) thì web xoá token và quay về trang đăng nhập.
- Mỗi lần mở web, web gọi `GET /api/auth/me` để lấy lại tên và biết tài khoản đã có Face ID chưa.
- **Đăng xuất:** xoá token trong trình duyệt rồi về trang đăng nhập.

**Giới hạn hiện tại** (nói nếu thầy hỏi):
- Chưa có chức năng quên mật khẩu. Nút "Quên mật khẩu?" chỉ nhắc liên hệ quản trị viên hoặc đăng nhập bằng Face ID.
- Chưa giới hạn số lần nhập sai mật khẩu.
- Backend không lưu phiên, nên đăng xuất chỉ xoá token ở trình duyệt. Token đã lộ vẫn dùng được tới khi hết hạn.
- Mật khẩu tối thiểu chỉ 4 ký tự.
- Phải chạy backend bằng `python main.py` (lý do ở phần "Xử lý key ở backend" ngay dưới).

#### Xử lý key ở backend

Backend giữ 2 key bí mật, đều nằm trong `backend/.env`. File này bị `.gitignore` chặn nên không lên GitHub; mẫu để điền là `backend/.env.example`.

| Key | Biến trong `.env` | Dùng để | Đọc ở đâu |
|---|---|---|---|
| Key Adafruit IO | `ADAFRUIT_IO_USERNAME`, `ADAFRUIT_IO_KEY` | Đăng nhập vào máy chủ MQTT của Adafruit IO để gửi lệnh và nhận số đo | `backend/adafruit_mqtt.py` |
| Khoá ký token | `SECRET_KEY` | Ký và kiểm chữ ký token đăng nhập (HMAC-SHA256) | `backend/routes/auth.py` |

**Key Adafruit IO:**
- **Nạp key:** lúc khởi động, `adafruit_mqtt.py` nạp `backend/.env` (thư viện `python-dotenv`) rồi đọc username và key.
- **Dùng key:**
  - Key làm mật khẩu khi kết nối MQTT.
  - Kết nối chạy qua TLS ở cổng 8883, nên key được mã hoá trên đường truyền.
  - Log của backend chỉ in host, cổng và TLS, không bao giờ in key.
- **Thiếu key:**
  - Backend ghi lỗi `ADAFRUIT_IO_USERNAME / ADAFRUIT_IO_KEY not set` và không kết nối.
  - Web vẫn chạy bình thường; lệnh điều khiển được ghi trạng thái `OFFLINE`.
- **Web không bao giờ thấy key Adafruit:** web chỉ gọi backend, và chỉ backend nói chuyện với Adafruit IO.
- **Theo dõi lỗi từ Adafruit:** backend nghe thêm 2 kênh của tài khoản và ghi cả hai vào log:
  - `<username>/errors`: lỗi, ví dụ "Feed limit reached" khi mạch gửi lên một feed không có.
  - `<username>/throttle`: báo khi gửi quá 30 lần mỗi phút.
- **Mạch có bản key riêng** trong `firmware/include/secrets.h`. Git chỉ giữ bản chữ mẫu; giá trị thật chỉ điền trên máy và không commit.

**`SECRET_KEY`:**
- **Dùng để ký token:** `HMAC-SHA256(SECRET_KEY, "user_id:hạn_dùng")`. Không có khoá thì không tạo được token hợp lệ.
- **Không bao giờ rời server:** khoá không có trong response nào và không có trên web.
- **Đổi `SECRET_KEY` thì mọi token cũ mất hiệu lực** và mọi người phải đăng nhập lại. Đây cũng là cách đăng xuất tất cả mọi người nếu nghi token bị lộ.
- **Giá trị đang dùng:** `.env` đang đặt một chuỗi riêng, khác giá trị mặc định ghi trong code.
- **Lưu ý khi chạy:**
  - `routes/auth.py` đọc `SECRET_KEY` ngay lúc được import, mà lúc đó `.env` chưa được nạp.
  - Chạy bằng `python main.py`: chế độ tự nạp lại tạo một tiến trình con, tiến trình này kế thừa các biến mà tiến trình cha đã nạp từ `.env`, nên dùng đúng khoá.
  - Chạy bằng `uvicorn main:app`: backend dùng giá trị mặc định ghi trong code. Repo đang công khai, nên ai đọc được code cũng tự tạo được token.

---

## 3. Các tính năng AI

| Tính năng | Chạy ở đâu | Dùng gì | Nhóm có tự train không |
|---|---|---|---|
| Face ID khi đeo khẩu trang | Backend | OpenCV: YuNet (tìm mặt), SFace (vector 128 số), adapter MLP | **Có:** adapter 128→256→128 |
| Trợ lý giọng nói | Trình duyệt | Web Speech API để nghe, bộ luật từ khoá để hiểu, SpeechSynthesis để đọc trả lời | Không |
| TinyML báo cháy | Mạch ESP32 | Hồi quy logistic có ràng buộc, 2 đầu vào: nhiệt độ, độ ẩm | **Có:** 3 hệ số |
| AI làm mát trước | Mạch ESP32 | Dự báo 15 phút bằng đường xu hướng, làm mượt EMA, ngưỡng trễ | Không (luật và thống kê) |

### 3.1 Face ID: nhận diện cả khi đeo khẩu trang

**Ý tưởng.** Người dùng chỉ đăng ký **mặt bình thường** (có kính cũng được). Lúc đăng nhập, **đeo khẩu trang vẫn vào được**, còn người lạ thì bị từ chối.

**Dùng gì:**
- **YuNet** (model có sẵn của OpenCV): tìm khuôn mặt và 5 điểm mốc.
- **SFace** (model có sẵn của OpenCV): biến khuôn mặt thành vector 128 số.
- **Adapter** do nhóm tự train: mạng MLP nhỏ, chỉnh vector SFace để mặt đeo và không đeo khẩu trang của cùng một người gần nhau hơn.
- Cả ba chạy trên backend bằng OpenCV và numpy, không cần GPU.

```
ảnh webcam (rộng 640px)
  → YuNet: tìm mặt + 5 điểm mốc                 (model có sẵn, OpenCV)
  → alignCrop: cắt mặt chuẩn 112×112
  → SFace: vector 128 số                         (model có sẵn, OpenCV)
  → Adapter: MLP dư 128→256→128                  ← NHÓM TỰ TRAIN
  → so độ giống (cosine) với mẫu đã lưu → quyết định
```

**Đăng ký** (`POST /api/auth/face/enroll`, cần đăng nhập):
1. Web chụp 10 khung trong khoảng 4 giây.
2. Mỗi khung phải có đúng một mặt, đủ to (≥ 80 px), đủ sáng, không mờ. Khung không đạt bị loại, kèm lý do.
3. Khung đạt được lưu vector SFace gốc, loại `plain`. Server vẽ thêm **2 khẩu trang giả lập** lên ảnh mặt đã căn rồi lưu thêm 2 vector loại `synthetic_mask`.
4. Mỗi loại giữ tối đa 20 mẫu; quá thì mẫu cũ nhất bị thay. Tuỳ chọn: thêm mẫu khẩu trang thật, loại `mask`.

**Đăng nhập** (`POST /api/auth/face-login`):

```
3 khung (cách nhau 300 ms) → khung nào có đúng 1 mặt → vector → adapter      (cần ≥ 2 khung)
với mỗi người u: điểm[u] = trung bình qua các khung của (độ giống cao nhất với các mẫu của u)
u1, u2 = người điểm cao nhất, cao nhì
ngưỡng = 0.60 nếu mẫu khớp nhất của u1 là mặt thường, 0.65 nếu là khẩu trang (thật hoặc giả lập)
chấp nhận nếu điểm[u1] ≥ ngưỡng  VÀ  điểm[u1] − điểm[u2] ≥ 0.05
```

- **Không khớp ai:** "Khuôn mặt không khớp với tài khoản nào."
- **Giống hai người quá:** yêu cầu tháo khẩu trang hoặc dùng mật khẩu.
- **Thành công:** trả token như đăng nhập bằng mật khẩu.

**Train adapter** (`ai-models/face/`):

```
video/ảnh điện thoại hoặc webcam
  → collect.py --import            tách khung tốt, tự xoay       → data/team/<người>/s1/<điều kiện>/
  → extract_features.py lfw|team   vector SFace + khẩu trang giả  → out/features_*.npz
  → train_adapter.py --variant home                               → out/adapter_home.npz
  → chép vào backend/face_models/adapter.npz
```

- **Dữ liệu:**
  - LFW: 13.233 ảnh công khai của 5.749 người, chia 80% để train, 20% để kiểm tra trong lúc train.
  - Nhóm: 5 người, mỗi người 3 kiểu (không đeo, khẩu trang, khẩu trang + kính nếu có kính).
- **Hàm mất mát:** batch-hard triplet. Kéo mặt có và không khẩu trang của cùng một người lại gần nhau, đẩy người khác ra xa.
- **Lúc đầu adapter không làm gì cả:** W2 và b2 khởi tạo bằng 0, nên adapter chưa train cho ra đúng vector SFace gốc. Script chỉ xuất adapter nếu nó tốt hơn SFace gốc trên tập kiểm tra.

**Kết quả đạt được:**
- **Tỉ lệ từ chối nhầm người đúng khi đeo khẩu trang** (đo trên LFW, khẩu trang giả lập, cố định tỉ lệ nhận nhầm người lạ ở 1%): giảm từ **2,14% xuống 1,38%**. Khi không đeo khẩu trang thì giữ nguyên 0,09%.
- **Chọn ngưỡng bằng phép thử bỏ-một-người** (5 thành viên; lần lượt coi mỗi người là người lạ):

  | Ngưỡng | Thành viên vào được (không đeo / khẩu trang / khẩu trang + kính) | Người lạ lọt vào |
  |---|---|---|
  | 0.363 (OpenCV đề xuất) | 30/30, 24/24, 18/18 | **19/30, 13/24, 16/18** |
  | **0.60 / 0.65 (đang dùng)** | **30/30, 24/24, 18/18** | **0/30, 0/24, 0/18** |

**Quyền riêng tư:**
- **Backend không lưu ảnh,** chỉ lưu vector.
- **Ảnh và video của nhóm** chỉ nằm trên máy người train và đã gitignore.
- **Adapter** là trọng số mạng, không chứa ảnh hay vector của ai.

### 3.2 Trợ lý giọng nói

**Dùng gì:**
- **Nghe:** Web Speech API của trình duyệt, ngôn ngữ `vi-VN`. Trên Chrome, âm thanh được gửi tới dịch vụ nhận dạng giọng nói của Google, nên cần Internet và chỉ chạy trên Chrome hoặc Edge.
- **Hiểu:** không dùng mô hình ngôn ngữ. Hàm `executeCommand` trong `VoiceModal.tsx` so khớp từ khoá theo thứ tự:

  | Thứ tự | Câu nói chứa | Kết quả |
  |---|---|---|
  | 1 | "nhiệt độ", "độ ẩm" | Đọc số đo hiện tại |
  | 2 | "tự động", "auto" | Quạt về chế độ tự động (`AUTO_AI`) |
  | 3 | "tắt"/"dừng" + "quạt" | Tắt quạt |
  | 4 | "quạt"/"tốc độ"/"mức" + con số | Đặt quạt đúng %; hoặc "nhẹ" 40%, "vừa" 70%, "mạnh" 100% |
  | 5 | "bật"/"mở" + "quạt" | Bật quạt (mặc định 70%) |
  | 6 | "tắt cảnh báo", "an toàn" | LED về trạng thái an toàn |
  | 7 | "cảnh báo", "đèn đỏ" | Bật LED cảnh báo đỏ |

- **Trả lời:** SpeechSynthesis của trình duyệt đọc câu trả lời bằng tiếng Việt.

**Kỳ vọng:**
- Nói một câu ngắn, lệnh tới mạch giống như bấm nút.
- Lệnh gửi với nguồn `VOICE`, nên mạch xử lý như người dùng chỉnh tay (khoá tay 30 phút). Nhật ký ghi tên người nói.
- Câu không chứa từ khoá nào thì trợ lý trả lời "Chưa nhận ra câu lệnh".

**Giới hạn:** phụ thuộc mạng và độ chính xác nhận dạng của Google; chỉ hiểu các mẫu câu có sẵn.

`ai-models/speech.py` là bản thử ban đầu bằng thư viện `speech_recognition` (cũng dùng Google), không dùng trong app.

### 3.3 TinyML phát hiện cháy (chạy trên mạch)

**Bài toán.** Từ nhiệt độ và độ ẩm, mạch tính một **điểm nguy cơ từ 0 đến 1**. Điểm cao liên tục thì báo động.

**Mô hình:** hồi quy logistic có ràng buộc.

```
z     = a·(T − 35)/10 + c·(RH − 50)/50 + b        T: nhiệt độ °C, RH: độ ẩm %
điểm  = 1 / (1 + e^(−z))
a = 3,366    c = −0,168    b = 1,301               (model ID 7129a5137abe)
```

**Train cái gì:** học 3 hệ số a, b, c.
- **Dữ liệu:**
  - 2 file CSV có nhãn trong `tinyml-fire/data/reference/`, tổng 108 dòng.
  - Bỏ 1 dòng lỗi, còn 79 dòng khác nhau.
  - Nhãn 0 = bình thường, 1 = nguy cơ.
- **Hàm mất mát:** cross-entropy có cân bằng hai lớp, cộng thêm phạt L2 nhỏ.
- **Ràng buộc:**
  - a > 0, nên nhiệt độ tăng thì điểm tăng.
  - Độ ẩm chỉ được ảnh hưởng nhẹ: cả dải 0–100% chỉ tương đương khoảng 1 °C.
- **Script:** `tinyml-fire/scripts/train_temperature_model.py`. Script xuất ra `temperature_model.h` (3 hằng số C), file này được build thẳng vào firmware.

**Chạy trên mạch:**
- Tác vụ `tinyml` tính điểm mỗi khi có số đo mới, tức mỗi 2 giây.
- Không cần thư viện ML: chỉ vài phép nhân và một hàm mũ.

**Kỳ vọng ra cái gì:**
- **Mỗi lần đo:** một điểm 0–1 và trạng thái `OK`, `ALERT` hoặc `SENSOR_ERROR`.
- **Báo động:**
  - Bật khi điểm ≥ 0,80 trong 3 lần đo liên tiếp (khoảng 6 giây). Với độ ẩm 50%, mức này ứng với khoảng **35,3 °C**.
  - Nhả khi điểm ≤ 0,75 trong 3 lần liên tiếp (khoảng 34,4 °C).
  - Đọc cảm biến lỗi thì không bao giờ xoá một cảnh báo đang có.
- **Đầu ra:**
  - Mạch gửi `TINYML:ALERT:0.952` lên cloud ngay khi trạng thái đổi, và nhắc lại mỗi 60 giây.
  - Backend lưu mọi kết quả vào `lich_su_canh_bao_chay`. Nhật ký sự kiện chỉ ghi khi trạng thái đổi.
  - LCD hiện `FIRE! S:0.95`.
- **Kết quả trên dữ liệu train, ngưỡng 0,80:**
  - 53/53 mẫu bình thường được nhận đúng (không báo giả).
  - 21/26 mẫu nguy cơ được phát hiện (bỏ sót 5).

**Giới hạn cần nói rõ:**
- Dữ liệu còn nhỏ, và mới chỉ đánh giá trên chính dữ liệu đã dùng để train.
- Điểm không phải xác suất cháy, và không thay được đầu báo khói.
- Luật 45 °C chạy độc lập song song, không tính là kết quả của ML.

### 3.4 AI làm mát trước (chạy trên mạch)

- **Dự báo** nhiệt độ 15 phút tới bằng đường xu hướng (hồi quy tuyến tính) trên 10 phút gần nhất. Chưa có mạng nơ-ron train sẵn: nếu sau này có file `forecast_model.h` thì mạch dùng file đó thay đường xu hướng.
- **Quyết định bật quạt:**
  - Dự báo tiến gần mức dễ chịu 30 °C thì điểm "khó chịu" tăng.
  - Điểm này được làm mượt bằng EMA. Quạt bật khi điểm ≥ 0,68 và tắt khi ≤ 0,48 trong 3 chu kỳ.
  - Tốc độ quạt từ 40 đến 100%, bước 10%, đổi tối đa mỗi phút một lần.
  - Chỉ bật khi có người, nếu mạch có cảm biến chuyển động.
- **Phát hiện bất thường:** dựa trên sai số giữa nhiệt độ thật và dự báo (Module 2).

---

## 4. Mạch ESP32 (`firmware/`)

### 4.1 Năm tác vụ FreeRTOS chạy song song

5 tác vụ này là các luồng chạy trên chip, không phải 5 module chức năng ở mục 2.

| Tác vụ | Lõi | Ưu tiên | Việc |
|---|---|---|---|
| `cloud` | 0 | 2 | Kết nối Wi-Fi và Adafruit IO. Gửi số liệu, nhận lệnh. Gửi bù dữ liệu tích lại khi có mạng trở lại |
| `sensor` | 1 | 3 | Đọc DHT20 (nhiệt độ, độ ẩm); ánh sáng và chuyển động nếu có |
| `control` | 1 | 4 | Bộ não: nhận số đo và lệnh, quyết định quạt, LED, relay, còi |
| `display` | 1 | 1 | Màn LCD 16x2: nhiệt độ, độ ẩm, chế độ, trạng thái |
| `tinyml` | 1 | 2 | Mô hình phát hiện cháy chạy ngay trên chip |

- **Chỉ tác vụ `cloud` đụng thư viện Adafruit IO.** Các tác vụ khác giao tiếp qua hàng đợi (`cloud_post_sample`, `cloud_post_ack`, `qCloudCommands`).
- **Trạng thái kết nối** báo bằng bit `EVT_CLOUD_UP`.

### 4.2 Luồng một số đo

```
DHT20 ──► sensor ──► control.reading()
                       ├─ an toàn nhiệt / cảnh báo nóng
                       ├─ gộp trung bình theo phút ──► dự báo 15 phút ──► phát hiện bất thường
                       └─ AI làm mát trước (nếu không bị khoá)
          sensor ──► cloud ──► feed temperature / humidity (/ light / presence)
          sensor ──► tinyml ──► điểm cháy ──► sự kiện TINYML:<trạng thái>:<điểm>
```

### 4.3 Thứ tự ưu tiên khi điều khiển (`control.cpp`)

1. **An toàn nhiệt:**
   - Nhiệt độ trên 45 °C thì bật chế độ an toàn: quạt 100%, LED đỏ, còi kêu ngắt quãng (Yolo:Bit có còi; Yolo Uno không có). Hết an toàn khi xuống dưới 43 °C.
   - Trong lúc an toàn, lệnh giảm quạt hay đổi LED đều bị từ chối với lý do `SAFE`.
2. **Cảnh báo nóng:** từ 33 °C LED chuyển cam, tắt khi dưới 32,5 °C. Khoảng chênh giữa hai mức giúp LED không chớp liên tục quanh ngưỡng.
3. **Khoá tay (`MANUAL_LOCKDOWN`):**
   - Người dùng chỉnh quạt (trên web, bằng giọng nói, hay nút SW1 trên board) thì board giữ đúng mức đó trong 30 phút, hoặc theo `hold_min` nếu lệnh có gửi kèm.
   - Trong thời gian này AI không tự đổi quạt. Lệnh AI gửi tới bị từ chối với lý do `LOCK`.
   - Nút SW2 huỷ khoá, về tự động.
4. **Lịch hẹn giờ:**
   - Lệnh từ lịch được chạy kể cả khi đang khoá tay, vì người dùng đã hẹn trước.
   - Có thể kèm `hold_min` để tạm dừng AI.
5. **AI làm mát trước (`AUTO_AI`):** xem mục 3.4.
6. **Phát hiện bất thường:** nhiệt độ thực lệch dự báo quá 2,5 độ lệch chuẩn trong 3 phút liên tiếp thì gửi sự kiện `ANOM:+x.x`.

Các chế độ hiển thị: `AUTO_AI`, `MANUAL_LOCKDOWN`, `OFFLINE_FAILSAFE` (mất mạng, board tự chạy).

### 4.4 Nút trên board
- **SW1:** đổi quạt theo vòng tắt → 40 → 70 → 100 → tắt. Tính là người dùng chỉnh, nên bật khoá tay.
- **SW2:** huỷ khoá tay, về `AUTO_AI`.
- Cả hai nút đều gửi sự kiện `BTN:...` lên cloud.

---

## 5. Giao thức qua Adafruit IO

**10 feed** (tối đa của gói miễn phí):

| Chiều | Feed |
|---|---|
| Board → cloud | `yolohome-temperature`, `-humidity`, `-light`, `-presence`, `-ack`, `-event`, `-mode`, `-fan-state` |
| Cloud → board | `yolohome-fan`, `yolohome-led` |

Tên feed trong `firmware/include/config.h` phải khớp đúng 10 feed trên tài khoản. Sai một tên thì Adafruit cố tạo feed mới, báo lỗi "Feed limit reached" và bỏ dữ liệu.

**Định dạng.** Mỗi chuỗi tối đa 44 ký tự, không có dấu phẩy hay dấu nháy.
- **Lệnh:** `<giá trị>:<cmd_id>:<người gửi>[:hold_min]`, ví dụ `70:a1b2c3d4:U`.
- **ACK:** `<thiết bị>:<cmd_id>:<ok>:<giá trị>:<người gửi>[:<lý do>]`. Lý do từ chối có `LOCK`, `SAFE`, …
- **Người gửi:** `U` người dùng, `V` giọng nói, `S` lịch, `Y` đồng bộ lại sau khi mất mạng (không bao giờ bật khoá tay), `A` AI, `X` hệ thống.
- **Sự kiện:** `LOẠI:dữ liệu`, ví dụ `SAFETY:46.2`, `HOT:33.9`, `AI:70:31.2`, `ANOM:+3.1`, `TINYML:ALERT:0.95`, `BTN:FAN:70`. Dữ liệu gửi bù sau khi mất mạng có tiền tố `B:`.

Hai đầu của giao thức là `backend/adafruit_mqtt.py` và `firmware/include/adafruitio_task.h`; đổi bên này thì phải đổi bên kia.

---

## 6. Backend (`backend/`, FastAPI + SQLite)

### 6.1 Khởi động (`main.py`)
1. Tạo bảng và nâng cấp schema (`create_all()`, `upgrade_schema()`).
2. Tạo sẵn 2 thiết bị: quạt và LED.
3. Đăng ký các hàm xử lý ACK, hết hạn lệnh, sự kiện.
4. Kết nối MQTT tới Adafruit IO. Không có key thì backend vẫn chạy, chỉ không gửi được lệnh.
5. Chạy luồng scheduler.

### 6.2 Vòng đời một lệnh điều khiển

```
Web: POST /api/devices/{id}/control {action, speed}
  └─ device_control.dispatch()
       1. ghi ActivityLog trạng thái PENDING (kèm người bấm) và COMMIT trước
          (vì ACK có thể về ngay trên luồng MQTT)
       2. gửi lệnh lên feed yolohome-fan / yolohome-led
       3a. board ACK ──► _on_ack(): PENDING → OK hoặc REJECTED (kèm lý do), cập nhật trạng thái thiết bị
       3b. 30 giây không ACK ──► scheduler gọi expire_pending() ──► TIMEOUT (chỉ khi vẫn còn PENDING)
       3c. backend đang mất kết nối ──► OFFLINE
```

- **Ba luồng chạy song song:** luồng web, luồng MQTT (của paho) và luồng scheduler.
- Dữ liệu dùng chung được khoá bằng `mqtt_client._lock`.

### 6.3 Dữ liệu nhận từ board
- **Số đo:** nhiệt độ và độ ẩm về gần nhau được gộp thành một dòng trong `lich_su_cam_bien`.
- **Sự kiện:** ghi vào nhật ký hoạt động bằng câu dễ đọc, ví dụ "AN TOÀN: Nhiệt độ vượt ngưỡng → Quạt 100%" hay "Nút cứng SW1".
- **`TINYML:<trạng thái>:<điểm>`:** lưu vào `lich_su_canh_bao_chay`, đọc được qua `GET /api/sensors/fire-status`.
- **Feed `mode` và `fan-state`:** cập nhật trạng thái thật của quạt. Web chỉ hiện trạng thái do board báo về, không tự đoán.

### 6.4 Lịch hẹn giờ (`scheduler.py`)
- **Vòng lặp:** chạy định kỳ, tìm lịch đã tới giờ (một lần / hằng ngày / hằng tuần) và gửi lệnh với người gửi `S`.
- **Lịch một lần** chạy xong thì tự tắt. **Lịch bị lỡ** lúc backend đang tắt thì bỏ qua, không chạy dồn.
- **Hết hạn lệnh:** cùng vòng lặp này đánh dấu hết hạn các lệnh quá 30 giây chưa có ACK.

### 6.5 Database (SQLite, `backend/yolohome.db`)

| Bảng | Nội dung |
|---|---|
| `nguoi_dung` | Tài khoản (mật khẩu băm PBKDF2) |
| `face_templates` | Mẫu Face ID: vector 128 số, loại `plain` / `mask` / `synthetic_mask` |
| `face_profiles` | Bảng dlib cũ, không dùng nữa |
| `thiet_bi`, `trang_thai_thiet_bi` | Thiết bị và trạng thái |
| `lich_su_cam_bien` | Lịch sử nhiệt độ, độ ẩm |
| `lich_trinh` | Lịch hẹn giờ |
| `nhat_ky_hoat_dong` | Mọi lệnh và sự kiện, kèm trạng thái, thời gian phản hồi và người thực hiện |
| `lich_su_canh_bao_chay` | Kết quả TinyML |

- **Không có migration.** Cột mới trên bảng đã có thì thêm `ALTER` vào `upgrade_schema()`.
- **Giờ trong DB là UTC.** API trả giờ dạng ISO có hậu tố `Z`. Lịch và CSV dùng giờ Việt Nam (UTC+7).

### 6.6 API

| Nhóm | Endpoint |
|---|---|
| Tài khoản | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Face ID | `POST /api/auth/face/enroll`, `GET /api/auth/face/status`, `DELETE /api/auth/face`, `POST /api/auth/face-login` |
| Thiết bị | `GET /api/devices/`, `POST /api/devices/{id}/control` |
| Cảm biến | `GET /api/sensors/current`, `/history`, `/export-csv`, `/fire-status` |
| Lịch | `GET`/`POST /api/schedules/`, `PATCH`/`DELETE /api/schedules/{id}` |
| Nhật ký | `GET /api/activity/` |

- Token đăng nhập ký bằng HMAC với `SECRET_KEY` và hết hạn sau 7 ngày. Web gửi token trong header `Authorization: Bearer ...`.
- Các nhóm Thiết bị, Cảm biến, Lịch, Nhật ký đều cần token; thiếu hoặc hết hạn thì trả 401.

---

## 7. Kiểm thử và CI/CD

| Ở đâu | Kiểm gì |
|---|---|
| `backend/tests/` (pytest) | Vòng đời lệnh (ACK, hết hạn, mất kết nối), gộp số đo, lịch, sự kiện, TinyML, bắt buộc đăng nhập, nhật ký ghi người thực hiện. Face ID dùng engine giả nên không cần file model |
| `.github/workflows/test.yml` | Build frontend; kiểm cú pháp và chạy pytest backend; build firmware `yolo_uno`; kiểm cú pháp `ai-models` |
| `.github/workflows/deploy.yml` | Build frontend và firmware, lưu file kết quả (artifact) |

Cả hai workflow chạy khi push lên `main` (`test.yml` chạy cả khi có Pull Request vào `main`).

---

## 8. Cách chạy

```powershell
# Backend (PowerShell, từ thư mục backend)
..\.venv\Scripts\Activate.ps1
python download_face_models.py      # chỉ lần đầu: model YuNet + SFace
python main.py                      # http://localhost:8000, tài liệu API ở /docs

# Frontend (từ thư mục frontend)
npm install --legacy-peer-deps      # chỉ lần đầu
npm run dev                         # http://localhost:5173

# Firmware (từ thư mục firmware)
pio run -e yolo_uno -t upload
pio device monitor -e yolo_uno
```

- **Backend:** key Adafruit IO đặt trong `backend/.env`.
- **Board:** Wi-Fi và key đặt trong `firmware/include/secrets.h`; file này có trong git dưới dạng chữ mẫu, **đừng commit giá trị thật**.
- **Không có key Adafruit IO** thì web vẫn chạy được, chỉ không điều khiển được board.

---

## 9. Một kịch bản demo đầy đủ

1. **AI làm mát trước:** phòng nóng dần. Board đo 29,6 °C và dự báo 15 phút nữa là 30,8 °C. AI bật quạt 60% rồi gửi sự kiện `AI:60:30.8`. Backend ghi nhật ký, web hiện quạt 60% ở chế độ `AUTO_AI`.
2. **Face ID:** người dùng đeo khẩu trang về nhà, đăng nhập bằng khuôn mặt. Mẫu khẩu trang giả lập khớp với điểm khoảng 0,8, vượt ngưỡng 0,65, nên vào được.
3. **Điều khiển tay:** người dùng kéo quạt lên 100%.
   - Backend ghi dòng `PENDING` rồi gửi lệnh `100:ab12cd34:U`.
   - Board chạy lệnh, bật khoá tay 30 phút và ACK `fan:ab12cd34:1:100:U`.
   - Dòng nhật ký đổi thành `OK`, kèm thời gian phản hồi và tên người bấm.
4. **Giọng nói:** người dùng nói "quạt 40 phần trăm". Lệnh đi với nguồn `VOICE`, nhật ký ghi tên người nói.
5. **Lịch hẹn giờ:** lịch "18:00 tắt quạt" tới giờ. Lệnh từ lịch được chạy dù đang khoá tay.
6. **Nếu có cháy:**
   - Nhiệt độ vượt khoảng 35,3 °C trong 3 lần đo liên tiếp: TinyML gửi `TINYML:ALERT:0.95`, LCD hiện `FIRE!`.
   - Nhiệt độ vượt 45 °C: board tự bật quạt 100% và LED đỏ, không cần mạng hay backend, rồi gửi `SAFETY:46.2`.
   - Backend lưu lại; web hiện cảnh báo trên thẻ đèn LED và trong nhật ký.
   - Nếu lúc đó board mất mạng, board gửi bù các sự kiện khi có mạng lại.

---

## 10. Đối chiếu yêu cầu 3 hướng chuyên môn

| Hướng | Yêu cầu | Bài có gì | Mức đáp ứng |
|---|---|---|---|
| AI | Sử dụng machine learning | Face ID adapter và TinyML báo cháy, cả hai do nhóm tự train | **Có** |
| CNPM | Sử dụng design pattern | 9 pattern dùng thật trong code (bảng ở mục 10.2) | **Có** |
| HTTT | Visualization dashboard | Trang Dashboard có biểu đồ nhiệt độ và độ ẩm 24 giờ cùng số liệu trực tiếp; trang Nhật ký có bảng lịch sử và xuất CSV | **Có** |

### 10.1 Hướng AI: machine learning

Nhóm có **2 mô hình tự train**: một chạy trên server, một chạy ngay trên vi điều khiển.

| Mô hình | Loại | Dữ liệu train | Kết quả | Chi tiết |
|---|---|---|---|---|
| Face ID adapter | Mạng MLP dư 128→256→128, hàm mất mát triplet | LFW (5.749 người) và ảnh của 5 thành viên, có khẩu trang giả lập | Từ chối nhầm khi đeo khẩu trang giảm từ 2,14% xuống 1,38%; người lạ lọt 0 lần | Mục 3.1 |
| TinyML báo cháy | Hồi quy logistic có ràng buộc, 3 hệ số | 79 mẫu nhiệt độ, độ ẩm có nhãn | Trên dữ liệu train: phát hiện 21/26 mẫu nguy cơ, 0 báo giả | Mục 3.3 |

Có thể nói thêm về các model có sẵn, không do nhóm train:
- **YuNet và SFace:** mạng nơ-ron train sẵn của OpenCV, nhóm dùng để tìm mặt và trích vector.
- **Nhận dạng giọng nói:** dịch vụ của Google, gọi qua Web Speech API của trình duyệt.

**AI làm mát trước** dùng hồi quy tuyến tính trên 10 phút gần nhất và phát hiện bất thường bằng độ lệch chuẩn của sai số dự báo. Phần này là thống kê chạy trực tiếp trên mạch, không có bước train.

### 10.2 Hướng CNPM: design pattern

| Pattern | Ở đâu trong code | Vì sao dùng |
|---|---|---|
| Publish–Subscribe | Mạch và backend trao đổi qua các feed MQTT của Adafruit IO | Mạch và backend không cần biết nhau, chỉ cần biết tên feed. Backend tắt thì mạch vẫn chạy |
| Observer | `mqtt_client.on("ack" / "event" / "timeout", handler)` trong `backend/adafruit_mqtt.py`; `device_control.register_handlers()` đăng ký các hàm xử lý | Phần MQTT không cần biết database; phần ghi nhật ký tự đăng ký để được gọi khi có tin |
| Singleton | `mqtt_client` (`adafruit_mqtt.py`), `scheduler` (`scheduler.py`), engine Face ID nạp một lần (`get_face_engine` trong `routes/auth.py`) | Chỉ một kết nối MQTT giữ danh sách lệnh đang chờ ACK; chỉ một luồng lịch; model ONNX nặng chỉ nạp một lần |
| Dependency Injection | FastAPI `Depends(get_db)`, `Depends(require_user)`, `Depends(get_face_engine)` | Route không tự tạo DB hay engine. Khi test, engine Face ID thật được thay bằng engine giả nên không cần file model |
| Producer–Consumer | Hàng đợi FreeRTOS `qSamples`, `qOut`, `qCloudCommands` giữa các tác vụ trên mạch (`adafruitio_task.cpp`) | Các tác vụ chạy trên hai lõi trao dữ liệu qua hàng đợi; tác vụ đọc cảm biến không bị mạng chậm chặn lại |
| Facade | Chỉ tác vụ `cloud` gọi thư viện Adafruit IO; tác vụ khác chỉ gọi `cloud_post_sample`, `cloud_post_ack`, `cloud_post_event` | Gom kết nối, kết nối lại và giới hạn 30 lần gửi/phút vào một chỗ |
| State machine | Chế độ `AUTO_AI` / `MANUAL_LOCKDOWN` / `OFFLINE_FAILSAFE`, trạng thái an toàn nhiệt (`control.cpp`); trạng thái `OK` / `ALERT` của TinyML (`fire_engine.h`) | Hành vi dễ đoán: mỗi lệnh được chạy hoặc bị từ chối kèm lý do (`LOCK`, `SAFE`) |
| Interceptor | `api.interceptors` trong `frontend/src/services/api.ts` | Tự gắn token vào mọi request; gặp lỗi 401 thì tự quay về trang đăng nhập |
| Kiến trúc nhiều tầng | API (`routes/`) → xử lý (`device_control.py`, `scheduler.py`) → dữ liệu (`models.py`, SQLAlchemy ORM) | Mỗi tầng một việc; đổi database không phải sửa route |

### 10.3 Hướng HTTT: visualization dashboard

**Biểu đồ trên trang Dashboard** (`frontend/src/components/SensorChart.tsx`, thư viện `recharts`):
- **Hai biểu đồ đường, 24 giờ qua:** một cho nhiệt độ (°C), một cho độ ẩm (%). Dữ liệu lấy từ `GET /api/sensors/history`, tự cập nhật mỗi 5 giây.
- **Vì sao hai biểu đồ riêng mà không gộp làm một:** hai đại lượng khác đơn vị. Gộp chung thì phải có hai trục dọc, người xem dễ so sai.
- **Rê chuột:** có đường dóng dọc và ô hiện giá trị kèm giờ đo. Điểm cuối có ghi giá trị mới nhất.
- **Mất kết nối:** nếu mạch im lặng quá 5 phút (mất mạng), đường bị ngắt tại đó chứ không nối thẳng qua khoảng trống, nên không vẽ ra dữ liệu giả.
- **Màu:** cam cho nhiệt độ, xanh dương cho độ ẩm. Hai màu đã kiểm tra: phân biệt được với người mù màu, và đủ tương phản trên nền tối.

**Các phần hiển thị khác:**
- **Trang Dashboard:**
  - Nhiệt độ, độ ẩm hiện tại.
  - Dòng cảnh báo khi vượt ngưỡng người dùng tự đặt.
  - Trạng thái quạt (tốc độ, chế độ) và đèn LED cảnh báo.
  - 6 lần đo gần nhất.
- **Trang Nhật ký:** bảng lịch sử cảm biến theo số giờ chọn, bảng nhật ký sự kiện có người thực hiện, xuất CSV để phân tích bằng Excel.
- **Màn LCD trên mạch:** hiện số đo, chế độ và cảnh báo ngay tại chỗ.
