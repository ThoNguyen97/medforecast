# Datasheet — bộ huấn luyện MedForecast v1.0

Viết theo khung *Datasheets for Datasets* (Gebru et al., 2021), rút gọn cho
phạm vi đồ án.

## 1. Động cơ

Tạo ra để huấn luyện và kiểm định mô hình dự báo số lượt bệnh hô hấp theo
tháng (Tầng 1 của DSS MedForecast), và để hội đồng / người tái sử dụng kiểm
chứng độc lập bảng số công bố mà không cần truy cập HIS. Người tạo: sinh viên
thực hiện đồ án; không có tài trợ.

## 2. Thành phần

- 3 khối ICD-10 (J00-J06, J09-J18, J20-J22), 20 mã ICD 3 ký tự.
- Tháng 2019-01 → 2026-09 (92 tháng; kỳ 2026-09 đang mở, `is_complete = 0`).
  Kỳ đã chốt: 91–92 tháng/khối.
- 278 dòng mức khối, 938 dòng mức mã, 20 dòng tỷ trọng.
- Thời tiết: 93 tháng có dữ liệu, một trạm đại diện.
- Không có mẫu bị thiếu ở cột `cases`; thiếu ở thời tiết là tháng chưa có
  quan trắc.
- Không có nhãn "đúng/sai": bài toán là dự báo chuỗi thời gian, nhãn là chính
  giá trị tháng kế tiếp.

## 3. Quy trình thu thập

- Số lượt lấy từ bảng khám/điều trị của HIS bằng thủ tục T-SQL
  `usp_MedForecast_DayDuLieu` (mã trong `sql_his/`), đếm DISTINCT lượt theo
  (tháng, khối) và (tháng, mã), đẩy sang cơ sở trung gian STA; app nạp về
  bằng tài khoản chỉ đọc.
- Thời tiết tải từ Open-Meteo archive API theo ngày rồi gộp tháng.
- Thời điểm xuất ghi trong `manifest.json`; sha256 từng file để đối chiếu.

## 4. Tiền xử lý và làm sạch

- Gộp mã ICD vào khối theo bảng phân cấp cố định; loại lượt không có chẩn đoán
  chính thuộc J00–J22.
- Cờ `is_covid` cho 2020-01 → 2021-12; các thành viên hồi quy loại các tháng
  này khỏi ước lượng (không xoá khỏi file).
- Cờ `is_complete` để loại kỳ đang mở khỏi huấn luyện.
- Không nội suy, không làm mượt, không cắt ngoại lai — mô hình nhìn đúng số
  HIS ghi.
- Không có bước "chia train/test" cố định trong file: giao thức chia là
  walk-forward mở rộng cửa sổ (xem README) và được thực thi trong `train.py`.

## 5. Khử định danh và đạo đức

- Toàn bộ là **số đếm theo tháng**; không có mã bệnh nhân, ngày sinh, giới,
  địa chỉ, số hồ sơ, ngày khám. Không có trường nào cho phép truy ngược cá nhân.
- Bản phát hành gộp toàn quốc (không tách tỉnh/huyện).
- **Ô nhỏ (cases < 5)** ở mức mã được giữ nguyên, có chủ đích: đó là đếm trên
  toàn bệnh viện theo tháng, không kết hợp được với thuộc tính nào khác trong
  bộ này để nhận dạng ai; che ô nhỏ sẽ phá chuỗi thời gian mà mô hình cần.
  Nếu phát hành ra ngoài bệnh viện kèm theo tách tỉnh hoặc tuổi/giới thì phải
  áp ngưỡng k = 5.
- Dữ liệu thuộc bệnh viện; điều kiện sử dụng và công bố do bệnh viện quyết
  định — ghi rõ căn cứ cho phép khi nộp đồ án. Không dùng để suy đoán về cá
  nhân hay cơ sở khác.

## 6. Hạn chế đã biết

- **Đứt gãy chế độ ghi nhận đầu 2025** (Đ11): phân cấp chăm sóc và cách nhập
  chẩn đoán thay đổi, kéo mức nền J09-J18 lên ~3,7×; mô hình học được nhờ xu
  hướng + hệ số lệch nhưng người dùng phải biết đây là thay đổi hành chính, không
  phải dịch.
- **Giai đoạn COVID 2020–2021** không đại diện; đã gắn cờ.
- Một bệnh viện, một trạm thời tiết: không suy rộng cho địa bàn khác nếu không
  huấn luyện lại.
- Chuỗi ngắn (92 tháng, 7 chu kỳ mùa): đủ cho mô hình thống kê, **không đủ cho
  deep learning** — đó là lý do không dùng LSTM.
- Số lượt ≠ số bệnh nhân: một người khám hai lần trong tháng là hai lượt.
- Kỳ đang mở luôn thấp hơn thật; không dùng để so xu hướng.

## 7. Bảo trì và phiên bản

- Phiên bản `1.0` (11/09/2026). Xuất lại khi có tháng mới bằng
  `python -m app.forecasting.dataset`; tăng phiên bản khi đổi định nghĩa cột
  hoặc quy tắc gộp, không tăng khi chỉ thêm tháng.
- Kết quả huấn luyện chính thức trên bản này: RelMAE mức mã 0,500 (top-down
  động), mức nhóm 0,516 / 0,377 / 0,541 — `docs/KetQua_Backtest_ChonCauHinh.md`.

## 8. Cách trích dẫn

[Họ tên tác giả] (2026). *Bộ huấn luyện MedForecast v1.0 — số lượt bệnh hô hấp
theo tháng và thời tiết, 2019–2026*. Đồ án tốt nghiệp, UIT–VNU-HCM.
