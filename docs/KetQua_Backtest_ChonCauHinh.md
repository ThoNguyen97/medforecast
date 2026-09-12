# Kết quả backtest chính thức — cấu hình sản xuất M12 (11/09/2026, chiều)

**Lệnh sinh ra bảng này** (máy có `statsmodels`; bench cloud tái lập đúng số Windows
buổi sáng trước khi đổi, xem mục 0.4):

    cd backend && python -m app.forecasting.run_eval --db data/medforecast.db --out ketqua_backtest

## 0. M12 — kết hợp thích ứng + hiệu chỉnh lệch + ETS: RelMAE mã 0,659 → **0,500**

### 0.1 · Vì sao trung bình đều là sai lầm

Ghi dự báo của TỪNG thành viên ở 68 bước walk-forward rồi chấm riêng (mức nhóm):

| Thành viên | J00-J06 | J09-J18 | J20-J22 | MPE (J09-J18) |
|---|---|---|---|---|
| SARIMAX(thời tiết) | **0,518** | **0,360** | **0,560** | −6,0% |
| ETS Holt–Winters (mới) | 0,547 | 0,395 | 0,578 | −1,4% |
| Harmonic-Poisson(thời tiết) | 0,777 | 0,686 | 0,755 | −17,2% |
| PoissonTrend | 1,057 | 0,730 | 0,932 | −11,7% |
| SeasonalTrend | 1,229 | 0,908 | 0,981 | −23,6% |
| *Trung bình đều 4 thành viên (cũ)* | *0,755* | *0,594* | *0,688* | *−14,5%* |

Hai thành viên numpy đầu tiên **tệ hơn seasonal-naive** (RelMAE > 1 ở J00-J06) mà
vẫn được 1/4 phiếu → tổ hợp tệ hơn thành viên tốt nhất của chính nó. Đó là lý
do "bỏ một thành viên yếu" đã cải thiện ngay. Nhưng bỏ tay là quyết định cứng;
cách đúng là **để dữ liệu chọn** — trọng số nghịch đảo MAE trên cửa sổ trượt
(Bates–Granger 1969), tính lại mỗi bước từ các bước TRƯỚC.

### 0.2 · Các biến thể kết hợp (`ket_hop.csv`, cùng một bản ghi thành viên)

| Biến thể | J00-J06 | J09-J18 | J20-J22 | TB | MPE 3 nhóm | Độ phủ 90% |
|---|---|---|---|---|---|---|
| mean (cũ) | 0,755 | 0,594 | 0,688 | 0,679 | +7,1 / −14,5 / +13,1 | 88 / 68 / 85 |
| mean + bias | 0,738 | 0,472 | 0,630 | 0,613 | +3,8 / −6,7 / +7,7 | 88 / 77 / 85 |
| inv_mae (p=2, w=12) | 0,533 | 0,441 | 0,611 | 0,528 | +1,8 / −10,7 / +6,4 | 88 / 77 / 86 |
| inv_mae + bias | 0,550 | 0,426 | 0,571 | 0,516 | −0,3 / −3,1 / +4,8 | 88 / 77 / 85 |
| mean + ETS | 0,654 | 0,509 | 0,616 | 0,593 | | |
| inv_mae + ETS | 0,504 | 0,388 | 0,559 | 0,484 | +1,4 / −7,7 / +4,9 | 85 / 80 / 85 |
| **inv_mae + bias + ETS (CHỌN)** | **0,516** | **0,377** | **0,541** | **0,478** | **−0,5 / −3,0 / +4,1** | **87 / 80 / 85** |

Chọn biến thể cuối vì: RelMAE ngang biến thể tốt nhất (0,473 với w=24 không
bias — chênh trong sai số chọn mẫu), nhưng **lệch hệ thống về gần 0** ở cả ba
nhóm — đúng vấn đề mà mục 2 (bản sáng) đã nêu là rủi ro thiếu hàng lặp lại.
Tham số: cửa sổ 12 bước, luỹ thừa 2, hệ số lệch = 1 + 0,5·(median(thực/dự báo) − 1),
chặn [1/1,5; 1,5], chỉ tính từ quá khứ. Độ nhạy w=12/24, p=1/2, shrink 0,5/1,0
đều nằm trong 0,47–0,53 — kết luận không phụ thuộc một bộ tham số.

### 0.3 · Kết quả chính thức với cấu hình M12

**Quy mô dữ liệu đã chốt (đếm lại 12/09/2026):** **23.653 lượt** ở các kỳ đã
chốt — J00-J06 11.514 · J09-J18 7.754 · J20-J22 4.385; 92 tháng (2019-01 →
2026-08), kỳ 2026-09 đang mở nên bị loại. Đây là con số đếm ở **mức khối**
(`COUNT(DISTINCT` lượt tiếp nhận`)` cho mỗi khối) và là con số phải trích vào
báo cáo. Đếm ở mức mã ra 23.713 vì một lượt có hai mã ICD **cùng khối** được
tính hai lần ở mức mã — chênh lệch này chỉ xuất hiện từ kỳ 2026-06, khi chẩn
đoán phụ bắt đầu được ghi. Hệ quả phương pháp: **cộng dồn bottom-up từ mã lên
khối sẽ vượt số thật**, đây là một lập luận nữa cho top-down ngoài lý do chuỗi
thưa. Khớp `dataset/v1/nhom_thang.csv` và `ma_thang.csv`.

**Mức MÃ (4 hướng phân cấp):**

| Nhóm | Bottom-up | TD cố định | **TD động (EWMA)** | Hoà giải OLS |
|---|---|---|---|---|
| J00-J06 (7 mã) | 0,652 | 0,659 | **0,547** | 0,621 |
| J09-J18 (10 mã) | 0,546 | 0,439 | **0,413** | 0,569 |
| J20-J22 (3 mã) | 0,617 | 0,542 | **0,541** | 0,587 |
| **Tổng hợp** | 0,605 | 0,547 | **0,500** | 0,592 |

> **Cảnh báo về cột "TD cố định":** tỷ trọng cố định lấy từ
> `mart_icd_share_in_block`, được tính trên **toàn lịch sử**
> (`app/data_pipeline/pipeline.py:402`) rồi dùng lại ở mọi bước walk-forward
> (`app/forecasting/evaluate.py:92,173`) — nghĩa là dự báo mã năm 2021 đã dùng tỷ
> trọng ước lượng từ dữ liệu tới 2026-09. Cột này vì vậy **được ưu ái**, con số
> thật của nó sẽ tệ hơn 0,547; khoảng cách thực với top-down động còn lớn hơn
> bảng đang in. Phương án **được chọn** (TD động EWMA) không có vấn đề này: nó
> dùng `ewma_shares(hist_g, hist_c)` chỉ từ quá khứ
> (`app/forecasting/hierarchical.py:15-29`), nên **0,500 / 0,516 / 0,377 / 0,541
> là số walk-forward trung thực**. Sửa cột TD cố định cho đúng là việc của hướng
> phát triển; nó không đổi kết luận vì phương án cố định đã bị loại.

MPE TD động: −2,0 / −5,7 / +4,0 % · sMAPE 33,7 % · WAPE 28,3 %. Top-down thắng
bottom-up rõ hơn trước vì Ŷ_g giờ tốt hơn nhiều còn mức mã vẫn trung bình đều
(mã ngắn, SARIMAX/ETS rớt 70 % số lần).

**Mức NHÓM:**

| Nhóm | MAE | RelMAE | ME | MPE | sMAPE | Độ phủ 90% | Bề rộng/thực tế |
|---|---|---|---|---|---|---|---|
| J00-J06 | 26,7 | **0,516** | −0,7 | −0,5 % | 23,3 % | 86,7 % | 0,90 |
| J09-J18 | 19,6 | **0,377** | −3,1 | −3,0 % | 23,7 % | 80,0 % | 0,92 |
| J20-J22 | 16,5 | **0,541** | +2,3 | +4,1 % | 35,8 % | 84,7 % | 1,38 |

So bản sáng: MAE nhóm giảm 32 % / 37 % / 21 %; lệch J09-J18 từ −14,4 % về −3,0 %;
độ phủ J09-J18 từ 68 % lên 80 %; khoảng hẹp hơn (0,90 so 1,29 ở J00-J06). Thời tiết
ở ensemble mới: +5,2 % / −4,4 % / +3,3 % MAE — vẫn nhỏ và trái chiều ở J09-J18,
kết luận mục 3 giữ nguyên.

### 0.4 · Đối chứng XGBoost và Prophet — đã thử, có số (`doi_chung_xgb_prophet.csv`)

Cùng 68 bước walk-forward, cùng bản ghi thành viên (`app/forecasting/candidates_opt.py`):
XGBoost trên [lag 1/2/3/12, sin/cos tháng, xu hướng, thời tiết trễ 1–2] thang log1p,
cây sâu 3, 200 cây; Prophet mặc định (mùa năm, changepoint 0,05) trên log1p, bỏ tháng COVID.

| Đứng một mình (RelMAE) | J00-J06 | J09-J18 | J20-J22 |
|---|---|---|---|
| SARIMAX(thời tiết) | **0,518** | **0,360** | **0,560** |
| ETS | 0,547 | 0,395 | 0,578 |
| **XGBoost** | 0,669 | 0,473 | 0,570 |
| Harmonic-Poisson | 0,777 | 0,686 | 0,755 |
| **Prophet** | 2,422 | 1,304 | 1,875 |

| Tổ hợp inv_mae + bias | J00-J06 | J09-J18 | J20-J22 | TB |
|---|---|---|---|---|
| **5 thành viên (sản xuất)** | 0,516 | 0,377 | 0,541 | **0,478** |
| + XGBoost | 0,501 | 0,378 | 0,540 | 0,473 |
| + Prophet | 0,558 | 0,407 | 0,523 | 0,496 |
| + cả hai | 0,538 | 0,404 | 0,518 | 0,487 |
| chỉ SARIMAX + ETS | 0,495 | 0,373 | 0,581 | 0,483 |
| SARIMAX + ETS + XGBoost | 0,479 | 0,362 | 0,564 | 0,468 |

Kết luận: **Prophet tệ hơn seasonal-naive** trên cả ba khối (chuỗi ngắn, mức nền
đứt gãy — changepoint tự động chạy theo nhiễu) và kéo tổ hợp xuống. **XGBoost**
đứng thứ ba, thêm vào chỉ được 0,478 → 0,473 (1 %, trong sai số chọn mẫu) với giá
là thêm một phụ thuộc nặng và một bộ siêu tham số; **không đưa vào sản xuất**,
giữ làm đối chứng. Hai thành viên numpy yếu (SeasonalTrend, PoissonTrend) có thể
bỏ hẳn (0,483) hoặc giữ (0,478) — khác biệt không có ý nghĩa; giữ để tổ hợp không
phụ thuộc statsmodels.

### 0.5 · Tính tái lập

Bench cloud (Linux, numpy 2.4, statsmodels 0.15) chạy đúng cấu hình sáng cho
0,659 / 0,755 / 0,594 / 0,688 / 88–68–85 % — khớp Windows tới chữ số thứ ba.
Phát hiện nhân tiện: `PoissonTrend.predict` gọi `float()` trên mảng (1,) — numpy
≥ 2.x coi là lỗi → thành viên rớt 100 % ở mức mã trên máy mới; đã sửa.

---

# Bản sáng 11/09/2026 — cấu hình TRƯỚC M12 (giữ làm đối chứng)

**Lệnh sinh ra bảng này** (chạy trên máy có `statsmodels`, ghi kèm `cau_hinh.json`):

    cd backend && python -m app.forecasting.run_eval --db data/medforecast.db --out ketqua_backtest

**Cấu hình** (`app/forecasting/config.py`, `PRODUCTION_CONFIG` — nguồn tham số DUY
NHẤT cho cả backtest lẫn ba màn hình): ensemble SeasonalTrend + PoissonTrend +
Harmonic-Poisson(thời tiết trễ 1–2 tháng) + SARIMAX(1,1,1)(1,0,0,12) exog thời
tiết chuẩn hoá · Ridge λ=10 trên cột đã chuẩn hoá · smearing tắt · lịch sử đầy đủ
từ 2019 · `min_train` 24 · top-down động EWMA span 6 · khoảng dự báo 90% từ
phân vị 24 phần dư gần nhất. Walk-forward mở rộng cửa sổ, dự báo 1 bước,
68 bước kiểm định/nhóm (67 với J20-J22).

## 1. Mức MÃ — bốn hướng phân cấp

RelMAE = MAE / MAE(seasonal-naive out-of-sample cùng các bước); < 1 là thắng
seasonal-naive. Bản 09/08 gọi chỉ số này là "MASE" — không đúng tên, xem mục 4.

| Nhóm | Bottom-up | TD cố định | **TD động (EWMA)** | Hoà giải OLS |
|---|---|---|---|---|
| J00-J06 (7 mã) | 0,714 | 0,742 | **0,664** | 0,719 |
| J09-J18 (10 mã) | 0,628 | 0,661 | **0,621** | 0,658 |
| J20-J22 (3 mã) | 0,692 | 0,693 | 0,692 | **0,689** |
| **Tổng hợp** | 0,678 | 0,699 | **0,659** | 0,689 |

Kèm sai số có dấu (MPE, dương = thừa) cho TD động: J00-J06 **+5,6%**, J09-J18
**−17,2%**, J20-J22 **+13,0%**. sMAPE 40,8% · WAPE 36,8% (tổng hợp).

**Kết luận giữ nguyên: top-down động là mặc định.** Thắng ở 2/3 nhóm và tổng
hợp; hoà ở J20-J22 (chỉ 3 mã, chia xuống gần như không đổi gì).

## 2. Mức NHÓM + độ phủ khoảng dự báo

| Nhóm | MAE | RelMAE | ME | MPE | sMAPE | Độ phủ 90% | Bề rộng/thực tế |
|---|---|---|---|---|---|---|---|
| J00-J06 | 39,1 | 0,756 | +9,0 | +7,1% | 32,0% | **88,3%** (60 bước) | 1,29 |
| J09-J18 | 30,9 | 0,595 | −15,0 | **−14,4%** | 33,3% | **68,3%** | 0,88 |
| J20-J22 | 21,0 | 0,689 | +7,2 | +13,1% | 43,7% | **84,7%** | 1,55 |

**Hai điều bảng này nói mà bảng cũ không nói được:**

- **Lệch có dấu.** J09-J18 hụt hệ thống −14% — đây là nhóm có dịch chuyển mức
  nền 3,66×, ensemble theo không kịp. Hai nhóm kia thừa +7…+13%. MAE/RMSE/RelMAE
  đều triệt tiêu dấu nên trước đây không thấy. Với DSS vật tư, hụt hệ thống ở
  nhóm lớn nhất (J09-J18 ≈ 30% số ca) là rủi ro thiếu hàng lặp lại — điểm cần
  nêu rõ trong hạn chế và hướng phát triển.
- **Độ phủ đo được.** Khoảng 90% phủ thật 88% và 85% ở hai nhóm — gần danh
  nghĩa; **J09-J18 chỉ 68%** vì khoảng đặt quanh một tâm đã lệch. Bản cũ dựng
  khoảng bằng mean ± 1,96σ và báo phủ 87–90,7%; cách mới (phân vị thực nghiệm,
  không giả định phân phối) cho số trung thực hơn và chỉ đúng chỗ hỏng.

## 3. Thời tiết — kết quả khác hẳn bản 09/08, và vì sao

Ensemble sản xuất CÓ vs KHÔNG thành viên thời tiết (mức nhóm):

| Nhóm | Không TT (RelMAE) | Có TT | Giảm MAE |
|---|---|---|---|
| J00-J06 | 0,770 | 0,756 | **+1,8%** |
| J09-J18 | 0,566 | 0,595 | **−5,1%** (có hại) |
| J20-J22 | 0,707 | 0,689 | **+2,6%** |

Bản 09/08 ghi thời tiết giảm 32,9% / 28,5% MAE. Con số đó **đúng nhưng đo thứ
khác**: `HarmonicPoissonForecaster` ĐỨNG MỘT MÌNH có vs không thời tiết. Ở tầng
ensemble, khi đã có SARIMAX, phần đóng góp biên của thời tiết chỉ còn 2–3% và
**âm ở J09-J18** — viêm phổi nhập viện do tuổi, bệnh nền, quy mô tiếp nhận chi
phối hơn là mùa.

Cách viết vào báo cáo: giả thiết môi trường của đề tài **đúng ở mức mô hình đơn**
(−33%/−28% cho hai nhóm hô hấp trên và phế quản), và **đúng yếu ở mức ensemble**
(+2–3%) vì SARIMAX có mùa vụ đã hấp thụ phần lớn tín hiệu đó. Đây là kết quả
trung thực và có cơ chế giải thích — mạnh hơn con số 33% đứng một mình.

## 4. Điều gì đã thay đổi so với bản 09/08

| | 09/08/2026 | 11/09/2026 |
|---|---|---|
| Thời tiết trong backtest | **KHÔNG** — `evaluate.py` gọi `build_default_ensemble()` không tham số, `group_series()` không có cột thời tiết | Có, đúng cấu hình sản xuất |
| SARIMAX + thời tiết | chưa từng chạy | exog chuẩn hoá z-score; chặn dự báo > 5× max lịch sử |
| Ridge | λ=1, cột chưa chuẩn hoá | λ=10, cột chuẩn hoá (dò λ∈{3…300}: 10 thắng/hoà bản cũ ở mọi ô) |
| Tên chỉ số | "MASE" | **RelMAE** — mẫu số out-of-sample, không phải MASE theo Hyndman & Koehler |
| "MinT" | | **Hoà giải OLS** (W = I), không phải MinT |
| Ensemble | trung bình đều, nuốt mọi lỗi | trung bình đều, **ghi lại** thành viên đóng góp/rớt |
| Khoảng dự báo | mean ± 1,96σ, σ từ 12 phần dư | phân vị thực nghiệm, 24 phần dư, độ phủ đo được |
| Chỉ số | MAE/RMSE/"MASE" | + ME, MPE, sMAPE, WAPE |

**Về chuyện "bottom-up nổ tung" (MASE 483,7 ở bản cũ):** hiện tượng có thật,
nhưng nguyên nhân là SARIMAX không hội tụ trên chuỗi mã thưa cho ra 10^45 và
ensemble cũ đưa thẳng vào trung bình. Với chặn dự báo phi lý và từ chối chuỗi
< 26 tháng, bottom-up nay là 0,678 — thua top-down động 3%, không nổ nữa.
**Lập luận cho top-down vẫn đứng**: nó bền trước chuỗi thưa *theo thiết kế*
(chỉ mô hình hoá chuỗi nhóm), còn bottom-up bền *nhờ có lưới chắn*. Bảng
`thanhvien.csv` cho thấy ở mức mã SARIMAX chỉ fit được 18–72% số lần vì chuỗi
quá ngắn — bottom-up đang chạy trên ensemble mỏng hơn nó tưởng.

## 5. Đối chứng smearing (Duan) — giữ tắt

| Nhóm | Không (RelMAE / MPE) | Có (RelMAE / MPE) |
|---|---|---|
| J00-J06 | 0,756 / +7,1% | 0,805 / +12,9% |
| J09-J18 | 0,595 / −14,4% | **0,557 / −7,2%** |
| J20-J22 | 0,689 / +13,1% | 0,739 / +22,2% |

Smearing nhân với hệ số ≥ 1 nên chỉ giúp nơi đang hụt (J09-J18) và hại nơi
đang thừa. Bật theo nhóm là tinh chỉnh trên tập kiểm định — không làm. Ghi
vào hướng phát triển cùng với dò λ theo nhóm.

## 6. Số của bản TRƯỚC M12 — KHÔNG trích vào báo cáo

> Mục này giữ để so sánh trước/sau M12. Số đưa vào luận văn nằm ở **mục 0.3**
> (RelMAE mức mã 0,500). Con số lượt khám dưới đây là số đếm tại 11/09 sáng.

- Dự báo mức mã tốt hơn seasonal-naive **~34%** (RelMAE 0,659 tổng hợp, top-down
  động, cấu hình sản xuất, 68 bước walk-forward/nhóm trên 92 tháng dữ liệu HIS
  thật, 23.429 lượt khám — số đếm tại thời điểm đó; số chốt hiện nay là
  23.653, xem mục 0.3).
- Mức nhóm: RelMAE 0,60–0,76 tuỳ nhóm; khoảng dự báo 90% phủ thật 85–88% ở hai
  nhóm, 68% ở nhóm có dịch chuyển mức nền.
- Lệch có dấu: hụt −14% ở J09-J18, thừa +7…+13% ở hai nhóm còn lại — đo được
  nhờ ME/MPE, là hạn chế nêu rõ.
- Thời tiết: −33%/−28% MAE ở mức mô hình đơn cho hai nhóm hô hấp trên và phế
  quản; +2–3% ở mức ensemble; không giúp viêm phổi.
- Mọi con số truy ngược được về `ketqua_backtest/cau_hinh.json` (cấu hình + thời
  điểm chạy + có statsmodels).

---

# PHỤ LỤC — Bản 09/08/2026 (giữ làm tư liệu, KHÔNG trích số)

> Các bảng dưới đây đo trên cấu hình **không có thời tiết**, SARIMAX không có
> lưới chắn, Ridge λ=1 chưa chuẩn hoá, và gọi RelMAE là "MASE". Giá trị còn
> lại của phụ lục: **phân tích độ nhạy ba cửa sổ lịch sử** (lý do giữ toàn bộ
> lịch sử từ 2019 vẫn đúng) và mô tả hiện tượng bottom-up nổ.

## (cũ) Kết quả backtest: chọn cấu hình dự báo (dữ liệu HIS thật, 09/08/2026)

Ba lần chạy walk-forward (mở rộng cửa sổ, dự báo 1 bước, tối thiểu 24 tháng
huấn luyện), khác nhau đúng một tham số — mốc bắt đầu lịch sử:

| Lần chạy | Lịch sử từ | Số bước kiểm định | Giai đoạn được kiểm |
|---|---|---|---|
| A | 2019-01 (toàn bộ, 92 tháng) | 66–67 | ~02/2021 → 07/2026 |
| B | 2022-01 (55 tháng) | 31 | ~01/2024 → 07/2026 |
| C | 2023-01 (43 tháng) | 19 | ~12/2024 → 07/2026 |

### Bảng MASE mức mã (thấp hơn = tốt hơn; < 1 = thắng seasonal-naive)

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

### Phát hiện quan trọng nhất: bottom-up NỔ TUNG trên chuỗi thưa

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

### Chọn cửa sổ lịch sử: giữ TOÀN BỘ, kèm một lưu ý phương pháp

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

### Hiệu quả biến thời tiết (mức nhóm, có độ trễ — cửa sổ A)

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

### Số đưa vào tóm tắt báo cáo

- Dự báo mức mã tốt hơn seasonal-naive **~40%** (MASE 0,60 trung bình toàn cục,
  cửa sổ đầy đủ, TD động 0,608 / bottom-up 0,602).
- Dự báo TỔNG nhóm: MASE 0,51–0,65 tuỳ nhóm.
- 4 phương án phân cấp × 3 cửa sổ × 3 nhóm = 36 cấu hình đã kiểm bằng
  walk-forward trên 92 tháng dữ liệu HIS thật (23.429 lượt khám tại 09/08;
  số chốt hiện nay 23.653 — mục 0.3).

### Ghi chú kỹ thuật

Loạt cảnh báo `ConvergenceWarning` / `Too few observations` khi chạy là
SARIMAX báo không hội tụ trên chuỗi mã thưa — vô hại với kết quả cuối
(ensemble lấy TRUNG BÌNH ĐỀU các thành viên — xem `models.py` lớp
`Ensemble` — nên một thành viên tồi bị làm loãng chứ KHÔNG bị hạ trọng
số; hiện chưa có cơ chế trọng số thích ứng) nhưng chính là "triệu chứng" của hiện
tượng bottom-up nổ tung nói trên. Không tắt bằng suppress toàn cục trong app;
chỉ lọc khi chạy backtest cho dễ đọc output.
