# Lịch sử thay đổi và chức năng hiện tại

File này ghi lại hệ thống đang làm được gì và lần thay đổi nào sửa gì. Có thay đổi mới thì thêm một mục ở đầu phần "Lịch sử thay đổi".

Tài liệu liên quan:
- `Guide.md`: hướng dẫn thuyết trình và luồng logic của toàn hệ thống.
- `HUONG_FACE_ID.md`: thiết kế và số liệu chi tiết của Face ID.
- `CLAUDE.md`: kiến trúc và lệnh cho người viết code.
- `README.md`: tổng quan dự án, code và `Guide.md` là nguồn chuẩn nhất.

## Chức năng hiện tại

### Nhà thông minh
- **Theo dõi cảm biến:** nhiệt độ và độ ẩm từ board ESP32 (Yolo Uno), gửi qua Adafruit IO. Cảm biến ánh sáng và chuyển động là tuỳ chọn khi build firmware.
- **Điều khiển thiết bị:** quạt (có tốc độ) và đèn LED.
  - Mỗi lệnh đều được board xác nhận (ACK). Lệnh bị từ chối thì có lý do, ví dụ đang khoá tay hoặc đang bật an toàn.
  - Không có phản hồi sau 30 giây thì lệnh bị đánh dấu hết hạn.
- **Thứ tự ưu tiên điều khiển trên board:**
  1. An toàn nhiệt: trên 45 °C thì bật quạt, dưới 43 °C thì tắt.
  2. Khoá tay: 30 phút sau mỗi lần người dùng điều khiển.
  3. Lịch hẹn giờ.
  4. AI làm mát trước, dựa trên dự báo nhiệt độ 15 phút.
- **Lịch hẹn giờ:** một lần, hằng ngày hoặc hằng tuần.
- **Dashboard:** số liệu hiện tại và biểu đồ nhiệt độ, độ ẩm 24 giờ qua.
- **Nhật ký hoạt động:** xem lịch sử lệnh và cảm biến, có cột người thực hiện, xuất CSV.
- **Điều khiển bằng giọng nói** trên web.
- **Cảnh báo cháy TinyML:** mô hình chạy ngay trên board, backend lưu lịch sử cảnh báo.
- **Màn hình LCD trên board.**

### Tài khoản và Face ID
- **Tài khoản:** đăng ký và đăng nhập bằng email + mật khẩu. Mọi trang và API, trừ đăng ký và đăng nhập, đều cần đăng nhập.
- **Face ID** là cách đăng nhập thêm, không thay mật khẩu:
  - **Đăng ký:** sau khi đăng nhập, bấm "+ Face ID" rồi "Chụp khuôn mặt". Máy chụp 10 khung trong khoảng 4 giây. Không cần đeo khẩu trang; ai hay đeo kính thì cứ đeo. Tạo tài khoản mới xong thì hộp thoại này tự mở.
  - **Đăng nhập:** ở trang Login, bấm "Đăng nhập bằng khuôn mặt". Máy chụp 3 khung. **Đeo khẩu trang vẫn đăng nhập được.**
  - **Quản lý:** chụp thêm (ví dụ có và không đeo kính), thêm ảnh đeo khẩu trang thật nếu hay bị từ chối khi đeo, hoặc xoá Face ID.
- **Cách hoạt động:**
  - YuNet tìm khuôn mặt, SFace biến khuôn mặt thành vector 128 số, rồi một **adapter do nhóm tự train** chỉnh lại vector đó. Cả YuNet và SFace đều chạy bằng OpenCV.
  - Mỗi ảnh đăng ký được vẽ thêm 2 khẩu trang giả lập, nên đeo khẩu trang vẫn khớp được.
  - Backend chỉ lưu vector, không lưu ảnh.

### Dữ liệu
- **Database là SQLite:** file `backend/yolohome.db`, không cần cài server database.

## Lịch sử thay đổi

### 23/11/2026: Dọn dẹp tài liệu cũ, thu gọn comment code, nạp .env cho auth

**Tài liệu & dọn dẹp**
- Xoá các file markdown đã cũ hoặc thừa: `SETUP.md` (hướng dẫn cũ về PostgreSQL), `BAO_CAO_HOAN_THANH.md` (bản báo cáo 05/11 đã có `Guide.md` và `LICH_SU_THAY_DOI.md` thay thế), `tinyml-fire/docs/KIEM_THU.md`, `tinyml-fire/docs/TICH_HOP_BACKEND.md`.
- Xoá `ai-models/faces_data.pkl`: file pickle dlib cũ không còn sử dụng.
- Cập nhật các liên kết tài liệu trong `README.md`, `CLAUDE.md`, `tinyml-fire/README.md` trỏ về `Guide.md`.

**Mã nguồn**
- `backend/routes/auth.py`: Gọi `load_dotenv()` trước khi đọc `SECRET_KEY` từ biến môi trường.
- `backend/adafruit_mqtt.py`, `firmware/include/config.h`, `firmware/include/adafruitio_task.h`, `firmware/src/tasks/adafruitio_task.cpp`: Lược bỏ các comment banner và đoạn diễn giải dài dòng, giữ lại định nghĩa ngắn gọn, rõ ràng.
- `frontend/src/components/VoiceControl.tsx`: Dọn dẹp comment TODO không cần thiết.

### 23/11/2026: Sửa tên feed, ghi người thực hiện, bắt buộc đăng nhập, biểu đồ Dashboard

**Firmware**
- **Sửa tên feed Adafruit IO** (`firmware/include/config.h`):
  - Commit "Fix threshold" (07/11) đã đổi 9 feed từ `yolohome-*` sang tên ngắn (`temperature`, `event`, …). Backend và tài khoản Adafruit thì vẫn dùng `yolohome-*`.
  - Hậu quả:
    - Adafruit báo "Feed limit reached": tài khoản đã đủ 10 feed nên không tạo thêm được, và dữ liệu của mạch bị bỏ.
    - Web không có số đo, và lệnh từ web không tới được mạch.
  - Đã đổi lại về `yolohome-*`. Cần nạp lại firmware.
- **Ngưỡng cảnh báo nóng về 33 °C** (`firmware/include/control.h`):
  - Trước đây LED chuyển cam từ 33,8 °C và tắt dưới 33,5 °C, trong khi trang Thiết bị ghi "Cam khi ≥ 33°C". Trong khoảng 33,0 đến 33,7 °C, web và mạch không khớp.
  - Giờ LED chuyển cam từ 33 °C và tắt dưới 32,5 °C. Mức đỏ (> 45 °C) giữ nguyên. Cần nạp lại firmware.

**Backend**
- **Nhật ký ghi người thực hiện:**
  - Bảng `nhat_ky_hoat_dong` có thêm cột `user_id`. `upgrade_schema()` tự thêm cột này vào database cũ.
  - Lệnh gửi từ web và bằng giọng nói lưu lại tài khoản đã gửi.
  - `GET /api/activity/` trả thêm trường `user`: tên tài khoản, hoặc email nếu tài khoản không có tên.
  - Dòng do mạch, lịch hoặc AI tạo thì để trống.
- **Bắt buộc đăng nhập:**
  - API thiết bị, cảm biến, lịch hẹn giờ và nhật ký trả 401 nếu thiếu token hoặc token hết hạn (`main.py`, `require_user`).
  - Trước đây ai truy cập được backend cũng điều khiển được quạt mà không cần tài khoản.
  - Các API trong `/api/auth/` giữ nguyên như trước.
- **TinyML không lấn nhật ký nữa:**
  - Mạch nhắc lại trạng thái TinyML mỗi 60 giây. Trước đây lần nào cũng thành một dòng nhật ký (47/65 dòng), đẩy lệnh của người dùng ra khỏi danh sách.
  - Giờ nhật ký chỉ ghi khi trạng thái đổi (OK ↔ ALERT). Mọi kết quả vẫn được lưu đủ trong `lich_su_canh_bao_chay`.
- **Test:**
  - Thêm 3 test: bắt buộc đăng nhập, nhật ký ghi người thực hiện, TinyML chỉ ghi khi đổi trạng thái.
  - Các test cũ chạy bằng một tài khoản đã đăng nhập.
  - Tổng cộng 33 test qua.

**Frontend**
- **Biểu đồ trên Dashboard** (`components/SensorChart.tsx`, mới, dùng thư viện `recharts`):
  - Hai biểu đồ đường: nhiệt độ và độ ẩm trong 24 giờ qua.
  - Rê chuột thì hiện đường dóng và ô giá trị.
  - Đường bị ngắt khi mạch mất kết nối quá 5 phút.
- **Cột "Người thực hiện":** có ở trang Nhật ký và trong file CSV xuất ra. Trang Thiết bị hiện tên sau mỗi thao tác.
- **Xuất CSV cảm biến:** giờ tải qua axios để gửi kèm token, vì API cảm biến đã cần đăng nhập. Trước đây nút này mở thẳng đường dẫn.

**Tài liệu**
- **`Guide.md` (mới):** hướng dẫn thuyết trình, gồm:
  - 5 module chức năng.
  - Các tính năng AI: Face ID, giọng nói, TinyML, AI làm mát.
  - Đối chiếu 3 hướng chuyên môn: AI, CNPM, HTTT.
  - Quy tắc đăng ký và đăng nhập.
  - Cách backend xử lý key.
- **`CLAUDE.md`:**
  - Cách gọi Python trong venv trên Windows.
  - File `command_latency.csv`.
  - Webhook chưa dùng.
  - Mức chênh 0.05 của Face ID.
  - Thêm chỗ trỏ tới `Guide.md`.

### 20/11/2026: Face ID nhận diện khi đeo khẩu trang

**Phần Machine Learning (`ai-models/face/`, mới)**
- **Bộ script train**, dùng chung đoạn tiền xử lý với backend (`backend/face_engine.py`):
  - `collect.py`: tách ảnh từ video hoặc ảnh chụp bằng điện thoại (`--import`), hoặc quay bằng webcam. Tự xoay video bị nằm ngang hay lộn ngược. Bỏ khung không thấy mặt, mờ, tối. In bảng số ảnh của từng người.
  - `extract_features.py`: biến ảnh thành vector SFace, kèm khẩu trang giả lập. Dùng cho bộ ảnh công khai LFW (13.233 ảnh, 5.749 người) và ảnh của nhóm.
  - `train_adapter.py`: train adapter. Đây là mạng MLP nhỏ (khoảng 66 nghìn tham số), dùng hàm mất mát batch-hard triplet để kéo mặt có và không khẩu trang của cùng một người lại gần nhau. Script chỉ xuất adapter nếu nó tốt hơn SFace gốc.
  - `evaluate.py`: bảng thí nghiệm E0–E5. Script này cần quay thêm một buổi thứ hai, nên không nằm trong kế hoạch hiện tại.
- **Dữ liệu nhóm:** 5 thành viên quay **một lần**, mỗi người tối đa 3 kiểu: không đeo, khẩu trang, khẩu trang + kính (ai có kính). Ảnh và video chỉ nằm trên máy, không có trong git.
- **Kết quả train** (FRR là tỉ lệ từ chối nhầm người đúng, đo khi tỉ lệ nhận nhầm người lạ cố định 1%, trên LFW với khẩu trang giả lập):
  - Khi đeo khẩu trang: SFace gốc 2,14%, có adapter 1,38%.
  - Khi không đeo: giữ nguyên 0,09%.

**Backend**
- **Thay dlib (`face_recognition`) bằng OpenCV YuNet + SFace.** Thêm `backend/face_engine.py` và `backend/download_face_models.py` (tải 2 file model ONNX, có kiểm SHA256).
- **Bảng mới `face_templates`:** mỗi người nhiều mẫu, tối đa 20 mẫu mỗi loại (`plain`, `mask`, `synthetic_mask`). Bảng cũ `face_profiles` (dlib) không dùng nữa, **mọi người phải đăng ký Face ID lại**.
- **API mới:** `POST /api/auth/face/enroll`, `GET /api/auth/face/status`, `DELETE /api/auth/face`, và `POST /api/auth/face-login` (nhận 2–5 khung).
- **Vá lỗ hổng bảo mật:** đã xoá `POST /api/auth/register-face`. API cũ này chỉ cần email, nên ai biết email người khác cũng gắn được mặt mình vào tài khoản đó.
- **Ngưỡng nhận diện** là 0.60 (mặt thường) và 0.65 (khẩu trang), trong `backend/face_models/thresholds.json`.
  - Mức cũ 0.363 (OpenCV đề xuất) để người lạ lọt vào 19/30 lần trong phép thử bỏ-một-người.
  - Mức mới: thành viên vào được 30/30 khi không đeo, 24/24 khi đeo khẩu trang, 18/18 khi khẩu trang + kính; người lạ lọt 0 lần. Chi tiết ở `HUONG_FACE_ID.md` mục 4.4.
- **Adapter đã train:** `backend/face_models/adapter.npz`.
- **Chỉ dùng SQLite:** bỏ `face-recognition` và `psycopg2-binary` khỏi `backend/requirements.txt`.
- **Test:** thêm `backend/tests/test_face.py` (14 test, dùng engine giả nên không cần file model). Tổng cộng 30 test qua.

**Frontend**
- **`FaceCapture`:** mỗi lần bấm chụp nhiều khung, thu nhỏ ảnh về rộng 640px trước khi gửi.
- **`FaceSetup` (mới):** hộp thoại Face ID với các nút chụp khuôn mặt, thêm ảnh khẩu trang (tuỳ chọn) và xoá.
- **Login:** đăng nhập bằng 3 khung. Bỏ nút "Đăng ký Face ID cho tài khoản hiện có".
- **`ProtectedLayout`:** nút "Face ID" mở `FaceSetup`; tạo tài khoản xong thì tự mở.

**CI/CD**
- **`test.yml`:** cài thẳng `backend/requirements.txt`, không còn phải lọc `face-recognition` ra (vì đã bỏ dlib, không còn bước build lâu).

**Tài liệu**
- Thêm `CLAUDE.md`, `HUONG_FACE_ID.md` và file này.

## Những thứ không có trong git

| Thứ | Ở đâu | Cách có |
|---|---|---|
| Mật khẩu, key Adafruit IO | `backend/.env` (gitignore) | Chép từ `backend/.env.example` rồi điền |
| Wi-Fi, key cho board | `firmware/include/secrets.h` | Git chỉ giữ bản chữ mẫu (`your_...`). Điền giá trị thật trên máy và **không commit file này** |
| Tài khoản, lịch sử, mẫu Face ID | `backend/yolohome.db` | Backend tự tạo lần chạy đầu |
| Model YuNet + SFace (khoảng 38 MB) | `backend/face_models/*.onnx` | `python download_face_models.py` trong `backend/` |
| Ảnh, video khuôn mặt của nhóm | `ai-models/face/data/` | Dữ liệu cá nhân, chỉ để trên máy người train |
| Vector mặt, kết quả train | `ai-models/face/out/` | Chạy lại các script trong `ai-models/face/` |

## Cách chạy

Dùng venv của repo (PowerShell):

```powershell
cd backend
..\.venv\Scripts\Activate.ps1          # đầu dòng hiện (.venv)
python download_face_models.py         # chỉ lần đầu
python main.py                         # API ở http://localhost:8000
```

```powershell
cd frontend
npm install --legacy-peer-deps         # chỉ lần đầu
npm run dev                            # web ở http://localhost:5173
```

Train lại adapter khi có thêm video: xem `HUONG_FACE_ID.md` mục 7.

## Việc còn lại và hạn chế

- **Chưa thử Face ID bằng webcam thật.** Số liệu hiện có đo trên ảnh từ video quay bằng điện thoại.
- **Ngưỡng chỉ chọn trên 5 người,** nên khi demo cần thử lại. Chỉnh trong `backend/face_models/thresholds.json`.
- **Người mới chưa có trong dữ liệu train,** nếu chỉ đăng ký mặt thường: đeo khẩu trang vào được 19/24 lần, khẩu trang + kính chỉ 2/18. Nên đăng ký lúc đang đeo kính (nếu hay đeo), thêm ảnh khẩu trang thật, hoặc train lại adapter.
- **Chưa chống giả mạo:** giơ ảnh chụp người nhà trước webcam có thể đăng nhập được.
- **Đăng nhập còn thiếu:** chức năng quên mật khẩu, giới hạn số lần nhập sai, và thu hồi token khi đăng xuất (token còn dùng được tới khi hết hạn 7 ngày).
