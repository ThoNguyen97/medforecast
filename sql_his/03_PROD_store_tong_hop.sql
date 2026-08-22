/* =============================================================================
   03 — BƯỚC 3: THỦ TỤC TỔNG HỢP TRÊN PROD VÀ ĐẨY XUỐNG STAGING
   =============================================================================
   Chạy trên: HIS PROD. Cần chạy script 01 và 02 trước.

   NGUỒN GỐC: thủ tục này là câu truy vấn export dataset của nhóm, giữ NGUYÊN
   logic nghiệp vụ, chỉ bổ sung phần cơ chế đồng bộ:
     • tham số hoá khoảng thời gian + nạp tăng dần theo mốc (watermark)
     • đẩy kết quả xuống STA qua linked server thay vì trả về màn hình
     • ghi nhật ký mỗi lần chạy
     • gộp thêm luồng tồn kho (query gốc chưa có)
     • chế độ @ChiXem để đối chiếu với query gốc trước khi bật job
     • ngưỡng ô nhỏ chống tái định danh (xem bước 3b)
     • mở phạm vi từ 4 mã lẻ lên ĐỦ BA NHÓM ICD theo đề cương, lấy danh mục
       từ TM_ICD.PHANNHOM thay vì viết cứng trong câu lệnh (xem bước 0b)
     • bảng số ca theo NHÓM tính riêng bằng COUNT(DISTINCT lượt khám) — không
       suy ra được từ bảng theo mã (xem bước 7b)

   TỔNG HỢP NGAY TRÊN PROD, CHỈ ĐẨY SỐ ĐÃ GỘP
   Không có mã bệnh nhân, không có ngày khám cụ thể, không có họ tên / số định
   danh / địa chỉ nào rời khỏi PROD.

   KHÔNG BAO GIỜ CỘNG DỒN VÀO DỮ LIỆU CŨ
   Mỗi lần chạy, thủ tục XOÁ sạch cửa sổ đang xử lý bên STA rồi CHÈN LẠI kết quả
   vừa tính. Không có phép cộng vào số cũ, nên chạy lại mười lần cũng ra đúng một
   kết quả. Ba lớp bảo vệ:
     1. Gom theo đúng hạt (tháng × mã bệnh × vùng × mã thuốc) — xem CTE Agg.
     2. Kiểm tra trùng khoá TRƯỚC khi đẩy, có trùng thì dừng, không đẩy.
     3. Đối chiếu số dòng bên STA sau khi đẩy; lệch thì báo lỗi.
   Bảng bên STA còn có UNIQUE index trên bộ khoá đó (script 01) — chốt chặn cuối.

   KHÔNG BỌC TRANSACTION QUANH PHẦN GHI XA
   Mở BEGIN TRANSACTION rồi ghi qua linked server sẽ nâng thành giao dịch phân
   tán và bắt buộc cấu hình MSDTC giữa hai máy — thường bị chặn. Thay vào đó ghi
   theo kiểu xoá-rồi-chèn từng cửa sổ, chạy lại được.
============================================================================= */

CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayDuLieu
    @SoThangLuiLai       INT   = 3,              -- khớp PIPELINE_LOOKBACK_MONTHS
    @NapLaiToanBo        BIT   = 0,
    @TuNgayGoc           DATE  = '2019-01-01',   -- mốc khi nạp lại toàn bộ
    @BENHVIEN_ID         INT   = NULL,           -- ⚙ đặt 79428 nếu DB nhiều bệnh viện
    @NhomBenhDich        NVARCHAR(400) = N'J00-J06,J09-J18,J20-J22',
                                                 -- 3 nhóm ICD theo đề cương; lấy thẳng
                                                 -- từ TM_ICD.PHANNHOM, KHÔNG hardcode mã
    @XuLyVungKhongXacDinh TINYINT = 1,           -- 0 = giữ nguyên nhãn '(Không xác định)'
                                                 -- 1 = gộp vào @NhanGopVung (mặc định, giữ đủ tổng)
                                                 -- 2 = loại bỏ (đúng như query export gốc)
    @NguongOutlier       FLOAT = NULL,           -- ví dụ 1000000; NULL = không cắt
    @NguongOToiThieu     INT   = 5,              -- ngưỡng ô nhỏ; 0 hoặc 1 = tắt
    @NhanGopVung         NVARCHAR(120) = N'Tỉnh khác',
    @GiuNhomKhongCoThuoc BIT   = 1,              -- 1 = giữ nhóm ca không có toa nào
                                                 -- (0 = giống hệt query export gốc)
    @ChiXem              BIT   = 0               -- 1 = chỉ SELECT, không đẩy xuống STA
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @BatDau  DATETIME2(0) = SYSDATETIME();
    DECLARE @Moc     DATE, @TuNgay DATE, @DenNgay DATE = CAST(GETDATE() AS DATE);
    DECLARE @nDong INT = 0, @nTonKho INT = 0, @nOGop INT = 0;
    DECLARE @ChuCaiDich CHAR(1), @nMaDich INT = 0, @nNhomDich INT = 0, @nDongNhom INT = 0;
    DECLARE @TongCa INT = 0,           -- số ca THỰC SỰ đẩy đi
            @TongCaGoc INT = 0,        -- số ca gốc, đo NGAY khi dựng xong #Dx
            @nCaKhongRoTinh INT = 0,   -- số ca bị loại vì không xác định được tỉnh
            @nNhomKhongThuoc INT = 0;  -- nhóm ca không có dòng thuốc nào

    BEGIN TRY
        /* --- Cửa sổ cần tổng hợp lại ------------------------------------- */
        IF @ChiXem = 0
            SELECT @Moc = MocDaDay
            FROM   [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
            WHERE  TenLuong = 'CaBenh';

        SET @TuNgay = CASE
            WHEN @NapLaiToanBo = 1 OR @Moc IS NULL THEN @TuNgayGoc
            ELSE DATEFROMPARTS(YEAR(DATEADD(MONTH, -@SoThangLuiLai, @Moc)),
                               MONTH(DATEADD(MONTH, -@SoThangLuiLai, @Moc)), 1)
        END;

        PRINT CONCAT(N'Tổng hợp từ ', CONVERT(varchar(10), @TuNgay, 120),
                     N' đến ', CONVERT(varchar(10), @DenNgay, 120));

        /* =====================================================================
           0) Danh mục TỈNH — dò trong địa chỉ text khi không suy ra được qua xã
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Tinh') IS NOT NULL DROP TABLE #Tinh;
        SELECT DISTINCT TENDONVI
        INTO   #Tinh
        FROM   TM_DONVIHANHCHINH
        WHERE  CAPDONVI = 2 AND LEN(TENDONVI) >= 4;

        /* =====================================================================
           0b) DANH MỤC MÃ BỆNH ĐÍCH — lấy theo NHÓM ICD, không hardcode mã
           ---------------------------------------------------------------------
           Đề cương chốt dự báo trên BA NHÓM ICD-10 rồi mới phân bổ xuống mã:
               J00-J06  Nhiễm khuẩn cấp đường hô hấp trên
               J09-J18  Cúm và viêm phổi
               J20-J22  Nhiễm khuẩn cấp đường hô hấp dưới khác
           Gom nhóm để mỗi chuỗi thời gian có đủ số quan sát — mã lẻ như J21 hay
           J13 vài tháng mới có một ca, không mô hình hoá được.

           `TM_ICD.PHANNHOM` của HIS CHÍNH LÀ mã nhóm (đã kiểm: 'J00-J06',
           'J09-J18', 'J20-J22'), nên lấy thẳng từ đó. Hệ quả:
             • đổi phạm vi bệnh = đổi tham số @NhomBenhDich, không sửa code
             • không còn phụ thuộc file TM_ICD.xlsx bên ứng dụng
             • tên bệnh lấy từ TM_ICD thay vì CASE cứng 4 dòng

           #IcdDich giữ TOÀN BỘ ICD_ID thuộc nhóm đích (kể cả mã 4 ký tự như
           J06.9) để lọc thẳng trên khoá số của bảng giao dịch — nhanh hơn nhiều
           so với LIKE trên chuỗi mã.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#NhomDich') IS NOT NULL DROP TABLE #NhomDich;
        SELECT LTRIM(RTRIM(value)) AS Nhom
        INTO   #NhomDich
        FROM   STRING_SPLIT(@NhomBenhDich, ',')
        WHERE  LTRIM(RTRIM(value)) <> '';

        SELECT @nNhomDich  = COUNT(*),
               @ChuCaiDich = MAX(LEFT(Nhom, 1))
        FROM   #NhomDich;

        IF @nNhomDich = 0
            THROW 50003, N'@NhomBenhDich rỗng — không biết lấy nhóm bệnh nào.', 1;

        IF (SELECT COUNT(DISTINCT LEFT(Nhom, 1)) FROM #NhomDich) > 1
            THROW 50004, N'@NhomBenhDich đang trộn nhiều chương ICD (khác chữ cái đầu). Thủ tục chỉ hỗ trợ một chương mỗi lần chạy.', 1;

        IF OBJECT_ID('tempdb..#IcdDich') IS NOT NULL DROP TABLE #IcdDich;
        SELECT icd.ICD_ID,
               LEFT(LTRIM(RTRIM(icd.MAICD)), 3) AS Ma3
        INTO   #IcdDich
        FROM   TM_ICD icd
        JOIN   #NhomDich n ON n.Nhom = LTRIM(RTRIM(icd.PHANNHOM))
        WHERE  icd.MAICD IS NOT NULL
          AND  LEN(LTRIM(RTRIM(icd.MAICD))) >= 3;
        CREATE UNIQUE CLUSTERED INDEX IX_IcdDich ON #IcdDich(ICD_ID);

        /* Mức MÃ 3 KÝ TỰ — hạt dữ liệu mà mô hình học, kèm nhóm cha.
           Tên bệnh ưu tiên dòng có mã đúng 3 ký tự (tên tổng quát của mã),
           thiếu thì lấy tên mã con đầu tiên.                                   */
        IF OBJECT_ID('tempdb..#Ma3') IS NOT NULL DROP TABLE #Ma3;
        SELECT
            m.Ma3,
            CAST(ISNULL(m.TenChinh, m.TenBatKy) AS NVARCHAR(400)) AS DiseaseName,
            m.Nhom                                                AS DiseaseGroup,
            CAST(ISNULL(tn.TenNhom, m.Nhom) AS NVARCHAR(255))     AS DiseaseGroupName
        INTO #Ma3
        FROM (
            SELECT LEFT(LTRIM(RTRIM(icd.MAICD)), 3) AS Ma3,
                   MIN(LTRIM(RTRIM(icd.PHANNHOM)))  AS Nhom,
                   MAX(CASE WHEN LEN(LTRIM(RTRIM(icd.MAICD))) = 3
                            THEN icd.TENICD END)    AS TenChinh,
                   MIN(icd.TENICD)                  AS TenBatKy
            FROM   TM_ICD icd
            JOIN   #NhomDich n ON n.Nhom = LTRIM(RTRIM(icd.PHANNHOM))
            WHERE  icd.MAICD IS NOT NULL
              AND  LEN(LTRIM(RTRIM(icd.MAICD))) >= 3
            GROUP BY LEFT(LTRIM(RTRIM(icd.MAICD)), 3)
        ) m
        LEFT JOIN (VALUES
            ('J00-J06', N'Nhiễm khuẩn cấp đường hô hấp trên'),
            ('J09-J18', N'Cúm và viêm phổi'),
            ('J20-J22', N'Nhiễm khuẩn cấp đường hô hấp dưới khác')
        ) AS tn(Nhom, TenNhom) ON tn.Nhom = m.Nhom;
        CREATE UNIQUE CLUSTERED INDEX IX_Ma3 ON #Ma3(Ma3);

        SELECT @nMaDich = COUNT(*) FROM #Ma3;
        IF @nMaDich = 0
            THROW 50005, N'Không tìm thấy mã ICD nào thuộc @NhomBenhDich trong TM_ICD — kiểm tra lại cột PHANNHOM.', 1;

        PRINT CONCAT(N'Phạm vi bệnh: ', @nNhomDich, N' nhóm (', @NhomBenhDich,
                     N') → ', @nMaDich, N' mã 3 ký tự.');

        /* =====================================================================
           1) #Enc — lượt khám thuộc các nhóm bệnh đích, GỘP nội trú + ngoại trú
           ---------------------------------------------------------------------
           BA.ICD_BENHCHINH lẫn lộn (khi thì ID số, khi thì text chẩn đoán) nên
           dùng TRY_CAST(... AS INT) để fallback an toàn.
           BA.ICD_BENHPHU là free-text (tên bệnh + mã trong ngoặc) — KHÔNG trích
           mã được, chỉ dùng KB.DS_MAICDPHU (danh sách mã chuẩn).
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Enc') IS NOT NULL DROP TABLE #Enc;

        -- 1a) NỘI TRÚ
        SELECT
            CAST('NT' AS VARCHAR(3)) AS LoaiDieuTri,
            KB.KHAMBENH_ID,
            tn.TIEPNHAN_ID,
            tn.BENHNHAN_ID,
            DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1) AS MonthStart,
            ISNULL(icdc.MAICD, icdBA.MAICD) AS PrimaryICD,
            KB.DS_MAICDPHU                  AS SubICD
        INTO #Enc
        FROM      TT_TIEPNHAN         tn
        JOIN      TT_NOITRU_BENHAN    BA    ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
        JOIN      TT_NOITRU_KHAMBENH  KB    ON KB.BENHAN_ID   = BA.BENHAN_ID
        LEFT JOIN TM_ICD              icdc  ON icdc.ICD_ID    = KB.ICDCHINH_ID
        LEFT JOIN TM_ICD              icdBA ON icdBA.ICD_ID   = TRY_CAST(BA.ICD_BENHCHINH AS INT)
        WHERE tn.NGAYTIEPNHAN >= @TuNgay
          AND tn.NGAYTIEPNHAN <  DATEADD(DAY, 1, @DenNgay)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
          /* Chẩn đoán CHÍNH lọc CHÍNH XÁC bằng khoá số (nhanh, có index).
             Chẩn đoán PHỤ chỉ lọc THÔ theo chương ICD ở đây — DS_MAICDPHU là
             chuỗi nhiều mã nên không lọc chính xác được; bước 3 tách chuỗi rồi
             JOIN #Ma3 mới là bộ lọc thật. Lọc thô cho ra tập CHA, không mất ca. */
          AND ( KB.ICDCHINH_ID IN (SELECT ICD_ID FROM #IcdDich)
             OR TRY_CAST(BA.ICD_BENHCHINH AS INT) IN (SELECT ICD_ID FROM #IcdDich)
             OR KB.DS_MAICDPHU LIKE '%' + @ChuCaiDich + '[0-9][0-9]%' );

        -- 1b) NGOẠI TRÚ
        INSERT INTO #Enc (LoaiDieuTri, KHAMBENH_ID, TIEPNHAN_ID, BENHNHAN_ID,
                          MonthStart, PrimaryICD, SubICD)
        SELECT 'NGT', KB.KHAMBENH_ID, tn.TIEPNHAN_ID, tn.BENHNHAN_ID,
               DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1),
               icdc.MAICD, KB.DS_MAICDPHU
        FROM TT_TIEPNHAN            tn
        JOIN TT_NGOAITRU_KHAMBENH   KB   ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
        JOIN TM_ICD                 icdc ON icdc.ICD_ID    = KB.CHANDOANICD_ID
        WHERE KB.NGAYKHAM >= @TuNgay
          AND KB.NGAYKHAM <  DATEADD(DAY, 1, @DenNgay)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
          AND ( KB.CHANDOANICD_ID IN (SELECT ICD_ID FROM #IcdDich)
             OR KB.DS_MAICDPHU LIKE '%' + @ChuCaiDich + '[0-9][0-9]%' );

        /* =====================================================================
           2) #PatReg — vùng (tỉnh) tính MỘT LẦN cho mỗi bệnh nhân
           ===================================================================== */
        IF OBJECT_ID('tempdb..#PatReg') IS NOT NULL DROP TABLE #PatReg;
        SELECT DISTINCT
               bn.BENHNHAN_ID,
               COALESCE(tinh.TENDONVI, addr.TENDONVI, N'(Không xác định)') AS Region
        INTO   #PatReg
        FROM       (SELECT DISTINCT BENHNHAN_ID FROM #Enc) e
        JOIN       TT_BENHNHAN        bn    ON bn.BENHNHAN_ID = e.BENHNHAN_ID
        LEFT JOIN  TM_DONVIHANHCHINH  xa    ON xa.MADONVI              = bn.XAPHUONG_ID
        LEFT JOIN  TM_DONVIHANHCHINH  huyen ON huyen.DONVIHANHCHINH_ID = xa.CAPTREN_ID
        LEFT JOIN  TM_DONVIHANHCHINH  tinh  ON tinh.DONVIHANHCHINH_ID  =
                   ISNULL(CASE WHEN xa.CAPDONVI = 3 THEN xa.CAPTREN_ID
                               ELSE huyen.CAPTREN_ID END, bn.TINHTHANH_ID)
        OUTER APPLY (
            SELECT TOP 1 p.TENDONVI FROM #Tinh p
            WHERE  tinh.TENDONVI IS NULL
              AND  bn.DIACHITHUONGTRU LIKE N'%' + p.TENDONVI + N'%'
            ORDER BY LEN(p.TENDONVI) DESC
        ) addr
        WHERE ISNULL(NULLIF(LTRIM(RTRIM(bn.ACTIVE)), ''), '1') <> '0';   -- bỏ hồ sơ đã ngưng/gộp trùng
        CREATE UNIQUE CLUSTERED INDEX IX_PatReg ON #PatReg(BENHNHAN_ID);

        /* =====================================================================
           3) #Dx — 1 dòng / (loại × lượt khám × mã bệnh), gộp chính + phụ
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Dx') IS NOT NULL DROP TABLE #Dx;
        SELECT DISTINCT
               x.LoaiDieuTri, x.KHAMBENH_ID, x.TIEPNHAN_ID, x.MonthStart,
               pr.Region, x.DiseaseCode
        INTO #Dx
        FROM (
            -- chẩn đoán CHÍNH
            SELECT e.LoaiDieuTri, e.KHAMBENH_ID, e.TIEPNHAN_ID, e.BENHNHAN_ID,
                   e.MonthStart, m.Ma3 AS DiseaseCode
            FROM   #Enc e
            JOIN   #Ma3 m ON m.Ma3 = LEFT(e.PrimaryICD, 3)
            UNION ALL
            -- chẩn đoán PHỤ (chỉ từ DS_MAICDPHU — danh sách mã chuẩn).
            -- JOIN #Ma3 ở đây mới là bộ lọc CHÍNH XÁC cho phần chẩn đoán phụ.
            SELECT e.LoaiDieuTri, e.KHAMBENH_ID, e.TIEPNHAN_ID, e.BENHNHAN_ID,
                   e.MonthStart, m.Ma3
            FROM   #Enc e
            CROSS APPLY STRING_SPLIT(e.SubICD, ';') s
            JOIN   #Ma3 m ON m.Ma3 = LEFT(TRIM(s.value), 3)
        ) x
        JOIN #PatReg pr ON pr.BENHNHAN_ID = x.BENHNHAN_ID;
        CREATE CLUSTERED INDEX IX_Dx ON #Dx(LoaiDieuTri, KHAMBENH_ID);

        /* Tên bệnh và nhóm cha KHÔNG giữ trong #Dx: chúng phụ thuộc hàm vào
           DiseaseCode nên chỉ cần JOIN #Ma3 một lần ở bước 7. Giữ trong #Dx sẽ
           phình bảng tạm và tạo rủi ro lệch nhãn giữa các dòng cùng mã.         */

        /* Đo số ca GỐC ngay tại đây — trước mọi phép gộp/lọc. Đây là mốc để
           đối chiếu về sau: mọi thay đổi cấu hình đều phải giải thích được
           bằng con số này trừ đi phần bị loại có chủ đích.                     */
        SELECT @TongCaGoc = SUM(Cases) FROM (
            SELECT COUNT(DISTINCT TIEPNHAN_ID) AS Cases
            FROM   #Dx GROUP BY MonthStart, Region, DiseaseCode) z0;

        /* =====================================================================
           3a) VÙNG KHÔNG XÁC ĐỊNH — phải xử lý TRƯỚC bước gộp ô nhỏ
           ---------------------------------------------------------------------
           Nếu để sau, những ô '(Không xác định)' nhỏ sẽ bị bước 3b gộp vào
           '@NhanGopVung' và thoát khỏi bộ lọc — số ca giao đi sẽ nhảy lên tuỳ
           theo có bật ngưỡng hay không. Đúng lỗi đã gặp: 248 ca không rõ tỉnh
           bị đổi nhãn thành 'Tỉnh khác' rồi lọt qua.

           Ba cách xử lý, chọn bằng @XuLyVungKhongXacDinh:
             0 — giữ nguyên nhãn '(Không xác định)' như một vùng riêng
             1 — GỘP vào '@NhanGopVung' (mặc định): giữ đủ tổng số ca, và về mặt
                 ngữ nghĩa "không rõ tỉnh" cũng là một dạng "khác"
             2 — LOẠI BỎ hẳn: đúng hành vi query export gốc, nhưng làm hụt tổng
                 (đo trên dữ liệu thật: 342/14.215 ca, tức 2,4%)
           ===================================================================== */
        /* Nhận diện nhãn "không rõ tỉnh" bằng LIKE chứ không so bằng (=):
           ngoài nhãn '(Không xác định)' do chính thủ tục sinh ra, bảng
           TM_DONVIHANHCHINH của HIS còn chứa các dòng placeholder do người
           dùng tạo — đã gặp thật: đơn vị tên 'Không Xác Định Tỉnh' (7 ca lọt
           qua bộ lọc và hiện lên ứng dụng như một tỉnh). Placeholder là dữ
           liệu nhập tay nên so khớp phải bao quát biến thể viết hoa/thường.  */
        IF OBJECT_ID('tempdb..#VungKhongRo') IS NOT NULL DROP TABLE #VungKhongRo;
        SELECT DISTINCT Region INTO #VungKhongRo FROM #Dx
        WHERE  Region = N'(Không xác định)'
           OR  LOWER(Region) LIKE N'%không xác định%'
           OR  LOWER(Region) LIKE N'%khong xac dinh%';

        IF @XuLyVungKhongXacDinh = 1
        BEGIN
            UPDATE #Dx SET Region = @NhanGopVung
            WHERE  Region IN (SELECT Region FROM #VungKhongRo);
            PRINT CONCAT(N'Vùng không xác định: đã gộp vào "', @NhanGopVung, N'".');
        END
        ELSE IF @XuLyVungKhongXacDinh = 2
        BEGIN
            SELECT @nCaKhongRoTinh = SUM(Cases) FROM (
                SELECT COUNT(DISTINCT TIEPNHAN_ID) AS Cases
                FROM   #Dx WHERE Region IN (SELECT Region FROM #VungKhongRo)
                GROUP BY MonthStart, DiseaseCode) zk;
            SET @nCaKhongRoTinh = ISNULL(@nCaKhongRoTinh, 0);

            DELETE FROM #Dx WHERE Region IN (SELECT Region FROM #VungKhongRo);
            PRINT CONCAT(N'Vùng không xác định: đã loại bỏ ', @nCaKhongRoTinh, N' ca.');
        END

        /* =====================================================================
           3b) NGƯỠNG Ô NHỎ — chống tái định danh
           ---------------------------------------------------------------------
           Tổng hợp KHÔNG tự động đồng nghĩa với ẩn danh. Một ô (tháng × bệnh ×
           tỉnh) chỉ có 1 ca thì dòng đó chính là hồ sơ của đúng một người, kèm
           tỉnh cư trú, tháng khám, chẩn đoán và danh sách thuốc — ghép với thông
           tin bên ngoài là truy ra được.

           Đo trên dữ liệu Gia An: 55% số ô có đúng 1 ca.

           Cách xử lý: KHÔNG xoá (xoá sẽ làm sai tổng, mô hình học lệch) mà GỘP
           LÊN — tỉnh nào trong (tháng × bệnh) có dưới ngưỡng thì dồn vào nhóm
           '@NhanGopVung'. Tổng số ca và tổng lượng thuốc GIỮ NGUYÊN TUYỆT ĐỐI,
           chỉ mất chi tiết tỉnh ở phần đuôi.

           Về mặt pháp lý (Luật Bảo vệ dữ liệu cá nhân 91/2025, Điều 2): đây là
           bước biến dữ liệu từ "đã tổng hợp" thành "đã khử nhận dạng" — không
           còn khả năng định danh một con người cụ thể.

           Ô trong nhóm gộp vẫn có thể nhỏ, nhưng lúc đó tỉnh đã bị che nên
           không còn là dấu hiệu định danh.

           Đặt @NguongOToiThieu = 0 để tắt (chỉ nên dùng khi so với query gốc).
           ===================================================================== */
        IF @NguongOToiThieu > 1
        BEGIN
            IF OBJECT_ID('tempdb..#ONho') IS NOT NULL DROP TABLE #ONho;
            SELECT MonthStart, DiseaseCode, Region
            INTO   #ONho
            FROM   #Dx
            WHERE  Region <> @NhanGopVung
            GROUP BY MonthStart, DiseaseCode, Region
            HAVING COUNT(DISTINCT TIEPNHAN_ID) < @NguongOToiThieu;

            SELECT @nOGop = COUNT(*) FROM #ONho;

            UPDATE d
            SET    d.Region = @NhanGopVung
            FROM   #Dx d
            JOIN   #ONho n ON n.MonthStart  = d.MonthStart
                          AND n.DiseaseCode = d.DiseaseCode
                          AND n.Region      = d.Region;

            PRINT CONCAT(N'Ngưỡng ô nhỏ k=', @NguongOToiThieu, N': đã gộp ',
                         @nOGop, N' ô (tháng × bệnh × tỉnh) vào nhóm "',
                         @NhanGopVung, N'".');
        END

        /* =====================================================================
           4) #DrugMeta — danh mục thuốc + phân nhóm dược lý (CASE chạy 1 lần)
           ===================================================================== */
        IF OBJECT_ID('tempdb..#DrugMeta') IS NOT NULL DROP TABLE #DrugMeta;
        SELECT
            D.DUOC_ID,
            D.MADUOC         AS SupplyCode,
            D.TENDUOCDAYDU   AS SupplyName,
            dvt.TENDONVITINH AS SupplyUnit,
            nd.TENNHOMDUOC   AS DrugGroup,
            CAST(CASE
                WHEN nd.TENNHOMDUOC LIKE N'%kháng sinh%' OR pld.TENPHANLOAIDUOC LIKE N'%kháng sinh%' THEN N'Kháng sinh'
                WHEN D.TENHOATCHAT LIKE N'%paracetamol%' OR D.TENHOATCHAT LIKE N'%ibuprofen%' OR D.TENHOATCHAT LIKE N'%diclofenac%'
                  OR nd.TENNHOMDUOC LIKE N'%hạ sốt%' OR nd.TENNHOMDUOC LIKE N'%giảm đau%' OR pld.TENPHANLOAIDUOC LIKE N'%giảm đau%' THEN N'Thuốc hạ sốt giảm đau'
                WHEN D.TENHOATCHAT LIKE N'%acetylcystein%' OR D.TENHOATCHAT LIKE N'%ambroxol%' OR D.TENHOATCHAT LIKE N'%bromhexin%'
                  OR D.TENHOATCHAT LIKE N'%carbocistein%' OR nd.TENNHOMDUOC LIKE N'%long đờm%' OR nd.TENNHOMDUOC LIKE N'%tiêu nhầy%' THEN N'Thuốc long đờm'
                WHEN D.TENHOATCHAT LIKE N'%fexofenadin%' OR D.TENHOATCHAT LIKE N'%loratadin%' OR D.TENHOATCHAT LIKE N'%cetirizin%'
                  OR D.TENHOATCHAT LIKE N'%chlorpheniramin%' OR nd.TENNHOMDUOC LIKE N'%kháng histamin%' OR nd.TENNHOMDUOC LIKE N'%dị ứng%' THEN N'Kháng histamin'
                WHEN D.TENHOATCHAT LIKE N'%salbutamol%' OR D.TENHOATCHAT LIKE N'%theophyllin%' OR D.TENHOATCHAT LIKE N'%ipratropium%'
                  OR D.TENHOATCHAT LIKE N'%formoterol%' OR D.TENHOATCHAT LIKE N'%budesonid%' OR nd.TENNHOMDUOC LIKE N'%giãn phế quản%' THEN N'Thuốc giãn phế quản'
                WHEN D.TENHOATCHAT LIKE N'%prednison%' OR D.TENHOATCHAT LIKE N'%prednisolon%' OR D.TENHOATCHAT LIKE N'%methylprednisolon%'
                  OR D.TENHOATCHAT LIKE N'%dexamethason%' OR D.TENHOATCHAT LIKE N'%hydrocortison%'
                  OR nd.TENNHOMDUOC LIKE N'%corticoid%' OR pld.TENPHANLOAIDUOC LIKE N'%corticoid%' THEN N'Corticoid'
                WHEN D.TENHOATCHAT LIKE N'%natri clorid%' OR D.TENHOATCHAT LIKE N'%glucose%' OR D.TENHOATCHAT LIKE N'%ringer%'
                  OR nd.TENNHOMDUOC LIKE N'%dịch truyền%' OR pld.TENPHANLOAIDUOC LIKE N'%dịch truyền%' THEN N'Dịch truyền'
                ELSE N'Khác'
            END AS NVARCHAR(100)) AS NoteCategory
        INTO #DrugMeta
        FROM      TM_DUOC          D
        JOIN      TM_LOAIDUOC      ld  ON ld.LOAIDUOC_ID   = D.LOAIDUOC_ID
        LEFT JOIN TM_DONVITINH     dvt ON dvt.DONVITINH_ID = D.DONVITINH_ID
        LEFT JOIN TM_PHANLOAIDUOC  pld ON pld.PHANLOAIDUOC = D.PHANLOAIDUOC
        LEFT JOIN TM_NHOMDUOC      nd  ON nd.NHOMDUOC_ID   = D.NHOMDUOC_ID
        WHERE ld.LOAIVATTU_ID = 'T'                                      -- chỉ thuốc
          AND D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
          AND D.TENDUOCDAYDU IS NOT NULL
          AND (@BENHVIEN_ID IS NULL OR D.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE UNIQUE CLUSTERED INDEX IX_DM ON #DrugMeta(DUOC_ID);

        /* =====================================================================
           5) Chặn quét toàn bảng toa thuốc
           ===================================================================== */
        IF OBJECT_ID('tempdb..#K_NT')  IS NOT NULL DROP TABLE #K_NT;
        IF OBJECT_ID('tempdb..#K_NGT') IS NOT NULL DROP TABLE #K_NGT;
        SELECT DISTINCT KHAMBENH_ID INTO #K_NT  FROM #Dx WHERE LoaiDieuTri = 'NT';
        SELECT DISTINCT KHAMBENH_ID INTO #K_NGT FROM #Dx WHERE LoaiDieuTri = 'NGT';
        CREATE CLUSTERED INDEX IX_KNT  ON #K_NT(KHAMBENH_ID);
        CREATE CLUSTERED INDEX IX_KNGT ON #K_NGT(KHAMBENH_ID);

        /* =====================================================================
           6) #Drug — gom số lượng theo (loại × lượt khám × thuốc)
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Drug') IS NOT NULL DROP TABLE #Drug;
        CREATE TABLE #Drug (
            LoaiDieuTri  VARCHAR(3),  KHAMBENH_ID BIGINT,
            SupplyCode   NVARCHAR(50), SupplyName NVARCHAR(500),
            SupplyUnit   NVARCHAR(50), DrugGroup  NVARCHAR(200),
            NoteCategory NVARCHAR(100), Qty       FLOAT
        );

        -- 6a) NỘI TRÚ: số lượng = số thực lĩnh, thiếu thì lấy số kê
        INSERT INTO #Drug
        SELECT 'NT', tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
               dm.DrugGroup, dm.NoteCategory,
               SUM(CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT))
        FROM #K_NT k
        JOIN TT_NOITRU_TOATHUOC tt ON tt.KHAMBENH_ID = k.KHAMBENH_ID
        JOIN #DrugMeta          dm ON dm.DUOC_ID     = tt.DUOC_ID
        WHERE ISNULL(tt.HUYTOATHUOC, '0') <> '1'
          AND ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) > 0
        GROUP BY tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
                 dm.DrugGroup, dm.NoteCategory
        HAVING SUM(CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT)) > 0;

        -- 6b) NGOẠI TRÚ
        INSERT INTO #Drug
        SELECT 'NGT', tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
               dm.DrugGroup, dm.NoteCategory,
               SUM(CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT))
        FROM #K_NGT k
        JOIN TT_NGOAITRU_TOATHUOC tt ON tt.KHAMBENH_ID = k.KHAMBENH_ID
        JOIN #DrugMeta            dm ON dm.DUOC_ID     = tt.DUOC_ID
        WHERE ISNULL(tt.HUYTOATHUOC, '0') <> '1'
          AND ISNULL(tt.SOLUONG, 0) > 0
        GROUP BY tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
                 dm.DrugGroup, dm.NoteCategory
        HAVING SUM(CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT)) > 0;
        CREATE CLUSTERED INDEX IX_Drug ON #Drug(LoaiDieuTri, KHAMBENH_ID);

        /* =====================================================================
           7) Kết quả cuối — đúng hợp đồng dữ liệu của MedForecast
           ---------------------------------------------------------------------
           `cases` = COUNT(DISTINCT TIEPNHAN_ID) theo (tháng × vùng × mã bệnh),
           LẶP trên mọi dòng thuốc của nhóm đó. Tầng sau lấy max() để khử phần lặp.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#KQ') IS NOT NULL DROP TABLE #KQ;
        ;WITH DiseaseCases AS (
            SELECT MonthStart, Region, DiseaseCode,
                   COUNT(DISTINCT TIEPNHAN_ID)  AS Cases
            FROM   #Dx
            GROUP BY MonthStart, Region, DiseaseCode
        ),
        Agg AS (
            -- Gom theo ĐÚNG "hạt" dữ liệu: (tháng × mã bệnh × vùng × mã thuốc).
            -- Các cột mô tả lấy MAX() thay vì đưa vào GROUP BY — nếu hai bản ghi
            -- thuốc khác nhau cùng dùng một MADUOC (tên/đơn vị/nhóm ghi lệch nhau)
            -- thì gộp làm MỘT dòng và CỘNG số lượng, thay vì tách thành hai dòng
            -- trùng khoá. Đây là chỗ duy nhất có thể sinh dòng trùng.
            SELECT dx.MonthStart, dx.DiseaseCode, dx.Region, dr.SupplyCode,
                   MAX(dr.SupplyName)   AS SupplyName,
                   MAX(dr.SupplyUnit)   AS SupplyUnit,
                   MAX(dr.DrugGroup)    AS DrugGroup,
                   MAX(dr.NoteCategory) AS NoteCategory,
                   SUM(dr.Qty)          AS SupplyQty
            FROM #Dx   dx
            JOIN #Drug dr ON dr.LoaiDieuTri = dx.LoaiDieuTri
                         AND dr.KHAMBENH_ID = dx.KHAMBENH_ID
            GROUP BY dx.MonthStart, dx.DiseaseCode, dx.Region, dr.SupplyCode
            -- Cột supply_quantity bên STA là decimal(18,3). Lượng nhỏ hơn 0,0005
            -- sẽ làm tròn thành 0.000 khi ghi xuống, tạo ra dòng "có mã thuốc mà
            -- không có số lượng" — vô nghĩa với bài toán nhu cầu, và làm hỏng
            -- phép chia định mức ở tầng sau. Loại ngay tại đây, TRƯỚC nhánh (b):
            -- nhóm nào vì thế mà hết sạch dòng thuốc sẽ được nhánh (b) nhặt lại
            -- nên KHÔNG mất ca.
            HAVING SUM(dr.Qty) >= 0.001
        )
        SELECT
            u.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(u.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(u.MonthStart) AS varchar(4)) AS [month],
            u.DiseaseCode  AS disease_code,
            m3.DiseaseName      AS disease_name,
            m3.DiseaseGroup     AS disease_group,       -- nhóm ICD, vd 'J20-J22'
            m3.DiseaseGroupName AS disease_group_name,
            u.Region       AS region,
            u.Cases        AS cases,
            u.SupplyCode   AS supply_code,
            u.SupplyName   AS supply_name,
            u.SupplyQty    AS supply_quantity,
            u.SupplyUnit   AS supply_unit,
            u.DrugGroup    AS supply_category,
            u.NoteCategory AS note
        INTO #KQ
        FROM (
            /* (a) Nhóm ca CÓ dùng thuốc — mỗi mã thuốc một dòng */
            SELECT a.MonthStart, a.DiseaseCode, a.Region, dc.Cases,
                   a.SupplyCode, a.SupplyName, a.SupplyQty, a.SupplyUnit,
                   a.DrugGroup, a.NoteCategory
            FROM      Agg a
            JOIN      DiseaseCases dc ON dc.MonthStart  = a.MonthStart
                                     AND dc.Region      = a.Region
                                     AND dc.DiseaseCode = a.DiseaseCode

            UNION ALL

            /* (b) Nhóm ca KHÔNG có dòng thuốc nào — vẫn phải giữ số ca.
               Query export gốc dùng INNER JOIN nên những nhóm này bị rơi mất, và
               chuỗi số ca mà mô hình học bị thiếu đúng phần đó. Ở đây trả về một
               dòng với supply_code NULL: tầng sau tính fact_disease_case từ mọi
               dòng, còn fact_supply_usage thì bỏ qua dòng không có mã vật tư —
               nên vừa đủ số ca vừa không sinh nhu cầu thuốc ảo.
               Đặt @GiuNhomKhongCoThuoc = 0 để quay lại đúng hành vi query gốc.  */
            SELECT dc.MonthStart, dc.DiseaseCode, dc.Region, dc.Cases,
                   CAST(NULL AS NVARCHAR(50)), CAST(NULL AS NVARCHAR(500)),
                   CAST(NULL AS FLOAT), CAST(NULL AS NVARCHAR(50)),
                   CAST(NULL AS NVARCHAR(200)), CAST(NULL AS NVARCHAR(100))
            FROM   DiseaseCases dc
            WHERE  @GiuNhomKhongCoThuoc = 1
              AND  NOT EXISTS (SELECT 1 FROM Agg a
                               WHERE a.MonthStart  = dc.MonthStart
                                 AND a.Region      = dc.Region
                                 AND a.DiseaseCode = dc.DiseaseCode)
        ) u
        -- Nhãn bệnh + nhóm cha gắn ở đúng một chỗ này, từ TM_ICD.
        JOIN #Ma3 m3 ON m3.Ma3 = u.DiseaseCode
        -- Vùng không xác định đã xử lý ở bước 3a, không lọc lại ở đây.
        -- NULL phải lọt qua bộ lọc outlier, nếu không nhóm không thuốc sẽ bị rơi.
        WHERE (@NguongOutlier IS NULL OR u.SupplyQty IS NULL OR u.SupplyQty < @NguongOutlier);

        SELECT @nDong  = COUNT(*) FROM #KQ;
        SELECT @nNhomKhongThuoc = COUNT(*) FROM #KQ WHERE supply_code IS NULL;

        /* Số ca THỰC SỰ đẩy đi (sau khi lọc vùng) */
        SELECT @TongCa = SUM(cases) FROM (
            SELECT MAX(cases) AS cases FROM #KQ GROUP BY Period, disease_code, region) z;

        /* BẤT BIẾN: số ca đẩy đi phải luôn bằng số ca gốc trừ phần loại bỏ có
           chủ đích — và KHÔNG phụ thuộc ngưỡng ô nhỏ. Lệch là có chỗ làm mất ca. */
        IF @TongCa <> @TongCaGoc - @nCaKhongRoTinh
            PRINT CONCAT(N'CẢNH BÁO BẤT BIẾN: số ca đẩy đi (', @TongCa, N') khác số ca gốc (',
                         @TongCaGoc, N') trừ phần đã loại (', @nCaKhongRoTinh,
                         N'). Có chỗ đang làm mất hoặc nhân đôi ca — kiểm tra trước khi đẩy.');

        /* =====================================================================
           7b) SỐ CA THEO NHÓM ICD — bảng riêng, KHÔNG suy ra được từ bảng mã
           ---------------------------------------------------------------------
           Đề cương dự báo ở cấp NHÓM rồi mới phân bổ xuống mã. Nhưng số ca của
           nhóm KHÔNG phải tổng số ca các mã con:

               J01 chính + J06 phụ trong cùng một lượt khám
               → lượt đó tính 1 ca cho J01 và 1 ca cho J06
               → cộng lại thành 2, trong khi nhóm J00-J06 chỉ có 1 lượt.

           Chỉ PROD mới còn TIEPNHAN_ID để đếm DISTINCT ở mức nhóm; xuống tới STA
           thì thông tin đó đã mất. Vì vậy phải tính ở đây và đẩy thành bảng
           riêng, thay vì để tầng sau cộng dồn rồi sai.

           Hạt: (tháng × nhóm × vùng), kèm dòng vùng 'TOAN_QUOC' — cũng phải đếm
           DISTINCT riêng chứ không cộng các tỉnh, vì bước gộp ô nhỏ có thể xếp
           cùng một lượt vào hai nhãn vùng khác nhau ở hai mã khác nhau.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#KQN') IS NOT NULL DROP TABLE #KQN;
        SELECT
            g.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(g.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(g.MonthStart) AS varchar(4)) AS [month],
            g.DiseaseGroup AS disease_group,
            n.DiseaseGroupName AS disease_group_name,
            g.Region       AS region,
            g.Cases        AS cases
        INTO #KQN
        FROM (
            SELECT dx.MonthStart, m3.DiseaseGroup, dx.Region,
                   COUNT(DISTINCT dx.TIEPNHAN_ID) AS Cases
            FROM   #Dx dx
            JOIN   #Ma3 m3 ON m3.Ma3 = dx.DiseaseCode
            GROUP BY dx.MonthStart, m3.DiseaseGroup, dx.Region
            UNION ALL
            SELECT dx.MonthStart, m3.DiseaseGroup, N'TOAN_QUOC',
                   COUNT(DISTINCT dx.TIEPNHAN_ID)
            FROM   #Dx dx
            JOIN   #Ma3 m3 ON m3.Ma3 = dx.DiseaseCode
            GROUP BY dx.MonthStart, m3.DiseaseGroup
        ) g
        JOIN (SELECT DISTINCT DiseaseGroup, DiseaseGroupName FROM #Ma3) n
              ON n.DiseaseGroup = g.DiseaseGroup;

        SELECT @nDongNhom = COUNT(*) FROM #KQN;

        /* =====================================================================
           8) Tồn kho — ảnh chụp hiện tại (query gốc chưa có phần này)
           ===================================================================== */
        IF OBJECT_ID('tempdb..#TK') IS NOT NULL DROP TABLE #TK;
        SELECT
            dm.SupplyCode                      AS supply_code,
            MAX(D.MA_BHYT)                     AS drug_code,
            MAX(D.TENHOATCHAT)                 AS ten_hoat_chat,
            MAX(dm.SupplyUnit)                 AS unit,
            MAX(dm.DrugGroup)                  AS group_name,
            MAX(dm.NoteCategory)               AS category,
            SUM(CAST(tk.SOLUONG AS BIGINT))    AS stock_quantity,
            MAX(dm.SupplyName)                 AS [description]
        INTO #TK
        FROM TT_DUOC_TONKHO tk
        JOIN #DrugMeta      dm ON dm.DUOC_ID = tk.DUOC_ID
        JOIN TM_DUOC        D  ON D.DUOC_ID  = tk.DUOC_ID
        WHERE (@BENHVIEN_ID IS NULL OR tk.BENHVIEN_ID = @BENHVIEN_ID)
        GROUP BY dm.SupplyCode
        HAVING SUM(CAST(tk.SOLUONG AS BIGINT)) IS NOT NULL;

        SELECT @nTonKho = COUNT(*) FROM #TK;

        /* =====================================================================
           9) Đẩy xuống STA — hoặc chỉ trả kết quả nếu @ChiXem = 1
           ===================================================================== */
        IF @ChiXem = 1
        BEGIN
            PRINT CONCAT(N'CHẾ ĐỘ CHỈ XEM — không đẩy. Dòng = ', @nDong,
                         N', dòng nhóm = ', @nDongNhom,
                         N', ca gốc = ', @TongCaGoc,
                         N', loại vì không rõ tỉnh = ', @nCaKhongRoTinh,
                         N', ca đẩy đi = ', @TongCa,
                         N', nhóm không thuốc = ', @nNhomKhongThuoc,
                         N', ô đã gộp = ', @nOGop, N', tồn kho = ', @nTonKho);
            SELECT [month], disease_code, disease_name,
                   disease_group, disease_group_name,
                   region, cases,
                   supply_code, supply_name, supply_quantity, supply_unit,
                   supply_category, note
            FROM   #KQ
            ORDER BY Period, disease_group, disease_code, region, supply_quantity DESC;

            /* Số ca theo NHÓM (đếm DISTINCT ở mức nhóm, KHÔNG cộng các mã con).
               Cột 'CongDonMaCon' cho thấy nếu tầng sau cộng dồn thì sai bao nhiêu. */
            SELECT n.disease_group, n.disease_group_name,
                   COUNT(DISTINCT n.Period)                          AS SoThangCoDuLieu,
                   SUM(n.cases)                                      AS TongCa_DungCach,
                   CAST(1.0 * SUM(n.cases) / NULLIF(COUNT(DISTINCT n.Period), 0)
                        AS decimal(10,1))                            AS CaTrungBinhMoiThang,
                   MAX(k.SoMaBenh)                                   AS SoMaBenh,
                   MAX(k.CongDon)                                    AS CongDonMaCon_SaiNeuDungCachNay
            FROM   #KQN n
            LEFT JOIN (
                SELECT disease_group,
                       COUNT(DISTINCT disease_code) AS SoMaBenh,
                       SUM(cases)                   AS CongDon
                FROM (SELECT Period, region, disease_group, disease_code,
                             MAX(cases) AS cases
                      FROM #KQ
                      GROUP BY Period, region, disease_group, disease_code) z
                GROUP BY disease_group) k ON k.disease_group = n.disease_group
            WHERE  n.region = N'TOAN_QUOC'
            GROUP BY n.disease_group, n.disease_group_name
            ORDER BY n.disease_group;
            RETURN;
        END

        /* Chốt chặn 1 — không cho dữ liệu trùng khoá rời khỏi PROD.
           Nếu còn trùng thì có gì đó sai ở tầng gom, dừng lại chứ không đẩy.   */
        DECLARE @nTrung INT = (
            SELECT COUNT(*) FROM (
                SELECT 1 AS x FROM #KQ
                GROUP BY Period, disease_code, region, supply_code
                HAVING COUNT(*) > 1) t);
        IF @nTrung > 0
            THROW 50001, N'Kết quả tổng hợp có dòng trùng khoá (Period, disease_code, region, supply_code) — không đẩy xuống STA.', 1;

        /* Xoá rồi chèn lại đúng cửa sổ — KHÔNG cộng dồn vào dữ liệu cũ.
           Chạy lại bao nhiêu lần cũng ra cùng một kết quả.                     */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
        WHERE  Period >= @TuNgay;

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
              (Period, [month], disease_code, disease_name,
               disease_group, disease_group_name, region, cases,
               supply_code, supply_name, supply_quantity, supply_unit,
               supply_category, note, NgayCapNhat)
        SELECT Period, [month], disease_code, disease_name,
               disease_group, disease_group_name, region, cases,
               supply_code, supply_name, supply_quantity, supply_unit,
               supply_category, note, SYSDATETIME()
        FROM   #KQ;

        /* Số ca theo NHÓM — cùng cửa sổ, cùng kiểu xoá-rồi-chèn. */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
        WHERE  Period >= @TuNgay;

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
              (Period, [month], disease_group, disease_group_name, region, cases, NgayCapNhat)
        SELECT Period, [month], disease_group, disease_group_name, region, cases, SYSDATETIME()
        FROM   #KQN;

        /* Chốt chặn 2 — số dòng bên STA trong cửa sổ phải khớp số dòng vừa gom. */
        DECLARE @nSauKhiDay INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
            WHERE Period >= @TuNgay);
        IF @nSauKhiDay <> @nDong
            THROW 50002, N'Số dòng bên STA không khớp số dòng đã gom — nghi có dữ liệu thừa hoặc thiếu.', 1;

        EXEC (N'TRUNCATE TABLE dbo.MF_TonKho') AT [MEDFORECAST_STA];

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho]
              (supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], NgayCapNhat)
        SELECT supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], SYSDATETIME()
        FROM   #TK;

        /* --- 10) Mốc và nhật ký ------------------------------------------- */
        DECLARE @MocMoi DATE = (SELECT MAX(Period) FROM #KQ);

        UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay    = CASE WHEN @MocMoi > ISNULL(MocDaDay, '19000101')
                                  THEN @MocMoi ELSE MocDaDay END,
               LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'CaBenh';

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
              (BatDau, KetThuc, TuNgay, SoDongCaBenh, SoDongTonKho, TongSoCa,
               TrangThai, ThongDiep)
        VALUES (@BatDau, SYSDATETIME(), @TuNgay, @nDong, @nTonKho, @TongCa, 'ok',
                CONCAT(N'Mốc mới = ', CONVERT(varchar(10), @MocMoi, 120),
                       N'; ngưỡng ô nhỏ k=', @NguongOToiThieu,
                       N', đã gộp ', @nOGop, N' ô vào "', @NhanGopVung, N'"',
                       N'; ca gốc ', @TongCaGoc, N', loại vì không rõ tỉnh ',
                       @nCaKhongRoTinh, N', đẩy đi ', @TongCa,
                       N'; nhóm không có thuốc: ', @nNhomKhongThuoc,
                       N'; phạm vi ', @NhomBenhDich, N' = ', @nMaDich, N' mã, ',
                       @nDongNhom, N' dòng nhóm'));

        PRINT CONCAT(N'Xong. Dòng = ', @nDong, N', dòng nhóm = ', @nDongNhom,
                     N', ca gốc = ', @TongCaGoc,
                     N', loại vì không rõ tỉnh = ', @nCaKhongRoTinh,
                     N', ca đẩy đi = ', @TongCa,
                     N', nhóm không thuốc = ', @nNhomKhongThuoc,
                     N', ô đã gộp = ', @nOGop, N', tồn kho = ', @nTonKho);
    END TRY
    BEGIN CATCH
        BEGIN TRY
            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
                  (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
            VALUES (@BatDau, SYSDATETIME(), @TuNgay, 'failed',
                    CONCAT(N'Lỗi ', ERROR_NUMBER(), N' dòng ', ERROR_LINE(),
                           N': ', ERROR_MESSAGE()));
        END TRY
        BEGIN CATCH
            PRINT N'Không ghi được nhật ký xuống STA — kiểm tra linked server.';
        END CATCH
        THROW;
    END CATCH
END
GO

/* =============================================================================
   CÁCH DÙNG

   BƯỚC A — đối chiếu với query gốc TRƯỚC KHI bật job (không ghi gì xuống STA).
   Tắt ngưỡng ô nhỏ để so đúng từng dòng với query gốc:
       EXEC dbo.usp_MedForecast_DayDuLieu
            @NapLaiToanBo = 1, @ChiXem = 1, @NguongOToiThieu = 0;

   Sau đó bật lại ngưỡng và xem nó gộp bao nhiêu ô — tổng số ca phải KHÔNG ĐỔI:
       EXEC dbo.usp_MedForecast_DayDuLieu
            @NapLaiToanBo = 1, @ChiXem = 1, @NguongOToiThieu = 5;
   Chạy song song query export gốc rồi so số dòng và tổng cột supply_quantity.
   Phải khớp tuyệt đối — nếu lệch, dừng lại, đừng đẩy.

   BƯỚC B — nạp lần đầu xuống STA (toàn bộ lịch sử):
       EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;

   BƯỚC C — các lần sau (job gọi câu này), tổng hợp lại 3 tháng gần nhất:
       EXEC dbo.usp_MedForecast_DayDuLieu;

   Nếu DB chứa nhiều bệnh viện thì thêm @BENHVIEN_ID = 79428.

   -----------------------------------------------------------------------------
   PHẠM VI BỆNH — ĐỔI BẰNG THAM SỐ, KHÔNG SỬA CODE
   Mặc định lấy đúng ba nhóm trong đề cương:
       @NhomBenhDich = N'J00-J06,J09-J18,J20-J22'

   Muốn quay lại đúng phạm vi của query export cũ để đối chiếu số cũ (chỉ 4 mã
   J01, J02, J06, J20) thì KHÔNG có cách nào bằng tham số — vì tham số nhận
   NHÓM chứ không nhận mã lẻ. Đó là chủ ý: 4 mã lẻ không phải một phạm vi có
   nghĩa về dịch tễ, chỉ là những mã tình cờ nhiều ca nhất.

   Chỉ chạy một nhóm để xem riêng:
       EXEC dbo.usp_MedForecast_DayDuLieu
            @NapLaiToanBo = 1, @ChiXem = 1, @NhomBenhDich = N'J09-J18';

   Ở chế độ @ChiXem, thủ tục trả về HAI bảng: chi tiết theo mã, và tổng hợp
   theo nhóm kèm số ca trung bình mỗi tháng — con số quyết định nhóm nào đủ dày
   để mô hình hoá.

   -----------------------------------------------------------------------------
   CHỌN NGƯỠNG Ô NHỎ THẾ NÀO
   Thông lệ là k = 5 (một số nơi dùng 10). Đo thử trên dữ liệu Gia An:

       k     ô bị gộp        tỉnh còn nêu tên     ca nằm trong nhóm gộp
       3     71%             14/48                13,1%
       5     81%              5/48                18,3%
      10     85%              3/48                18,3%

   Tổng số ca giữ nguyên 13.351 ở MỌI ngưỡng — chỉ chi tiết tỉnh bị gộp bớt.
   Riêng bệnh viện này 79% số ca đến từ TP. Hồ Chí Minh nên chiều "tỉnh" vốn
   không mang nhiều thông tin ngoài vài tỉnh đầu; mô hình lại dự báo ở mức toàn
   quốc, nên k = 5 gần như không ảnh hưởng độ chính xác.

   -----------------------------------------------------------------------------
   MỘT ĐẶC ĐIỂM CẦN BIẾT KHI ĐỌC SỐ
   Một lượt khám có thể mang nhiều mã đích (ví dụ J01 chính + J06 phụ). Khi đó
   lượt đó được tính vào CẢ HAI mã, và lượng thuốc của lượt đó cũng được gán cho
   cả hai. Vì vậy tổng `cases` cộng qua nhiều mã sẽ LỚN HƠN số lượt thật.
   Đây là lựa chọn có chủ đích: mô hình dự báo theo từng bệnh cần biết "lượt khám
   có chẩn đoán X đã dùng bao nhiêu thuốc", không phải chia phần thuốc cho các
   bệnh đồng mắc. Nhưng khi đối chiếu với báo cáo tổng của phòng KHTH thì phải
   so theo TỪNG MÃ BỆNH, đừng cộng dồn.

   ⚠ Điều này cũng đúng ở MỨC NHÓM, và còn nặng hơn: J01 + J06 cùng thuộc
   J00-J06 nên một lượt mang cả hai mã sẽ bị đếm hai lần trong tổng của nhóm.
   Vì vậy số ca của NHÓM mà tầng sau dùng để dự báo PHẢI đếm
   COUNT(DISTINCT lượt khám) ở mức nhóm, KHÔNG phải SUM(cases) của các mã con.
   Bảng mart_block_month bên ứng dụng chịu trách nhiệm việc này — xem
   `backend/app/data_pipeline/pipeline.py`. Dữ liệu đẩy xuống STA cố tình giữ ở
   mức mã để tầng sau còn tính được tỷ trọng mã trong nhóm.
============================================================================= */
