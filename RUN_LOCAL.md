# Chạy thử cục bộ (trước khi deploy) — Windows

Chạy 2 cửa sổ terminal: một cho backend, một cho frontend. Dùng SQLite sẵn có
(không cần Docker/Postgres ở bước thử này).

## 1) Backend (FastAPI)
```powershell
cd D:\Personnal\LienThong\CDTN\webyte\webyte\backend
python -m venv venv                # nếu chưa có
venv\Scripts\activate
pip install -r requirements.txt    # lần đầu — mất khoảng 5-10 phút
uvicorn app.main:app --reload --port 8000
```
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
- Đăng nhập **admin / admin123**. Nếu sai mật khẩu: `python scripts\create_admin_user.py`.
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
- **Trang Kế hoạch nhập kho trống / 503**: chưa bấm Đồng bộ (mart trống) → bấm
  Đồng bộ ở trang Dịch tễ trước.
- **Network Error / 404 ở mọi API**: backend chưa chạy, hoặc đang chạy ở cổng khác
  8000 (Vite proxy trỏ cứng sang `http://localhost:8000`, đổi bằng biến
  `VITE_PROXY_TARGET`).
- **CORS**: `backend\.env` cần `CORS_ORIGINS` chứa `http://localhost:3000` (đã có).
- **Đăng nhập lỗi**: chạy `python scripts\seed_data.py` để tạo lại admin (nếu DB mới).
- **`ModuleNotFoundError: xgboost` / `prophet`**: chưa cài hết requirements — xem
  ghi chú ở mục 1.
