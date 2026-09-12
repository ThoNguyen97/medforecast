# Chạy thử cục bộ (trước khi deploy) — Windows

Chạy 2 cửa sổ terminal: một cho backend, một cho frontend. Dùng SQLite sẵn có
(không cần Docker/Postgres ở bước thử này).

## 0) Máy MỚI vừa `git clone` — chạy một lệnh khởi tạo

`backend\.env` và `backend\data\*.db` **không nằm trong git** (chứa mật khẩu HIS
và dữ liệu bệnh viện). Clone xong là thư mục trống: backend tự tạo một DB rỗng,
không có tài khoản nào, và mọi lần đăng nhập trả **401**. Lệnh dưới lấp đúng
khoảng trống đó — tạo `.env`, tạo bảng, tạo tài khoản, nạp bộ dữ liệu đóng gói:

```powershell
cd <thư-mục-repo>\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts\khoi_tao_moi.py          # ~10 giây
```

Sau đó chạy được ngay: đăng nhập (**admin / admin123**, đổi mật khẩu ngay), trang
Dữ liệu bệnh, Phân tích & Dự báo, và Dashboard phần dịch tễ (số ca, xu hướng, dự
báo kỳ tới, chất lượng mô hình) — vì `dataset\v1` đã có 92 tháng số ca + thời tiết.

Phần **vật tư** (tồn kho, DOI, Cảnh báo thiếu hụt) cần dữ liệu kho của bệnh viện:
vào **Quản trị → Kết nối HIS**, nhập thông tin STA rồi bấm **Đồng bộ**. Bộ dữ liệu
công bố không chứa dữ liệu vật tư, nên trước khi đồng bộ Dashboard sẽ ghi rõ
"thiếu dữ liệu tồn kho" thay vì hiện 0.

Muốn máy mới giống hệt máy đang làm việc thì chép `backend\data\medforecast.db`
và `backend\.env` sang — nhưng chỉ làm vậy giữa hai thư mục của **cùng một người**;
DB chứa dữ liệu bệnh viện, không gửi ra ngoài.

## 0.1) Máy ĐÃ chạy trước đó, nhưng mã nguồn vừa đổi bảng

DB không nằm trong git nên mỗi máy giữ lược đồ riêng. Khi khởi động, backend gọi
`Base.metadata.create_all`: lệnh đó **tạo bảng còn thiếu nhưng không bao giờ thêm
cột** vào bảng đã có — và không báo lỗi. Backend vẫn lên, đến khi màn hình nào
chạm cột mới thì chết với `no such column: ...`.

Sau mỗi lần `git pull` có thay đổi model, chạy:

```powershell
cd <thư-mục-repo>\backend
venv\Scripts\activate
python -m scripts.nang_cap_db              # xem sẽ đổi gì (chạy khô)
python -m scripts.nang_cap_db --ap-dung    # thực thi, tự sao lưu DB trước
```

Script so `Base.metadata` với lược đồ thật trong SQLite: tạo bảng còn thiếu, sinh
`ALTER TABLE ... ADD COLUMN` cho cột còn thiếu, và **chỉ báo cáo** những việc
SQLite không làm an toàn được (xoá cột, đổi kiểu, cột `NOT NULL` không có giá trị
mặc định) để xử lý tay. Chạy lại nhiều lần vô hại.

Nếu máy đó không có dữ liệu HIS cần giữ thì đơn giản hơn: xoá
`backend\data\medforecast.db` rồi chạy lại `python scripts\khoi_tao_moi.py`.

## 0.2) Xoá hẳn DB và dựng lại từ đầu

```powershell
cd <thư-mục-repo>\backend
venv\Scripts\activate
copy data\medforecast.db data\saoluu_truoc_khi_xoa.db   # giữ lại cho chắc
del data\medforecast.db
del data\medforecast_dw.db          # file thừa từ lần tách DB cũ
python scripts\khoi_tao_moi.py
uvicorn app.main:app --reload --reload-dir app --port 8000
```

**Mất gì:** toàn bộ dữ liệu HIS đã đồng bộ (tồn kho, tiêu hao,
`fact_usage/cases_by_care_level`). `dataset\v1` KHÔNG có phần vật tư — phải vào
**Quản trị → Kết nối HIS → Đồng bộ** mới có lại Cảnh báo thiếu hụt và Định mức
thực nghiệm. Trước đó hai màn hình đó ghi rõ "thiếu dữ liệu tồn kho", đúng thiết kế.

**Giữ lại ghi chú nguồn:** `khoi_tao_moi` gieo `dss.care_level` và
`dss.thresholds` bằng giá trị mặc định (18/36 ngày, cửa sổ 12 kỳ từ 2025-04).
Phần chú thích `nguon` (Đ9, Đ11) trong DB cũ sẽ mất — muốn giữ thì chép lại
trước khi xoá:

```powershell
python -c "import sqlite3;c=sqlite3.connect('data/medforecast.db');[print(r) for r in c.execute(\"SELECT config_key, config_value FROM system_config WHERE config_key LIKE 'dss.%'\")]"
```

## 1) Backend (FastAPI)
```powershell
cd D:\Personnal\LienThong\CDTN\webyte\webyte\backend
python -m venv venv                # nếu chưa có
venv\Scripts\activate
pip install -r requirements.txt    # lần đầu — mất khoảng 5-10 phút
uvicorn app.main:app --reload --reload-dir app --port 8000
```
> `--reload-dir app` để watcher chỉ theo dõi mã nguồn; thiếu nó thì mỗi lần
> SQLite ghi là một dòng log "changes detected" (log phình hàng chục nghìn dòng).
- Kiểm tra: mở http://localhost:8000/docs → thấy các nhóm API (có `data-sync`,
  `supply-planning`, `forecast-hierarchical`).
- Lần khởi động đầu, backend tự tạo thêm các bảng `stg_/dim_/fact_/mart_` của tầng
  dữ liệu ngay trong `data\medforecast.db`. Log sẽ ghi
  `Data-pipeline (mart) tables verified / created.`

> **Cài đặt lâu?** `xgboost` và `prophet` chiếm phần lớn thời gian nhưng **không
> endpoint nào dùng tới** — chúng chỉ bị kéo theo vì `app/ai_engine/__init__.py`
> import sẵn ở đầu file. Muốn cài nhanh: xoá (hoặc chú thích) 3 dòng
> `from .xgboost_forecaster import ...` / `prophet_forecaster` / `ensemble_forecaster`
> trong `app\ai_engine\__init__.py`, rồi chú thích luôn `xgboost`, `prophet`,
> `celery`, `redis` trong `requirements.txt`.

> **Lỗi ở `pyodbc`** (chỉ cần khi nối HIS SQL Server): chú thích dòng `pyodbc`
> trong `requirements.txt` rồi cài lại — không ảnh hưởng chạy thử với nguồn file.

## 2) Frontend (React + Vite)
```powershell
cd D:\Personnal\LienThong\CDTN\webyte\webyte\frontend
npm install                        # lần đầu
npm run dev
```
- Mở **http://localhost:3000** (cổng đặt trong `vite.config.ts`, không phải 5173).
- Đăng nhập **admin / admin123**. Chưa có tài khoản: `python scripts\khoi_tao_moi.py`
  (hoặc `python scripts\create_admin_user.py` nếu chỉ cần tạo mỗi tài khoản).
- Frontend gọi API qua đường dẫn tương đối `/api/v1`, được Vite proxy sang
  `http://localhost:8000`. Vì vậy **phải chạy backend trước**.

## 3) Kịch bản kiểm thử (theo thứ tự)
1. Vào trang **Dịch tễ** → bấm nút **Đồng bộ HIS** (góc trên bên phải).
   - Job đọc `webyte\data\data_GIAAN_...csv` + tồn kho + thời tiết → dựng các bảng
     mart. Chờ vài giây, thấy số dòng đã nạp.
   - Đây là bước **bắt buộc ở lần chạy đầu**: chưa đồng bộ thì mart trống và trang
     Kế hoạch nhập kho sẽ không có dữ liệu.
2. Vào menu **Kế hoạch nhập kho**:
   - Chọn nhóm bệnh (J00–J06 / J20–J22) → xem dự báo + khoảng dự báo + badge
     "Có dùng thời tiết" + bảng đề xuất nhập (nhu cầu / mức an toàn / tồn / đề xuất).
3. Kiểm tra các trang cũ (Dashboard, Tồn kho, Dự báo, Thời tiết, Báo cáo) vẫn chạy.

## 4) Checklist "ổn hay chưa"
- [ ] `/docs` mở được, không lỗi khởi động.
- [ ] Đăng nhập admin thành công.
- [ ] Bấm Đồng bộ → có số dòng, không lỗi 500.
- [ ] Trang Kế hoạch nhập kho hiện dữ liệu (không trống, không lỗi 503).
- [ ] Số tồn kho trong bảng khớp dữ liệu thật (khác 0).

Nếu tất cả ✔ thì sẵn sàng chuyển sang bước deploy Docker (xem DEPLOY.md).

## 5) Tự kiểm tra tầng đồng bộ (không cần chạy web)
```powershell
cd D:\Personnal\LienThong\CDTN\webyte\webyte\backend
venv\Scripts\activate
python scripts\verify_his_pipeline.py --data-dir ..\..\data
```
Chạy 28 kiểm tra trên SQLite tạm (không đụng DB của ứng dụng): không hồi quy số
liệu, watermark nạp lại đúng cửa sổ, cờ tháng-trọn-vẹn tự sửa, hợp đồng cột,
đường đọc SQL Server, và tính idempotent. Kỳ vọng: `KẾT QUẢ: TẤT CẢ PASS`.

## Lỗi thường gặp

### `IntegrityError: datatype mismatch` khi mở Tổng quan trên DB vừa dựng lại
Triệu chứng: đăng nhập được, `/api/v1/dashboard/v2` trả **500**, traceback dừng ở
`SELECT ... FROM v_care_level_share`.

Nguyên nhân: view đó đọc `system_config` để lấy cửa sổ tính. DB mới không có
dòng `dss.care_level` → truy vấn con trả NULL → `LIMIT NULL`, và SQLite coi đó
là lỗi kiểu. Lỗi nổ lúc **SELECT**, không phải lúc tạo view, nên
`khoi_tao_moi.py` vẫn báo "4/4 view" rồi trang mới chết.

Đã sửa 12/09/2026 (gieo sẵn hai dòng cấu hình + bọc `COALESCE` trong view). Máy
đã lỡ dựng DB bằng bản cũ thì chạy một lệnh là xong, không cần dựng lại:

```powershell
cd <thư-mục-repo>\backend
venv\Scripts\activate
python -c "from app.data_pipeline.views import dam_bao_luoc_do; [print(k, v) for k, v in dam_bao_luoc_do().items()]"
```

- **Log chạy như thác, toàn dòng `watchfiles.main - INFO - 1 change detected`**:
  `uvicorn --reload` dùng watchfiles; watchfiles ghi log ở mức INFO; dòng log đó
  được ghi vào `backend/logs/medforecast.log`; tệp log nằm TRONG thư mục đang
  theo dõi → watchfiles lại thấy thay đổi → ghi tiếp. Vòng lặp tự nuôi khoảng
  400 ms một vòng. Đã chặn trong mã (hạ `watchfiles` xuống WARNING), nhưng vẫn
  nên chạy đúng lệnh có `--reload-dir app` để watcher không quét cả `data\` và
  `logs\`.
- **Log toàn câu SQL**: `.env` đang đặt `DEBUG=True`. Từ 12/09 việc in SQL tách
  sang biến riêng `SQL_ECHO` (mặc định False) — bật `DEBUG` không còn kéo theo
  SQL nữa. Nếu vẫn thấy SQL thì kiểm tra `SQL_ECHO` trong `.env`.
- **Trang Kế hoạch nhập kho trống / 503**: chưa bấm Đồng bộ (mart trống) → bấm
  Đồng bộ ở trang Dịch tễ trước.
- **Network Error / 404 ở mọi API**: backend chưa chạy, hoặc đang chạy ở cổng khác
  8000 (Vite proxy trỏ cứng sang `http://localhost:8000`, đổi bằng biến
  `VITE_PROXY_TARGET`).
- **CORS**: `backend\.env` cần `CORS_ORIGINS` chứa `http://localhost:3000` (đã có).
- **Đăng nhập lỗi**: chạy `python scripts\seed_data.py` để tạo lại admin (nếu DB mới).
- **`ModuleNotFoundError: xgboost` / `prophet`**: chưa cài hết requirements — xem
  ghi chú ở mục 1.
