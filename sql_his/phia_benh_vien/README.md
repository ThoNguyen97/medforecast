# phia_benh_vien/ — thủ tục PHÍA CƠ SỞ Y TẾ sinh ra snapshot MEDFORECAST_DW

**Ứng dụng MedForecast không chạy bất kỳ file nào trong thư mục này.** Đây là
các thủ tục T-SQL mà bộ phận CNTT bệnh viện thực thi trên SQL Server HIS
(eHospital PROD) để:

1. **Tổng hợp và khử định danh** ngay trong vùng bệnh viện — gộp theo
   (kỳ tháng × nhóm/mã ICD × rổ chăm sóc × vật tư). Không có mã bệnh nhân,
   ngày khám cụ thể, họ tên, số định danh hay địa chỉ rời khỏi HIS.
2. Ghi kết quả vào database `MEDFORECAST_DW` (12 bảng `dbo.MF_*`, kèm
   `MF_Watermark` = mốc kỳ đã chốt và `MF_SyncLog` = nhật ký chạy).
3. **Bàn giao snapshot** database này (bản `.bak`) cho nhóm nghiên cứu theo đợt.

Nhóm nghiên cứu **khôi phục snapshot trên SQL Server cục bộ** của máy trạm;
ứng dụng đọc 7 view `vw_MedForecast_*` tại đó (xem `../01_STA_tao_database_va_bang.sql`,
`../phase0/Phase0_01_STA_bang_moi.sql`, `../phase0/G1_01_STA_sua_bang.sql` —
các file tạo bảng/view, chạy lại được trên bản khôi phục nếu view thiếu).

| File | Việc phía bệnh viện |
|---|---|
| `00_PROD_xac_nhan_cot.sql` | Xác nhận cột/bảng HIS trước khi viết thủ tục |
| `02_PROD_linked_server.sql` | Linked server PROD → máy chứa `MEDFORECAST_DW` (giai đoạn bệnh viện chạy nội bộ) |
| `03_PROD_store_tong_hop.sql` → `phase0/G1_00_PROD_store_cabenh_v3.sql` | `usp_MedForecast_DayDuLieu`: ca bệnh theo mã/nhóm ICD, theo rổ chăm sóc, tồn kho |
| `phase0/G1_02…`, `G2_03…_v2.sql` | `usp_MedForecast_DayTieuHaoToanVien`: tiêu hao toàn viện + D_baseline |
| `phase0/Phase0_03…`, `G2_01…_v2.sql` | `usp_MedForecast_DayKhoCungUng`: ảnh chụp tồn kho theo lô (FEFO) |
| `phase0/G2_04_PROD_sua_danh_muc_dich_truyen.sql` | Sửa danh mục dịch truyền trước khi đo |
| `04_PROD_job.sql` | SQL Agent job — chỉ dùng nếu bệnh viện tự chạy định kỳ; với bàn giao theo đợt thì chạy tay |

Ý nghĩa với luận văn: ba thủ tục này là **bằng chứng nguồn gốc dữ liệu**
(data provenance) — cho biết mỗi bảng `MF_*` được tính từ bảng HIS nào, gộp
ở mức nào, và khử định danh ở bước nào. Chúng thuộc Chương 3 (thu thập dữ
liệu), không thuộc hướng dẫn cài đặt ứng dụng (Chương 4).
