# TinyML Fire V2 — ưu tiên nhiệt độ

Model mới: **logistic regression có ràng buộc**, suy luận trực tiếp trên Yolo UNO. Trọng số được học từ hai CSV gốc; không tự sinh dữ liệu. Nhiệt độ tác động dương; thay đổi toàn dải độ ẩm chỉ ảnh hưởng tương đương khoảng 1°C.

- Firmware đọc DHT20 thật qua I2C GPIO11/12, không cần train trên mạch.
- Model đang dùng: `firmware/include/temperature_model.h`, ID **7129a5137abe**.
- Công thức: `score = sigmoid(a*(T-35)/10 + c*(RH-50)/50 + b)`.
- Hệ số đi kèm: a=3.36644578, c=-0.168322295, b=1.30093718.
- Chỉnh cảnh báo tại **firmware/include/alarm_config.h**: bật ML ở 0,90; nhả ở 0,80; 3 mẫu liên tiếp. Luật nhiệt 45/43°C là phần độc lập.
- Gateway, tài khoản trong `.env`, COM và ba feed giữ nguyên. Không sửa nguồn firmware/backend gốc của nhóm.
- `scripts/train_model.py` nay chạy trainer ưu tiên nhiệt độ, không còn train mạng Dense V1. Không cần TensorFlow cho V2.
- Model H5/TFLite/Dense V1 giữ để tham khảo; không được chạy bởi firmware V2.

Hướng dẫn cập nhật, công thức, chỉnh ngưỡng và train lại: **[HUONG_DAN_CHAY_THUC_TE.md](HUONG_DAN_CHAY_THUC_TE.md)**.

Kiểm tra: [docs/KIEM_THU.md](docs/KIEM_THU.md). Bản V2 đã kiểm tra C++ trên máy tính và protocol; chưa cross-compile/nạp phần cứng trong phiên cập nhật này.

Score là điểm phân loại thử nghiệm, không phải xác suất cháy được hiệu chuẩn. Dữ liệu gốc nhỏ và chưa đại diện môi trường thật; còn bỏ sót ngay trên dữ liệu fit. Không dùng thay đầu báo cháy đã kiểm định.
