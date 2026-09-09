/* =============================================================================
   PHASE 0 — BƯỚC 2: THỦ TỤC CA BỆNH, BẢN 2 (thay thế 03_PROD_store_tong_hop.sql)
   =============================================================================
   Chạy trên: HIS PROD (GIAAN115_HIS). Cần script 01 + 02 cũ và Phase0_01 mới.

   ĐÂY LÀ BẢN THAY THẾ TOÀN BỘ, KHÔNG PHẢI BẢN VÁ.
   Giữ nguyên tên thủ tục `usp_MedForecast_DayDuLieu` và toàn bộ tham số cũ,
   nên job hiện tại (04_PROD_job.sql) không phải sửa.

   -----------------------------------------------------------------------------
   NHỮNG GÌ ĐỔI SO VỚI BẢN 1 — đọc hết trước khi chạy

   A. BA LỖI ĐÃ SỬA
      A1  DELETE bên STA không giới hạn theo nhóm bệnh.
          Bản cũ:  DELETE ... WHERE Period >= @TuNgay
          Chạy `@NhomBenhDich = N'J09-J18'` để xem riêng một nhóm sẽ XOÁ SẠCH
          dữ liệu của hai nhóm còn lại trong cùng cửa sổ rồi chèn lại có mỗi
          nhóm vừa chạy. Không có thông báo lỗi nào. Bản mới giới hạn DELETE
          theo đúng danh sách nhóm của lần chạy (biến @NhomChuan).

      A2  TRUNCATE bảng tồn kho không có chốt chặn, lại sai tên đầy đủ.
          Bản cũ:  EXEC (N'TRUNCATE TABLE dbo.MF_TonKho') AT [MEDFORECAST_STA]
          Hai vấn đề: (i) `dbo.MF_TonKho` phụ thuộc database mặc định của
          login đẩy — nếu ai đó đổi default database thì lệnh này chạy nhầm
          chỗ hoặc lỗi; (ii) nếu #TK rỗng (ví dụ đặt sai @BENHVIEN_ID, hoặc
          TM_LOAIDUOC đổi mã) thì bảng bị xoá sạch rồi chèn 0 dòng, và ứng
          dụng thấy TOÀN BỘ tồn kho = 0 → mọi vật tư báo thiếu hàng.
          Bản mới: tên ba phần đầy đủ, đổi TRUNCATE thành DELETE (không cần
          quyền ALTER), và THROW nếu #TK rỗng trước khi đụng vào bảng đích.

      A3  Nhánh ngoại trú dùng INNER JOIN TM_ICD.
          Bản cũ:  JOIN TM_ICD icdc ON icdc.ICD_ID = KB.CHANDOANICD_ID
          Lượt ngoại trú có CHANDOANICD_ID rỗng nhưng DS_MAICDPHU chứa mã
          đích sẽ bị loại ngay ở bước 1b, dù mệnh đề WHERE đã cố tình cho
          phép trường hợp đó. Nhánh nội trú (1a) dùng LEFT JOIN nên không
          dính. Bản mới: LEFT JOIN, đối xứng với 1a.

   B. PHÂN CẤP CHĂM SÓC — thêm mới
      Nguồn: TT_NOITRU_KHAMBENH.PHANCAPCHAMSOC_ID → LST_DICTIONARY
             (DICTIONARY_TYPE_CODE = 'PhanCapChamSoc', mã '1' | '2' | '3').
      Quy tắc một đợt: cấp = MIN(mã) trên các y lệnh của đợt (mã nhỏ = nặng).
      Đ4 xác nhận quy tắc này gần như không mất thông tin: 59,9% số đợt chỉ có
      đúng một cấp, và trong nhóm nhiều cấp thì hầu hết là nặng → nhẹ (hồi phục).

      NĂM RỔ, không phải bốn: NGT | NT1 | NT2 | NT3 | NT0.
      Đ5 đo trên 12 tháng gần nhất: NGT 4,72 dòng toa/lượt, NT-cấp 3 16,89 —
      chênh 3,5 lần. Quy ước cũ "ngoại trú = cấp 3" vì vậy bị bác bỏ bằng số.
      NT0 = nội trú chưa gán phân cấp (Đ3: 0% giai đoạn 2019-2025, 0,02% năm
      2026) — giữ riêng chứ không nhét vào NT3, để phần thiếu dữ liệu luôn
      nhìn thấy được thay vì hoà tan vào một rổ có thật.

   C. BA BẢNG ĐẦU RA MỚI (xem Phase0_01 để biết cấu trúc)
      MF_CaBenh_PhanCap    mẫu số định mức, ĐẾM Ở MỨC NHÓM
      MF_TieuHao_PhanCap   tử số định mức
      MF_TieuHao_Tong      tiêu hao theo tháng × vật tư, bỏ chiều bệnh

      ⚠ ĐIỂM DỄ SAI NHẤT CỦA BẢN NÀY: chống đếm hai lần ở mức nhóm.
      Một lượt mang J01 (chính) + J06 (phụ) sinh HAI dòng trong #Dx. Bảng cũ
      MF_CaBenh_VatTu cố ý giữ cả hai (dự báo theo từng mã cần vậy). Nhưng ở
      mức NHÓM, J01 và J06 cùng thuộc J00-J06, nên nếu ghép thẳng #Dx với
      #Drug thì lượng thuốc của lượt đó bị CỘNG HAI LẦN vào nhóm J00-J06.
      Bản này dựng bảng trung gian #DxG (khử trùng ở mức nhóm) rồi mới ghép.
      Bất biến kiểm chứng: SUM(MF_TieuHao_PhanCap.so_luong) của một nhóm phải
      BẰNG tổng lượng thuốc của các lượt thuộc nhóm đó — thủ tục tự kiểm và
      in CẢNH BÁO nếu lệch.

   D. VẬT TƯ Y TẾ — tham số @GomVTYT, mặc định TẮT
      Bản cũ chỉ lấy TM_LOAIDUOC.LOAIVATTU_ID = 'T' (thuốc). Đặt @GomVTYT = 1
      để lấy cả VTYT. Lưu ý nghiệp vụ: y lệnh VTYT có ISYLENHVTYT = 1 và
      KHÔNG mang phân cấp chăm sóc, nên với các dòng is_vtyt = 1 thì tầng sau
      PHẢI gộp NT1+NT2+NT3+NT0 lại trước khi chia định mức. Cột `is_vtyt`
      trong bảng đầu ra chính là để tầng sau biết mà gộp.
============================================================================= */

CREATE OR ALTER PROCEDURE dbo.usp_MedForecast_DayDuLieu
    @SoThangLuiLai       INT   = 3,              -- khớp PIPELINE_LOOKBACK_MONTHS
    @NapLaiToanBo        BIT   = 0,
    @TuNgayGoc           DATE  = '2019-01-01',   -- mốc khi nạp lại toàn bộ
    @BENHVIEN_ID         INT   = NULL,           -- ⚙ đặt 79428 nếu DB nhiều bệnh viện
    @NhomBenhDich        NVARCHAR(400) = N'J00-J06,J09-J18,J20-J22',
    @XuLyVungKhongXacDinh TINYINT = 1,           -- 0 giữ nhãn | 1 gộp | 2 loại bỏ
    @NguongOutlier       FLOAT = NULL,
    @NguongOToiThieu     INT   = 5,              -- ngưỡng ô nhỏ; 0 hoặc 1 = tắt
    @NhanGopVung         NVARCHAR(120) = N'Tỉnh khác',
    @GiuNhomKhongCoThuoc BIT   = 1,
    @ChiXem              BIT   = 0,              -- 1 = chỉ SELECT, không đẩy
    /* ★ Phase 0 */
    @GomVTYT             BIT   = 0,              -- 1 = lấy cả vật tư y tế
    @DayLuongPhanCap     BIT   = 1               -- 0 = tắt 3 bảng mới (để so số cũ)
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
    /* ★ Phase 0 */
    DECLARE @NhomChuan NVARCHAR(500),
            @nDongPhanCap INT = 0, @nDongTieuHao INT = 0, @nDongTieuHaoTong INT = 0,
            @nONhoPhanCap INT = 0,
            @QtyNhom FLOAT = 0, @QtyRo FLOAT = 0;

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

        /* ★ SỬA LỖI A1 — chuỗi nhóm đã chuẩn hoá, dùng để giới hạn mọi lệnh
           DELETE bên STA. Dạng ',J00-J06,J09-J18,J20-J22,' để so bằng LIKE
           mà không cần đẩy bảng tạm qua linked server.                        */
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
            THROW 50005, N'Không tìm thấy mã ICD nào thuộc @NhomBenhDich trong TM_ICD — kiểm tra lại cột PHANNHOM.', 1;

        PRINT CONCAT(N'Phạm vi bệnh: ', @nNhomDich, N' nhóm (', @NhomBenhDich,
                     N') → ', @nMaDich, N' mã 3 ký tự.');

        /* =====================================================================
           1) #Enc — lượt khám thuộc các nhóm bệnh đích, GỘP nội trú + ngoại trú
           ---------------------------------------------------------------------
           ★ Phase 0: thêm cột CapYLenh — phân cấp chăm sóc của TỪNG y lệnh.
           Chỉ y lệnh THUỐC (ISYLENHVTYT = 0) mới có phân cấp; y lệnh VTYT để
           NULL và sẽ tự bị MIN() bỏ qua ở bước 1c. Không cần lọc thêm.
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
            KB.DS_MAICDPHU                  AS SubICD,
            TRY_CAST(pccs.DICTIONARY_CODE AS INT) AS CapYLenh   -- ★ 1 | 2 | 3 | NULL
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

        -- 1b) NGOẠI TRÚ
        --     ★ SỬA LỖI A3: LEFT JOIN TM_ICD (bản cũ dùng INNER JOIN nên lượt
        --     có CHANDOANICD_ID rỗng mà DS_MAICDPHU chứa mã đích bị rơi mất).
        --     Ngoại trú không có phân cấp chăm sóc → CapYLenh = NULL, rổ 'NGT'.
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

        /* =====================================================================
           1c) ★ #CapDot — RỔ của mỗi đợt điều trị
           ---------------------------------------------------------------------
           cap(đợt) = MIN(mã phân cấp trên các y lệnh của đợt). Mã nhỏ = nặng
           hơn, nên MIN chính là "cấp nặng nhất mà bệnh nhân từng ở trong đợt".

           Phạm vi MIN chỉ tính trên các y lệnh ĐÃ LỌT BỘ LỌC BỆNH ĐÍCH (tức
           các dòng trong #Enc), không phải toàn bộ y lệnh của đợt. Đây là chủ
           ý: cần mức độ nặng TRONG LÚC điều trị bệnh hô hấp, không phải mức
           nặng vì một bệnh khác cùng đợt.

           Rổ: NGT | NT1 | NT2 | NT3 | NT0.
           NT0 nghĩa là nội trú nhưng không y lệnh nào của đợt có phân cấp.
           ===================================================================== */
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

        /* Cấp lạ (mã phân cấp không phải 1/2/3) sẽ tạo rổ ngoài danh sách và
           bị CHECK constraint bên STA chặn. Chuẩn hoá về NT0 và báo ra ngay,
           thay vì để lỗi nổ ở bước đẩy khi đã chạy xong 20 phút.               */
        IF EXISTS (SELECT 1 FROM #CapDot WHERE Ro NOT IN ('NGT','NT1','NT2','NT3','NT0'))
        BEGIN
            PRINT N'CẢNH BÁO: có mã phân cấp chăm sóc ngoài {1,2,3} — đã dồn vào rổ NT0. Kiểm tra LST_DICTIONARY.';
            UPDATE #CapDot SET Ro = 'NT0'
            WHERE  Ro NOT IN ('NGT','NT1','NT2','NT3','NT0');
        END

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
        WHERE ISNULL(NULLIF(LTRIM(RTRIM(bn.ACTIVE)), ''), '1') <> '0';
        CREATE UNIQUE CLUSTERED INDEX IX_PatReg ON #PatReg(BENHNHAN_ID);

        /* =====================================================================
           3) #Dx — 1 dòng / (loại × lượt khám × mã bệnh), gộp chính + phụ
           ★ Phase 0: gắn thêm cột Ro (từ #CapDot). Ro là hàm của
             (LoaiDieuTri, TIEPNHAN_ID) nên KHÔNG làm tăng số dòng.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Dx') IS NOT NULL DROP TABLE #Dx;
        SELECT DISTINCT
               x.LoaiDieuTri, x.KHAMBENH_ID, x.TIEPNHAN_ID, x.MonthStart,
               pr.Region, x.DiseaseCode, cd.Ro
        INTO #Dx
        FROM (
            -- chẩn đoán CHÍNH
            SELECT e.LoaiDieuTri, e.KHAMBENH_ID, e.TIEPNHAN_ID, e.BENHNHAN_ID,
                   e.MonthStart, m.Ma3 AS DiseaseCode
            FROM   #Enc e
            JOIN   #Ma3 m ON m.Ma3 = LEFT(e.PrimaryICD, 3)
            UNION ALL
            -- chẩn đoán PHỤ (chỉ từ DS_MAICDPHU — danh sách mã chuẩn)
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

        /* =====================================================================
           3a) VÙNG KHÔNG XÁC ĐỊNH — phải xử lý TRƯỚC bước gộp ô nhỏ
           ===================================================================== */
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
           3b) NGƯỠNG Ô NHỎ — chống tái định danh (chỉ tác động chiều VÙNG)
           ---------------------------------------------------------------------
           ★ Lưu ý Phase 0: bước này đổi cột Region, KHÔNG đổi Ro và không đổi
           số ca. Vì vậy ba bảng mới (không có chiều vùng) hoàn toàn không bị
           ảnh hưởng bởi ngưỡng k — đúng như mong muốn: tỷ trọng phân cấp phải
           là con số thật, không bị làm mờ.
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
           4) #DrugMeta — danh mục thuốc (+ VTYT nếu @GomVTYT = 1)
           ★ Phase 0: thêm cột IsVtyt; nới bộ lọc LOAIVATTU_ID theo tham số.
           ===================================================================== */
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
        WHERE (@GomVTYT = 1 OR ld.LOAIVATTU_ID = 'T')     -- ★ mặc định: chỉ thuốc
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
           ★ Phase 0: thêm SoDong (số dòng toa gốc) và IsVtyt.
             SoDong CHỈ để đối chiếu — Đ5 cho thấy dùng nó thay số lượng sẽ
             sai hệ thống (NGT 4,72 dòng/lượt × 18,29 đv/dòng so với
             NT-cấp 3 16,89 dòng/lượt × 3,33 đv/dòng).
           ===================================================================== */
        IF OBJECT_ID('tempdb..#Drug') IS NOT NULL DROP TABLE #Drug;
        CREATE TABLE #Drug (
            LoaiDieuTri  VARCHAR(3),   KHAMBENH_ID BIGINT,
            SupplyCode   NVARCHAR(50), SupplyName  NVARCHAR(500),
            SupplyUnit   NVARCHAR(50), DrugGroup   NVARCHAR(200),
            NoteCategory NVARCHAR(100), IsVtyt     BIT,
            Qty          FLOAT,        SoDong      INT
        );

        -- 6a) NỘI TRÚ: số lượng = số thực lĩnh, thiếu thì lấy số kê
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

        -- 6b) NGOẠI TRÚ
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

        /* =====================================================================
           7) #KQ — kết quả theo MÃ bệnh (hợp đồng dữ liệu cũ, không đổi)
           ===================================================================== */
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
                         N'). Có chỗ đang làm mất hoặc nhân đôi ca — kiểm tra trước khi đẩy.');

        /* =====================================================================
           7b) SỐ CA THEO NHÓM ICD — bảng riêng (không đổi so với bản 1)
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
           ★ 7c) #DxG — KHỬ TRÙNG Ở MỨC NHÓM
           ---------------------------------------------------------------------
           Đây là bảng quan trọng nhất mà bản 1 không có, và là chỗ dễ sai nhất
           của toàn Phase 0.

           #Dx có một dòng cho MỖI MÃ bệnh. Một lượt khám mang J01 (chính) và
           J06 (phụ) sẽ có HAI dòng. Cả hai mã cùng thuộc nhóm J00-J06.
           Nếu ghép thẳng #Dx với #Drug rồi gom theo nhóm, lượng thuốc của lượt
           đó được CỘNG HAI LẦN vào J00-J06 — định mức sẽ phồng lên đúng bằng
           tỷ lệ đồng mắc trong nhóm, và không có cách nào phát hiện từ kết quả.

           #DxG khử trùng xuống một dòng cho mỗi (lượt khám × nhóm). Lượt mang
           mã ở HAI nhóm khác nhau (J06 + J20) vẫn giữ hai dòng — đó là chủ ý,
           vì thuốc của lượt đó phục vụ cả hai bệnh và định mức của từng nhóm
           đều phải thấy nó.
           ===================================================================== */
        IF OBJECT_ID('tempdb..#DxG') IS NOT NULL DROP TABLE #DxG;
        SELECT DISTINCT
               dx.LoaiDieuTri, dx.KHAMBENH_ID, dx.TIEPNHAN_ID, dx.MonthStart,
               m3.DiseaseGroup, m3.DiseaseGroupName, dx.Ro
        INTO   #DxG
        FROM   #Dx dx
        JOIN   #Ma3 m3 ON m3.Ma3 = dx.DiseaseCode;
        CREATE CLUSTERED INDEX IX_DxG ON #DxG(LoaiDieuTri, KHAMBENH_ID);

        /* Danh sách lượt khám × tháng, khử trùng qua mọi nhóm — cho bảng tổng */
        IF OBJECT_ID('tempdb..#EncThang') IS NOT NULL DROP TABLE #EncThang;
        SELECT DISTINCT LoaiDieuTri, KHAMBENH_ID, TIEPNHAN_ID, MonthStart
        INTO   #EncThang
        FROM   #DxG;
        CREATE CLUSTERED INDEX IX_EncThang ON #EncThang(LoaiDieuTri, KHAMBENH_ID);

        /* =====================================================================
           ★ 7d) #KQP — MẪU SỐ: số ca theo (tháng × nhóm × rổ)
           ===================================================================== */
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

        /* =====================================================================
           ★ 7e) #KQT — TỬ SỐ: tiêu hao theo (tháng × nhóm × rổ × vật tư)
           ===================================================================== */
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

        /* KIỂM CHỨNG KHỬ TRÙNG — bất biến quan trọng nhất của Phase 0.
           Tổng lượng theo (nhóm × rổ) phải bằng tổng lượng theo nhóm khi gom
           trực tiếp từ #DxG. Nếu #DxG còn trùng thì hai số này vẫn bằng nhau,
           nên phải so với một cách tính ĐỘC LẬP: gom từ danh sách lượt khám
           khử trùng hoàn toàn (#EncThang) — số này phải NHỎ HƠN HOẶC BẰNG,
           chênh đúng bằng phần lượt nằm ở hai nhóm khác nhau.                 */
        SELECT @QtyRo = ISNULL(SUM(so_luong), 0) FROM #KQT;
        SELECT @QtyNhom = ISNULL(SUM(dr.Qty), 0)
        FROM   #EncThang e
        JOIN   #Drug dr ON dr.LoaiDieuTri = e.LoaiDieuTri
                       AND dr.KHAMBENH_ID = e.KHAMBENH_ID;

        IF @QtyRo < @QtyNhom - 0.5
            PRINT CONCAT(N'CẢNH BÁO: tổng lượng theo rổ (', @QtyRo,
                         N') NHỎ HƠN tổng lượng theo lượt (', @QtyNhom,
                         N') — đang mất dữ liệu ở bước gom theo rổ.');
        ELSE
            PRINT CONCAT(N'Tiêu hao: tổng theo rổ = ', @QtyRo,
                         N'; tổng theo lượt = ', @QtyNhom,
                         N' (chênh = phần lượt thuộc nhiều nhóm bệnh, đúng như thiết kế).');

        /* =====================================================================
           ★ 7f) #KQTT — tiêu hao theo (tháng × vật tư), bỏ chiều bệnh
           ===================================================================== */
        IF OBJECT_ID('tempdb..#KQTT') IS NOT NULL DROP TABLE #KQTT;
        SELECT
            e.MonthStart AS Period,
            RIGHT('0' + CAST(MONTH(e.MonthStart) AS varchar(2)), 2)
                + '/' + CAST(YEAR(e.MonthStart) AS varchar(4)) AS [month],
            dr.SupplyCode      AS supply_code,
            MAX(dr.SupplyName) AS supply_name,
            MAX(dr.SupplyUnit) AS supply_unit,
            MAX(CAST(dr.IsVtyt AS TINYINT)) AS is_vtyt,
            SUM(dr.Qty)        AS so_luong,
            SUM(dr.SoDong)     AS so_dong_toa,
            COUNT(DISTINCT e.TIEPNHAN_ID) AS so_luot
        INTO   #KQTT
        FROM   #EncThang e
        JOIN   #Drug dr ON dr.LoaiDieuTri = e.LoaiDieuTri
                       AND dr.KHAMBENH_ID = e.KHAMBENH_ID
        GROUP BY e.MonthStart, dr.SupplyCode
        HAVING SUM(dr.Qty) >= 0.001;

        SELECT @nDongTieuHaoTong = COUNT(*) FROM #KQTT;

        /* =====================================================================
           8) Tồn kho — ảnh chụp hiện tại (tổng, không theo lô)
           Tồn theo LÔ nằm ở thủ tục riêng: usp_MedForecast_DayKhoCungUng.
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
                         N', dòng phân cấp = ', @nDongPhanCap,
                         N', dòng tiêu hao rổ = ', @nDongTieuHao,
                         N', dòng tiêu hao tổng = ', @nDongTieuHaoTong,
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

            /* ★ Bảng thứ ba: tỷ trọng phân cấp p̂(g,c) — con số THAY THẾ bảng
               severity_rates gõ tay. So trực tiếp với 71,49/23,51/5 đang nhập. */
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

            /* ★ Bảng thứ tư: định mức thực nghiệm 20 vật tư lớn nhất mỗi rổ.
               Đây là con số Tầng 3 sẽ dùng — xem trước khi bật đẩy.            */
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

        /* Chốt chặn 1 — không cho dữ liệu trùng khoá rời khỏi PROD. */
        DECLARE @nTrung INT = (
            SELECT COUNT(*) FROM (
                SELECT 1 AS x FROM #KQ
                GROUP BY Period, disease_code, region, supply_code
                HAVING COUNT(*) > 1) t);
        IF @nTrung > 0
            THROW 50001, N'Kết quả tổng hợp có dòng trùng khoá (Period, disease_code, region, supply_code) — không đẩy xuống STA.', 1;

        /* ★ SỬA LỖI A1 — DELETE giới hạn theo NHÓM của lần chạy này.
           @NhomChuan có dạng ',J00-J06,J09-J18,J20-J22,'. Dòng disease_group
           NULL là rác từ bản trước (khi chưa có cột nhóm) nên dọn luôn.       */
        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
        WHERE  Period >= @TuNgay
          AND (disease_group IS NULL
               OR @NhomChuan LIKE N'%,' + disease_group + N',%');

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

        DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
        WHERE  Period >= @TuNgay
          AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_Nhom]
              (Period, [month], disease_group, disease_group_name, region, cases, NgayCapNhat)
        SELECT Period, [month], disease_group, disease_group_name, region, cases, SYSDATETIME()
        FROM   #KQN;

        /* Chốt chặn 2 — số dòng bên STA trong CÙNG PHẠM VI phải khớp. */
        DECLARE @nSauKhiDay INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_VatTu]
            WHERE Period >= @TuNgay
              AND (disease_group IS NULL
                   OR @NhomChuan LIKE N'%,' + disease_group + N',%'));
        IF @nSauKhiDay <> @nDong
            THROW 50002, N'Số dòng bên STA không khớp số dòng đã gom — nghi có dữ liệu thừa hoặc thiếu.', 1;

        /* ★ Ba bảng mới — cùng kiểu xoá-rồi-chèn, cùng phạm vi nhóm.
           MF_TieuHao_Tong KHÔNG có chiều bệnh nên không giới hạn theo nhóm
           được; nó chỉ đúng khi chạy đủ ba nhóm. Vì vậy chỉ đẩy bảng này khi
           lần chạy bao trọn danh sách nhóm mặc định.                          */
        IF @DayLuongPhanCap = 1
        BEGIN
            DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_PhanCap]
            WHERE  Period >= @TuNgay
              AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_CaBenh_PhanCap]
                  (Period, [month], disease_group, disease_group_name, ro, cases, NgayCapNhat)
            SELECT Period, [month], disease_group, disease_group_name, ro, cases, SYSDATETIME()
            FROM   #KQP;

            DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_PhanCap]
            WHERE  Period >= @TuNgay
              AND  @NhomChuan LIKE N'%,' + disease_group + N',%';

            INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_PhanCap]
                  (Period, [month], disease_group, ro, supply_code, supply_name,
                   supply_unit, supply_category, note, is_vtyt,
                   so_luong, so_dong_toa, NgayCapNhat)
            SELECT Period, [month], disease_group, ro, supply_code, supply_name,
                   supply_unit, supply_category, note, is_vtyt,
                   so_luong, so_dong_toa, SYSDATETIME()
            FROM   #KQT;

            IF @nNhomDich >= 3
            BEGIN
                DELETE FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
                WHERE  Period >= @TuNgay;

                INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TieuHao_Tong]
                      (Period, [month], supply_code, supply_name, supply_unit,
                       is_vtyt, so_luong, so_dong_toa, so_luot, NgayCapNhat)
                SELECT Period, [month], supply_code, supply_name, supply_unit,
                       is_vtyt, so_luong, so_dong_toa, so_luot, SYSDATETIME()
                FROM   #KQTT;
            END
            ELSE
                PRINT N'Bỏ qua MF_TieuHao_Tong: lần chạy này không bao trọn ba nhóm bệnh, đẩy vào sẽ làm hụt số của các nhóm không chạy.';
        END

        /* ★ SỬA LỖI A2 — tồn kho: chốt chặn trước, tên ba phần đầy đủ,
           DELETE thay cho TRUNCATE (không cần quyền ALTER SCHEMA).            */
        IF @nTonKho = 0
            THROW 50006, N'Ảnh chụp tồn kho rỗng — DỪNG, không xoá MF_TonKho bên STA. Kiểm tra @BENHVIEN_ID và TM_LOAIDUOC.LOAIVATTU_ID.', 1;

        EXEC (N'DELETE FROM MEDFORECAST_DW.dbo.MF_TonKho;') AT [MEDFORECAST_STA];

        INSERT INTO [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho]
              (supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], NgayCapNhat)
        SELECT supply_code, drug_code, ten_hoat_chat, unit, group_name,
               category, stock_quantity, [description], SYSDATETIME()
        FROM   #TK;

        DECLARE @nTonKhoSTA INT = (
            SELECT COUNT(*) FROM [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_TonKho]);
        IF @nTonKhoSTA <> @nTonKho
            THROW 50007, N'Số dòng tồn kho bên STA không khớp ảnh chụp vừa tính.', 1;

        /* --- 10) Mốc và nhật ký ------------------------------------------- */
        DECLARE @MocMoi DATE = (SELECT MAX(Period) FROM #KQ);

        UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
        SET    MocDaDay    = CASE WHEN @MocMoi > ISNULL(MocDaDay, '19000101')
                                  THEN @MocMoi ELSE MocDaDay END,
               LanChayCuoi = SYSDATETIME()
        WHERE  TenLuong = 'CaBenh';

        IF @DayLuongPhanCap = 1
            UPDATE [MEDFORECAST_STA].[MEDFORECAST_DW].[dbo].[MF_Watermark]
            SET    MocDaDay    = CASE WHEN @MocMoi > ISNULL(MocDaDay, '19000101')
                                      THEN @MocMoi ELSE MocDaDay END,
                   LanChayCuoi = SYSDATETIME()
            WHERE  TenLuong = 'PhanCap';

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
                       @nDongNhom, N' dòng nhóm',
                       N'; PHÂN CẤP: ', @nDongPhanCap, N' dòng ca (',
                       @nONhoPhanCap, N' ô dưới 5 ca), ',
                       @nDongTieuHao, N' dòng tiêu hao rổ, ',
                       @nDongTieuHaoTong, N' dòng tiêu hao tổng',
                       N'; VTYT=', @GomVTYT));

        PRINT CONCAT(N'Xong. Dòng = ', @nDong, N', dòng nhóm = ', @nDongNhom,
                     N', dòng phân cấp = ', @nDongPhanCap,
                     N', dòng tiêu hao rổ = ', @nDongTieuHao,
                     N', dòng tiêu hao tổng = ', @nDongTieuHaoTong,
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
   CÁCH DÙNG — PHASE 0

   BƯỚC A · Đối chiếu số CŨ, chưa đẩy gì. Phải ra ĐÚNG con số của bản 1.
       EXEC dbo.usp_MedForecast_DayDuLieu
            @NapLaiToanBo = 1, @ChiXem = 1, @DayLuongPhanCap = 0;
       → so số dòng và tổng supply_quantity với lần chạy bản 1.
       Chênh duy nhất được phép: nhiều hơn một ít lượt NGOẠI TRÚ (do sửa lỗi A3
       LEFT JOIN). Nếu chênh theo hướng ngược lại thì DỪNG.

   BƯỚC B · Xem bốn bảng mới, vẫn chưa đẩy.
       EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1, @ChiXem = 1;
       → Bảng 3 (tỷ trọng phân cấp) là cái phải soi kỹ nhất. Đối chiếu với
         Đ4: cấp 1 ≈ 42%, cấp 2 ≈ 41%, cấp 3 ≈ 17% trên toàn viện. Ở mức
         từng nhóm bệnh con số sẽ khác — J09-J18 (viêm phổi) phải nặng hơn
         J00-J06 (viêm hô hấp trên) rõ rệt. Nếu KHÔNG thấy chênh lệch đó thì
         cột PHANCAPCHAMSOC_ID đang không phản ánh mức độ nặng, và toàn bộ
         Tầng 2 phải xem lại trước khi đi tiếp.
       → Bảng 4 (định mức thực nghiệm): kiểm tra vài dòng bằng tay với khoa
         Dược. Một dòng vô lý (ví dụ 4.000 viên paracetamol mỗi ca) là dấu
         hiệu đơn vị tính lệch giữa TM_DONVITINH và thực tế cấp phát.

   BƯỚC C · Nạp thật lần đầu.
       EXEC dbo.usp_MedForecast_DayDuLieu @NapLaiToanBo = 1;

   BƯỚC D · Job hằng ngày — không đổi câu lệnh, không cần sửa 04_PROD_job.sql.
       EXEC dbo.usp_MedForecast_DayDuLieu;

   Nếu DB nhiều bệnh viện: thêm @BENHVIEN_ID = 79428 ở mọi lần gọi.

   -----------------------------------------------------------------------------
   CHẠY MỘT NHÓM ĐỂ XEM RIÊNG — giờ đã AN TOÀN
       EXEC dbo.usp_MedForecast_DayDuLieu @NhomBenhDich = N'J09-J18';
   Bản 1 làm việc này sẽ xoá mất hai nhóm kia (lỗi A1). Bản này chỉ đụng đúng
   nhóm J09-J18; MF_TieuHao_Tong tự động bị bỏ qua vì nó không có chiều bệnh
   nên chỉ đúng khi chạy đủ ba nhóm.

   -----------------------------------------------------------------------------
   QUAY VỀ HÀNH VI BẢN 1 (nếu cần so số trong lúc bảo vệ)
       @DayLuongPhanCap = 0   tắt ba bảng mới
       @GomVTYT         = 0   chỉ thuốc (mặc định)
   Hai lỗi A1 và A2 KHÔNG có công tắc tắt — chúng là lỗi, không phải lựa chọn.
============================================================================= */
