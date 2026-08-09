/**
 * Master data: 63 tỉnh/thành phố trực thuộc trung ương + đầy đủ quận/huyện/thị xã/thành
 * phố trực thuộc tỉnh của Việt Nam (tính tới 2024).
 *
 * Dùng cho dropdown cascade ở Module Bệnh / Thời tiết.
 */

// 5 thành phố trực thuộc trung ương — luôn xếp lên đầu dropdown
const MAJOR_CITIES = ['TP. Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Hải Phòng', 'Cần Thơ'];

/**
 * Chuẩn hoá tên tỉnh/thành về dạng dùng trong master VN_REGIONS.
 *
 * Data thật (data_HM) dùng tên đầy đủ "Thành phố Hồ Chí Minh", "Thành phố Hà Nội"...
 * còn master dùng dạng ngắn "TP. Hồ Chí Minh", "Hà Nội". Hàm này map 2 biến thể
 * về 1 key chung để dropdown + cascade phường/xã khớp nhau.
 */
const PROVINCE_ALIASES: Record<string, string> = {
  'Thành phố Hồ Chí Minh': 'TP. Hồ Chí Minh',
  'Thành Phố Hồ Chí Minh': 'TP. Hồ Chí Minh',
  'Hồ Chí Minh': 'TP. Hồ Chí Minh',
  'TP Hồ Chí Minh': 'TP. Hồ Chí Minh',
  'TPHCM': 'TP. Hồ Chí Minh',
  'Thành phố Hà Nội': 'Hà Nội',
  'Thành Phố Hà Nội': 'Hà Nội',
  'Thành phố Đà Nẵng': 'Đà Nẵng',
  'Thành phố Hải Phòng': 'Hải Phòng',
  'Thành phố Cần Thơ': 'Cần Thơ',
};

export function normalizeProvinceName(name: string): string {
  if (!name) return name;
  const trimmed = name.trim();
  return PROVINCE_ALIASES[trimmed] ?? trimmed;
}

// Map tỉnh/thành → list đơn vị hành chính cấp huyện
export const VN_REGIONS: Record<string, string[]> = {
  // ── 5 thành phố trực thuộc trung ương ──────────────────────────────
  'TP. Hồ Chí Minh': [
    'Quận 1', 'Quận 3', 'Quận 4', 'Quận 5', 'Quận 6', 'Quận 7', 'Quận 8',
    'Quận 10', 'Quận 11', 'Quận 12',
    'Quận Bình Tân', 'Quận Bình Thạnh', 'Quận Gò Vấp', 'Quận Phú Nhuận',
    'Quận Tân Bình', 'Quận Tân Phú',
    'Thành phố Thủ Đức',
    'Huyện Bình Chánh', 'Huyện Cần Giờ', 'Huyện Củ Chi', 'Huyện Hóc Môn', 'Huyện Nhà Bè',
  ],
  'Hà Nội': [
    'Quận Ba Đình', 'Quận Hoàn Kiếm', 'Quận Tây Hồ', 'Quận Long Biên',
    'Quận Cầu Giấy', 'Quận Đống Đa', 'Quận Hai Bà Trưng', 'Quận Hoàng Mai',
    'Quận Thanh Xuân', 'Quận Hà Đông', 'Quận Bắc Từ Liêm', 'Quận Nam Từ Liêm',
    'Thị xã Sơn Tây',
    'Huyện Ba Vì', 'Huyện Chương Mỹ', 'Huyện Đan Phượng', 'Huyện Đông Anh',
    'Huyện Gia Lâm', 'Huyện Hoài Đức', 'Huyện Mê Linh', 'Huyện Mỹ Đức',
    'Huyện Phú Xuyên', 'Huyện Phúc Thọ', 'Huyện Quốc Oai', 'Huyện Sóc Sơn',
    'Huyện Thạch Thất', 'Huyện Thanh Oai', 'Huyện Thanh Trì',
    'Huyện Thường Tín', 'Huyện Ứng Hòa',
  ],
  'Đà Nẵng': [
    'Quận Hải Châu', 'Quận Thanh Khê', 'Quận Sơn Trà', 'Quận Ngũ Hành Sơn',
    'Quận Liên Chiểu', 'Quận Cẩm Lệ',
    'Huyện Hòa Vang', 'Huyện Hoàng Sa',
  ],
  'Hải Phòng': [
    'Quận Hồng Bàng', 'Quận Lê Chân', 'Quận Ngô Quyền', 'Quận Kiến An',
    'Quận Hải An', 'Quận Đồ Sơn', 'Quận Dương Kinh',
    'Huyện An Dương', 'Huyện An Lão', 'Huyện Bạch Long Vĩ', 'Huyện Cát Hải',
    'Huyện Kiến Thụy', 'Huyện Thủy Nguyên', 'Huyện Tiên Lãng', 'Huyện Vĩnh Bảo',
  ],
  'Cần Thơ': [
    'Quận Ninh Kiều', 'Quận Bình Thủy', 'Quận Cái Răng', 'Quận Ô Môn',
    'Quận Thốt Nốt',
    'Huyện Cờ Đỏ', 'Huyện Phong Điền', 'Huyện Thới Lai', 'Huyện Vĩnh Thạnh',
  ],

  // ── 58 tỉnh còn lại ───────────────────────────────────────────────
  'An Giang': [
    'Thành phố Long Xuyên', 'Thành phố Châu Đốc',
    'Thị xã Tân Châu',
    'Huyện An Phú', 'Huyện Châu Phú', 'Huyện Châu Thành', 'Huyện Chợ Mới',
    'Huyện Phú Tân', 'Huyện Thoại Sơn', 'Huyện Tịnh Biên', 'Huyện Tri Tôn',
  ],
  'Bà Rịa - Vũng Tàu': [
    'Thành phố Vũng Tàu', 'Thành phố Bà Rịa',
    'Thị xã Phú Mỹ',
    'Huyện Châu Đức', 'Huyện Côn Đảo', 'Huyện Đất Đỏ',
    'Huyện Long Điền', 'Huyện Xuyên Mộc',
  ],
  'Bạc Liêu': [
    'Thành phố Bạc Liêu',
    'Thị xã Giá Rai',
    'Huyện Đông Hải', 'Huyện Hòa Bình', 'Huyện Hồng Dân',
    'Huyện Phước Long', 'Huyện Vĩnh Lợi',
  ],
  'Bắc Giang': [
    'Thành phố Bắc Giang',
    'Huyện Hiệp Hòa', 'Huyện Lạng Giang', 'Huyện Lục Nam', 'Huyện Lục Ngạn',
    'Huyện Sơn Động', 'Huyện Tân Yên', 'Huyện Việt Yên', 'Huyện Yên Dũng',
    'Huyện Yên Thế',
  ],
  'Bắc Kạn': [
    'Thành phố Bắc Kạn',
    'Huyện Ba Bể', 'Huyện Bạch Thông', 'Huyện Chợ Đồn', 'Huyện Chợ Mới',
    'Huyện Na Rì', 'Huyện Ngân Sơn', 'Huyện Pác Nặm',
  ],
  'Bắc Ninh': [
    'Thành phố Bắc Ninh', 'Thành phố Từ Sơn',
    'Huyện Gia Bình', 'Huyện Lương Tài', 'Huyện Quế Võ',
    'Huyện Thuận Thành', 'Huyện Tiên Du', 'Huyện Yên Phong',
  ],
  'Bến Tre': [
    'Thành phố Bến Tre',
    'Huyện Ba Tri', 'Huyện Bình Đại', 'Huyện Châu Thành',
    'Huyện Chợ Lách', 'Huyện Giồng Trôm', 'Huyện Mỏ Cày Bắc',
    'Huyện Mỏ Cày Nam', 'Huyện Thạnh Phú',
  ],
  'Bình Dương': [
    'Thành phố Thủ Dầu Một', 'Thành phố Dĩ An', 'Thành phố Thuận An',
    'Thành phố Tân Uyên',
    'Thị xã Bến Cát',
    'Huyện Bàu Bàng', 'Huyện Dầu Tiếng', 'Huyện Phú Giáo', 'Huyện Bắc Tân Uyên',
  ],
  'Bình Định': [
    'Thành phố Quy Nhơn',
    'Thị xã An Nhơn', 'Thị xã Hoài Nhơn',
    'Huyện An Lão', 'Huyện Hoài Ân', 'Huyện Phù Cát', 'Huyện Phù Mỹ',
    'Huyện Tây Sơn', 'Huyện Tuy Phước', 'Huyện Vân Canh', 'Huyện Vĩnh Thạnh',
  ],
  'Bình Phước': [
    'Thành phố Đồng Xoài',
    'Thị xã Bình Long', 'Thị xã Phước Long', 'Thị xã Chơn Thành',
    'Huyện Bù Đăng', 'Huyện Bù Đốp', 'Huyện Bù Gia Mập',
    'Huyện Đồng Phú', 'Huyện Hớn Quản', 'Huyện Lộc Ninh', 'Huyện Phú Riềng',
  ],
  'Bình Thuận': [
    'Thành phố Phan Thiết',
    'Thị xã La Gi',
    'Huyện Bắc Bình', 'Huyện Đức Linh', 'Huyện Hàm Tân',
    'Huyện Hàm Thuận Bắc', 'Huyện Hàm Thuận Nam', 'Huyện Phú Quý',
    'Huyện Tánh Linh', 'Huyện Tuy Phong',
  ],
  'Cà Mau': [
    'Thành phố Cà Mau',
    'Huyện Cái Nước', 'Huyện Đầm Dơi', 'Huyện Năm Căn', 'Huyện Ngọc Hiển',
    'Huyện Phú Tân', 'Huyện Thới Bình', 'Huyện Trần Văn Thời', 'Huyện U Minh',
  ],
  'Cao Bằng': [
    'Thành phố Cao Bằng',
    'Huyện Bảo Lạc', 'Huyện Bảo Lâm', 'Huyện Hạ Lang', 'Huyện Hà Quảng',
    'Huyện Hòa An', 'Huyện Nguyên Bình', 'Huyện Quảng Hòa',
    'Huyện Thạch An', 'Huyện Trùng Khánh',
  ],
  'Đắk Lắk': [
    'Thành phố Buôn Ma Thuột',
    'Thị xã Buôn Hồ',
    'Huyện Buôn Đôn', 'Huyện Cư Kuin', 'Huyện Cư M\'gar',
    'Huyện Ea H\'leo', 'Huyện Ea Kar', 'Huyện Ea Súp',
    'Huyện Krông Ana', 'Huyện Krông Bông', 'Huyện Krông Búk',
    'Huyện Krông Năng', 'Huyện Krông Pắc', 'Huyện Lắk', 'Huyện M\'Đrắk',
  ],
  'Đắk Nông': [
    'Thành phố Gia Nghĩa',
    'Huyện Cư Jút', 'Huyện Đắk Glong', 'Huyện Đắk Mil', 'Huyện Đắk R\'Lấp',
    'Huyện Đắk Song', 'Huyện Krông Nô', 'Huyện Tuy Đức',
  ],
  'Điện Biên': [
    'Thành phố Điện Biên Phủ',
    'Thị xã Mường Lay',
    'Huyện Điện Biên', 'Huyện Điện Biên Đông', 'Huyện Mường Ảng',
    'Huyện Mường Chà', 'Huyện Mường Nhé', 'Huyện Nậm Pồ',
    'Huyện Tủa Chùa', 'Huyện Tuần Giáo',
  ],
  'Đồng Nai': [
    'Thành phố Biên Hòa', 'Thành phố Long Khánh',
    'Huyện Cẩm Mỹ', 'Huyện Định Quán', 'Huyện Long Thành', 'Huyện Nhơn Trạch',
    'Huyện Tân Phú', 'Huyện Thống Nhất', 'Huyện Trảng Bom',
    'Huyện Vĩnh Cửu', 'Huyện Xuân Lộc',
  ],
  'Đồng Tháp': [
    'Thành phố Cao Lãnh', 'Thành phố Sa Đéc', 'Thành phố Hồng Ngự',
    'Huyện Cao Lãnh', 'Huyện Châu Thành', 'Huyện Hồng Ngự',
    'Huyện Lai Vung', 'Huyện Lấp Vò', 'Huyện Tam Nông',
    'Huyện Tân Hồng', 'Huyện Thanh Bình', 'Huyện Tháp Mười',
  ],
  'Gia Lai': [
    'Thành phố Pleiku',
    'Thị xã An Khê', 'Thị xã Ayun Pa',
    'Huyện Chư Păh', 'Huyện Chư Prông', 'Huyện Chư Pưh', 'Huyện Chư Sê',
    'Huyện Đắk Đoa', 'Huyện Đắk Pơ', 'Huyện Đức Cơ', 'Huyện Ia Grai',
    'Huyện Ia Pa', 'Huyện K\'Bang', 'Huyện Kông Chro',
    'Huyện Krông Pa', 'Huyện Mang Yang', 'Huyện Phú Thiện',
  ],
  'Hà Giang': [
    'Thành phố Hà Giang',
    'Huyện Bắc Mê', 'Huyện Bắc Quang', 'Huyện Đồng Văn', 'Huyện Hoàng Su Phì',
    'Huyện Mèo Vạc', 'Huyện Quản Bạ', 'Huyện Quang Bình',
    'Huyện Vị Xuyên', 'Huyện Xín Mần', 'Huyện Yên Minh',
  ],
  'Hà Nam': [
    'Thành phố Phủ Lý',
    'Thị xã Duy Tiên',
    'Huyện Bình Lục', 'Huyện Kim Bảng', 'Huyện Lý Nhân', 'Huyện Thanh Liêm',
  ],
  'Hà Tĩnh': [
    'Thành phố Hà Tĩnh',
    'Thị xã Hồng Lĩnh', 'Thị xã Kỳ Anh',
    'Huyện Cẩm Xuyên', 'Huyện Can Lộc', 'Huyện Đức Thọ', 'Huyện Hương Khê',
    'Huyện Hương Sơn', 'Huyện Kỳ Anh', 'Huyện Lộc Hà', 'Huyện Nghi Xuân',
    'Huyện Thạch Hà', 'Huyện Vũ Quang',
  ],
  'Hải Dương': [
    'Thành phố Hải Dương', 'Thành phố Chí Linh',
    'Thị xã Kinh Môn',
    'Huyện Bình Giang', 'Huyện Cẩm Giàng', 'Huyện Gia Lộc', 'Huyện Kim Thành',
    'Huyện Nam Sách', 'Huyện Ninh Giang', 'Huyện Thanh Hà',
    'Huyện Thanh Miện', 'Huyện Tứ Kỳ',
  ],
  'Hậu Giang': [
    'Thành phố Vị Thanh', 'Thành phố Ngã Bảy',
    'Thị xã Long Mỹ',
    'Huyện Châu Thành', 'Huyện Châu Thành A', 'Huyện Long Mỹ',
    'Huyện Phụng Hiệp', 'Huyện Vị Thủy',
  ],
  'Hòa Bình': [
    'Thành phố Hòa Bình',
    'Huyện Cao Phong', 'Huyện Đà Bắc', 'Huyện Kim Bôi', 'Huyện Lạc Sơn',
    'Huyện Lạc Thủy', 'Huyện Lương Sơn', 'Huyện Mai Châu',
    'Huyện Tân Lạc', 'Huyện Yên Thủy',
  ],
  'Hưng Yên': [
    'Thành phố Hưng Yên',
    'Thị xã Mỹ Hào',
    'Huyện Ân Thi', 'Huyện Khoái Châu', 'Huyện Kim Động',
    'Huyện Phù Cừ', 'Huyện Tiên Lữ', 'Huyện Văn Giang',
    'Huyện Văn Lâm', 'Huyện Yên Mỹ',
  ],
  'Khánh Hòa': [
    'Thành phố Nha Trang', 'Thành phố Cam Ranh',
    'Thị xã Ninh Hòa',
    'Huyện Cam Lâm', 'Huyện Diên Khánh', 'Huyện Khánh Sơn',
    'Huyện Khánh Vĩnh', 'Huyện Trường Sa', 'Huyện Vạn Ninh',
  ],
  'Kiên Giang': [
    'Thành phố Rạch Giá', 'Thành phố Hà Tiên', 'Thành phố Phú Quốc',
    'Huyện An Biên', 'Huyện An Minh', 'Huyện Châu Thành', 'Huyện Giang Thành',
    'Huyện Giồng Riềng', 'Huyện Gò Quao', 'Huyện Hòn Đất',
    'Huyện Kiên Hải', 'Huyện Kiên Lương', 'Huyện Tân Hiệp',
    'Huyện U Minh Thượng', 'Huyện Vĩnh Thuận',
  ],
  'Kon Tum': [
    'Thành phố Kon Tum',
    'Huyện Đắk Glei', 'Huyện Đắk Hà', 'Huyện Đắk Tô', 'Huyện Ia H\'Drai',
    'Huyện Kon Plông', 'Huyện Kon Rẫy', 'Huyện Ngọc Hồi',
    'Huyện Sa Thầy', 'Huyện Tu Mơ Rông',
  ],
  'Lai Châu': [
    'Thành phố Lai Châu',
    'Huyện Mường Tè', 'Huyện Nậm Nhùn', 'Huyện Phong Thổ', 'Huyện Sìn Hồ',
    'Huyện Tam Đường', 'Huyện Tân Uyên', 'Huyện Than Uyên',
  ],
  'Lạng Sơn': [
    'Thành phố Lạng Sơn',
    'Huyện Bắc Sơn', 'Huyện Bình Gia', 'Huyện Cao Lộc', 'Huyện Chi Lăng',
    'Huyện Đình Lập', 'Huyện Hữu Lũng', 'Huyện Lộc Bình', 'Huyện Tràng Định',
    'Huyện Văn Lãng', 'Huyện Văn Quan',
  ],
  'Lào Cai': [
    'Thành phố Lào Cai',
    'Thị xã Sa Pa',
    'Huyện Bắc Hà', 'Huyện Bảo Thắng', 'Huyện Bảo Yên', 'Huyện Bát Xát',
    'Huyện Mường Khương', 'Huyện Si Ma Cai', 'Huyện Văn Bàn',
  ],
  'Lâm Đồng': [
    'Thành phố Đà Lạt', 'Thành phố Bảo Lộc',
    'Huyện Bảo Lâm', 'Huyện Cát Tiên', 'Huyện Đạ Huoai', 'Huyện Đạ Tẻh',
    'Huyện Đam Rông', 'Huyện Di Linh', 'Huyện Đơn Dương',
    'Huyện Đức Trọng', 'Huyện Lạc Dương', 'Huyện Lâm Hà',
  ],
  'Long An': [
    'Thành phố Tân An',
    'Thị xã Kiến Tường',
    'Huyện Bến Lức', 'Huyện Cần Đước', 'Huyện Cần Giuộc', 'Huyện Châu Thành',
    'Huyện Đức Hòa', 'Huyện Đức Huệ', 'Huyện Mộc Hóa', 'Huyện Tân Hưng',
    'Huyện Tân Thạnh', 'Huyện Tân Trụ', 'Huyện Thạnh Hóa',
    'Huyện Thủ Thừa', 'Huyện Vĩnh Hưng',
  ],
  'Nam Định': [
    'Thành phố Nam Định',
    'Huyện Giao Thủy', 'Huyện Hải Hậu', 'Huyện Mỹ Lộc', 'Huyện Nam Trực',
    'Huyện Nghĩa Hưng', 'Huyện Trực Ninh', 'Huyện Vụ Bản', 'Huyện Xuân Trường',
    'Huyện Ý Yên',
  ],
  'Nghệ An': [
    'Thành phố Vinh',
    'Thị xã Cửa Lò', 'Thị xã Hoàng Mai', 'Thị xã Thái Hòa',
    'Huyện Anh Sơn', 'Huyện Con Cuông', 'Huyện Diễn Châu', 'Huyện Đô Lương',
    'Huyện Hưng Nguyên', 'Huyện Kỳ Sơn', 'Huyện Nam Đàn', 'Huyện Nghi Lộc',
    'Huyện Nghĩa Đàn', 'Huyện Quế Phong', 'Huyện Quỳ Châu',
    'Huyện Quỳ Hợp', 'Huyện Quỳnh Lưu', 'Huyện Tân Kỳ',
    'Huyện Thanh Chương', 'Huyện Tương Dương', 'Huyện Yên Thành',
  ],
  'Ninh Bình': [
    'Thành phố Ninh Bình', 'Thành phố Tam Điệp',
    'Huyện Gia Viễn', 'Huyện Hoa Lư', 'Huyện Kim Sơn',
    'Huyện Nho Quan', 'Huyện Yên Khánh', 'Huyện Yên Mô',
  ],
  'Ninh Thuận': [
    'Thành phố Phan Rang - Tháp Chàm',
    'Huyện Bác Ái', 'Huyện Ninh Hải', 'Huyện Ninh Phước',
    'Huyện Ninh Sơn', 'Huyện Thuận Bắc', 'Huyện Thuận Nam',
  ],
  'Phú Thọ': [
    'Thành phố Việt Trì',
    'Thị xã Phú Thọ',
    'Huyện Cẩm Khê', 'Huyện Đoan Hùng', 'Huyện Hạ Hòa', 'Huyện Lâm Thao',
    'Huyện Phù Ninh', 'Huyện Tam Nông', 'Huyện Tân Sơn', 'Huyện Thanh Ba',
    'Huyện Thanh Sơn', 'Huyện Thanh Thủy', 'Huyện Yên Lập',
  ],
  'Phú Yên': [
    'Thành phố Tuy Hòa',
    'Thị xã Đông Hòa', 'Thị xã Sông Cầu',
    'Huyện Đồng Xuân', 'Huyện Phú Hòa', 'Huyện Sơn Hòa',
    'Huyện Sông Hinh', 'Huyện Tây Hòa', 'Huyện Tuy An',
  ],
  'Quảng Bình': [
    'Thành phố Đồng Hới',
    'Thị xã Ba Đồn',
    'Huyện Bố Trạch', 'Huyện Lệ Thủy', 'Huyện Minh Hóa',
    'Huyện Quảng Ninh', 'Huyện Quảng Trạch', 'Huyện Tuyên Hóa',
  ],
  'Quảng Nam': [
    'Thành phố Tam Kỳ', 'Thành phố Hội An',
    'Thị xã Điện Bàn',
    'Huyện Bắc Trà My', 'Huyện Đại Lộc', 'Huyện Đông Giang',
    'Huyện Duy Xuyên', 'Huyện Hiệp Đức', 'Huyện Nam Giang',
    'Huyện Nam Trà My', 'Huyện Nông Sơn', 'Huyện Núi Thành',
    'Huyện Phú Ninh', 'Huyện Phước Sơn', 'Huyện Quế Sơn',
    'Huyện Tây Giang', 'Huyện Thăng Bình', 'Huyện Tiên Phước',
  ],
  'Quảng Ngãi': [
    'Thành phố Quảng Ngãi',
    'Thị xã Đức Phổ',
    'Huyện Ba Tơ', 'Huyện Bình Sơn', 'Huyện Lý Sơn', 'Huyện Minh Long',
    'Huyện Mộ Đức', 'Huyện Nghĩa Hành', 'Huyện Sơn Hà', 'Huyện Sơn Tây',
    'Huyện Sơn Tịnh', 'Huyện Trà Bồng', 'Huyện Tư Nghĩa',
  ],
  'Quảng Ninh': [
    'Thành phố Hạ Long', 'Thành phố Cẩm Phả', 'Thành phố Móng Cái',
    'Thành phố Uông Bí', 'Thành phố Đông Triều',
    'Thị xã Quảng Yên',
    'Huyện Ba Chẽ', 'Huyện Bình Liêu', 'Huyện Cô Tô', 'Huyện Đầm Hà',
    'Huyện Hải Hà', 'Huyện Tiên Yên', 'Huyện Vân Đồn',
  ],
  'Quảng Trị': [
    'Thành phố Đông Hà',
    'Thị xã Quảng Trị',
    'Huyện Cam Lộ', 'Huyện Cồn Cỏ', 'Huyện Đa Krông', 'Huyện Gio Linh',
    'Huyện Hải Lăng', 'Huyện Hướng Hóa', 'Huyện Triệu Phong', 'Huyện Vĩnh Linh',
  ],
  'Sóc Trăng': [
    'Thành phố Sóc Trăng',
    'Thị xã Vĩnh Châu', 'Thị xã Ngã Năm',
    'Huyện Châu Thành', 'Huyện Cù Lao Dung', 'Huyện Kế Sách', 'Huyện Long Phú',
    'Huyện Mỹ Tú', 'Huyện Mỹ Xuyên', 'Huyện Thạnh Trị', 'Huyện Trần Đề',
  ],
  'Sơn La': [
    'Thành phố Sơn La',
    'Thị xã Mộc Châu',
    'Huyện Bắc Yên', 'Huyện Mai Sơn', 'Huyện Mường La',
    'Huyện Phù Yên', 'Huyện Quỳnh Nhai', 'Huyện Sông Mã',
    'Huyện Sốp Cộp', 'Huyện Thuận Châu', 'Huyện Vân Hồ', 'Huyện Yên Châu',
  ],
  'Tây Ninh': [
    'Thành phố Tây Ninh',
    'Thị xã Hòa Thành', 'Thị xã Trảng Bàng',
    'Huyện Bến Cầu', 'Huyện Châu Thành', 'Huyện Dương Minh Châu',
    'Huyện Gò Dầu', 'Huyện Tân Biên', 'Huyện Tân Châu',
  ],
  'Thái Bình': [
    'Thành phố Thái Bình',
    'Huyện Đông Hưng', 'Huyện Hưng Hà', 'Huyện Kiến Xương', 'Huyện Quỳnh Phụ',
    'Huyện Thái Thụy', 'Huyện Tiền Hải', 'Huyện Vũ Thư',
  ],
  'Thái Nguyên': [
    'Thành phố Thái Nguyên', 'Thành phố Sông Công', 'Thành phố Phổ Yên',
    'Huyện Đại Từ', 'Huyện Định Hóa', 'Huyện Đồng Hỷ',
    'Huyện Phú Bình', 'Huyện Phú Lương', 'Huyện Võ Nhai',
  ],
  'Thanh Hóa': [
    'Thành phố Thanh Hóa', 'Thành phố Sầm Sơn',
    'Thị xã Bỉm Sơn', 'Thị xã Nghi Sơn',
    'Huyện Bá Thước', 'Huyện Cẩm Thủy', 'Huyện Đông Sơn', 'Huyện Hà Trung',
    'Huyện Hậu Lộc', 'Huyện Hoằng Hóa', 'Huyện Lang Chánh', 'Huyện Mường Lát',
    'Huyện Nga Sơn', 'Huyện Ngọc Lặc', 'Huyện Như Thanh', 'Huyện Như Xuân',
    'Huyện Nông Cống', 'Huyện Quan Hóa', 'Huyện Quan Sơn',
    'Huyện Quảng Xương', 'Huyện Thạch Thành', 'Huyện Thiệu Hóa',
    'Huyện Thọ Xuân', 'Huyện Thường Xuân', 'Huyện Triệu Sơn',
    'Huyện Vĩnh Lộc', 'Huyện Yên Định',
  ],
  'Thừa Thiên Huế': [
    'Thành phố Huế',
    'Thị xã Hương Thủy', 'Thị xã Hương Trà',
    'Huyện A Lưới', 'Huyện Nam Đông', 'Huyện Phong Điền',
    'Huyện Phú Lộc', 'Huyện Phú Vang', 'Huyện Quảng Điền',
  ],
  'Tiền Giang': [
    'Thành phố Mỹ Tho',
    'Thị xã Cai Lậy', 'Thị xã Gò Công',
    'Huyện Cái Bè', 'Huyện Cai Lậy', 'Huyện Châu Thành', 'Huyện Chợ Gạo',
    'Huyện Gò Công Đông', 'Huyện Gò Công Tây', 'Huyện Tân Phú Đông',
    'Huyện Tân Phước',
  ],
  'Trà Vinh': [
    'Thành phố Trà Vinh',
    'Thị xã Duyên Hải',
    'Huyện Càng Long', 'Huyện Cầu Kè', 'Huyện Cầu Ngang', 'Huyện Châu Thành',
    'Huyện Duyên Hải', 'Huyện Tiểu Cần', 'Huyện Trà Cú',
  ],
  'Tuyên Quang': [
    'Thành phố Tuyên Quang',
    'Huyện Chiêm Hóa', 'Huyện Hàm Yên', 'Huyện Lâm Bình', 'Huyện Na Hang',
    'Huyện Sơn Dương', 'Huyện Yên Sơn',
  ],
  'Vĩnh Long': [
    'Thành phố Vĩnh Long',
    'Thị xã Bình Minh',
    'Huyện Bình Tân', 'Huyện Long Hồ', 'Huyện Mang Thít',
    'Huyện Tam Bình', 'Huyện Trà Ôn', 'Huyện Vũng Liêm',
  ],
  'Vĩnh Phúc': [
    'Thành phố Vĩnh Yên', 'Thành phố Phúc Yên',
    'Huyện Bình Xuyên', 'Huyện Lập Thạch', 'Huyện Sông Lô', 'Huyện Tam Đảo',
    'Huyện Tam Dương', 'Huyện Vĩnh Tường', 'Huyện Yên Lạc',
  ],
  'Yên Bái': [
    'Thành phố Yên Bái',
    'Thị xã Nghĩa Lộ',
    'Huyện Lục Yên', 'Huyện Mù Cang Chải', 'Huyện Trạm Tấu', 'Huyện Trấn Yên',
    'Huyện Văn Chấn', 'Huyện Văn Yên', 'Huyện Yên Bình',
  ],
};

/**
 * Trả về danh sách quận/huyện cho 1 tỉnh/thành.
 * - Ưu tiên master data (chính xác, theo thứ tự tự nhiên).
 * - Bổ sung những quận/huyện DB đã có nhưng master chưa liệt kê (chống lệch khi master out-of-date).
 */
export function getDistrictsForRegion(
  region: string,
  dbCascade?: Record<string, string[]>,
): string[] {
  const canonical = normalizeProvinceName(region);
  // Master có thể dùng key chuẩn; cascade DB có thể dùng tên gốc — gộp cả 2.
  const master = VN_REGIONS[canonical] ?? VN_REGIONS[region] ?? [];
  const fromDb = [
    ...(dbCascade?.[region] ?? []),
    ...(dbCascade?.[canonical] ?? []),
  ];
  const masterSet = new Set(master);
  const extras = Array.from(new Set(fromDb))
    .filter((d) => d && !masterSet.has(d))
    .sort((a, b) => a.localeCompare(b, 'vi'));
  return [...master, ...extras];
}

/**
 * Danh sách 63 tỉnh/thành — đã sắp xếp 5 TP trực thuộc trung ương lên đầu, sau đó các
 * tỉnh còn lại theo thứ tự alphabet tiếng Việt.
 */
export const VN_PROVINCES: string[] = (() => {
  const all = Object.keys(VN_REGIONS);
  const others = all
    .filter((p) => !MAJOR_CITIES.includes(p))
    .sort((a, b) => a.localeCompare(b, 'vi'));
  return [...MAJOR_CITIES, ...others];
})();

/** Set lookup nhanh để filter values nào là tỉnh thật. */
export const VN_PROVINCES_SET: Set<string> = new Set(VN_PROVINCES);
