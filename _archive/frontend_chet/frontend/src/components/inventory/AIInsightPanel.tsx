import { Brain, TrendingUp, AlertTriangle, Package } from 'lucide-react';
import Card from '../common/Card';
import type { Inventory } from '../../types/inventory';

interface AIInsightPanelProps {
  inventory: Inventory[];
}

export default function AIInsightPanel({ inventory }: AIInsightPanelProps) {
  // Calculate insights from inventory data
  const criticalItems = inventory.filter((item) => item.stock_status === 'critical').length;
  const lowStockItems = inventory.filter((item) => item.stock_status === 'low').length;
  const totalValue = inventory.reduce(
    (sum, item) => sum + item.quantity_on_hand * item.supply.unit_price,
    0
  );

  // Find items with highest shortage risk
  const highRiskItems = inventory
    .filter((item) => item.stock_status === 'critical' || item.stock_status === 'low')
    .sort((a, b) => {
      const aRatio = a.quantity_on_hand / a.safety_stock_level;
      const bRatio = b.quantity_on_hand / b.safety_stock_level;
      return aRatio - bRatio;
    })
    .slice(0, 3);

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-blue-100 rounded-lg">
          <Brain className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-blue-900 mb-3">Phân tích AI - Dự báo Nhu cầu</h3>

          {/* Key Metrics */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="p-3 bg-white/60 rounded-lg">
              <div className="flex items-center gap-2 text-red-600 mb-1">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-medium">Nguy cơ cao</span>
              </div>
              <div className="text-lg font-bold text-neutral-900">{criticalItems}</div>
            </div>

            <div className="p-3 bg-white/60 rounded-lg">
              <div className="flex items-center gap-2 text-yellow-600 mb-1">
                <TrendingUp className="w-4 h-4" />
                <span className="text-xs font-medium">Sắp hết</span>
              </div>
              <div className="text-lg font-bold text-neutral-900">{lowStockItems}</div>
            </div>

            <div className="p-3 bg-white/60 rounded-lg">
              <div className="flex items-center gap-2 text-blue-600 mb-1">
                <Package className="w-4 h-4" />
                <span className="text-xs font-medium">Tổng giá trị</span>
              </div>
              <div className="text-lg font-bold text-neutral-900">
                {new Intl.NumberFormat('vi-VN', {
                  style: 'currency',
                  currency: 'VND',
                  notation: 'compact',
                  maximumFractionDigits: 1,
                }).format(totalValue)}
              </div>
            </div>
          </div>

          {/* High Risk Items */}
          {highRiskItems.length > 0 && (
            <div className="p-3 bg-white/60 rounded-lg">
              <h4 className="text-xs font-semibold text-neutral-700 mb-2">
                Vật tư cần ưu tiên nhập hàng:
              </h4>
              <ul className="space-y-2">
                {highRiskItems.map((item) => {
                  const stockRatio = (item.quantity_on_hand / item.safety_stock_level) * 100;
                  return (
                    <li key={item.id} className="flex items-center justify-between text-xs">
                      <span className="text-neutral-700 font-medium">{item.supply.name}</span>
                      <span
                        className={`font-semibold ${
                          stockRatio < 50
                            ? 'text-red-600'
                            : stockRatio < 100
                            ? 'text-yellow-600'
                            : 'text-green-600'
                        }`}
                      >
                        {stockRatio.toFixed(0)}% mức an toàn
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* AI Recommendation */}
          <div className="mt-3 p-3 bg-blue-100/50 rounded-lg border border-blue-200">
            <p className="text-xs text-blue-900">
              <span className="font-semibold">💡 Khuyến nghị:</span> Dựa trên xu hướng tiêu thụ và
              dự báo dịch bệnh, hệ thống đề xuất nhập thêm{' '}
              <span className="font-semibold">{criticalItems + lowStockItems}</span> loại vật tư
              trong 7 ngày tới để đảm bảo đáp ứng nhu cầu.
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}
