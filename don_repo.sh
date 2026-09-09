#!/usr/bin/env bash
# =============================================================================
# DỌN 4 FILE TẠM KHỎI REPO — và xoá luôn khỏi lịch sử
#
#   LICH_SU_GIT_CU.txt    danh sách commit của repo cũ (không còn liên quan)
#   git_lam_lai.sh        script dùng một lần, đã chạy xong
#   commit_medforecast.sh script dùng một lần, không còn dùng
#   env_stagging.txt      ghi chú cấu hình, thuộc về .env.example / DEPLOY.md
#
# Bốn file này là công cụ dựng repo, không phải mã nguồn của phần mềm. Chúng
# không thuộc về repo dự án bất kể lý do gì.
#
# CHẠY Ở ĐÂU:
#     cd "D:/Personnal/LienThong/CDTN/webyte/webyte"
#     bash don_repo.sh
#
# VÌ SAO PHẢI --amend CHỨ KHÔNG CHỈ `git rm` RỒI COMMIT MỚI
# `git rm` + commit mới chỉ làm file biến mất ở bản mới nhất. Nó VẪN NẰM
# TRONG LỊCH SỬ và ai cũng mở được bằng:
#       git show a828a95:LICH_SU_GIT_CU.txt
# GitHub cũng vẫn xem được qua tab History. Muốn mất thật thì phải viết lại
# commit đã chứa nó. Cả bốn file đều nằm gọn trong commit cuối ("chore: dong
# goi Docker...") nên chỉ cần --amend commit đó, không phải rebase cả nhánh.
#
# File trên đĩa KHÔNG bị xoá — chỉ gỡ khỏi git. Muốn xoá hẳn thì tự xoá tay.
# =============================================================================
set -e

if [ ! -d backend ] || [ ! -d sql_his ]; then
    echo "DỪNG: không phải thư mục gốc repo MedForecast. Đang ở: $(pwd)"
    exit 1
fi

CAN_XOA="LICH_SU_GIT_CU.txt git_lam_lai.sh commit_medforecast.sh env_stagging.txt"

echo "=== Trạng thái hiện tại ==="
git log --oneline -1
echo

# --- 1. Gỡ khỏi git, giữ nguyên file trên đĩa --------------------------------
for f in $CAN_XOA; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        git rm --cached -q "$f"
        echo "→ đã gỡ khỏi git: $f  (file trên đĩa vẫn còn)"
    fi
done

# --- 2. Chặn quay lại lần sau ------------------------------------------------
# Không thêm thì lần `git add -A` sau lại kéo chúng vào.
if ! grep -q "^LICH_SU_GIT_CU.txt$" .gitignore 2>/dev/null; then
cat >> .gitignore <<'EOF'

# Script dựng repo dùng một lần — không thuộc mã nguồn dự án
LICH_SU_GIT_CU.txt
git_lam_lai.sh
commit_medforecast.sh
env_stagging.txt
EOF
    echo "→ đã thêm 4 tên file vào .gitignore"
fi
git add .gitignore

# --- 3. Viết lại commit cuối -------------------------------------------------
# Giữ nguyên nội dung thông điệp commit cũ.
git commit -q --amend --no-edit
echo "→ đã viết lại commit cuối"

# --- 4. Kiểm chứng -----------------------------------------------------------
echo
echo "=== Kiểm lại ==="
for f in $CAN_XOA; do
    if git log --all --oneline -- "$f" 2>/dev/null | grep -q .; then
        echo "  ⚠ $f VẪN còn trong lịch sử"
    else
        echo "  ✓ $f đã sạch khỏi lịch sử"
    fi
done
echo
echo "Số file trong repo : $(git ls-files | wc -l)"
git log --oneline
echo
echo "Bước cuối — ghi đè bản trên GitHub (bắt buộc, vì lịch sử đã đổi):"
echo "    git push --force-with-lease origin main"
echo
echo "Sau khi push, mở lại GitHub và bấm vào tab History của thư mục gốc để"
echo "tự xác nhận bốn file kia không còn ở bất kỳ commit nào."
