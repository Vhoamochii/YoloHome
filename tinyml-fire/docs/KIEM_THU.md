# V2: model ưu tiên nhiệt độ

Kết quả hiện tại: `temperature_verification.json` và `models/temperature_priority/training_report.json`.

Model được fit trên cả hai CSV gốc (108 dòng, loại 1 dòng 85,7°C ngoài miền DHT20, bỏ mẫu trùng còn 79 mẫu). Không tự sinh dữ liệu, không sửa nhãn. Các thống kê trên 79 mẫu chỉ là kết quả in-sample, không phải độ chính xác trên dữ liệu chưa thấy.

Ở ngưỡng score 0,9: TN=53, FP=0, FN=5, TP=21 trên dữ liệu fit. Ưu tiên nhiệt độ đồng nghĩa model mới sẽ bỏ sót một số mẫu đã gán nhãn 1 ở nhiệt độ thấp trong dữ liệu cũ. Muốn đánh giá ứng dụng thật cần dữ liệu độc lập đại diện môi trường và mục tiêu mới.

Các báo cáo build/model cũ ở `legacy/` thuộc V1. Chưa cross-compile hoặc kiểm thử phần cứng cho V2 trong phiên này. Không suy diễn các báo cáo V1 thành kết quả build V2.
