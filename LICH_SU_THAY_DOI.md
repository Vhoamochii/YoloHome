# Lịch sử thay đổi và chức năng hiện tại

File này ghi lại hệ thống đang làm được gì và lần thay đổi nào sửa gì. Có thay đổi mới thì thêm một mục ở đầu phần "Lịch sử thay đổi".

Tài liệu liên quan:
- `HUONG_FACE_ID.md`: thiết kế và số liệu chi tiết của Face ID.
- `CLAUDE.md`: kiến trúc và lệnh cho người viết code.
- `README.md` và `SETUP.md`: đã cũ một phần, code là nguồn đúng nhất.

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
- **Nhật ký hoạt động:** xem lịch sử lệnh và cảm biến, xuất CSV.
- **Điều khiển bằng giọng nói** trên web.
- **Cảnh báo cháy TinyML:** mô hình chạy ngay trên board, backend lưu lịch sử cảnh báo.
- **Màn hình LCD trên board.**

### Tài khoản và Face ID
- **Tài khoản:** đăng ký và đăng nhập bằng email + mật khẩu.
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
- **`SECRET_KEY`:** backend ký token đăng nhập bằng `SECRET_KEY`. Nếu `backend/.env` không đặt `SECRET_KEY`, backend dùng giá trị mặc định ghi sẵn trong code, mà repo đang công khai. Nên đặt một chuỗi ngẫu nhiên riêng.
- **`ai-models/faces_data.pkl`:** vector mặt của bản thử cũ, đang nằm trong git. Nên xoá khỏi repo.
