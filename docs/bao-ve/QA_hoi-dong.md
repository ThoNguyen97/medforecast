# Q&A bảo vệ — MedForecast AI (soạn 13/09/2026)

Năm câu hỏi thầy cô đã báo trước, kèm số liệu đo trên chính DB thật `backend/data/medforecast.db`.
Quy ước: **In đậm** = con số phải thuộc lòng. Mỗi câu có bản nói 30–45 giây, rồi phần đào sâu.

---

## 1. "Train như thế nào?"

### Nói 30 giây
Hệ thống không huấn luyện một mạng nơ-ron rồi lưu trọng số. Tầng dự báo là **tổ hợp 5 mô hình thống kê** khớp lại trên chuỗi tháng mỗi lần chạy:

1. **Seasonal-Trend** (xu thế + chỉ số mùa 12 tháng)
2. **Poisson-Ridge** (hồi quy đếm, ridge λ = 10)
3. **Harmonic-Poisson có thời tiết** (sóng điều hòa + nhiệt độ/độ ẩm/mưa từ Open-Meteo)
4. **SARIMAX** (có biến ngoại sinh thời tiết, trễ 1 tháng)
5. **ETS** (san mũ có mùa)

Năm đầu ra được **tổ hợp theo Bates–Granger**: trọng số tỉ lệ **nghịch đảo MAE** của từng thành viên trên **cửa sổ 12 bước gần nhất** (lũy thừa 2), thành viên có dưới 6 bước lịch sử thì nhận trung bình các thành viên đủ lịch sử. Sau tổ hợp có **hiệu chỉnh lệch** (bias factor, cửa sổ 12, co ngót 0,5, chặn ở ±1,5 lần). Cấu hình này gọi là **M12**, khai báo một chỗ duy nhất (`PRODUCTION_CONFIG`) và dùng chung cho cả backtest lẫn sản xuất — không có hai bộ tham số.

Dự báo ra ở **mức khối ICD-10** (J00-J06, J09-J18, J20-J22), rồi **phân rã top-down động** về từng mã bệnh bằng tỉ trọng **EWMA span 6**.

### Đào sâu
- **Vì sao không dùng XGBoost / LSTM / Prophet?** Chuỗi chỉ có **92 tháng ≈ 7 chu kỳ mùa**. Với cỡ mẫu đó, mô hình thống kê thắng học máy — đúng kết luận các cuộc thi M của Makridakis. Và em **đã đo chứ không nói suông**: XGBoost và Prophet được giữ làm **mô hình đối chứng**, Prophet cho RelMAE **2,42 / 1,30 / 1,88** — tệ hơn cả seasonal-naive. Kết quả trong `ketqua_backtest/doi_chung_xgb_prophet.csv`, Bảng 5.3 của báo cáo.
- **"Train" chạy lúc nào?** Mỗi lần bấm **Phân tích**: fit lại toàn bộ 5 mô hình trên dữ liệu tính đến kỳ neo, không dùng checkpoint cũ → mô hình luôn học trên dữ liệu mới nhất, không bao giờ lệch pha với DB.
- **Khoảng tin cậy 90 %** không lấy từ giả định phân phối của mô hình mà **dựng thực nghiệm** từ phân vị sai số của **24 bước walk-forward gần nhất**.
- **Thời tiết đóng góp bao nhiêu?** Trung thực: −33 % / −28 % MAE ở **mô hình đơn lẻ**, nhưng chỉ **+5,2 % / +3,3 % / −4,4 %** ở **mức tổ hợp** — thành phần mùa đã hấp thụ gần hết thông tin thời tiết. Em vẫn giữ vì không làm xấu đi và cho phép giải thích theo mùa lạnh/mưa.

---

## 2. "Chia bộ dataset ra sao?"

### Nói 30 giây
Đây là **chuỗi thời gian**, nên **không chia ngẫu nhiên train/test** — chia ngẫu nhiên sẽ để mô hình nhìn thấy tương lai. Em dùng **walk-forward mở rộng (expanding window)**:

- **min_train = 24 tháng**: 24 tháng đầu chỉ để huấn luyện, không chấm điểm.
- Từ tháng thứ 25 trở đi, mỗi bước: huấn luyện trên **toàn bộ quá khứ tính đến t**, dự báo **đúng 1 bước** (t+1), so với số thực tế, rồi mới nạp t+1 vào tập huấn luyện cho bước sau.
- Số bước chấm điểm: **68 / 68 / 67 bước** cho ba khối.

Chống rò rỉ tương lai ở hai chỗ: (a) trong walk-forward, `combine()` **gọi trước** `update()` — trọng số tổ hợp ở bước t chỉ dùng sai số các bước ≤ t−1; (b) **kỳ chưa chốt bị loại khỏi mọi cửa sổ** (`period < tháng hiện tại`, cột `is_complete`) — tháng dở dang không bao giờ được coi là số thực tế.

### Đào sâu
- **Chỉ số dùng gì?** Chỉ số chính là **RelMAE = MAE / MAE(seasonal-naive)** trên cùng tập kiểm; < 1 là tốt hơn phép dự báo ngây thơ. Bổ sung WAPE, ME/MPE, độ phủ khoảng. Em **bỏ R²** vì với chuỗi có mùa, so với giá trị trung bình là chuẩn so sánh vô nghĩa — giải thích rõ trong chương 5.
- **Kết quả:** RelMAE mức mã **0,500** (sai số bằng một nửa seasonal-naive), mức nhóm **0,516 / 0,377 / 0,541**; WAPE mức mã **28,3 %**; MPE **−0,5 / −3,0 / +4,1 %** (không lệch hệ thống); độ phủ khoảng 90 % đo thật **87 / 80 / 85 %**.
- **Tại sao độ phủ chưa đạt 90 %?** Khoảng dựng trên 24 bước gần nhất; đoạn 2025 có đứt gãy chế độ ghi nhận nên phương sai thật lớn hơn phương sai lịch sử. Đây là hạn chế em ghi thẳng trong báo cáo, không tô hồng.

---

## 3. "Dataset thu thập có tin cậy không?"

### Nói 30 giây
Dữ liệu **không phải tự sinh, không phải khảo sát**: lấy trực tiếp từ **HIS đang chạy sản xuất của một cơ sở y tế phối hợp**, qua đường một chiều **PROD → STA (`MEDFORECAST_DW`) → ứng dụng**, bằng 3 thủ tục có kiểm soát; tài khoản ứng dụng **chỉ có quyền SELECT** trên STA. Quy mô: **23.653 lượt khám đã chốt kỳ**, **92 tháng**, 3 khối ICD-10 (J00-J06: 11.514 · J09-J18: 7.754 · J20-J22: 4.385), **5.051 mã thuốc**, tiêu hao thực tế theo từng lượt.

Và em **có kiểm định chất lượng chứ không tin mặc định**: 0 bản ghi trùng khóa tự nhiên, 0 bản ghi mồ côi, 0 số ca âm, tổng tỉ trọng phân cấp đúng 1,0, **93 kỳ liên tục không đứt**, chỉ kỳ hiện tại mang cờ `is_complete = 0` và bị loại khỏi mọi phép tính.

### Đào sâu
- **Đếm ca thế nào?** `COUNT(DISTINCT TIEPNHAN_ID)` — đếm **lượt tiếp nhận**, không đếm dòng chẩn đoán. Vì vậy tổng mức khối (**23.653**) **nhỏ hơn** tổng mức mã (23.713): một lượt có hai mã trong cùng khối chỉ tính một lần. Đây là **đúng theo thiết kế**, không phải lỗi mất dữ liệu.
- **Hạn chế em chủ động nêu (điểm cộng, đừng giấu):**
  - **Đứt gãy chế độ ghi nhận đầu 2025** đẩy mức nền khối J09-J18 lên ~**3,7×** — thay đổi quy trình mã hóa bệnh án phía bệnh viện, không phải hiện tượng dịch tễ. Mô hình hấp thụ được nhờ thành phần xu thế, nhưng độ phủ khoảng bị ảnh hưởng.
  - **Thời tiết** lấy từ **Open-Meteo** (dữ liệu tái phân tích mở), không phải trạm đo trong khuôn viên bệnh viện.
  - **AQI/PM2.5**: có 144 dòng nhưng chỉ ~50 kỳ đã chốt, **ngắn hơn 2 chu kỳ mùa** nên chưa đưa vào mô hình — chờ đủ dữ liệu, không phải "không có dữ liệu".
  - Dữ liệu một cơ sở → kết quả **chưa khái quát cho toàn ngành**; đây là DSS cho chính cơ sở đó.
- **Bảo mật/y đức:** không có dữ liệu định danh bệnh nhân trong kho phân tích (chỉ mã lượt, mã ICD, mã thuốc, kỳ); tên cơ sở được ẩn danh trong báo cáo.

---

## 4. "Độ trễ suy luận của web?"

### Nói 30 giây
Phải tách hai đường, vì chúng chênh nhau hai bậc độ lớn:

- **Đường người dùng đi hằng ngày** (Tổng quan, Cảnh báo thiếu hụt, Vật tư, Báo cáo): dự báo **đã được ghi nhận và lưu**, các trang chỉ đọc và quy đổi → **10–450 ms**.
- **Đường chạy mô hình** (bấm "Phân tích" ở trang Phân tích & Dự báo): fit lại 5 mô hình + 25 lần walk-forward để lấy trọng số và khoảng tin cậy → **khoảng 6–8 giây cho một khối**, **~22 giây** khi chạy cả Toàn quốc kèm 11 tỉnh. Đây là thao tác **chủ động, mỗi kỳ làm một lần**, không phải thao tác lặp lại.

### Số đo thật (đo 13/09/2026, `medforecast.db` 70 MB, VM Linux 2 vCPU ngay trên máy làm việc, gọi in-process nên **chưa gồm độ trễ mạng và thời gian render**)

| Endpoint (màn hình) | p50 | p95 | Payload |
|---|---:|---:|---:|
| `GET /dashboard/v2` (Tổng quan) | **435 ms** | 544 ms | 13,7 KB |
| `GET /dashboard/v2/alerts` (Cảnh báo, 20 dòng) | **293 ms** | 329 ms | 18,4 KB |
| `GET /dashboard/v2/forecast` | 24 ms | 37 ms | 3,6 KB |
| `GET /supply-requirements/summary` | 245 ms | 360 ms | 318,9 KB |
| `GET /dss/norms` (Định mức thực nghiệm) | 77 ms | 134 ms | 25,9 KB |
| `GET /dss/params`, `/forecast/history` | 9–11 ms | 13 ms | ~3 KB |
| `GET /inventory/` (Vật tư, 50 dòng) | 19 ms | 24 ms | 21,3 KB |
| `POST /forecast/analyze` — **chỉ nạp bản đã ghi nhận** | **144 ms** | 150 ms | 3,5 KB |
| `POST /forecast/analyze` — **chạy mô hình, 1 tỉnh** | ~12,2 s | 12,6 s | 3,4 KB |
| `POST /forecast/analyze` — **chạy mô hình, Toàn quốc + 11 tỉnh** | **~22,4 s** | 22,5 s | 3,6 KB |
| Tầng 1 thuần `forecast_group()` một khối | **5,8–7,5 s** | 8,1 s | — |

### Chậm ở đâu, và vì sao chấp nhận được
Em có **profile** chứ không đoán: trong 8,3 s của một lần dự báo một khối, **5,3 s (64 %) là SARIMAX** — cụ thể là tối ưu hợp lý cực đại L-BFGS-B của statsmodels; phần còn lại chủ yếu là ETS. Và mô hình phải fit **25 lần** chứ không phải 1: 24 lần cho cửa sổ walk-forward dựng trọng số tổ hợp + khoảng tin cậy thực nghiệm, 1 lần cho kỳ đích. Đó là cái giá của việc **có khoảng tin cậy đo thật thay vì giả định phân phối**.

Thiết kế đã tính đến điều này:
- Endpoint `/analyze` cố ý khai `def` thường **chứ không `async def`** → FastAPI đẩy sang threadpool, việc nặng CPU **không chặn event loop**, người dùng khác vẫn thao tác bình thường trong lúc chạy.
- Kết quả được **ghi nhận vào DB**; mở lại trang chỉ tốn **144 ms**. Dược sĩ mở dashboard hàng ngày không bao giờ phải chờ 22 giây.
- Nếu thầy hỏi "làm sao giảm": ba hướng đã nhận diện — (a) `/analyze` hiện chạy ensemble cho **mọi tỉnh** dù người dùng chỉ xem Toàn quốc, tách ra là giảm ngay ~60 %; (b) cache trọng số tổ hợp theo kỳ neo thay vì tính lại 24 bước mỗi lần; (c) đẩy sang tác vụ nền + thông báo. Em xếp vào Hướng phát triển vì trong phạm vi khóa luận, 22 giây cho một thao tác mỗi tháng không phải nút thắt thực tế.

---

## 5. "AI trên web response có đúng không?"

Tách làm hai nghĩa, trả lời cả hai.

### (a) Đúng theo nghĩa **nhất quán** — mọi màn hình cùng một con số
Đây từng là lỗi thật của hệ thống và em đã sửa, nên trả lời được rất chắc: trước 12/09 có **ba đường tính nhu cầu song song** (định mức nhập tay, `supply_requirements`, `dss_alerts`) → hai trang ra hai con số. Nay **gom về một chuỗi duy nhất**: `tang1_tang2()` → `dss_alerts.alert_rows()`. Trang Cảnh báo, Tổng quan, Báo cáo thiếu hụt, chi tiết ca bệnh, `/supply-requirements/summary` **đều gọi cùng hàm đó**. Chỉ còn **một bộ tham số** duy nhất trong `system_config.dss` — không còn bảng nào gõ tay tham gia công thức.

Kiểm chứng vừa chạy lại trên DB thật, ba màn hình khớp từng số:

- Dự báo Toàn quốc kỳ 2026-09: **393 ca** (161 + 190 + 42), khoảng 90 %: **274–620**.
- Cảnh báo trên tập trọng tâm **242 mã**: **Đỏ 40 · Vàng 27 · Xanh 138 · Xám 37**; 205 mã có dữ liệu tồn FEFO, 37 mã Xám đúng vì **không có dòng tồn**, không phải lỗi tính.
- Định mức thực nghiệm EF5T (Paracetamol, khối J00-J06): **1,01 viên/ca**, phân rã theo rổ chăm sóc NGT 73,1 % · NT1 5,4 % · NT2 15,8 % · NT3 5,7 %, rổ mẫu nhỏ được co ngót và gộp — **xem trực tiếp trên màn hình Quản trị → Định mức thực nghiệm**, không phải con số trong đầu em.

Chỗ này có một bẫy nên chủ động nói trước: tab **Lịch sử phân tích** hiện tổng theo tỉnh **425** trong khi Tổng quan hiện **393** — **hai phạm vi khác nhau theo thiết kế**, không phải lệch: 393 là số **top-down chính thức** ở mức Toàn quốc, 425 là tổng **bottom-up** từng tỉnh, giữ lại chỉ để tham khảo dịch tễ và đã gắn nhãn rõ "không cộng vào Toàn quốc". Tổng bottom-up **luôn lớn hơn** vì mức khối đếm `DISTINCT` lượt.

### (b) Đúng theo nghĩa **dự báo chính xác** — em không nói "đúng", em nói sai số bao nhiêu
- **RelMAE mức mã 0,500** — sai số bằng **một nửa** phép dự báo seasonal-naive; gộp chung 0,485.
- Mức nhóm: **0,516 / 0,377 / 0,541**; MAE tuyệt đối **10,6 / 16,3 / 16,4 ca**/tháng.
- **MPE −0,5 / −3,0 / +4,1 %** → không lệch hệ thống về một phía.
- **Độ phủ khoảng 90 %: đo thật 86,7 / 80,0 / 84,7 %**, trung bình **83,8 %** — em nói thẳng là **chưa đạt mục tiêu 90 %** và giải thích vì đứt gãy 2025.
- Các con số này **hiển thị ngay trên Dashboard** (thẻ chất lượng mô hình đọc từ `ketqua_backtest/`), tức người dùng thấy được độ tin cậy chứ không chỉ thấy con số dự báo trần trụi.

### Điều phải nói thật nếu bị hỏi sâu
Bảng `forecast_runs` (đối chiếu dự báo đã ghi nhận với số thực tế khi kỳ chốt) hiện **chưa có bản ghi nào được đối chiếu** — hệ thống mới ghi nhận 32 bản dự báo cho kỳ 2026-09, mà kỳ này **chưa chốt**. Nên bằng chứng độ chính xác hiện nay là **backtest walk-forward 68 bước trên dữ liệu lịch sử**, còn **track record trực tuyến thì cần thêm vài kỳ vận hành** mới có. Cơ chế đối chiếu đã dựng sẵn (`actual`, `abs_err`, `in_interval`, `actual_filled_at`), chỉ chờ dữ liệu. Trả lời thẳng như vậy tốt hơn nhiều so với để thầy tự phát hiện.

### Câu chốt nên dùng
"Hệ thống là **DSS — hỗ trợ quyết định**, không thay thế dược sĩ. Nó không khẳng định 'tháng sau chắc chắn 393 ca'; nó nói '393 ca, khoảng tin cậy 274–620, sai số lịch sử bằng một nửa cách làm thủ công theo cùng kỳ năm trước, và với dự báo đó thì 40 mã thuốc sẽ hết trước 18 ngày'. Quyết định vẫn là của Khoa Dược."

---

## Phụ lục — câu hỏi rất dễ đi kèm

| Câu hỏi | Trả lời một câu |
|---|---|
| "Khoa Dược muốn sửa định mức thì sao?" | Định mức **tự cập nhật theo tiêu hao thực** mỗi lần đồng bộ HIS; ghi đè thủ công là hướng phát triển (một lớp override trên `/dss/norms`) — cố ý không cho gõ tay để không quay lại cảnh hai con số. |
| "Sao ngưỡng 18 và 36 ngày?" | Tham số cấu hình được, không hard-code, sửa ở Quản trị → Tham số DSS, mọi thay đổi ghi `audit_logs`; 18/36 là chu kỳ đặt hàng thực tế của cơ sở. |
| "Sao dùng DOI chứ không dùng lượng thiếu hụt?" | DOI (số ngày tồn còn dùng được) **so sánh được giữa các mã** có đơn vị và quy mô khác nhau; lượng thiếu hụt thì không. |
| "Vì sao bỏ phân hệ mua sắm?" | Phạm vi khóa luận là DSS: dừng ở **cảnh báo**, không sinh đơn hàng — tránh đưa ra quyết định tài chính mà dữ liệu (lead time, MOQ) chưa đủ tin cậy. |
| "Tại sao SQLite?" | Quy mô một cơ sở, DB 70 MB, truy vấn đọc là chính; đã đo p50 < 450 ms cho màn hình nặng nhất. Đổi sang PostgreSQL là thay chuỗi kết nối SQLAlchemy, không phải viết lại. |
| "Vật tư y tế thì sao?" | Cố ý **chỉ dự báo thuốc**: thuốc tiêu thụ theo chẩn đoán, vật tư tiêu thụ theo lượt khám. Em đã **đo**: tỉ trọng hô hấp ở thuốc 4,39 % vs vật tư 25,71 %, nhưng 25,71 % là giả tạo — bật lên sẽ đẩy 155 mã vật tư vào tập trọng tâm và phá định nghĩa "tập mà mô hình dịch tễ lái được". |

---

*Cơ sở số liệu: `docs/ra-soat/RaSoat_KiemToan_2026-09-13.md`, `ketqua_backtest/`, đo latency bằng TestClient in-process trên bản sao `medforecast.db` ngày 13/09/2026.*
