/* =============================================================================
   prod/05_sql_agent_job.sql
   Chạy trên: HIS PROD, CSDL msdb.
   Mục đích: tạo SQL Agent job chạy usp_MedForecast_DayDuLieu hằng ngày 01:00
   để đẩy dữ liệu PROD → STA.
   Điều kiện: đã chạy prod/01..04.

   Lịch phải so le với pipeline ứng dụng (PIPELINE_CRON, 02:00); chạy trùng giờ
   thì ứng dụng đọc dữ liệu cũ một ngày. Job dùng tài nguyên máy chủ production
   nên đặt ngoài giờ cao điểm; chạy thử bằng tay để đo thời lượng trước khi bật lịch.
============================================================================= */

USE msdb;
GO

DECLARE @JobName sysname = N'MedForecast - Day du lieu tu PROD xuong STA';
DECLARE @HisDb   sysname = N'HISDB';        -- tên CSDL HIS trên PROD

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
     -- Nếu CSDL chứa nhiều bệnh viện, thêm @BENHVIEN_ID = 79428.
     --
     -- @NguongOToiThieu: ngưỡng ô nhỏ k chống tái định danh; không đặt 0 cho job
     -- tự động (0 chỉ dùng khi đối chiếu thủ công với truy vấn gốc).
     --
     -- @XuLyVungKhongXacDinh = 1: gộp ca không rõ tỉnh vào 'Tỉnh khác'. Giá trị 2
     -- (loại bỏ) làm hụt khoảng 2,4% số ca, và phần hụt còn phụ thuộc việc bật
     -- ngưỡng ô nhỏ, khiến chuỗi huấn luyện không ổn định.
     --
     -- @NhomBenhDich: ba nhóm ICD của đề cương, ghi tường minh để người vận hành
     -- thấy phạm vi bệnh. Đổi phạm vi thì sửa tại đây, không sửa thủ tục.
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

/* ── Chạy thử ngay, không chờ tới 01:00 ── */
-- EXEC msdb.dbo.sp_start_job @job_name = N'MedForecast - Day du lieu tu PROD xuong STA';

/* ── Kết quả các lần chạy gần nhất ── */
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
