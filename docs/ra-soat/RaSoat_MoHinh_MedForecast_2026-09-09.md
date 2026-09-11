# RÀ SOÁT TẦNG MÔ HÌNH — MedForecast AI

**Ngày:** 09/09/2026 · **Phạm vi:** `app/forecasting/{models, evaluate, hierarchical, sarimax_opt, topdown, data_access}.py`, `services/{group_ensemble, hierarchical_forecast}_service.py`
**Cách làm:** đọc toàn văn mã, truy vết mọi nơi gọi `build_default_ensemble`, đối chiếu tham số thực tế với con số công bố trong tài liệu.

---

## 0. TÓM TẮT

Thiết kế mô hình **tốt hơn mặt bằng đồ án**: walk-forward mở rộng cửa sổ đúng chuẩn, thời tiết dùng ở độ trễ nên không rò rỉ tương lai, khoảng dự báo dựng từ sai số backtest thực nghiệm chứ không phải công thức lý thuyết, và lựa chọn top-down có bằng chứng số. Đây là nền tảng vững.

Nhưng có **một vấn đề chặn** phải xử lý trước khi bảo vệ, và nó không phải lỗi mã:

> **Bốn cấu hình mô hình khác nhau đang cùng tồn tại. Con số MASE ~0,60 công bố trong báo cáo được đo trên một cấu hình mà KHÔNG màn hình nào của ứng dụng dùng.**

Ngoài ra: 3 mâu thuẫn giữa tài liệu và mã (một trong đó là hai con số khác nhau cho cùng một thí nghiệm), 4 lỗi phương pháp có thể bị hỏi, và 1 chỉ số quan trọng chưa được báo cáo.

---

## 1. VẤN ĐỀ CHẶN — BỐN MÔ HÌNH, MỘT CON SỐ CÔNG BỐ

### 1.1 · Hiện trạng đã truy vết

| Nơi sinh số | Mô hình thực tế | Thời tiết |
|---|---|---|
| **Backtest công bố** `evaluate.py:38` | `build_default_ensemble()` — **không tham số** → SeasonalTrend + PoissonTrend + SARIMAX | **KHÔNG** |
| **Dashboard** `dss_runner` → `topdown.py:188` | **sklearn Ridge + StandardScaler**, đặc trưng `t, month, quarter, sin1, cos1, sin2, cos2, lag*` — **không phải ensemble** | không |
| **Trang Phân tích** `group_ensemble_service.py:139` | `build_default_ensemble(use_weather=dung_thoi_tiet)` | **CÓ** |
| **Trang Kế hoạch** `hierarchical_forecast_service.py:136-137` | nhóm: `use_weather=weather_used` · **mã: `build_default_ensemble()` không thời tiết** | nửa có nửa không |

Ba điểm cần thấy rõ:

**a) Backtest chạy không có thời tiết.** `evaluate.py:38` gọi `build_default_ensemble()` với tham số mặc định `use_weather=False`, nên `HarmonicPoissonForecaster` **không có trong ensemble**. Hơn nữa `data_access.group_series()` (dòng 39-50) chỉ SELECT `period, year, month, cases, is_covid, is_complete` — **không có cột thời tiết nào**, nên `SarimaxForecaster._exog()` cũng trả `None`. Bảng MASE trong `KetQua_Backtest_ChonCauHinh.md` được đo trên một ensemble **hoàn toàn không dùng thời tiết**.

**b) Nhưng kết luận của tài liệu lại là "thời tiết bật".** `KetQua_Backtest_ChonCauHinh.md` chốt *"cấu hình sản xuất: lịch sử đầy đủ 2019 + top-down động + thời tiết bật"*. Hiệu quả thời tiết được đo **riêng**, bằng `weather_effect()` (`evaluate.py:101-131`), và hàm này so sánh `HarmonicPoissonForecaster` **đứng một mình** ở mức nhóm — không phải ensemble, không phải mức mã. **Chưa có phép đo nào cho ensemble-có-thời-tiết**, tức cấu hình được tuyên bố là cấu hình sản xuất.

**c) Dashboard không dùng ensemble.** `topdown.py` là một mô hình Ridge có trễ, riêng biệt. Nó chưa từng xuất hiện trong bảng so sánh nào.

### 1.2 · Vì sao đây là vấn đề chặn

Một câu hỏi rất tự nhiên trong buổi bảo vệ: *"Con số trên màn hình này có sai số bao nhiêu?"* Hiện tại không trả lời được, vì con số 0,60 thuộc về một mô hình thứ tư.

Nặng hơn: nếu thầy đối chiếu `forecasting/README.md` với `KetQua_Backtest_ChonCauHinh.md`, sẽ thấy **hai kết quả khác nhau cho cùng một thí nghiệm**:

| Nguồn | J00-J06 | J20-J22 | Mô tả |
|---|---|---|---|
| `forecasting/README.md:44-48` | −8,4% MAE | −8,1% MAE | "walk-forward group-level" |
| `KetQua_Backtest_ChonCauHinh.md` | **−32,9%** MAE | **−28,5%** MAE | "walk-forward group-level" |

Cả hai cùng mô tả một phép đo. Không thể cùng đúng.

### 1.3 · Cách xử lý

1. **Chốt một cấu hình sản xuất duy nhất**, viết thành hằng số ở một chỗ — ví dụ `PRODUCTION_CONFIG = dict(use_weather=True, method="top_down_dynamic", from_period=None, ewma_span=6)` — rồi **cả ba service lẫn `evaluate.py` đều đọc từ đó**. Không chỗ nào được tự đặt tham số.
2. **Chạy lại `walk_forward_block` với đúng cấu hình đó** (sửa `evaluate.py:38` thành `build_default_ensemble(use_weather=True)` và cho `group_series` join thời tiết như `weather_effect` đang làm ở dòng 109-111). Bảng số này mới là bảng đưa vào chương 4.
3. **Quyết định số phận `topdown.py`.** Hoặc đưa nó vào bảng so sánh như một phương án thứ năm và báo cáo sai số riêng, hoặc chuyển Dashboard sang dùng chung ensemble. Không để nó ở ngoài mọi phép đo.
4. **Sửa hoặc gỡ một trong hai bảng thời tiết** — giữ lại bảng của lần chạy chính thức, xoá bảng còn lại, ghi rõ ngày chạy và cấu hình.

---

## 2. LỖI PHƯƠNG PHÁP

### 2.1 · [CAO] Lệch hệ thống do biến đổi log — và không có chỉ số nào phát hiện ra nó

`PoissonTrendForecaster:108,119`, `HarmonicPoissonForecaster:187,217`, `SarimaxForecaster:39,56` đều khớp trên `log1p(y)` rồi trả về `expm1(Xβ)`.

Phép này ước lượng **trung vị** của Y, không phải **kỳ vọng**. Với phân phối lệch phải như số ca bệnh, `expm1(E[log1p Y]) < E[Y]` — mô hình **thấp hơn thực tế một cách hệ thống**, không phải nhiễu ngẫu nhiên. Hệ số lệch xấp xỉ `exp(σ²/2)` với σ là độ lệch chuẩn phần dư trên thang log.

Đây là hiện tượng kinh điển (retransformation bias, Duan 1983). Điều đáng nói: `RaSoat_DeCuong_vs_ThucTe.md` ghi engine cũ *"dự báo hụt ~40% so với thực tế T6 (65 vs ~110)"* — hụt một chiều đúng là triệu chứng của lỗi này.

**Và không có chỉ số nào trong `evaluate.py` phát hiện được.** Dòng 79-82 báo MAE, RMSE, MASE — cả ba đều lấy **trị tuyệt đối** hoặc bình phương, nên **lệch một chiều bị triệt tiêu hoàn toàn**. Một mô hình hụt đều 15% và một mô hình sai ngẫu nhiên ±15% cho MAE giống hệt nhau.

**Sửa — hai việc, đều nhỏ:**

```python
# a) Thêm ME (sai số trung bình có dấu) vào metrics() — 2 dòng
"ME":   float(np.average([np.mean(p - a) ...], weights=w)),
"MPE%": float(...),   # lệch tương đối, dễ đọc hơn trong báo cáo

# b) Hiệu chỉnh smearing (Duan) trong các mô hình log — ~5 dòng mỗi mô hình
#    fit():     self._smear = float(np.mean(np.exp(t - X @ self.beta)))
#    predict(): pred = np.exp(float(X @ self.beta)) * self._smear - 1.0
```

**Vì sao đáng làm:** với một hệ hỗ trợ quyết định vật tư, **hụt hệ thống nguy hiểm hơn nhiễu ngẫu nhiên** — nó dẫn thẳng đến thiếu hàng lặp lại. Đo được và sửa được điều này là một luận điểm mạnh cho chương 4, không phải một dòng sửa lỗi.

⚠ Lưu ý khi làm: `SeasonalTrendForecaster` **không** biến đổi log, nên nó nằm trên thang trung bình. Ensemble hiện đang lấy trung bình một dự báo thang-trung-bình với hai đến ba dự báo thang-trung-vị — về mặt thống kê là trộn hai đại lượng khác nhau. Sau khi hiệu chỉnh smearing thì cả bốn thành viên mới cùng thang.

### 2.2 · [CAO] `Ensemble` nuốt mọi lỗi, không ghi lại thành viên nào đã đóng góp

`models.py:228-242`:

```python
def fit(self, df):
    for m in self.members:
        try: m.fit(df)
        except Exception: pass          # ← không log, không đánh dấu
def predict(self, next_month):
    for m in self.members:
        try: vals.append(m.predict(next_month))
        except Exception: pass
    return float(np.mean(vals)) if vals else 0.0
```

Ba hệ quả:

1. **Thành viên khớp lỗi vẫn được gọi `predict`.** Không có cờ đánh dấu fit thất bại, nên nếu `fit` ném lỗi mà `predict` không ném, giá trị rác vẫn vào trung bình.
2. **Số thành viên thực tế thay đổi âm thầm.** Với chuỗi mã thưa, SARIMAX thường không hội tụ (`KetQua_Backtest` đã ghi nhận loạt `ConvergenceWarning`) — khi đó ensemble tụt từ 3-4 xuống 2-3 thành viên mà không ai biết. **Không thể báo cáo "ensemble 4 thành viên" nếu số thành viên thực tế không được ghi lại.**
3. **Trọng số là trung bình đều, không phải trọng số thích ứng.** Cần sửa câu *"ensemble tự hạ trọng số mô hình tồi"* trong `KetQua_Backtest_ChonCauHinh.md` — `np.mean` không làm điều đó.

**Sửa:** thêm `self.last_members_used: list[str]` ghi tên thành viên đóng góp, `logger.warning` khi một thành viên rớt, và ghi danh sách này vào `disease_forecasts` cùng kết quả (khớp với việc lưu vết huấn luyện ở Tuần 4). Nếu muốn tiến thêm: trọng số nghịch đảo MSE backtest thay cho trung bình đều — nhưng đây là cải tiến, không bắt buộc.

⚠ Đi kèm: `evaluate.py:38` tạo **một** đối tượng ensemble rồi tái sử dụng cho cả chuỗi nhóm lẫn mọi mã (dòng 47-48). Hiện `fit()` của các thành viên đều đặt lại trạng thái nên chưa sai, nhưng cộng với việc nuốt lỗi ở trên thì đây là bẫy: một thành viên khớp lỗi trên mã C vẫn giữ trạng thái của mã C-1 và trả về dự báo **của chuỗi khác**. Nên tạo ensemble mới trong vòng lặp.

### 2.3 · [TRUNG BÌNH] Ridge không chuẩn hoá — mã tự mâu thuẫn với chính mình

`PoissonTrendForecaster._design` (`models.py:95-100`) tạo ma trận thiết kế gồm `[1, idx/12, 11 biến giả tháng]`. Với 92 tháng, `idx/12` chạy 0→7,6 còn biến giả chỉ 0/1. Hình phạt Ridge `lam=1.0` áp đều lên mọi hệ số (đã đúng khi loại chặn ở dòng 110), nhưng **vì thang đo khác nhau nên hình phạt rơi lệch**: cột biên độ lớn gần như không bị phạt, cột biên độ nhỏ bị phạt nặng.

Điều đáng chú ý: **chính dự án đã biết điều này**. `topdown.py:188-194` viết rõ trong docstring:

> *"Ridge có chuẩn hoá. Chuẩn hoá là bắt buộc, không phải trang trí: `t` chạy 0→90 còn `sin1` chạy −1→1; không chuẩn hoá thì hình phạt L2 rơi gần hết vào các cột biên độ nhỏ."*

Nguyên tắc đúng, chỉ chưa áp cho `models.py`. Sửa bằng cách chuẩn hoá cột trước khi giải, hoặc dùng thẳng `sklearn` như `topdown.py` (scikit-learn đã có trong `requirements.txt`).

Đồng thời `lam = 1.0` ở cả hai mô hình **chưa từng được dò**. Với 24 tháng huấn luyện tối thiểu và 13 tham số ở `PoissonTrend`, giá trị này quyết định khá nhiều. Nên dò `lam` bằng chính vòng walk-forward — một thí nghiệm nhỏ, và là một mục đáng viết trong chương 4.

### 2.4 · [TRUNG BÌNH] Hai chỉ số bị gọi sai tên

**a) "MinT" không phải MinT.** `hierarchical.py:25-43` tính `G = (SᵀS)⁻¹Sᵀ`, tức **hoà giải OLS** (W = I) — đúng như docstring dòng 30 tự ghi. MinT (Wickramasuriya, Hyndman & Athanasopoulos 2019) đòi ước lượng ma trận hiệp phương sai sai số W, thường kèm co rút. Cột "MinT" trong bảng kết quả nên đổi thành **"Hoà giải OLS"**. Người phản biện quen tài liệu dự báo phân cấp sẽ nhận ra ngay.

Ghi chú thêm: `np.maximum(G @ b, 0.0)` ở dòng 42 cắt giá trị âm, làm **mất tính nhất quán** (tổng dự báo mã không còn bằng dự báo nhóm). Nên nêu trong phần hạn chế.

**b) "MASE" đang là RelMAE.** `evaluate.py:81` lấy mẫu số là MAE của seasonal-naive chạy **out-of-sample** — chú thích dòng 30 nói rõ đây là lựa chọn có chủ ý ("so cùng điều kiện"), và đó là lựa chọn hợp lý. Nhưng docstring dòng 3 lại ghi *"MASE (chuẩn hóa theo seasonal-naive in-sample)"* — **mâu thuẫn với chính mã**. MASE theo định nghĩa Hyndman & Koehler dùng mẫu số in-sample; cái đang tính là **RelMAE** (relative MAE).

Không cần đổi công thức — chỉ cần **gọi đúng tên và giải thích vì sao chọn mẫu số out-of-sample**. Đó là một đoạn hay để viết vào báo cáo.

### 2.5 · [TRUNG BÌNH] Khoảng dự báo hẹp hơn danh nghĩa

`hierarchical_forecast_service._group_sigma` dựng σ từ phần dư walk-forward 12 bước gần nhất — **cách làm đúng**, tốt hơn nhiều so với công thức lý thuyết. Nhưng ba chi tiết làm khoảng dự báo không đạt độ phủ 95%:

| Vấn đề | Vì sao | Sửa |
|---|---|---|
| `np.std(res)` bỏ qua độ lệch | Nếu mô hình hụt hệ thống (mục 2.1), khoảng vẫn được đặt quanh một tâm bị lệch | Dùng RMSE phần dư thay cho std, hoặc hiệu chỉnh lệch trước |
| `Z_SERVICE = 1.96` với σ ước lượng từ 12 điểm | σ có sai số ước lượng; đúng ra dùng phân phối t với ~11 bậc tự do → **t = 2,20**, tức khoảng hiện tại **hẹp hơn ~12%** | Đổi hằng số, hoặc dùng phân vị thực nghiệm của phần dư |
| Khoảng đối xứng trên dữ liệu đếm lệch phải | Cận dưới bị cắt về 0 (`:142`), nên độ phủ thực tế < 95% | Dùng phân vị thực nghiệm, hoặc khoảng trên thang log rồi biến đổi ngược |

Cách rẻ nhất và dễ bảo vệ nhất: thay `mean ± z·σ` bằng **phân vị 2,5% và 97,5% của phần dư walk-forward**. Không giả định phân phối, tự nhiên bất đối xứng, và **kiểm chứng được** — chạy backtest rồi đếm xem bao nhiêu phần trăm giá trị thật rơi trong khoảng. Con số độ phủ thực nghiệm đó là một kết quả đáng đưa vào báo cáo.

Chi phí cần biết: `_group_sigma` khớp lại ensemble **12 lần** cho mỗi lần dự báo. Có SARIMAX trong đó nên không rẻ.

### 2.6 · [THẤP] Các điểm kỹ thuật nhỏ

| Vị trí | Vấn đề |
|---|---|
| `models.py:62-64` | Hệ số mùa tính trên chuỗi **chưa khử xu hướng**, rồi mới khử mùa để khớp xu hướng. Phân rã một lượt — với chuỗi có dịch chuyển mức nền 3,66× (J09-J18) thì hệ số mùa hút một phần xu hướng. Lặp thêm một vòng là đủ |
| `models.py:64` | `sfac` **không chuẩn hoá về trung bình 1** — làm lệch mức dự báo |
| `models.py:217` | `np.array(row[:len(beta)]) @ beta[:len(row)]` — cắt ngắn âm thầm khi lệch chiều thay vì báo lỗi. Hiện chưa sai nhưng che giấu lỗi tương lai. Nên `assert len(row) == len(self.beta)` |
| `models.py:57,106,184` | Ngưỡng loại COVID không nhất quán: `>= 6`, `>= 14`, `>= max_lag + 6` — tuỳ tiện, không giải thích |
| `models.py:258` | SARIMAX chỉ được thêm **nếu môi trường có `statsmodels`** → cùng một mã cho ensemble 2 hay 3 thành viên tuỳ máy. **Rủi ro tái lập cho đồ án.** Nên ghi rõ số thành viên vào kết quả |
| `hierarchical_forecast_service.py:137` | `code_ens = build_default_ensemble()` — mức mã **không** dùng thời tiết trong khi mức nhóm có. Cố ý hay bỏ sót? Cần một dòng giải thích |

---

## 3. BA MÂU THUẪN TÀI LIỆU ↔ MÃ

Đây là nhóm dễ bị bắt nhất, và sửa nhanh nhất.

| # | Tài liệu nói | Mã thực tế | Xử lý |
|---|---|---|---|
| 1 | `RaSoat_DeCuong_vs_ThucTe.md`: *"is_covid 2020–2021, dùng làm **biến ngoại sinh SARIMAX**"* | `sarimax_opt.py:25-33` — `_exog()` **chỉ** lấy `temp, humidity, rainfall`. Không có `is_covid` ở bất kỳ đâu. Các mô hình khác dùng `is_covid` để **loại dòng**, không phải làm biến | Sửa tài liệu, **hoặc** thêm `is_covid` vào exog thật (2 dòng) rồi đo lại |
| 2 | `KetQua_Backtest`: thời tiết giảm **32,9% / 28,5%** MAE | `forecasting/README.md:44-48`: **8,4% / 8,1%** | Chạy lại một lần, giữ một bảng, ghi ngày và cấu hình |
| 3 | `KetQua_Backtest`: *"ensemble tự hạ trọng số mô hình tồi"* | `models.py:242` — `np.mean` trung bình đều | Sửa câu thành *"trung bình hoá làm loãng ảnh hưởng của thành viên tồi"* |

---

## 4. THỨ TỰ ĐIỀU CHỈNH

Gắn vào kế hoạch 6 tuần đã lập.

### Tuần 4 — bắt buộc, không lùi được

| # | Việc | Công |
|---|---|---|
| M1 | Chốt `PRODUCTION_CONFIG` một chỗ; `evaluate.py` và cả 3 service đọc từ đó | 1 buổi |
| M2 | Chạy lại `walk_forward_block` **có thời tiết** — bảng số chính thức cho chương 4 | nửa buổi (máy chạy) |
| M3 | Thêm **ME / MPE%** (sai số có dấu) vào `metrics()` — phát hiện lệch hệ thống | 30 phút |
| M4 | Sửa 3 mâu thuẫn tài liệu ở mục 3 | 30 phút |
| M5 | Đổi tên "MinT" → "Hoà giải OLS"; ghi rõ chỉ số đang dùng là RelMAE và vì sao | 30 phút |
| M6 | `Ensemble` ghi lại thành viên đã đóng góp + cảnh báo khi rớt; tạo ensemble mới trong vòng lặp `evaluate.py` | nửa buổi |
| M7 | Thêm sMAPE + WAPE (cam kết đề cương, đã nợ từ 09/08) | 30 phút |

### Tuần 4-5 — nên làm, giá trị khoa học cao

| # | Việc | Vì sao đáng |
|---|---|---|
| M8 | Hiệu chỉnh smearing cho các mô hình log; đo lệch trước và sau bằng ME | Biến một lỗi thành một kết quả nghiên cứu. Trực tiếp phục vụ luận điểm "hụt hệ thống gây thiếu hàng" |
| M9 | Khoảng dự báo bằng phân vị thực nghiệm; **báo cáo độ phủ đo được** | Con số độ phủ thực nghiệm là bằng chứng mạnh, hiếm đồ án có |
| M10 | Chuẩn hoá cột trước Ridge trong `models.py`; dò `lam` bằng walk-forward | Áp đúng nguyên tắc mà `topdown.py` đã tự phát biểu |

### Sau bảo vệ

M11 hợp nhất `topdown.py` với ensemble · M12 trọng số nghịch đảo MSE · M13 MinT thật có co rút hiệp phương sai · M14 chuẩn hoá hệ số mùa và lặp hai vòng.

---

## 5. NHỮNG GÌ LÀM ĐÚNG — GIỮ NGUYÊN VÀ NÊN NÓI RA KHI BẢO VỆ

| Điểm | Vị trí |
|---|---|
| **Walk-forward mở rộng cửa sổ, dự báo 1 bước, `min_train` rõ ràng** — không rò rỉ thứ tự thời gian | `evaluate.py:39-69` |
| **Thời tiết chỉ dùng ở độ trễ 1-2 tháng**, và lúc dự báo lấy từ dữ liệu **đã quan sát** (`j = i - L`) — không rò rỉ tương lai, đúng cơ chế dịch tễ | `models.py:172-177, 211-216` |
| **Khoảng dự báo dựng từ sai số backtest thực nghiệm**, không phải công thức lý thuyết | `hierarchical_forecast_service._group_sigma` |
| **Loại tháng COVID khi ước lượng mùa vụ và xu hướng**, có ngưỡng an toàn để không loại quá tay | `models.py:57, 106, 184` |
| **Giảm dần độ ngoại suy xu hướng** (`damping=0.9`) để chuỗi không trôi | `models.py:78-81` |
| **Chọn top-down bằng thí nghiệm, không bằng cảm tính** — và trung thực báo cáo trường hợp bottom-up nổ MASE 483,7 thay vì giấu đi | `KetQua_Backtest_ChonCauHinh.md` |
| **Phân tích độ nhạy theo cửa sổ lịch sử**, kèm cảnh báo rằng so MASE giữa các cửa sổ là không chặt chẽ | như trên |
| **Docstring giải thích *vì sao*, không chỉ *cái gì*** — `data_access.group_series` nêu rõ khi nào phải cắt lịch sử và đo bằng cách nào | `data_access.py:27-38` |

Mục cuối đáng nói riêng: chất lượng chú thích trong `app/forecasting` cao hơn hẳn mặt bằng. Nhiều đoạn ghi lại **lý do đưa ra quyết định** và **cách kiểm chứng lại** — đó là thứ giúp người đọc báo cáo tin rằng các lựa chọn có căn cứ.

---

*Rà soát dựa trên đọc toàn văn `app/forecasting/*` và truy vết mọi nơi gọi `build_default_ensemble` tại thời điểm 09/09/2026.*
