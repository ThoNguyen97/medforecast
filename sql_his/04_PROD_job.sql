/* =============================================================================
   04 — BƯỚC 4: SQL AGENT JOB CHẠY THỦ TỤC ĐẨY DỮ LIỆU
   =============================================================================
   Chạy trên: HIS PROD (msdb). Cần chạy script 01, 02, 03 trước.

   LỊCH CHẠY PHẢI SO LE VỚI ỨNG DỤNG
   Job này 01:00 → đẩy dữ liệu từ PROD xuống STA.
   MedForecast 02:00 (PIPELINE_CRON) → đọc STA dựng mart.
   Chạy trùng giờ thì ứng dụng sẽ đọc dữ liệu cũ một ngày.

   Job chạy trên máy chủ production nên đặt ngoài giờ cao điểm. Thử một lần
   bằng tay và xem mất bao lâu trước khi bật lịch.
============================================================================= */

USE msdb;
GO

DECLARE @JobName sysname = N'MedForecast - Day du lieu tu PROD xuong STA';
DECLARE @HisDb   sysname = N'HISDB';        -- ⚙ tên database HIS trên PROD

IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = @JobName)
    EXEC sp_delete_job @job_name = @JobName;

EXEC sp_add_job
     @job_name    = @JobName,
     @description = N'Tong hop du lieu kham benh + ton kho tren PROD roi day xuong MEDFORECAST_DW ben STA. Cua so tong hop lai 3 thang.',
     @enabled     = 1;

EXEC sp_add_jobstep
     @job_name       = @JobName,
     @step_name      = N'Chay thu tuc tong hop va day',
     @subsystem      = N'TSQL',
     @database_name  = @HisDb,
     @command        = N'EXEC dbo.usp_MedForecast_DayDuLieu
                              @SoThangLuiLai        = 3,
                              @NhomBenhDich         = N''J00-J06,J09-J18,J20-J22'',
                              @XuLyVungKhongXacDinh = 1,
                              @NguongOToiThieu      = 5;',
     -- ⚙ Nếu script 00 mục 1 cho thấy DB có nhiều bệnh viện, thêm @BENHVIEN_ID = 79428.
     --
     -- @NguongOToiThieu là ngưỡng ô nhỏ chống tái định danh — ĐỪNG đặt 0 ở job chạy
     -- tự động; 0 chỉ dùng khi đối chiếu thủ công với query gốc.
     --
     -- @XuLyVungKhongXacDinh = 1 (gộp ca không rõ tỉnh vào 'Tỉnh khác') là giá trị
     -- duy nhất nên dùng cho job. Đặt = 2 (loại bỏ hẳn, giống query export gốc) làm
     -- hụt ~2,4% số ca khỏi chuỗi mà mô hình học — và phần hụt đó lại thay đổi theo
     -- việc có bật ngưỡng ô nhỏ hay không, nên chuỗi huấn luyện sẽ không ổn định.
     --
     -- @NhomBenhDich là ba nhóm ICD trong đề cương. Ghi tường minh ở đây để người
     -- vận hành thấy ngay phạm vi bệnh mà không phải mở thủ tục ra đọc. Đổi phạm
     -- vi thì sửa đúng dòng này, KHÔNG sửa thủ tục.
     @retry_attempts = 2,
     @retry_interval = 15;      -- thử lại sau 15 phút nếu STA hoặc mạng chưa sẵn sàng

EXEC sp_add_jobschedule
     @job_name          = @JobName,
     @name              = N'Hang ngay 01:00',
     @freq_type         = 4,        -- hằng ngày
     @freq_interval     = 1,
     @active_start_time = 010000;

EXEC sp_add_jobserver @job_name = @JobName;
GO

/* --- Chạy thử ngay, không chờ tới 01:00 ---------------------------------- */
-- EXEC msdb.dbo.sp_start_job @job_name = N'MedForecast - Day du lieu tu PROD xuong STA';

/* --- Xem kết quả lần chạy gần nhất --------------------------------------- */
SELECT TOP 10
       j.name                                   AS Job,
       h.run_date, h.run_time,
       h.run_duration                           AS ThoiLuong_HHMMSS,
       CASE h.run_status WHEN 0 THEN N'Thất bại' WHEN 1 THEN N'Thành công'
                         WHEN 2 THEN N'Thử lại'  WHEN 3 THEN N'Đã huỷ'
                         ELSE N'Đang chạy' END   AS TrangThai,
       h.message
FROM   msdb.dbo.sysjobhistory h
JOIN   msdb.dbo.sysjobs j ON j.job_id = h.job_id
WHERE  j.name = N'MedForecast - Day du lieu tu PROD xuong STA'
ORDER BY h.run_date DESC, h.run_time DESC;
