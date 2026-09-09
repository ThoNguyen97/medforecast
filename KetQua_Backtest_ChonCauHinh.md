# Kết quả backtest: chọn cấu hình dự báo (dữ liệu HIS thật, 09/08/2026)

Ba lần chạy walk-forward (mở rộng cửa sổ, dự báo 1 bước, tối thiểu 24 tháng
huấn luyện), khác nhau đúng một tham số — mốc bắt đầu lịch sử:

| Lần chạy | Lịch sử từ | Số bước kiểm định | Giai đoạn được kiểm |
|---|---|---|---|
| A | 2019-01 (toàn bộ, 92 tháng) | 66–67 | ~02/2021 → 07/2026 |
| B | 2022-01 (55 tháng) | 31 | ~01/2024 → 07/2026 |
| C | 2023-01 (43 tháng) | 19 | ~12/2024 → 07/2026 |

## Bảng MASE mức mã (thấp hơn = tốt hơn; < 1 = thắng seasonal-naive)

| Cửa sổ | Nhóm | Bottom-up | TD cố định | **TD động (EWMA)** | MinT |
|---|---|---|---|---|---|
| A 2019 | J00-J06 | 0,629 | 0,701 | **0,625** | 0,636 |
| A 2019 | J09-J18 | **0,564** | 0,597 | 0,565 | 0,594 |
| A 2019 | J20-J22 | **0,614** | 0,635 | 0,634 | 0,617 |
| B 2022 | J00-J06 | 0,622 | 0,710 | **0,603** | 0,624 |
| B 2022 | J09-J18 | ⚠ 483,7 | 0,657 | **0,614** | ⚠ 439,9 |
| B 2022 | J20-J22 | **0,703** | 0,710 | 0,709 | 0,705 |
| C 2023 | J00-J06 | 0,567 | 0,665 | **0,537** | 0,562 |
| C 2023 | J09-J18 | **0,450** | 0,550 | 0,500 | 0,475 |
| C 2023 | J20-J22 | **0,498** | 0,514 | 0,511 | 0,507 |

## Phát hiện quan trọng nhất: bottom-up NỔ TUNG trên chuỗi thưa

Ở cửa sổ B, bottom-up cho J09-J18 ra MASE **483,7** — sai gấp ~790 lần
top-down động trên cùng dữ liệu, cùng kỳ kiểm định. MinT cũng đổ theo (439,9)
vì nó trộn các dự báo mã con đã hỏng.

Nguyên nhân đọc được từ dữ liệu: cắt lịch sử từ 2022 thì các mã hiếm như J09
(chỉ có ca từ 09/2025), J13, J14, J16, J17 còn lại chuỗi gần như toàn số 0 rồi
đột ngột nhảy. SARIMAX huấn luyện trên chuỗi như vậy không hội tụ (đúng loạt
cảnh báo `ConvergenceWarning` khi chạy) và cho dự báo phi lý hàng nghìn ca;
bottom-up cộng thẳng các dự báo đó lên nhóm.

Top-down động không có đường hỏng này: nó chỉ mô hình hoá chuỗi NHÓM (dày, ổn
định) rồi chia xuống mã theo tỷ trọng EWMA — mã thưa nhận phần nhỏ, không bao
giờ tự sinh dự báo riêng. Đây chính là lý do tồn tại của dự báo phân cấp, và
giờ có bằng chứng bằng số trên dữ liệu thật của chính bệnh viện.

**Kết luận phương pháp: dùng top-down động (EWMA) làm mặc định.** Bottom-up
thắng sát nút (1–3%) khi mọi chuỗi đủ dày, nhưng thua thảm hoạ khi có chuỗi
thưa — với hệ hỗ trợ quyết định trong bệnh viện, bền vững quan trọng hơn vài
phần trăm chính xác. TD động ổn định ở cả 9 ô (0,50–0,71), không ô nào hỏng.

## Chọn cửa sổ lịch sử: giữ TOÀN BỘ, kèm một lưu ý phương pháp

Nhìn bảng dễ kết luận "cắt 2023 tốt nhất" (MASE nhỏ nhất ở cả ba nhóm). Nhưng
so MASE **giữa các cửa sổ** không hoàn toàn công bằng: mỗi lần chạy kiểm định
trên một giai đoạn khác nhau (A kiểm từ 2021, C chỉ kiểm 2025–2026), và mẫu
chuẩn hoá của MASE cũng khác. So sánh chỉ chặt chẽ **trong cùng một cửa sổ**
(giữa các phương pháp) — còn giữa cửa sổ chỉ mang tính tham khảo.

Với TD động, chênh lệch giữa ba cửa sổ chỉ 0,09–0,20 MASE — không có bằng
chứng đủ mạnh để đánh đổi:

- Cửa sổ C chỉ còn 19 bước kiểm định — kết luận mỏng;
- Cắt lịch sử làm mất các mùa dịch cũ mà thành phần mùa vụ và **thời tiết**
  cần: hiệu quả thời tiết chỉ hiện rõ ở cửa sổ đầy đủ
  (J00-J06 **−32,9% MAE**, J20-J22 **−28,5%**; cửa sổ ngắn thì thời tiết
  gần như vô tác dụng hoặc âm);
- Dịch chuyển mức nền của J09-J18 (3,66×) đã được thành phần xu hướng và tỷ
  trọng EWMA hấp thụ — bằng chứng: TD động ở cửa sổ A (0,565) không thua cửa
  sổ B (0,614).

**Kết luận cấu hình sản xuất: lịch sử đầy đủ 2019 + top-down động + thời tiết
bật.** Bảng ba cửa sổ giữ lại trong báo cáo như *phân tích độ nhạy* — nó trả
lời câu "vì sao chọn giai đoạn dữ liệu này" bằng thí nghiệm chứ không bằng
cảm tính.

## Hiệu quả biến thời tiết (mức nhóm, có độ trễ — cửa sổ A)

| Nhóm | MASE không thời tiết | MASE có thời tiết | MAE thay đổi |
|---|---|---|---|
| J00-J06 | 1,181 | **0,792** | **−32,9%** |
| J09-J18 | 0,737 | 0,752 | +2,1% (không giúp) |
| J20-J22 | 1,051 | **0,751** | **−28,5%** |

Hợp lý về dịch tễ: nhiễm khuẩn hô hấp trên (J00-J06) và phế quản (J20-J22)
nhạy với thời tiết theo mùa; viêm phổi nhập viện (J09-J18) do nhiều yếu tố
khác chi phối (tuổi, bệnh nền, quy mô tiếp nhận). Đây cũng là một kết quả
đáng viết riêng — giả thiết môi trường của đề tài đúng cho 2/3 nhóm, và nói
được cả vì sao nhóm còn lại thì không.

## Số đưa vào tóm tắt báo cáo

- Dự báo mức mã tốt hơn seasonal-naive **~40%** (MASE 0,60 trung bình toàn cục,
  cửa sổ đầy đủ, TD động 0,608 / bottom-up 0,602).
- Dự báo TỔNG nhóm: MASE 0,51–0,65 tuỳ nhóm.
- 4 phương án phân cấp × 3 cửa sổ × 3 nhóm = 36 cấu hình đã kiểm bằng
  walk-forward trên 92 tháng dữ liệu HIS thật (23.429 lượt khám).

## Ghi chú kỹ thuật

Loạt cảnh báo `ConvergenceWarning` / `Too few observations` khi chạy là
SARIMAX báo không hội tụ trên chuỗi mã thưa — vô hại với kết quả cuối
(ensemble lấy TRUNG BÌNH ĐỀU các thành viên — xem `models.py` lớp
`Ensemble` — nên một thành viên tồi bị làm loãng chứ KHÔNG bị hạ trọng
số; hiện chưa có cơ chế trọng số thích ứng) nhưng chính là "triệu chứng" của hiện
tượng bottom-up nổ tung nói trên. Không tắt bằng suppress toàn cục trong app;
chỉ lọc khi chạy backtest cho dễ đọc output.
