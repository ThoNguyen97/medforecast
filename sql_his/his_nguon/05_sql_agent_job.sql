/* his_nguon/05_sql_agent_job.sql
   Chạy trên: máy chủ CSDL HIS, CSDL msdb.
   Mục đích: tạo SQL Agent job chạy usp_MedForecast_DayDuLieu hằng ngày 01:00, so le với
   PIPELINE_CRON (02:00) của ứng dụng; chạy thử bằng tay để đo thời lượng trước khi bật lịch.
   Điều kiện: đã chạy his_nguon/01..04. */

USE msdb;
GO

DECLARE @JobName sysname = N'MedForecast - Dong bo du lieu HIS sang MEDFORECAST_DW';
DECLARE @HisDb   sysname = N'HISDB';        -- CSDL HIS nguồn

IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = @JobName)
    EXEC sp_delete_job @job_name = @JobName;

EXEC sp_add_job
     @job_name    = @JobName,
     @description = N'Tong hop du lieu kham benh + ton kho tren CSDL HIS roi day sang MEDFORECAST_DW. Cua so tong hop lai 3 thang.',
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
     -- Nhiều bệnh viện trong CSDL: thêm @BENHVIEN_ID. @NguongOToiThieu không đặt 0 cho job tự động;
     -- @XuLyVungKhongXacDinh = 2 làm hụt ~2,4% số ca. Đổi phạm vi bệnh thì sửa @NhomBenhDich tại đây.
     @retry_attempts = 2,
     @retry_interval = 15;      -- phút

EXEC sp_add_jobschedule
     @job_name          = @JobName,
     @name              = N'Hang ngay 01:00',
     @freq_type         = 4,        -- hằng ngày
     @freq_interval     = 1,
     @active_start_time = 010000;

EXEC sp_add_jobserver @job_name = @JobName;
GO

/* Chạy thử ngay */
-- EXEC msdb.dbo.sp_start_job @job_name = N'MedForecast - Dong bo du lieu HIS sang MEDFORECAST_DW';

/* Kết quả các lần chạy gần nhất */
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
WHERE  j.name = N'MedForecast - Dong bo du lieu HIS sang MEDFORECAST_DW'
ORDER BY h.run_date DESC, h.run_time DESC;
