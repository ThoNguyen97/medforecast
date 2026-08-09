#!/bin/bash
# Test các endpoint mới mà không cần authentication

BASE_URL="http://localhost:8000/api/v1"

echo "============================================================"
echo "TEST API - Định mức theo cấp độ"
echo "============================================================"

# Test 1: Lấy tóm tắt tất cả bệnh (nên không cần auth)
echo ""
echo "1️⃣  Test: GET /admin/supply-norms/summary/all-diseases"
echo "Request: curl -X GET \"$BASE_URL/admin/supply-norms/summary/all-diseases\""
echo ""
curl -X GET "$BASE_URL/admin/supply-norms/summary/all-diseases" \
  -H "Accept: application/json" 2>/dev/null | head -200
echo ""
echo ""

# Test 2: Ma trận cho J20
echo "2️⃣  Test: GET /admin/supply-norms/matrix?icd_code=J20"
echo "Request: curl -X GET \"$BASE_URL/admin/supply-norms/matrix?icd_code=J20\""
echo ""
curl -X GET "$BASE_URL/admin/supply-norms/matrix?icd_code=J20" \
  -H "Accept: application/json" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -100
echo ""
echo ""

# Test 3: Lọc định mức nhẹ
echo "3️⃣  Test: GET /admin/supply-norms/by-severity?severity=mild"
echo "Request: curl -X GET \"$BASE_URL/admin/supply-norms/by-severity?severity=mild\""
echo ""
curl -X GET "$BASE_URL/admin/supply-norms/by-severity?severity=mild" \
  -H "Accept: application/json" 2>/dev/null | python3 -m json.tool 2>/dev/null | head -100
echo ""
echo ""

echo "============================================================"
echo "✅ Test hoàn thành!"
echo "============================================================"
