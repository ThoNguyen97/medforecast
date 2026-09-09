# G0 — Cắt phạm vi và đo bổ sung

Ba tệp đi kèm:

| Tệp | Chạy ở đâu | Có ghi dữ liệu? |
|---|---|---|
| `sql_his/phase0/MedForecast_D9_D10.sql` | SSMS → HIS PROD `GIAAN115_HIS` | **Không** — chỉ SELECT và bảng tạm |
| `G0_cat_pham_vi.py` | Thư mục gốc repo | Có, nhưng mặc định chỉ **thử** |
| `G0_HuongDan.md` | — | — |

**Trạng thái kiểm chứng:** script đã chạy thử trên đúng bản mã hiện tại của anh —
**15/15 phép sửa khớp chính xác, không có mục nào hỏng**. Với `--strip-masterdata`
thì thêm 4 phép nữa, cũng khớp hết.

---

## 1. Thứ tự làm

Hai việc **độc lập nhau**, làm song song được:

- **Nhánh A — đo:** chạy Đ9 và Đ10 trên SSMS. Kết quả quyết định tham số cho G4
  và quyết định phạm vi tuyên bố của đề tài. Đ10 chạy có thể lâu, cứ để chạy.
- **Nhánh B — cắt mã:** chạy script trên repo. Không phụ thuộc kết quả đo.

Làm nhánh A trước rồi bấm chạy, trong lúc chờ thì làm nhánh B.

---

## 2. Nhánh A — chạy Đ9 và Đ10

Hướng dẫn chi tiết nằm ngay đầu tệp `.sql`. Tóm tắt:

1. SSMS → kết nối HIS PROD → chọn database `GIAAN115_HIS`.
2. Bật **Results to Grid** (`Ctrl+D`).
3. Nếu DB nhiều bệnh viện: sửa `@BENHVIEN_ID = 79428` ở các dòng có dấu ⚙.
4. **Chạy từng khối, không chạy cả tệp một lượt.** Bôi đen khối rồi `F5`:
   - `BƯỚC 0` — xác nhận cột. Phải đủ 8 dòng `CoCot = 1`. Thiếu dòng nào thì
     dừng và gửi lại bảng đó.
   - Khối `Đ9` — nhanh, vài giây tới vài chục giây.
   - Khối `Đ10` — quét toa thuốc 12 tháng. **Chạy ngoài giờ cao điểm.** Nếu quá
     lâu, hạ `@SoThang` xuống 6 rồi 3; kết quả vẫn đủ để quyết định.
5. Xuất kết quả: chuột phải vào lưới → *Save Results As…* (CSV).

### Cần gửi lại những bảng nào

| Bảng | Dùng để |
|---|---|
| **Đ9-C** và **Đ9-E** | Chốt `doi_red_days` / `doi_amber_days`. Hai con số này thay cho 7/14 đang chọn tay. |
| **Đ10-A**, **Đ10-B** | **Cổng chặn.** Quyết định đi tiếp G1 hay phải thu hẹp tuyên bố đề tài. |
| **Đ10-C** | Đối chiếu bằng mắt với hiểu biết của khoa Dược. |
| **Đ10-D** (CSV) | Dữ liệu nhu cầu nền, nạp vào ở G3. |

### Đọc cổng chặn Đ10-B

Cộng `SoMa` của ba dòng đầu (≥75%, 50–75%, 25–50%):

- **≥ 100 mã** → luận điểm "dịch hô hấp lái nhu cầu vật tư" đứng vững. Đi tiếp G1.
- **< 100 mã** → dừng lại. Mô hình dịch tễ chỉ lái được một tập nhỏ. Khi đó
  *chính việc xác định tập đó* trở thành kết quả cần trình bày, chứ không phải
  một thất bại cần giấu. Gửi kết quả, tôi viết lại phạm vi tuyên bố cho luận văn.

### Ba điều cần biết khi đọc số

- **Đ9 dùng chu kỳ nhập thay cho thời gian giao hàng.** Đã bỏ phân hệ mua sắm nên
  không đo được lead time nhà cung cấp. Chu kỳ nhập trả lời đúng câu người dùng
  quan tâm: *"hàng còn đủ tới đợt nhập sau không"*. Ngưỡng Đỏ = trung vị chu kỳ,
  Vàng = gấp đôi.
- **Đ9-C lọc mã có ≥ 6 lần nhập.** Mã nhập 1–2 lần trong hai năm là hàng đặt theo
  yêu cầu, không có chu kỳ theo nghĩa vận hành, và đưa vào sẽ kéo trung vị lên cao
  giả tạo. Chọn ngưỡng từ **Đ9-C**, không phải Đ9-B.
- **Đ10 tính cả toa của lượt đồng mắc.** Một lượt vừa có bệnh hô hấp vừa có bệnh
  khác thì toàn bộ thuốc của lượt đó được tính là "hô hấp" — đúng bằng quy ước
  stored procedure đang dùng, để số đo khớp số hệ thống sẽ tính. Tỷ trọng vì vậy
  là **cận trên**. Ghi điều này trong luận văn.

---

## 3. Nhánh B — cắt phạm vi trong mã nguồn

```bash
cd D:\Personnal\LienThong\CDTN\webyte\webyte

git status                      # nên sạch trước khi chạy
python G0_cat_pham_vi.py        # THỬ — không đụng file nào
python G0_cat_pham_vi.py --apply
```

Thêm `--strip-masterdata` nếu muốn gỡ luôn hai cột `minimum_order_quantity` và
`storage_capacity`:

```bash
python G0_cat_pham_vi.py --apply --strip-masterdata
```

### Script làm gì

**Xoá** — `app/procurement/` (3 tệp, 602 dòng lõi) · `api/v1/procurement.py` (637
dòng, 8 endpoint gồm `/generate`, `/{id}/approve`, `/export`) · `test_procurement_api.py`
· `models/procurement_plan.py`.

**Sửa** — `main.py` (import + `include_router`) · `models/__init__.py` ·
`schemas/__init__.py` (6 import + 6 tên) · `schemas/base.py` (cắt khối
Procurement Plan, 1.239 ký tự) · `api/v1/inventory.py` (**cắt vòng lặp ghi ngược
`safety_stock`**) · `api/v1/reports.py` (gỡ loại báo cáo `procurement`) ·
`Sidebar.tsx` (nhãn "Đề xuất nhập kho" → "Cảnh báo tồn kho", icon giỏ hàng →
khiên).

### Bốn thứ script cố ý KHÔNG làm

Mỗi cái đều có lý do, đừng tự thêm vào:

1. **Không xoá trang `SupplyPlanning.tsx`.** Tôi đã liệt kê nó vào danh sách xoá ở
   bản rà soát — **đó là sai, tôi rút lại.** Kiểm tra mã cho thấy trang này là
   giao diện *duy nhất* của dự báo phân cấp (`useHierForecast`), một tính năng
   thuộc Tầng 1 đang giữ. Xoá bây giờ làm mất một tính năng đang chạy mà không
   được gì. Phần "mức an toàn + lead time" trong `supply_planning_service.py` sẽ
   được gọt ở G3.
2. **Không xoá ~550 dòng trình bày báo cáo mua sắm** trong `reports.py`. Script
   gỡ `"procurement"` khỏi danh sách loại hợp lệ nên endpoint từ chối ngay ở cửa
   — không còn logic nào chạy. Khung PDF/Excel giữ lại làm nền cho báo cáo DOI ở
   G5; xoá bây giờ thì G5 phải viết lại từ đầu.
3. **Không đụng `ai_engine/supply_demand_calculator.generate_procurement_suggestion`.**
   Đã kiểm: `ai_engine/forecasting_service.py` không được endpoint nào gọi. Mã
   chết trong nhánh cũ mà G2 sẽ thay toàn bộ.
4. **Không drop bảng `procurement_plans`** trong cơ sở dữ liệu. Gỡ model là đủ để
   không còn mã nào đọc/ghi. Giữ bảng tới khi bảo vệ xong, phòng khi cần đối chiếu.

### Kiểm tra sau khi chạy

```bash
cd backend && uvicorn app.main:app --reload    # phải khởi động sạch
# mở http://127.0.0.1:8000/docs                → không còn nhóm "procurement"
cd ../frontend && npm run build                # build phải xanh
pytest backend/app -q                          # chạy được
git diff --stat                                # xem lại trước khi commit
```

Script tự quét lại dấu vết còn sót sau khi `--apply` và in ra từng dòng.

### Nếu một phép sửa báo "KHÔNG KHỚP"

Script khớp chính xác từng ký tự và **bỏ qua** thay vì đoán, nên không làm hỏng
gì. Sửa tay theo bảng dưới rồi chạy lại:

| Mục | Sửa tay thế nào |
|---|---|
| `main.py` import | Xoá `procurement, ` khỏi dòng `from app.api.v1 import …` |
| `main.py` router | Xoá dòng `app.include_router(procurement.router, …)` |
| `models/__init__.py` | Xoá dòng import `ProcurementPlan` và mục `"ProcurementPlan",` trong `__all__` |
| `schemas/__init__.py` | Xoá 6 tên `Procurement*` ở cả khối import lẫn `__all__` |
| `schemas/base.py` | Xoá từ `# ── Procurement Plan schemas` tới ngay trước `# ── Dashboard schemas` |
| `inventory.py` | Xoá bốn dòng tính `calculated_safety` và dòng `inv.safety_stock = calculated_safety`; thay bằng `skipped += 1` và `continue` |
| `reports.py` | Xoá `"procurement",` khỏi `SUPPORTED_TYPES` |
| `Sidebar.tsx` | Đổi `ShoppingCart` → `ShieldAlert` (import và mục menu), nhãn → `'Cảnh báo tồn kho'` |

### Quay lại nếu cần

```bash
git checkout -- .          # chưa commit
git revert <commit>        # đã commit
```

---

## 4. Xong G0 khi nào

Đối chiếu với sáu ô tích của G0 trong lộ trình:

- [ ] Gỡ router trước, xoá tệp sau → script bước 1–2
- [ ] Cắt vòng ghi ngược `safety_stock` → script bước 5
- [ ] Dọn frontend phần mua sắm → script bước 7 *(chỉ Sidebar; SupplyPlanning để G5)*
- [ ] **Đ9** — chu kỳ nhập → có `doi_red_days` và `doi_amber_days`
- [ ] **Đ10** — tỷ trọng hô hấp → qua được cổng chặn ≥ 100 mã
- [ ] Đổi tên bảng `supply_recommendations` → `supply_demand_forecast`

Ô cuối cùng **script không làm** — đổi tên bảng cần migration và nên làm cùng lúc
với việc gọt các cột `buffer_rate` / `suggested_import` ở G3, để chỉ một lần
migration thay vì hai.

**Cổng nghiệm thu G0:** app khởi động sạch, không còn chuỗi `procurement` nào
ngoài `ai_engine`, và hai con số ngưỡng đã ghi vào `system_config`.
