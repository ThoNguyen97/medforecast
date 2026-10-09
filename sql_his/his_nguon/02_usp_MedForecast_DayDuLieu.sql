/* his_nguon/02_usp_MedForecast_DayDuLieu.sql
   Chạy trên: máy chủ CSDL HIS. Điều kiện: his_nguon/01 và medforecast_dw/01..02; job his_nguon/05 gọi hằng ngày.
   Mục đích: tổng hợp lượt khám thuộc nhóm ICD đích (nội trú + ngoại trú), khử định danh, đẩy xuống
   MEDFORECAST_DW: MF_CaBenh_VatTu, MF_CaBenh_Nhom (T1), MF_CaBenh_PhanCap, MF_TieuHao_PhanCap (T2), MF_TonKho.
   Rổ chăm sóc NGT | NT1 | NT2 | NT3 | NT0, cấp của đợt = MIN(mã phân cấp) trên y lệnh thuốc của đợt. */

CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayDuLieu
    @SoThangLuiLai       INT   = 3,              -- khớp PIPELINE_LOOKBACK_MONTHS
    @NapLaiToanBo        BIT   = 0,
    @TuNgayGoc           DATE  = '2019-01-01',   -- mốc khi nạp lại toàn bộ
    @BENHVIEN_ID         VARCHAR(8)   = NULL,           -- khi DB nhiều bệnh viện
    @NhomBenhDich        NVARCHAR(400) = N'J00-J06,J09-J18,J20-J22',
    @XuLyVungKhongXacDinh TINYINT = 1,           -- 0 giữ nhãn | 1 gộp | 2 loại bỏ
    @NguongOutlier       FLOAT = NULL,
    @NguongOToiThieu     INT   = 5,              -- ngưỡng ô nhỏ; 0 hoặc 1 = tắt
    @NhanGopVung         NVARCHAR(120) = N'Tỉnh khác',
    @GiuNhomKhongCoThuoc BIT   = 1,
    @ChiXem              BIT   = 0,              -- 1 = chỉ SELECT, không đẩy
    @GomVTYT             BIT   = 0,              -- 1 = lấy thêm mã ngoài nhóm thuốc (chỉ để đối chứng)
    @DayLuongPhanCap     BIT   = 1               -- 0 = không đẩy hai bảng phân cấp
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @BatDau  DATETIME2(0) = SYSDATETIME();
    DECLARE @Moc     DATE, @TuNgay DATE, @DenNgay DATE = CAST(GETDATE() AS DATE);
    DECLARE @nDong INT = 0, @nTonKho INT = 0, @nOGop INT = 0;
    DECLARE @ChuCaiDich CHAR(1), @nMaDich INT = 0, @nNhomDich INT = 0, @nDongNhom INT = 0;
    DECLARE @TongCa INT = 0,
            @TongCaGoc INT = 0,
            @nCaKhongRoTinh INT = 0,
            @nNhomKhongThuoc INT = 0;
    DECLARE @NhomChuan NVARCHAR(500),
            @nDongPhanCap INT = 0, @nDongTieuHao INT = 0,
            @nONhoPhanCap INT = 0,
            @QtyNhom FLOAT = 0, @QtyRo FLOAT = 0;

    BEGIN TRY
        /* Cửa sổ cần tổng hợp lại */
        IF @ChiXem = 0
            SELECT @Moc = MocDaDay
            FROM   [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_Watermark]
            WHERE  TenLuong = 'CaBenh';

        SET @TuNgay = CASE
            WHEN @NapLaiToanBo = 1 OR @Moc IS NULL THEN @TuNgayGoc
            ELSE DATEFROMPARTS(YEAR(DATEADD(MONTH, -@SoThangLuiLai, @Moc)),
                               MONTH(DATEADD(MONTH, -@SoThangLuiLai, @Moc)), 1)
        END;

        PRINT CONCAT(N'Tổng hợp từ ', CONVERT(varchar(10), @TuNgay, 120),
                     N' đến ', CONVERT(varchar(10), @DenNgay, 120));

        /* 0) Danh mục tỉnh: dò trong địa chỉ text khi không suy ra được qua xã */
        IF OBJECT_ID('tempdb..#Tinh') IS NOT NULL DROP TABLE #Tinh;
        SELECT DISTINCT TENDONVI
        INTO   #Tinh
        FROM   TM_DONVIHANHCHINH
        WHERE  CAPDONVI = 2 AND LEN(TENDONVI) >= 4;

        /* 0b) Danh mục mã bệnh đích lấy theo nhóm ICD, không hardcode mã */
        IF OBJECT_ID('tempdb..#NhomDich') IS NOT NULL DROP TABLE #NhomDich;
        SELECT LTRIM(RTRIM(value)) AS Nhom
        INTO   #NhomDich
        FROM   STRING_SPLIT(@NhomBenhDich, ',')
        WHERE  LTRIM(RTRIM(value)) <> '';

        SELECT @nNhomDich  = COUNT(*),
               @ChuCaiDich = MAX(LEFT(Nhom, 1))
        FROM   #NhomDich;

        IF @nNhomDich = 0
            THROW 50003, N'@NhomBenhDich rỗng: không biết lấy nhóm bệnh nào.', 1;

        IF (SELECT COUNT(DISTINCT LEFT(Nhom, 1)) FROM #NhomDich) > 1
            THROW 50004, N'@NhomBenhDich đang trộn nhiều chương ICD (khác chữ cái đầu). Thủ tục chỉ hỗ trợ một chương mỗi lần chạy.', 1;

        /* Chuỗi nhóm chuẩn hoá ',J00-J06,...,' giới hạn mọi DELETE bên CSDL trung gian theo nhóm của lần chạy;
           so bằng LIKE để khỏi đẩy bảng tạm qua linked server */
        SELECT @NhomChuan = N',' + STRING_AGG(Nhom, N',') + N',' FROM #NhomDich;

        IF OBJECT_ID('tempdb..#IcdDich') IS NOT NULL DROP TABLE #IcdDich;
        SELECT icd.ICD_ID,
               LEFT(LTRIM(RTRIM(icd.MAICD)), 3) AS Ma3
        INTO   #IcdDich
        FROM   TM_ICD icd
        JOIN   #NhomDich n ON n.Nhom = LTRIM(RTRIM(icd.PHANNHOM))
        WHERE  icd.MAICD IS NOT NULL
          AND  LEN(LTRIM(RTRIM(icd.MAICD))) >= 3;
        CREATE UNIQUE CLUSTERED INDEX IX_IcdDich ON #IcdDich(ICD_ID);

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
            THROW 50005, N'Không tìm thấy mã ICD nào thuộc @NhomBenhDich trong TM_ICD, kiểm tra lại cột PHANNHOM.', 1;

        PRINT CONCAT(N'Phạm vi bệnh: ', @nNhomDich, N' nhóm (', @NhomBenhDich,
                     N') thành ', @nMaDich, N' mã 3 ký tự.');

        /* 1) #Enc: lượt khám thuộc nhóm bệnh đích; CapYLenh chỉ có ở y lệnh thuốc, VTYT để NULL */
        IF OBJECT_ID('tempdb..#Enc') IS NOT NULL DROP TABLE #Enc;

        -- 1a) Nội trú
        SELECT
            CAST('NT' AS VARCHAR(3)) AS LoaiDieuTri,
            KB.KHAMBENH_ID,
            tn.TIEPNHAN_ID,
            tn.BENHNHAN_ID,
            DATEFROMPARTS(YEAR(tn.NGAYTIEPNHAN), MONTH(tn.NGAYTIEPNHAN), 1) AS MonthStart,
            ISNULL(icdc.MAICD, icdBA.MAICD) AS PrimaryICD,
            KB.DS_MAICDPHU                  AS SubICD,
            TRY_CAST(pccs.DICTIONARY_CODE AS INT) AS CapYLenh   -- 1 | 2 | 3 | NULL
        INTO #Enc
        FROM      TT_TIEPNHAN         tn
        JOIN      TT_NOITRU_BENHAN    BA    ON BA.TIEPNHAN_ID = tn.TIEPNHAN_ID
        JOIN      TT_NOITRU_KHAMBENH  KB    ON KB.BENHAN_ID   = BA.BENHAN_ID
        LEFT JOIN TM_ICD              icdc  ON icdc.ICD_ID    = KB.ICDCHINH_ID
        LEFT JOIN TM_ICD              icdBA ON icdBA.ICD_ID   = TRY_CAST(BA.ICD_BENHCHINH AS INT)
        LEFT JOIN LST_DICTIONARY      pccs  ON pccs.DICTIONARY_ID        = KB.PHANCAPCHAMSOC_ID
                                           AND pccs.DICTIONARY_TYPE_CODE = 'PhanCapChamSoc'
        WHERE tn.NGAYTIEPNHAN >= @TuNgay
          AND tn.NGAYTIEPNHAN <  DATEADD(DAY, 1, @DenNgay)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
          AND ( KB.ICDCHINH_ID IN (SELECT ICD_ID FROM #IcdDich)
             OR TRY_CAST(BA.ICD_BENHCHINH AS INT) IN (SELECT ICD_ID FROM #IcdDich)
             OR KB.DS_MAICDPHU LIKE '%' + @ChuCaiDich + '[0-9][0-9]%' );

        -- 1b) Ngoại trú: LEFT JOIN TM_ICD để giữ lượt chỉ có mã đích ở DS_MAICDPHU; không phân cấp nên CapYLenh NULL
        INSERT INTO #Enc (LoaiDieuTri, KHAMBENH_ID, TIEPNHAN_ID, BENHNHAN_ID,
                          MonthStart, PrimaryICD, SubICD, CapYLenh)
        SELECT 'NGT', KB.KHAMBENH_ID, tn.TIEPNHAN_ID, tn.BENHNHAN_ID,
               DATEFROMPARTS(YEAR(KB.NGAYKHAM), MONTH(KB.NGAYKHAM), 1),
               icdc.MAICD, KB.DS_MAICDPHU, NULL
        FROM      TT_TIEPNHAN            tn
        JOIN      TT_NGOAITRU_KHAMBENH   KB   ON KB.TIEPNHAN_ID = tn.TIEPNHAN_ID
        LEFT JOIN TM_ICD                 icdc ON icdc.ICD_ID    = KB.CHANDOANICD_ID
        WHERE KB.NGAYKHAM >= @TuNgay
          AND KB.NGAYKHAM <  DATEADD(DAY, 1, @DenNgay)
          AND (@BENHVIEN_ID IS NULL OR tn.BENHVIEN_ID = @BENHVIEN_ID)
          AND ( KB.CHANDOANICD_ID IN (SELECT ICD_ID FROM #IcdDich)
             OR KB.DS_MAICDPHU LIKE '%' + @ChuCaiDich + '[0-9][0-9]%' );

        /* 1c) #CapDot: rổ của mỗi đợt = MIN(mã phân cấp) trên y lệnh đã qua bộ lọc bệnh đích;
           NT0 = nội trú không y lệnh nào có phân cấp */
        IF OBJECT_ID('tempdb..#CapDot') IS NOT NULL DROP TABLE #CapDot;
        SELECT
            e.LoaiDieuTri,
            e.TIEPNHAN_ID,
            CAST(CASE WHEN e.LoaiDieuTri = 'NGT' THEN 'NGT'
                      ELSE 'NT' + CAST(ISNULL(MIN(e.CapYLenh), 0) AS VARCHAR(1))
                 END AS VARCHAR(4)) AS Ro
        INTO   #CapDot
        FROM   #Enc e
        GROUP BY e.LoaiDieuTri, e.TIEPNHAN_ID;
        CREATE UNIQUE CLUSTERED INDEX IX_CapDot ON #CapDot(LoaiDieuTri, TIEPNHAN_ID);

        /* Mã phân cấp ngoài {1,2,3} bị CHECK bên CSDL trung gian chặn, dồn về NT0 và cảnh báo sớm */
        IF EXISTS (SELECT 1 FROM #CapDot WHERE Ro NOT IN ('NGT','NT1','NT2','NT3','NT0'))
        BEGIN
            PRINT N'CẢNH BÁO: có mã phân cấp chăm sóc ngoài {1,2,3}, đã dồn vào rổ NT0. Kiểm tra LST_DICTIONARY.';
            UPDATE #CapDot SET Ro = 'NT0'
            WHERE  Ro NOT IN ('NGT','NT1','NT2','NT3','NT0');
        END

        /* 2) #PatReg: vùng (tỉnh) tính một lần cho mỗi bệnh nhân */
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
        WHERE ISNULL(NULLIF(LTRIM(RTRIM(bn.ACTIVE)), ''), '1') <> '0';
        CREATE UNIQUE CLUSTERED INDEX IX_PatReg ON #PatReg(BENHNHAN_ID);

        /* 3) #Dx: 1 dòng / (loại × lượt × mã bệnh), gộp chính + phụ; Ro là hàm của (loại, lượt) nên không tăng dòng */
        IF OBJECT_ID('tempdb..#Dx') IS NOT NULL DROP TABLE #Dx;
        SELECT DISTINCT
               x.LoaiDieuTri, x.KHAMBENH_ID, x.TIEPNHAN_ID, x.MonthStart,
               pr.Region, x.DiseaseCode, cd.Ro
        INTO #Dx
        FROM (
            -- chẩn đoán chính
            SELECT e.LoaiDieuTri, e.KHAMBENH_ID, e.TIEPNHAN_ID, e.BENHNHAN_ID,
                   e.MonthStart, m.Ma3 AS DiseaseCode
            FROM   #Enc e
            JOIN   #Ma3 m ON m.Ma3 = LEFT(e.PrimaryICD, 3)
            UNION ALL
            -- chẩn đoán phụ từ DS_MAICDPHU
            SELECT e.LoaiDieuTri, e.KHAMBENH_ID, e.TIEPNHAN_ID, e.BENHNHAN_ID,
                   e.MonthStart, m.Ma3
            FROM   #Enc e
            CROSS APPLY STRING_SPLIT(e.SubICD, ';') s
            JOIN   #Ma3 m ON m.Ma3 = LEFT(TRIM(s.value), 3)
        ) x
        JOIN #PatReg pr ON pr.BENHNHAN_ID = x.BENHNHAN_ID
        JOIN #CapDot cd ON cd.LoaiDieuTri = x.LoaiDieuTri
                       AND cd.TIEPNHAN_ID = x.TIEPNHAN_ID;
        CREATE CLUSTERED INDEX IX_Dx ON #Dx(LoaiDieuTri, KHAMBENH_ID);

        SELECT @TongCaGoc = SUM(Cases) FROM (
            SELECT COUNT(DISTINCT TIEPNHAN_ID) AS Cases
            FROM   #Dx GROUP BY MonthStart, Region, DiseaseCode) z0;

        /* 3a) Vùng không xác định, xử lý trước bước gộp ô nhỏ */
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

        /* 3b) Ngưỡng ô nhỏ k chống tái định danh: ô (tháng × mã × tỉnh) < k lượt đổi nhãn vùng, không đổi Ro và số ca */
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

        /* 4) #DrugMeta: danh mục thuốc (+ VTYT nếu @GomVTYT = 1); NoteCategory theo thứ tự ưu tiên WHEN */
        IF OBJECT_ID('tempdb..#DrugMeta') IS NOT NULL DROP TABLE #DrugMeta;
        SELECT
            D.DUOC_ID,
            D.MADUOC         AS SupplyCode,
            D.TENDUOCDAYDU   AS SupplyName,
            dvt.TENDONVITINH AS SupplyUnit,
            nd.TENNHOMDUOC   AS DrugGroup,
            CAST(CASE WHEN ld.LOAIVATTU_ID = 'T' THEN 0 ELSE 1 END AS BIT) AS IsVtyt,
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
                WHEN nd.TENNHOMDUOC LIKE N'%dịch truyền%'
                  OR nd.TENNHOMDUOC LIKE N'%dung dịch điều chỉnh nước%'
                  OR (D.TENHOATCHAT LIKE N'%natri clorid%' AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
                  OR (D.TENHOATCHAT LIKE N'%glucose%'      AND dvt.TENDONVITINH IN (N'Chai', N'Túi', N'Lọ'))
                  OR  D.TENHOATCHAT LIKE N'%ringer%' THEN N'Dịch truyền'
                ELSE N'Khác'
            END AS NVARCHAR(100)) AS NoteCategory
        INTO #DrugMeta
        FROM      TM_DUOC          D
        JOIN      TM_LOAIDUOC      ld  ON ld.LOAIDUOC_ID   = D.LOAIDUOC_ID
        LEFT JOIN TM_DONVITINH     dvt ON dvt.DONVITINH_ID = D.DONVITINH_ID
        LEFT JOIN TM_PHANLOAIDUOC  pld ON pld.PHANLOAIDUOC = D.PHANLOAIDUOC
        LEFT JOIN TM_NHOMDUOC      nd  ON nd.NHOMDUOC_ID   = D.NHOMDUOC_ID
        WHERE (@GomVTYT = 1 OR ld.LOAIVATTU_ID = 'T')
          AND D.MADUOC IS NOT NULL AND LTRIM(RTRIM(D.MADUOC)) <> ''
          AND D.TENDUOCDAYDU IS NOT NULL
          AND (@BENHVIEN_ID IS NULL OR D.BENHVIEN_ID = @BENHVIEN_ID);
        CREATE UNIQUE CLUSTERED INDEX IX_DM ON #DrugMeta(DUOC_ID);

        /* 5) Chặn quét toàn bảng toa thuốc */
        IF OBJECT_ID('tempdb..#K_NT')  IS NOT NULL DROP TABLE #K_NT;
        IF OBJECT_ID('tempdb..#K_NGT') IS NOT NULL DROP TABLE #K_NGT;
        SELECT DISTINCT KHAMBENH_ID INTO #K_NT  FROM #Dx WHERE LoaiDieuTri = 'NT';
        SELECT DISTINCT KHAMBENH_ID INTO #K_NGT FROM #Dx WHERE LoaiDieuTri = 'NGT';
        CREATE CLUSTERED INDEX IX_KNT  ON #K_NT(KHAMBENH_ID);
        CREATE CLUSTERED INDEX IX_KNGT ON #K_NGT(KHAMBENH_ID);

        /* 6) #Drug: gom số lượng theo (loại × lượt × thuốc); SoDong chỉ để đối chiếu */
        IF OBJECT_ID('tempdb..#Drug') IS NOT NULL DROP TABLE #Drug;
        CREATE TABLE #Drug (
            LoaiDieuTri  VARCHAR(3),   KHAMBENH_ID BIGINT,
            SupplyCode   NVARCHAR(50), SupplyName  NVARCHAR(500),
            SupplyUnit   NVARCHAR(50), DrugGroup   NVARCHAR(200),
            NoteCategory NVARCHAR(100), IsVtyt     BIT,
            Qty          FLOAT,        SoDong      INT
        );

        -- 6a) Nội trú: số thực lĩnh, thiếu thì lấy số kê
        INSERT INTO #Drug
        SELECT 'NT', tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
               dm.DrugGroup, dm.NoteCategory, dm.IsVtyt,
               SUM(CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT)),
               COUNT(*)
        FROM #K_NT k
        JOIN TT_NOITRU_TOATHUOC tt ON tt.KHAMBENH_ID = k.KHAMBENH_ID
        JOIN #DrugMeta          dm ON dm.DUOC_ID     = tt.DUOC_ID
        WHERE ISNULL(tt.HUYTOATHUOC, '0') <> '1'
          AND ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) > 0
        GROUP BY tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
                 dm.DrugGroup, dm.NoteCategory, dm.IsVtyt
        HAVING SUM(CAST(ISNULL(tt.SOLUONGTHUCLINH, tt.SOLUONG) AS FLOAT)) > 0;

        -- 6b) Ngoại trú
        INSERT INTO #Drug
        SELECT 'NGT', tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
               dm.DrugGroup, dm.NoteCategory, dm.IsVtyt,
               SUM(CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT)),
               COUNT(*)
        FROM #K_NGT k
        JOIN TT_NGOAITRU_TOATHUOC tt ON tt.KHAMBENH_ID = k.KHAMBENH_ID
        JOIN #DrugMeta            dm ON dm.DUOC_ID     = tt.DUOC_ID
        WHERE ISNULL(tt.HUYTOATHUOC, '0') <> '1'
          AND ISNULL(tt.SOLUONG, 0) > 0
        GROUP BY tt.KHAMBENH_ID, dm.SupplyCode, dm.SupplyName, dm.SupplyUnit,
                 dm.DrugGroup, dm.NoteCategory, dm.IsVtyt
        HAVING SUM(CAST(ISNULL(tt.SOLUONG, 0) AS FLOAT)) > 0;
        CREATE CLUSTERED INDEX IX_Drug ON #Drug(LoaiDieuTri, KHAMBENH_ID);

        /* 7) #KQ: kết quả theo mã bệnh; cases lặp trên mọi dòng thuốc, khử lặp bằng MAX */
        IF OBJECT_ID('tempdb..#KQ') IS NOT NULL DROP TABLE #KQ;
        ;WITH DiseaseCases AS (
            SELECT MonthStart, Region, DiseaseCode,
                   COUNT(DISTINCT TIEPNHAN_ID)  AS Cases
            FROM   #Dx
            GROUP BY MonthStart, Region, DiseaseCode
        ),
        Agg AS (
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
            HAVING SUM(dr.Qty) >= 0.001
        )
        SELECT
            u.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(u.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(u.MonthStart) AS varchar(4)) AS [month],
            u.DiseaseCode  AS disease_code,
            m3.DiseaseName      AS disease_name,
            m3.DiseaseGroup     AS disease_group,
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
            SELECT a.MonthStart, a.DiseaseCode, a.Region, dc.Cases,
                   a.SupplyCode, a.SupplyName, a.SupplyQty, a.SupplyUnit,
                   a.DrugGroup, a.NoteCategory
            FROM      Agg a
            JOIN      DiseaseCases dc ON dc.MonthStart  = a.MonthStart
                                     AND dc.Region      = a.Region
                                     AND dc.DiseaseCode = a.DiseaseCode
            UNION ALL
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
        JOIN #Ma3 m3 ON m3.Ma3 = u.DiseaseCode
        WHERE (@NguongOutlier IS NULL OR u.SupplyQty IS NULL OR u.SupplyQty < @NguongOutlier);

        SELECT @nDong  = COUNT(*) FROM #KQ;
        SELECT @nNhomKhongThuoc = COUNT(*) FROM #KQ WHERE supply_code IS NULL;

        SELECT @TongCa = SUM(cases) FROM (
            SELECT MAX(cases) AS cases FROM #KQ GROUP BY Period, disease_code, region) z;

        IF @TongCa <> @TongCaGoc - @nCaKhongRoTinh
            PRINT CONCAT(N'CẢNH BÁO BẤT BIẾN: số ca đẩy đi (', @TongCa, N') khác số ca gốc (',
                         @TongCaGoc, N') trừ phần đã loại (', @nCaKhongRoTinh,
                         N'). Có chỗ đang làm mất hoặc nhân đôi ca, kiểm tra trước khi đẩy.');

        /* 7b) Số ca theo nhóm ICD: DISTINCT lượt ở mức nhóm, dòng 'TOAN_QUOC' đếm riêng */
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

        /* 7c) #DxG: khử trùng ở mức (lượt × nhóm); ghép thẳng #Dx với #Drug sẽ cộng thuốc hai lần
           cho lượt mang hai mã cùng nhóm */
        IF OBJECT_ID('tempdb..#DxG') IS NOT NULL DROP TABLE #DxG;
        SELECT DISTINCT
               dx.LoaiDieuTri, dx.KHAMBENH_ID, dx.TIEPNHAN_ID, dx.MonthStart,
               m3.DiseaseGroup, m3.DiseaseGroupName, dx.Ro
        INTO   #DxG
        FROM   #Dx dx
        JOIN   #Ma3 m3 ON m3.Ma3 = dx.DiseaseCode;
        CREATE CLUSTERED INDEX IX_DxG ON #DxG(LoaiDieuTri, KHAMBENH_ID);

        /* Lượt khám × tháng khử trùng qua mọi nhóm, cho bảng tổng */
        IF OBJECT_ID('tempdb..#EncThang') IS NOT NULL DROP TABLE #EncThang;
        SELECT DISTINCT LoaiDieuTri, KHAMBENH_ID, TIEPNHAN_ID, MonthStart
        INTO   #EncThang
        FROM   #DxG;
        CREATE CLUSTERED INDEX IX_EncThang ON #EncThang(LoaiDieuTri, KHAMBENH_ID);

        /* 7d) #KQP: mẫu số, số ca DISTINCT theo (tháng × nhóm × rổ) */
        IF OBJECT_ID('tempdb..#KQP') IS NOT NULL DROP TABLE #KQP;
        SELECT
            g.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(g.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(g.MonthStart) AS varchar(4)) AS [month],
            g.DiseaseGroup      AS disease_group,
            MAX(g.DiseaseGroupName) AS disease_group_name,
            g.Ro                AS ro,
            COUNT(DISTINCT g.TIEPNHAN_ID) AS cases
        INTO   #KQP
        FROM   #DxG g
        GROUP BY g.MonthStart, g.DiseaseGroup, g.Ro;

        SELECT @nDongPhanCap = COUNT(*) FROM #KQP;
        SELECT @nONhoPhanCap = COUNT(*) FROM #KQP WHERE cases < 5;

        /* 7e) #KQT: tử số, tiêu hao theo (tháng × nhóm × rổ × thuốc) */
        IF OBJECT_ID('tempdb..#KQT') IS NOT NULL DROP TABLE #KQT;
        SELECT
            g.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(g.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(g.MonthStart) AS varchar(4)) AS [month],
            g.DiseaseGroup       AS disease_group,
            g.Ro                 AS ro,
            dr.SupplyCode        AS supply_code,
            MAX(dr.SupplyName)   AS supply_name,
            MAX(dr.SupplyUnit)   AS supply_unit,
            MAX(dr.DrugGroup)    AS supply_category,
            MAX(dr.NoteCategory) AS note,
            MAX(CAST(dr.IsVtyt AS TINYINT)) AS is_vtyt,
            SUM(dr.Qty)          AS so_luong,
            SUM(dr.SoDong)       AS so_dong_toa
        INTO   #KQT
        FROM   #DxG  g
        JOIN   #Drug dr ON dr.LoaiDieuTri = g.LoaiDieuTri
                       AND dr.KHAMBENH_ID = g.KHAMBENH_ID
        GROUP BY g.MonthStart, g.DiseaseGroup, g.Ro, dr.SupplyCode
        HAVING SUM(dr.Qty) >= 0.001;

        SELECT @nDongTieuHao = COUNT(*) FROM #KQT;

        /* Kiểm chứng khử trùng: tổng theo #EncThang phải nhỏ hơn hoặc bằng tổng #KQT, chênh là lượt thuộc nhiều nhóm */
        SELECT @QtyRo = ISNULL(SUM(so_luong), 0) FROM #KQT;
        SELECT @QtyNhom = ISNULL(SUM(dr.Qty), 0)
        FROM   #EncThang e
        JOIN   #Drug dr ON dr.LoaiDieuTri = e.LoaiDieuTri
                       AND dr.KHAMBENH_ID = e.KHAMBENH_ID;

        IF @QtyRo < @QtyNhom - 0.5
            PRINT CONCAT(N'CẢNH BÁO: tổng lượng theo rổ (', @QtyRo,
                         N') NHỎ HƠN tổng lượng theo lượt (', @QtyNhom,
                         N'): đang mất dữ liệu ở bước gom theo rổ.');
        ELSE
            PRINT CONCAT(N'Tiêu hao: tổng theo rổ = ', @QtyRo,
                         N'; tổng theo lượt = ', @QtyNhom,
                         N' (chênh = phần lượt thuộc nhiều nhóm bệnh, đúng như thiết kế).');


        /* 8) Tồn kho: ảnh chụp tổng, không theo lô (lô do his_nguon/04 đẩy) */
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

        /* 9) Đẩy sang CSDL trung gian, hoặc chỉ trả kết quả nếu @ChiXem = 1 */
        IF @ChiXem = 1
        BEGIN
            PRINT CONCAT(N'CHẾ ĐỘ CHỈ XEM: không đẩy. Dòng = ', @nDong,
                         N', dòng nhóm = ', @nDongNhom,
                         N', dòng phân cấp = ', @nDongPhanCap,
                         N', dòng tiêu hao rổ = ', @nDongTieuHao,
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

            /* Kết quả 3: tỷ trọng phân cấp p̂(g,c) theo nhóm bệnh */
            SELECT  disease_group,
                    ro,
                    SUM(cases)                                                   AS TongCa,
                    CAST(100.0 * SUM(cases)
                         / SUM(SUM(cases)) OVER (PARTITION BY disease_group)
                         AS decimal(5,2))                                        AS TyTrong_PhanTram,
                    COUNT(*)                                                     AS SoThang,
                    SUM(CASE WHEN cases < 5 THEN 1 ELSE 0 END)                   AS SoThangDuoi5Ca
            FROM    #KQP
            GROUP BY disease_group, ro
            ORDER BY disease_group, ro;

            /* Kết quả 4: định mức thực nghiệm của thuốc tiêu hao lớn nhất */
            SELECT TOP 200
                   t.disease_group, t.ro, t.supply_code, t.supply_name, t.supply_unit,
                   SUM(t.so_luong)                                        AS TongLuong,
                   SUM(p.cases)                                           AS TongCa,
                   CAST(SUM(t.so_luong) / NULLIF(SUM(p.cases), 0)
                        AS decimal(12,3))                                 AS DinhMuc_MoiCa,
                   CAST(SUM(t.so_dong_toa) * 1.0 / NULLIF(SUM(p.cases), 0)
                        AS decimal(12,2))                                 AS SoDongToa_MoiCa
            FROM   #KQT t
            JOIN   #KQP p ON p.Period        = t.Period
                         AND p.disease_group = t.disease_group
                         AND p.ro            = t.ro
            GROUP BY t.disease_group, t.ro, t.supply_code, t.supply_name, t.supply_unit
            ORDER BY SUM(t.so_luong) DESC;

            RETURN;
        END

        /* Chốt chặn 1: không cho dữ liệu trùng khoá rời khỏi CSDL HIS */
        DECLARE @nTrung INT = (
            SELECT COUNT(*) FROM (
                SELECT 1 AS x FROM #KQ
                GROUP BY Period, disease_code, region, supply_code
                HAVING COUNT(*) > 1) t);
        IF @nTrung > 0
            THROW 50001, N'Kết quả tổng hợp có dòng trùng khoá (Period, disease_code, region, supply_code), không đẩy sang CSDL trung gian.', 1;

        /* DELETE giới hạn theo nhóm của lần chạy; dòng disease_group NULL được dọn luôn */
        DELETE FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
        WHERE  Period >= @TuNgay
          AND (disease_group IS NULL
               OR @NhomChuan LIKE N'%,' + disease_group + N',%');

        INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
              (Period, [month], disease_code, disease_name,
               disease_group, disease_group_name, region, cases,
               supply_code, supply_name, supply_quantity, supply_unit,
               supply_category, note, NgayCapNhat)
        SELECT Period, [month], disease_code, disease_name,
               disease_group, disease_group_name, region, cases,
               supply_code, supply_name, supply_quantity, supply_unit,
               supply_category, note, SYSDATETIME()
        FROM   #KQ;

        DELETE FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
        WHERE  Period >= @TuNgay
          AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

        INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
              (Period, [month], disease_group, disease_group_name, region, cases, NgayCapNhat)
        SELECT Period, [month], disease_group, disease_group_name, region, cases, SYSDATETIME()
        FROM   #KQN;

        /* Chốt chặn 2: số dòng bên CSDL trung gian cùng phạm vi phải khớp */
        DECLARE @nSauKhiDay INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
            WHERE Period >= @TuNgay
              AND (disease_group IS NULL
                   OR @NhomChuan LIKE N'%,' + disease_group + N',%'));
        IF @nSauKhiDay <> @nDong
            THROW 50002, N'Số dòng bên CSDL trung gian không khớp số dòng đã gom, nghi có dữ liệu thừa hoặc thiếu.', 1;

        /* Hai bảng phân cấp: xoá-rồi-chèn trong cùng phạm vi nhóm */
        IF @DayLuongPhanCap = 1
        BEGIN
            DELETE FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_PhanCap]
            WHERE  Period >= @TuNgay
              AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

            INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_CaBenh_PhanCap]
                  (Period, [month], disease_group, disease_group_name, ro, cases, NgayCapNhat)
            SELECT Period, [month], disease_group, disease_group_name, ro, cases, SYSDATETIME()
            FROM   #KQP;

            DELETE FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_TieuHao_PhanCap]
            WHERE  Period >= @TuNgay
              AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

            INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_TieuHao_PhanCap]
                  (Period, [month], disease_group, ro, supply_code, supply_name,
                   supply_unit, supply_category, note, is_vtyt,
                   so_luong, so_dong_toa, NgayCapNhat)
            SELECT Period, [month], disease_group, ro, supply_code, supply_name,
                   supply_unit, supply_category, note, is_vtyt,
                   so_luong, so_dong_toa, SYSDATETIME()
            FROM   #KQT;

        END

        /* Tồn kho: dừng nếu ảnh chụp rỗng để không xoá sạch MF_TonKho;
           DELETE thay TRUNCATE để không cần quyền ALTER */
        IF @nTonKho = 0
            THROW 50006, N'Ảnh chụp tồn kho rỗng: DỪNG, không xoá MF_TonKho bên CSDL trung gian. Kiểm tra @BENHVIEN_ID và TM_LOAIDUOC.LOAIVATTU_ID.', 1;

        EXEC (N'DELETE FROM MEDFORECAST_DW.dbo.MF_TonKho;') AT [MEDFORECAST_DW_LINK];

        INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_TonKho]
              (supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], NgayCapNhat)
        SELECT supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], SYSDATETIME()
        FROM   #TK;

        DECLARE @nTonKhoDW INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_TonKho]);
        IF @nTonKhoDW <> @nTonKho
            THROW 50007, N'Số dòng tồn kho bên CSDL trung gian không khớp ảnh chụp vừa tính.', 1;

        /* 10) Mốc và nhật ký */
        DECLARE @MocMoi DATE = (SELECT MAX(Period) FROM #KQ);

        UPDATE [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay    = CASE WHEN @MocMoi > ISNULL(MocDaDay, '19000101')
                                  THEN @MocMoi ELSE MocDaDay END,
               LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'CaBenh';

        IF @DayLuongPhanCap = 1
            UPDATE [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_Watermark]
            SET    MocDaDay    = CASE WHEN @MocMoi > ISNULL(MocDaDay, '19000101')
                                      THEN @MocMoi ELSE MocDaDay END,
                   LanChayCuoi = SYSDATETIME()
            WHERE  TenLuong = 'PhanCap';

        INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
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
                       @nDongNhom, N' dòng nhóm',
                       N'; PHÂN CẤP: ', @nDongPhanCap, N' dòng ca (',
                       @nONhoPhanCap, N' ô dưới 5 ca), ',
                       @nDongTieuHao, N' dòng tiêu hao rổ',
                       N'; VTYT=', @GomVTYT));

        PRINT CONCAT(N'Xong. Dòng = ', @nDong, N', dòng nhóm = ', @nDongNhom,
                     N', dòng phân cấp = ', @nDongPhanCap,
                     N', dòng tiêu hao rổ = ', @nDongTieuHao,
                     N', ca gốc = ', @TongCaGoc,
                     N', loại vì không rõ tỉnh = ', @nCaKhongRoTinh,
                     N', ca đẩy đi = ', @TongCa,
                     N', nhóm không thuốc = ', @nNhomKhongThuoc,
                     N', ô đã gộp = ', @nOGop, N', tồn kho = ', @nTonKho);
    END TRY
    BEGIN CATCH
        BEGIN TRY
            INSERT INTO [MEDFORECAST_DW_LINK].[MEDFORECAST_DW].[dbo].[MF_SyncLog]
                  (BatDau, KetThuc, TuNgay, TrangThai, ThongDiep)
            VALUES (@BatDau, SYSDATETIME(), @TuNgay, 'failed',
                    CONCAT(N'Lỗi ', ERROR_NUMBER(), N' dòng ', ERROR_LINE(),
                           N': ', ERROR_MESSAGE()));
        END TRY
        BEGIN CATCH
            PRINT N'Không ghi được nhật ký sang CSDL trung gian, kiểm tra linked server.';
        END CATCH
        THROW;
    END CATCH
END
GO


/* Cách dùng
   Xem trước:      EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1, @ChiXem = 1;
   Nạp lần đầu:    EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;
   Hằng ngày:      EXEC dbo.usp_MedForecast_DayDuLieu;
   Một nhóm:       EXEC dbo.usp_MedForecast_DayDuLieu @NhomBenhDich = N'J09-J18'; */
