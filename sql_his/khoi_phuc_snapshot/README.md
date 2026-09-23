# khoi_phuc_snapshot/ — dựng lại MEDFORECAST_DW trên SQL Server cục bộ

Thứ tự sau khi nhận file `.bak` từ bệnh viện:

| Bước | Việc | Ai/ở đâu |
|---|---|---|
| 0 | `RESTORE DATABASE MEDFORECAST_DW FROM DISK = N'...\MEDFORECAST_DW.bak' WITH MOVE ...` | SSMS, sysadmin |
| 1 | `01_quyen_sau_restore.sql` — nối lại user mồ côi, cấp SELECT toàn schema dbo | SSMS, sysadmin |
| 2 | (chỉ khi view thiếu) `../01_STA_tao_database_va_bang.sql` mục view, `../phase0/Phase0_01_STA_bang_moi.sql`, `../phase0/G1_01_STA_sua_bang.sql` — đều `CREATE OR ALTER` | SSMS |
| 3 | `cd backend && python scripts/kiem_tra_ket_noi_dw.py` — 6 bước OK | máy trạm |
| 4 | Quản trị → Nguồn dữ liệu (CSDL DW) → Kiểm tra kết nối → Lưu → Tổng quan → Nạp dữ liệu DW | giao diện |

Dùng **Windows Authentication** thì bỏ bước 1 (tài khoản Windows của anh thường đã là sysadmin trên instance cục bộ) — chọn "Windows Authentication" trong ô Xác thực.
