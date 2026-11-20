# Face ID nhận diện cả khi đeo khẩu trang

Tài liệu thiết kế phần Machine Learning của YoloHome: đăng nhập bằng khuôn mặt, nhận ra người nhà cả khi đeo khẩu trang. Có một mô hình tự train, và có số liệu so sánh trước/sau khi train.

## 1. Mục tiêu và phạm vi

**Làm được:**
- Đăng nhập bằng khuôn mặt khi không đeo khẩu trang, và khi đeo khẩu trang y tế hoặc khẩu trang vải.
- Từ chối người lạ.
- Mỗi người đăng ký nhiều mẫu mặt.

**Không làm:**
- Chống giả mạo bằng ảnh chụp (webcam 2D không đo được độ sâu).
- Nhận diện khi đeo cả khẩu trang lẫn kính râm.
- Nhận diện trên mạch ESP32: toàn bộ chạy ở backend trên laptop.

**Tiêu chí thành công:**
- **Train có lợi:** trên validation (LFW nhóm B, khẩu trang giả lập), khi cố định tỉ lệ nhận nhầm người lạ (FAR) ở 1%, adapter phải giảm tỉ lệ từ chối nhầm (FRR) khi **đeo khẩu trang** so với SFace gốc, và không làm tệ FRR khi **không đeo khẩu trang**. Script train tự kiểm tra (mục 4.3).
- **Demo:** mỗi thành viên đăng nhập được khi đeo khẩu trang; người ngoài nhóm bị từ chối.

## 2. Tích hợp vào tài khoản

Face ID là **cách đăng nhập thêm**. Nó không thay mật khẩu:
- Tài khoản vẫn tạo bằng email và mật khẩu.
- Mật khẩu là phương án dự phòng khi trời tối, camera hỏng, hoặc nhận diện thất bại.

**Đăng ký tài khoản:**
1. Đăng ký email và mật khẩu như hiện tại.
2. Đăng ký xong, app vào Dashboard và mở hộp thoại Face ID. Người dùng có thể đóng để làm sau.
3. **Chỉ cần chụp mặt bình thường, không đeo khẩu trang.** Ai hay đeo kính thì cứ đeo như mọi ngày. Máy tự chụp 10 khung trong khoảng 4 giây, nhắc người dùng quay đầu nhẹ sang trái, sang phải.
   - Mỗi ảnh được server tự vẽ thêm 2 mẫu khẩu trang giả lập (mục 4.2), nên **đeo khẩu trang vẫn đăng nhập được** mà không phải chụp lúc đeo.
   - Xong thì hiện số ảnh đã lưu, và ảnh nào bị loại vì sao (mờ, tối, mặt quá nhỏ…).

**Đăng nhập:** nút "Đăng nhập bằng khuôn mặt" ở trang Login. Máy tự chụp 3 khung, mỗi khung cách nhau khoảng 300 ms. Nếu thất bại, báo rõ lý do:
- Không thấy mặt.
- Không khớp tài khoản nào.
- Giống hai người quá, hãy tháo khẩu trang hoặc dùng mật khẩu.

**Quản lý:** nút "Face ID" trên Dashboard cho phép:
- Xem số ảnh đã lưu.
- Chụp thêm, ví dụ một lần có kính, một lần không kính.
- Thêm ảnh đeo khẩu trang thật (tuỳ chọn), cho ai hay bị từ chối khi đeo khẩu trang.
- Xoá hết để đăng ký lại.

**Đã bỏ:** nút "Đăng ký Face ID cho tài khoản hiện có" ở trang Login và API `/api/auth/register-face`. API này chỉ cần email, không cần đăng nhập, nên ai biết email người khác cũng gắn được mặt mình vào tài khoản đó rồi đăng nhập bằng mặt. Từ nay chỉ đăng ký mặt được **sau khi đã đăng nhập**.

## 3. Kiến trúc

```
Ảnh webcam (JPEG, rộng 640px)
  → YuNet: tìm mặt + 5 điểm mốc (2 mắt, mũi, 2 khoé miệng)
  → alignCrop: xoay, cắt về ảnh mặt chuẩn 112×112
  → SFace: vector 128 số                        ← mạng có sẵn, không train
  → Adapter (MLP nhỏ): vector 128 số mới        ← PHẦN NHÓM TỰ TRAIN
  → so cosine với các mẫu đã lưu của từng người → quyết định
```

- **Hai model có sẵn trong OpenCV.** YuNet và SFace là `cv2.FaceDetectorYN` và `cv2.FaceRecognizerSF`, file ONNX lấy từ OpenCV Zoo (github.com/opencv/opencv_zoo). SFace khoảng 37 MB, YuNet dưới 1 MB. Repo đã có OpenCV nên **bỏ được dlib / `face_recognition`**. Đây cũng là thư viện mà CI hiện phải loại ra vì build quá lâu.
- **Lưu vector SFace gốc, không lưu vector đã qua adapter.** Khi train lại adapter, mọi người không phải đăng ký mặt lại. Adapter được áp lúc so sánh, chỉ tốn vài phép nhân ma trận.
- **Không lưu ảnh mặt ở backend**, chỉ lưu vector.
- **Train và chạy thật dùng chung một đoạn tiền xử lý.** Script train gọi đúng `backend/face_engine.py` để tách đặc trưng, tránh trường hợp lúc train cắt mặt một kiểu mà lúc chạy thật cắt kiểu khác.

## 4. Phần train

### 4.1 Dữ liệu

| Nguồn | Nội dung | Dùng để |
|---|---|---|
| Nhóm (quay **một lần**) | Mỗi người 3 kiểu: không đeo gì, đeo khẩu trang, khẩu trang + kính (ai có kính). Mỗi kiểu một video điện thoại 20–30 s, hoặc ảnh chụp, hoặc quay webcam máy này | Train adapter riêng cho nhà |
| LFW (ảnh công khai, khoảng 5.700 người) | Chia theo người: nhóm A 80%, nhóm B 20% | A: train adapter. B: validation (chọn epoch, đo trước/sau train) |

- **Tách khung hình:**
  - Video: cứ 0,3 giây lấy 1 khung.
  - Ảnh chụp: xét hết.
  - Chỉ giữ khung có đúng một mặt đủ rõ. Một video 25 giây cho khoảng 60–80 ảnh.
- **Chia dữ liệu theo người:** người thuộc LFW nhóm B không xuất hiện khi train.
- **Không có tập kiểm tra trên mặt người nhà.** Muốn có, phải quay thêm một lần lúc khác, chỗ khác (buổi 2), rồi chạy `evaluate.py`. Kế hoạch hiện tại bỏ bước này.
- **Quyền riêng tư:** ảnh mặt thành viên chỉ để trên máy (`ai-models/face/data/`, đã gitignore). Không commit, không đưa lên Drive công khai. Phải có sự đồng ý của từng người, và xoá sau khi xong đồ án.

### 4.2 Khẩu trang giả lập (tăng cường dữ liệu)

- **Cách vẽ:** sau `alignCrop`, mũi và miệng luôn nằm ở vị trí gần như cố định trên ảnh 112×112. Chỉ cần vẽ một đa giác từ ngay dưới sống mũi xuống cằm, phủ hai má.
- **Đa dạng hoá:** lệch vị trí ngẫu nhiên vài pixel, màu ngẫu nhiên (trắng, xanh y tế, đen, xám), thêm chút nhiễu.
- **Dùng ở hai chỗ:**
  - Tạo dữ liệu đeo khẩu trang cho LFW khi train.
  - Tạo mẫu `synthetic_mask` khi người dùng bỏ qua bước đeo khẩu trang thật.
- **Tăng cường thêm khi train:** đổi độ sáng và độ tương phản, lật ngang.
- **Hạn chế cần ghi trong báo cáo:** khẩu trang thật còn làm lệch các điểm mốc lúc YuNet dò mặt, còn khẩu trang vẽ sau khi căn mặt thì không gây ra điều này.

### 4.3 Mô hình train: adapter

Đây là mạng MLP dư (residual), đặt sau SFace:

```
y = normalize( x + W2 · ReLU(W1 · x + b1) + b2 )      x: vector SFace 128 số (đã chuẩn hoá)
W1: 128→256, W2: 256→128 (khoảng 66 nghìn tham số), W2 và b2 khởi tạo bằng 0
```

- **Vì sao khởi tạo bằng 0:** lúc đầu y = x, tức là đúng bằng SFace gốc. Train chỉ đổi khi việc đổi giúp ích, nên khó tệ hơn hệ thống không train.
- **Hàm mất mát: batch-hard triplet loss với khoảng cách cosine,** biên 0.2. Trong mỗi batch, mỗi vector được so với vector cùng người xa nhất và vector người khác gần nhất. Dễ giải thích trong báo cáo: kéo mặt có và không khẩu trang của cùng một người lại gần nhau, đẩy người khác ra xa.
- **Batch:** 32 người × 4 ảnh mỗi người, trộn ảnh có và không khẩu trang. Mỗi batch chủ động ghép ảnh không khẩu trang (anchor) với ảnh đeo khẩu trang của cùng người đó (positive).
- **Optimizer:** Adam, lr 1e-3, weight decay 1e-4.
- **Dừng sớm** dựa vào FRR khi đeo khẩu trang (ở FAR 1%) trên validation (LFW nhóm B).
- **Tốc độ:** train bằng PyTorch trên CPU, chỉ vài phút, vì đầu vào là vector chứ không phải ảnh.
- **Xuất model:** trọng số ra `adapter.npz`. Backend chạy bằng numpy, không cần cài PyTorch.
- **Kiểm tra khớp kết quả:** script train so kết quả numpy với PyTorch trên 1.000 vector, sai khác phải dưới 1e-5.
- **Cổng xuất:** chỉ chép `adapter.npz` sang backend nếu adapter thắng SFace gốc trên validation. Thua thì vẫn ghi kết quả vào báo cáo, và backend chạy SFace gốc.

Train hai biến thể:
- **Adapter chung:** chỉ train trên LFW. Khi nhà có thêm người, không cần train lại.
- **Adapter riêng cho nhà:** LFW + dữ liệu nhóm. Khi có thêm người phải train lại bằng script, offline. Backend không tự train.

Không có tập kiểm tra của nhóm, nên không so được hai biến thể trên mặt người nhà. Thứ tự chọn:
1. Adapter riêng, nếu qua cổng.
2. Nếu không, adapter chung.
3. Cả hai không qua thì dùng SFace gốc.

### 4.4 Ngưỡng và số liệu báo cáo

- **Hai ngưỡng cosine:**
  - `plain`: so với mẫu không khẩu trang.
  - `mask`: so với mẫu khẩu trang thật hoặc giả lập.
- **Khoảng cách tối thiểu (`margin`, 0.05)** giữa người khớp nhất và người khớp nhì.
- **Giá trị: `plain` 0.60, `mask` 0.65**, ghi trong `backend/face_models/thresholds.json`. Chọn bằng phép thử bỏ-một-người dưới đây. Mức 0.363 mà OpenCV đề xuất (đo trên LFW) quá thấp: ảnh cùng camera, cùng phòng giống nhau hơn nhiều.
- **Chỉnh khi demo**, mỗi lần 0.02:
  - Người nhà đeo khẩu trang hay bị từ chối: hạ `mask`, hoặc cho người đó thêm ảnh khẩu trang thật.
  - Người lạ lọt vào: tăng ngưỡng.

**Phép thử bỏ-một-người** (5 thành viên, mỗi người 6 lần đăng nhập × 3 khung cho mỗi kiểu, chỉ đăng ký mặt thường):
- **Thành viên:** adapter đang dùng, mặt của họ có trong dữ liệu train.
- **Người lạ:** với từng người X, train lại adapter không có X, xoá mẫu của X, rồi cho X đăng nhập. X bị nhận thành người khác thì tính là lọt.

| Ngưỡng plain / mask | Thành viên vào được (không đeo / khẩu trang / khẩu trang + kính) | Người lạ lọt vào |
|---|---|---|
| 0.363 / 0.363 (OpenCV) | 30/30, 24/24, 18/18 | **19/30, 13/24, 16/18** |
| 0.55 / 0.55 | 30/30, 24/24, 18/18 | 0/30, 1/24, 2/18 |
| **0.60 / 0.65 (đang dùng)** | **30/30, 24/24, 18/18** | **0/30, 0/24, 0/18** |

- **Điểm thật sẽ thấp hơn:** khung đăng nhập lấy từ cùng video với lúc đăng ký, nên điểm của thành viên cao hơn khi đăng nhập thật bằng webcam vào hôm khác.
- **Người mới chưa có trong dữ liệu train** (cùng phép thử, ở ngưỡng 0.60 / 0.65):
  - Không đeo: vào được 30/30.
  - Khẩu trang: 19/24.
  - Khẩu trang + kính: chỉ 2/18, vì lúc đăng ký họ không đeo kính.
  - Cách khắc phục: khi nhà có người mới, cho họ đăng ký lúc đeo kính (nếu hay đeo) và thêm ảnh khẩu trang thật, hoặc quay video rồi train lại adapter.

**Số liệu cho báo cáo**, không cần quay thêm:
- **Bảng bỏ-một-người ở trên.**
- **Từ `out/train_<variant>.json`:**
  - FRR ở FAR = 1% của SFace gốc và của adapter trên LFW nhóm B, cho cặp không khẩu trang và cặp có khẩu trang (giả lập).
  - Diễn biến theo từng epoch.
- **Đo tay khi demo:**
  - Mỗi người thử đăng nhập vài lần với từng kiểu (không đeo / khẩu trang / khẩu trang + kính), đếm số lần được nhận.
  - Vài người ngoài nhóm thử đăng nhập, đếm số lần bị từ chối.
  - Thời gian một lần đăng nhập.

`evaluate.py` (bảng E0–E5, biểu đồ ROC) vẫn còn trong repo nhưng không nằm trong kế hoạch, vì cần buổi 2.

## 5. Backend (đã làm)

| File | Thay đổi |
|---|---|
| `backend/face_engine.py` (mới) | Nạp YuNet, SFace, `adapter.npz` (nếu có), `thresholds.json`. Hàm: `detect`, `embed`, `adapt`, `probe`, `masked_vectors`, `match`, `quality_reason` |
| `backend/face_models/` (mới) | `*.onnx` (gitignore, tải bằng script, kiểm SHA256), `adapter.npz` (chép từ `out/adapter_home.npz`), `thresholds.json` (commit vì nhỏ) |
| `backend/download_face_models.py` (mới) | Tải hai file ONNX |
| `backend/models.py` | Bảng mới `face_templates`. Bảng `face_profiles` cũ để nguyên, không dùng nữa: vector dlib không chuyển sang SFace được, mọi người đăng ký lại |
| `backend/routes/auth.py` | API mới. `register-face` chỉ còn nhận người đã đăng nhập. `/me` lấy `has_face` từ `face_templates` |
| `backend/requirements.txt` | Bỏ `face-recognition` |
| `backend/tests/test_face.py` (mới) | Test logic bằng engine giả, không cần file ONNX nên chạy được trên CI |

Bảng mới (`create_all()` tự tạo vì là bảng mới, không cần `ALTER`):

```
face_templates: id, user_id → nguoi_dung.id, kind ('plain' | 'mask' | 'synthetic_mask'),
                model ('sface-2021dec'), embedding (128 float32), created_at
```

Đăng nhập chỉ so với mẫu có `model` trùng model đang chạy. Đổi model thì mẫu cũ tự bị bỏ qua, mọi người đăng ký lại.

Mỗi người giữ tối đa 20 mẫu cho mỗi loại. Đủ 20 thì mẫu cũ nhất bị thay.

API:

```
POST   /api/auth/face/enroll   (cần đăng nhập)  {kind: "plain"|"mask", images: [≤12 ảnh base64]}
       → {accepted: 9, rejected: [{index: 3, reason: "Ảnh bị mờ"}], counts: {plain, mask, synthetic_mask}}
       Với mẫu "plain", tự sinh thêm 2 mẫu synthetic_mask.
GET    /api/auth/face/status   (cần đăng nhập)  → {has_face, counts}
DELETE /api/auth/face          (cần đăng nhập)  → xoá hết mẫu của mình
POST   /api/auth/face-login    {images: [2–5 ảnh base64]}
       → {token, user, score, matched_kind}  hoặc 401 kèm lý do
```

`/api/auth/register-face` cũ (chỉ cần email) đã bị xoá, xem mục 2.

Mã lỗi:
- 400: không ảnh nào dùng được, kèm lý do.
- 401: chưa đăng nhập, hoặc mặt không khớp / giống nhiều người.
- 404: chưa ai đăng ký mặt.
- 413: ảnh quá lớn.
- 503: máy chủ chưa tải model ONNX.

Ảnh bị loại khi:
- Không thấy mặt, hoặc có nhiều hơn một mặt.
- Mặt rộng dưới 80 px: "lại gần hơn". Chỉ áp dụng khi đăng ký.
- Ảnh bị mờ: phương sai Laplacian thấp.
- Ảnh quá tối.

Logic đăng nhập:

```
for mỗi khung có đúng 1 mặt:  v = adapt(embed(khung))
for mỗi người u:              s[khung][u] = max cosine(v, adapt(mẫu)) trên các mẫu của u
score[u] = trung bình s[.][u] qua các khung (cần ≥ 2 khung có mặt)
u1, u2 = người điểm cao nhất, cao nhì
nhóm = "plain" nếu mẫu khớp nhất của u1 là plain, ngược lại "mask"
chấp nhận nếu score[u1] ≥ ngưỡng[nhóm]  và  score[u1] − score[u2] ≥ margin
```

## 6. Frontend

| File | Thay đổi |
|---|---|
| `components/FaceCapture.tsx` | Thêm `frames`, `intervalMs`. `onSubmit(images: string[])`. Thu nhỏ ảnh về rộng 640px. Hiện "Đang chụp 4/10" |
| `components/FaceSetup.tsx` (mới) | Hộp thoại Face ID ở mục 2: chụp mặt thường, thêm ảnh khẩu trang (tuỳ chọn), xoá. Gọi `face/status`, `face/enroll`, `face`. Hiện ảnh bị loại và lý do |
| `components/ProtectedLayout.tsx` | Nút "Face ID" mở `FaceSetup`. Tự mở khi vừa tạo tài khoản |
| `pages/Login.tsx` | Bỏ nút đăng ký Face ID. Đăng nhập bằng mặt dùng 3 khung |
| `services/api.ts` | `faceEnroll`, `faceStatus`, `faceDelete`, `faceLogin(images)`. Thêm `score`, `matched_kind` vào kết quả đăng nhập |

`face-api.js` trong `package.json` không dùng ở đâu, có thể gỡ.

## 7. Script train (`ai-models/face/`)

| File | Việc |
|---|---|
| `common.py` | Đường dẫn, cách chia LFW, hàm tính FAR/FRR dùng chung |
| `collect.py` | Tách ảnh từ video/ảnh thành viên gửi (`data/raw/`) hoặc quay webcam. Chỉ lưu khung có đúng 1 mặt đủ rõ. In số ảnh mỗi người |
| `extract_features.py` | Ảnh → vector SFace (qua `backend/face_engine.py`), kèm khẩu trang giả lập |
| `train_adapter.py` | Train adapter, chỉ xuất khi thắng SFace gốc trên validation |
| `evaluate.py` | Chạy E0–E5. Cần buổi 2, không dùng trong kế hoạch hiện tại |

Cách chạy, từ thư mục gốc repo. Cần Python có `numpy`, `opencv-python`, `torch`; xem `ai-models/face/requirements.txt`.

```
python backend/download_face_models.py                  # 1 lần: YuNet + SFace (~38 MB)
cd ai-models/face
python extract_features.py lfw                          # 1 lần: tải LFW (~180 MB), khoảng 10 phút
python train_adapter.py --variant generic               # adapter chung, vài phút

# Video/ảnh thành viên gửi: xếp vào data/raw/<người>/<điều kiện>/, điều kiện là plain, mask, mask_glasses
#   data/raw/an/plain/video.mp4    data/raw/an/mask/IMG_0012.jpg    data/raw/an/mask_glasses/...
python collect.py --import                              # xử lý hết, in bảng số ảnh mỗi người
# Hoặc ngồi trước webcam máy này (30 giây, bấm q để dừng sớm):
python collect.py --person an --condition plain

python extract_features.py team
python train_adapter.py --variant home                  # adapter riêng cho nhà
```

- **Tên thư mục người:** chữ thường không dấu, ví dụ `an`, `binh_nguyen`.
- **Một kiểu có thể chứa nhiều file:** một thư mục điều kiện được để nhiều video và ảnh cùng lúc.
- **Tự xoay:** video hoặc ảnh bị nằm ngang hay lộn ngược được tự xoay lại.
- **Chạy lại không trùng:** chạy lại `--import` không tạo ảnh trùng, nên cứ thêm file rồi chạy lại.
- **Bảng cuối:** đếm cả ảnh lấy từ video, ảnh chụp và ảnh webcam. Ô có dấu `*` là dưới 50 ảnh. Dấu `-` ở cột `mask_glasses` là người không có kính, không sao.

Kết quả nằm trong `out/`:
- `adapter_<variant>.npz`: trọng số adapter. Chỉ có khi adapter qua cổng.
- `train_<variant>.json`: số liệu trước/sau train và từng epoch.

Thư mục `data/` và `out/` được gitignore, trừ `report.json`.

### Hướng dẫn quay video (gửi cho từng thành viên)

Mỗi người quay **một lần, 3 video**, mỗi video 20–30 giây:

1. **Không đeo gì.**
2. **Đeo khẩu trang** kín mũi.
3. **Khẩu trang + kính:** chỉ ai có kính cận hoặc kính thường; không dùng kính râm. Không có kính thì bỏ qua video này.

Không tiện quay video thì chụp ảnh cũng được: mỗi kiểu khoảng 30–50 ảnh, mỗi ảnh một góc khác nhau. Video vẫn tốt hơn vì cho nhiều ảnh hơn.

Cách quay:
- Dùng camera trước của điện thoại, cầm cách mặt khoảng 50 cm (một sải tay). Mặt chiếm khoảng 1/3 khung hình.
- Đủ sáng, đừng ngồi quay lưng ra cửa sổ. Trong khung chỉ có một người.
- Từ từ quay đầu nhẹ sang trái, sang phải, ngẩng lên, cúi xuống, có thể nói chuyện. Đừng ngồi im.

Gửi file **qua tin nhắn riêng** cho người chạy train, không gửi vào nhóm chung hay Drive công khai. Ghi kèm tên và kiểu, ví dụ "An, khẩu trang + kính". File iPhone nếu không đọc được: gửi qua Zalo/Messenger (tự đổi sang mp4/jpg), hoặc chọn Cài đặt > Camera > Định dạng > Tương thích nhất.

Người chạy train làm như sau:
1. Bỏ file vào `data/raw/<tên>/plain`, `mask` hoặc `mask_glasses`.
2. Chạy `python collect.py --import`.
3. Đọc dòng "bỏ qua ..." để biết file nào có vấn đề (không thấy mặt, mờ, tối).
4. Xem bảng cuối để biết còn thiếu ảnh của ai.

Khi làm backend (giai đoạn 2), chép `adapter_<variant>.npz` thành `backend/face_models/adapter.npz`, chỉ khi qua cổng ở mục 4.3. Ngưỡng nằm trong `backend/face_models/thresholds.json`: `{"plain": 0.60, "mask": 0.65, "margin": 0.05}` (mục 4.4).

## 8. Thứ tự làm

| Giai đoạn | Việc | Xong khi |
|---|---|---|
| 0 | Tải model ONNX. Thu video/ảnh của nhóm (một lần) | Bảng cuối của `collect.py --import` không còn ô `*` |
| 1 | `face_engine.py`, `extract_features.py`, train adapter chung | Có `out/train_generic.json` (đã xong) |
| 2 | Backend: bảng, API, test | `python -m pytest -q tests` qua (đã xong) |
| 3 | Frontend: hộp thoại Face ID, đăng nhập 3 khung, bỏ nút đăng ký ở Login | `npm run build` qua, thử tay bằng webcam |
| 4 | Train adapter riêng cho nhà | Có `out/train_home.json`, adapter qua cổng |
| 5 | Đưa `adapter.npz` + `thresholds.json` vào backend. Tập demo, chỉnh ngưỡng, đo tay, viết báo cáo | Đeo khẩu trang đăng nhập được, người lạ bị từ chối |

Giai đoạn 2–3 làm song song với giai đoạn 4 được. Khi chưa có `adapter.npz`, backend chạy SFace gốc với ngưỡng tạm.

## 9. Giới hạn (ghi vào báo cáo)

- **Chống ảnh chụp:** chưa có. Giơ ảnh chụp người nhà trước webcam có thể đăng nhập được. Hướng mở rộng: bắt nháy mắt hoặc quay đầu giữa các khung.
- **Khẩu trang + kính râm:** gần như hết thông tin, hệ thống sẽ từ chối.
- **Không có tập kiểm tra trên mặt người nhà:**
  - Số liệu trước/sau train đo trên LFW với khẩu trang giả lập.
  - Hiệu quả với khẩu trang thật chỉ thấy qua demo và số đo tay.
  - Ngưỡng chỉ được chọn bằng phép thử bỏ-một-người trên 5 người (mục 4.4), nên cần thử lại khi demo.
- **Dữ liệu ít người:** số đo tay có sai số lớn. LFW là ảnh báo chí, khác ảnh webcam.
- **File cũ trong git:** `ai-models/faces_data.pkl` đang nằm trong git, chứa vector mặt của bản thử cũ, nên xoá khỏi git.
