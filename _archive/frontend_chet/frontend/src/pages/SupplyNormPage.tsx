/**
 * Trang quản lý định mức thuốc/vật tư theo cấp độ
 */
import React from 'react';
import SupplyNormMatrix from '../components/SupplyNormMatrix';

export const SupplyNormPage: React.FC = () => {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-extrabold text-neutral-900">
          📊 Quản lý Định mức Thuốc/Vật tư theo Cấp độ
        </h1>
        <p className="text-sm text-neutral-500 mt-2">
          Xem và chỉnh sửa định mức thuốc/vật tư cho từng bệnh chia theo 3 cấp độ:
          Nhẹ (mild), Trung bình (moderate), Nặng (severe)
        </p>
      </div>

      <SupplyNormMatrix />
    </div>
  );
};

export default SupplyNormPage;
