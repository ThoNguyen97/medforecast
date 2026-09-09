#!/usr/bin/env bash
# ============================================================================
# bo_ma_chet.sh — Đóng gói mã chết vào _archive/  (MedForecast AI, 09/09/2026)
#
# CHẠY TỪ THƯ MỤC GỐC REPO (nơi có backend/ và frontend/).
#
#   bash bo_ma_chet.sh --thu      # chạy thử, chỉ in ra, KHÔNG di chuyển gì
#   bash bo_ma_chet.sh --that     # di chuyển thật (dùng git mv nếu có git)
#
# KHÔNG XOÁ file nào — chỉ di chuyển. Trừ .env.saoluu_* thì báo để bạn tự xoá.
#
# ⚠ SAU KHI CHẠY còn 3 việc PHẢI làm bằng tay, script không tự làm được:
#    1. app/ai_engine/__init__.py — xoá 3 dòng import 48-50
#       (xgboost_forecaster, prophet_forecaster, ensemble_forecaster)
#    2. connectors.py:231-233 — đổi SQL mặc định sang case_sta.sql /
#       inventory_sta.sql; sync_config_service.py:47-48 — bỏ profile "mssql"
#    3. app/main.py — bỏ include router nào trỏ vào file đã đóng gói,
#       và bỏ import celery_app nếu có
#    Rồi chạy:  python -m compileall backend/app   và   npm run build
# ============================================================================
set -uo pipefail

CHE_DO="${1:---thu}"
GOC="$(pwd)"
KHO="_archive"

if [[ ! -d backend || ! -d frontend ]]; then
  echo "✗ Không thấy backend/ và frontend/. Hãy chạy từ thư mục gốc repo."; exit 1
fi

CO_GIT=0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && CO_GIT=1

dem_ok=0; dem_thieu=0

chuyen() {  # chuyen <đường dẫn nguồn> <thư mục đích trong _archive>
  local src="$1" dest_dir="$KHO/$2"
  if [[ ! -e "$src" ]]; then
    printf '  · bỏ qua (không có): %s\n' "$src"; ((dem_thieu++)); return
  fi
  if [[ "$CHE_DO" == "--thu" ]]; then
    printf '  → %s\n' "$src"; ((dem_ok++)); return
  fi
  mkdir -p "$dest_dir/$(dirname "$src")"
  if [[ $CO_GIT -eq 1 ]] && git ls-files --error-unmatch "$src" >/dev/null 2>&1; then
    git mv "$src" "$dest_dir/$src" 2>/dev/null || mv "$src" "$dest_dir/$src"
  else
    mv "$src" "$dest_dir/$src"
  fi
  printf '  ✓ %s\n' "$src"; ((dem_ok++))
}

echo "=== CHẾ ĐỘ: $CHE_DO ==="; echo

# ---------------------------------------------------------------- 1
echo "[1/6] ai_engine_cu — nhánh AI cũ chưa từng chạy trong sản phẩm"
for f in forecasting_pipeline ensemble_forecaster xgboost_forecaster \
         prophet_forecaster model_evaluation feature_engineering \
         forecasting_service csv_data_processor supply_demand_calculator \
         weather_forecast correlation_analyzer; do
  chuyen "backend/app/ai_engine/${f}.py" ai_engine_cu
done
for f in test_conversion_module test_ensemble_forecaster test_ensemble_integration \
         test_forecasting_pipeline test_forecasting_pipeline_integration \
         test_prophet_forecaster test_xgboost_forecaster; do
  chuyen "backend/app/ai_engine/${f}.py" ai_engine_cu
done
chuyen "backend/app/ai_engine/models/saved_models" ai_engine_cu
echo

# ---------------------------------------------------------------- 2
echo "[2/6] dich_vu_chet — service/task không có nơi gọi"
chuyen "backend/app/services/forecast_service.py"        dich_vu_chet
chuyen "backend/app/tasks/forecast_tasks.py"             dich_vu_chet
chuyen "backend/app/celery_app.py"                       dich_vu_chet
chuyen "backend/app/services/data_collector_service.py"  dich_vu_chet
chuyen "backend/app/core/exceptions.py"                  dich_vu_chet
chuyen "backend/app/forecasting/ai_forecaster.py"        dich_vu_chet
chuyen "backend/app/services/test_alert_service.py"      dich_vu_chet
chuyen "backend/app/services/test_forecast_service.py"   dich_vu_chet
chuyen "backend/app/api/v1/test_alerts_api.py"           dich_vu_chet
chuyen "backend/app/api/v1/test_supply_requirements_api.py" dich_vu_chet
echo

# ---------------------------------------------------------------- 3
echo "[3/6] sql_schema_cu — SQL trỏ vào schema HIS không tồn tại"
echo "      ⚠ PHẢI đổi mặc định trong connectors.py:231-233 CÙNG LÚC!"
for f in case_mssql case_sqlite inventory_mssql inventory_sqlite; do
  chuyen "backend/app/data_pipeline/sql/${f}.sql" sql_schema_cu
done
echo

# ---------------------------------------------------------------- 4
echo "[4/6] frontend_chet — component/hook 0 tham chiếu"
echo "      ⚠ dashboardV2.ts KHÔNG đóng gói ở bước này — còn chứa bộ nhãn"
echo "        4 mức và GreyReason mà dss_alerts.py:63 tham chiếu (xem Tuần 5)."
chuyen "frontend/src/pages/SupplyNormPage.tsx"                    frontend_chet
chuyen "frontend/src/components/SupplyNormMatrix.tsx"             frontend_chet
chuyen "frontend/src/hooks/useAlerts.ts"                          frontend_chet
chuyen "frontend/src/services/alertsService.ts"                   frontend_chet
chuyen "frontend/src/hooks/useEpidemiology.ts"                    frontend_chet
chuyen "frontend/src/components/alerts"                           frontend_chet
chuyen "frontend/src/components/epidemiology"                     frontend_chet
chuyen "frontend/src/components/dashboard/CriticalAlertsTable.tsx" frontend_chet
chuyen "frontend/src/components/reports/ExportButton.tsx"         frontend_chet
chuyen "frontend/src/components/inventory/UpdateStockModal.tsx"   frontend_chet
chuyen "frontend/src/components/inventory/AIInsightPanel.tsx"     frontend_chet
echo

# ---------------------------------------------------------------- 5
echo "[5/6] postgres — hệ quả quyết định 'giữ SQLite'"
chuyen "docker-compose.yml"                         postgres
chuyen "docker-compose.dev.yml"                     postgres
chuyen "MIGRATE_POSTGRES.md"                        postgres
chuyen "backend/scripts/migrate_to_postgres.py"     postgres
echo "      ⚠ Nhớ sửa mục Docker/Postgres trong README.md bằng tay."
echo

# ---------------------------------------------------------------- 6
echo "[6/6] tap_nhap — rác ở gốc repo"
for f in .DS_Store commit_medforecast.sh don_repo.sh git_lam_lai.sh \
         G0_cat_pham_vi.py env_stagging.txt package.json package-lock.json; do
  chuyen "$f" tap_nhap
done
for f in kq_2022.csv kq_2023.csv kq_toanbo.csv test_api_simple.sh \
         seed_respiratory_diseases.py; do
  chuyen "backend/$f" tap_nhap
done
echo

# ---------------------------------------------------------------- README
if [[ "$CHE_DO" == "--that" && -d "$KHO" ]]; then
  cat > "$KHO/README.md" <<'HET'
# _archive — mã đã loại khỏi phạm vi sản phẩm

Đóng gói ngày 09/09/2026, trong đợt tái định hình MedForecast AI.
**Không xoá file nào** — mọi thứ ở đây vẫn tra cứu được khi viết báo cáo.

## Tiêu chí xác định mã chết
Grep tham chiếu ngược **có tính bắc cầu**: một file chỉ vào đây khi mọi nơi
gọi nó cũng nằm trong danh sách này. Đã loại trừ file `test_*` khỏi phép đếm.

## Các nhóm

- **ai_engine_cu/** — nhánh XGBoost/Prophet/LSTM. Điểm vào duy nhất là một
  Celery task không nơi nào gọi, và docker-compose không có worker nào; tức
  nhánh này **chưa từng chạy trong sản phẩm**. `ensemble_forecaster.py:89`
  cho thấy LSTM chưa bao giờ được cài đặt (`self.lstm_model = None`, dòng 280
  lấy trung bình XGBoost và Prophet rồi gán làm "dự đoán LSTM"). Kèm 8 file
  `.pkl` là artifact của nhánh này — trong đó 3 file thuộc phân hệ cũ
  (dengue_fever, seasonal_flu, respiratory_disease), không phải nhóm ICD hô hấp.
  *Dùng lại khi:* làm đối chứng XGBoost ở Tuần 4 — nhưng phải huấn luyện lại
  theo giao thức walk-forward, **không dùng lại MonthlyForecaster** (rò rỉ mục tiêu).

- **dich_vu_chet/** — service và Celery task 0 tham chiếu, cộng 4 file test
  nằm lẫn trong package sản phẩm.

- **sql_schema_cu/** — 4 file SQL truy vấn `KhamBenh`, `ChanDoan`, `BenhNhan`,
  `SuDungVatTu`, `VatTu`, `TonKho`: schema giả định thời chưa nối HIS thật.
  HIS thật dùng `TT_TIEPNHAN`, `TT_NGOAITRU_KHAMBENH`, `TM_ICD`, `TT_DUOC_TONKHO`.

- **frontend_chet/** — trang, hook và component 0 tham chiếu.
  `SupplyNormPage.tsx` còn không có `<Route>` nào trong `App.tsx`.

- **postgres/** — hệ quả quyết định giữ SQLite làm CSDL duy nhất. Để lại trong
  repo sẽ mâu thuẫn với kiến trúc đã chốt.

- **tap_nhap/** — script tạp, CSV kết quả tạm, file lạc chỗ ở gốc repo.

## Khôi phục
`git mv _archive/<nhóm>/<đường dẫn> <đường dẫn>` rồi hoàn lại 3 sửa đổi thủ
công ghi ở đầu `bo_ma_chet.sh`.
HET
  echo "✓ Đã ghi $KHO/README.md"
fi

echo
echo "════════════════════════════════════════════════════════"
printf "Xử lý: %d mục · Không tìm thấy: %d mục\n" "$dem_ok" "$dem_thieu"
if [[ "$CHE_DO" == "--thu" ]]; then
  echo "Đây là CHẠY THỬ — chưa di chuyển gì. Chạy lại với --that để thực hiện."
else
  echo "XONG. Giờ làm 3 việc thủ công ghi ở đầu file, rồi:"
  echo "   python -m compileall backend/app"
  echo "   cd frontend && npm run build"
fi
echo "════════════════════════════════════════════════════════"

# ---------------------------------------------------------------- cảnh báo
echo
if compgen -G "backend/.env.saoluu_*" > /dev/null; then
  echo "🔴 KHẨN: backend/.env.saoluu_* chứa mật khẩu HIS và .gitignore KHÔNG chặn nó."
  echo "   Chạy ngay:  echo '.env*' >> .gitignore && rm backend/.env.saoluu_*"
fi
