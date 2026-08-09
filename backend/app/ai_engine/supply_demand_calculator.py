"""
Supply Demand Calculator - Module 4

Quy đổi nhu cầu thuốc/vật tư từ số ca bệnh dự báo.

Đầu vào:
- Số ca bệnh dự báo
- Loại bệnh
- Tỷ lệ nhẹ / trung bình / nặng
- Định mức vật tư theo từng mức độ
- Hệ số dự phòng

Đầu ra:
- Số lượng thuốc cần dùng
- Số lượng vật tư cần dùng
- Mức dự phòng

Công thức:
    Nhu cầu = Σ (Số ca × Tỷ lệ mức độ × Định mức vật tư mức độ đó) × Hệ số dự phòng

VD: 138 ca sốt xuất huyết
    - 60% nhẹ (83 ca): Kit XN 1/ca, Dịch truyền 1/ca, Găng tay 2/ca
    - 30% TB (41 ca): Kit XN 2/ca, Dịch truyền 2/ca, Găng tay 4/ca
    - 10% nặng (14 ca): Kit XN 3/ca, Dịch truyền 5/ca, Găng tay 8/ca
    → Kit XN = 83×1 + 41×2 + 14×3 = 207 × 1.2 (dự phòng) ≈ 248 kit
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Tỷ lệ mức độ bệnh mặc định (có thể config)
DEFAULT_SEVERITY_RATIOS = {
    'respiratory_disease': {'mild': 0.65, 'moderate': 0.25, 'severe': 0.10},
    'dengue_fever': {'mild': 0.60, 'moderate': 0.30, 'severe': 0.10},
    'seasonal_flu': {'mild': 0.70, 'moderate': 0.22, 'severe': 0.08},
    'viral_infection': {'mild': 0.75, 'moderate': 0.20, 'severe': 0.05},
}

# Hệ số dự phòng mặc định
DEFAULT_SAFETY_FACTOR = 1.2  # +20%


class SupplyDemandCalculator:
    """
    Module 4: Quy đổi nhu cầu thuốc/vật tư.
    
    Tính toán dựa trên:
    - Số ca bệnh dự báo
    - Tỷ lệ nhẹ/TB/nặng
    - Định mức vật tư theo mức độ (học từ dữ liệu CSV)
    - Hệ số dự phòng
    """
    
    def __init__(self):
        self.ratios: Optional[pd.DataFrame] = None
        self.severity_ratios: Dict = DEFAULT_SEVERITY_RATIOS.copy()
        self.safety_factor: float = DEFAULT_SAFETY_FACTOR
        self.is_fitted = False
        
    def learn_ratios_from_data(self, csv_processor) -> pd.DataFrame:
        """
        Học định mức vật tư từ dữ liệu CSV thực tế.
        
        Tính: trung bình vật tư / ca bệnh theo nhóm bệnh.
        """
        logger.info("Learning conversion ratios from historical data...")
        self.ratios = csv_processor.get_conversion_ratios_from_data()
        self.is_fitted = True
        
        for nhom in self.ratios['NhomBenh'].unique():
            nhom_data = self.ratios[self.ratios['NhomBenh'] == nhom]
            logger.info(f"  {nhom}: {len(nhom_data)} drug/supply types")
        
        return self.ratios
    
    def set_severity_ratios(self, disease_type: str, mild: float, moderate: float, severe: float):
        """Cấu hình tỷ lệ nhẹ/TB/nặng cho loại bệnh."""
        total = mild + moderate + severe
        self.severity_ratios[disease_type] = {
            'mild': mild / total,
            'moderate': moderate / total,
            'severe': severe / total
        }
    
    def set_safety_factor(self, factor: float):
        """Cấu hình hệ số dự phòng."""
        self.safety_factor = max(1.0, factor)
    
    def calculate_demand(
        self,
        predicted_cases: Dict[str, int],
        top_n: int = 30,
        min_ratio: float = 0.01
    ) -> pd.DataFrame:
        """
        Tính nhu cầu vật tư có phân theo mức độ bệnh.
        
        Công thức:
            Nhu cầu = Σ (Số ca × Tỷ lệ mức độ × Định mức) × Hệ số dự phòng
        
        Vì dữ liệu CSV không phân biệt mức độ, ta dùng:
            - Nhẹ: ratio × 0.7
            - TB: ratio × 1.0
            - Nặng: ratio × 2.0
        
        Args:
            predicted_cases: {disease_type: case_count}
            top_n: Top N vật tư mỗi nhóm bệnh
            min_ratio: Bỏ qua ratio quá nhỏ
        """
        if not self.is_fitted:
            raise ValueError("Ratios chưa được học. Gọi learn_ratios_from_data() trước.")
        
        from .csv_data_processor import DISEASE_TYPE_TO_NHOM_BENH
        
        all_demands = []
        
        for disease_type, total_cases in predicted_cases.items():
            nhom_benh = DISEASE_TYPE_TO_NHOM_BENH.get(disease_type)
            if nhom_benh is None:
                continue
            
            # Lấy tỷ lệ mức độ
            severity = self.severity_ratios.get(disease_type, {'mild': 0.65, 'moderate': 0.25, 'severe': 0.10})
            cases_mild = int(total_cases * severity['mild'])
            cases_moderate = int(total_cases * severity['moderate'])
            cases_severe = total_cases - cases_mild - cases_moderate
            
            # Lấy ratios cho nhóm bệnh này
            disease_ratios = self.ratios[
                (self.ratios['NhomBenh'] == nhom_benh) &
                (self.ratios['ratio_per_case'] >= min_ratio)
            ].head(top_n)
            
            if disease_ratios.empty:
                continue
            
            for _, row in disease_ratios.iterrows():
                base_ratio = row['ratio_per_case']
                
                # Định mức theo mức độ
                qty_mild = cases_mild * (base_ratio * 0.7)
                qty_moderate = cases_moderate * (base_ratio * 1.0)
                qty_severe = cases_severe * (base_ratio * 2.0)
                
                total_qty = qty_mild + qty_moderate + qty_severe
                safety_qty = total_qty * self.safety_factor
                
                all_demands.append({
                    'DrugName': row['DrugName'],
                    'NhomBenh': nhom_benh,
                    'DiseaseType': disease_type,
                    'ratio_per_case': base_ratio,
                    'cases_mild': cases_mild,
                    'cases_moderate': cases_moderate,
                    'cases_severe': cases_severe,
                    'qty_mild': round(qty_mild, 1),
                    'qty_moderate': round(qty_moderate, 1),
                    'qty_severe': round(qty_severe, 1),
                    'total_predicted': round(total_qty, 1),
                    'safety_quantity': round(safety_qty, 1),
                    'safety_factor': self.safety_factor,
                    'UnitOfMeasure': row['UnitOfMeasure'],
                    'predicted_cases': total_cases,
                })
        
        demand_df = pd.DataFrame(all_demands)
        
        if not demand_df.empty:
            # Aggregate same drug across disease groups
            demand_summary = (
                demand_df
                .groupby(['DrugName', 'UnitOfMeasure'])
                .agg(
                    total_predicted=('total_predicted', 'sum'),
                    total_safety=('safety_quantity', 'sum'),
                    disease_groups=('NhomBenh', lambda x: ', '.join(x.unique())),
                    avg_ratio=('ratio_per_case', 'mean'),
                )
                .reset_index()
                .sort_values('total_predicted', ascending=False)
            )
            return demand_summary
        
        return demand_df
    
    def compare_with_inventory(
        self,
        demand_df: pd.DataFrame,
        current_inventory: Dict[str, float],
        safety_stock: Optional[Dict[str, float]] = None,
        lead_time_days: Optional[Dict[str, int]] = None
    ) -> pd.DataFrame:
        """
        Module 5: So sánh nhu cầu với tồn kho.
        
        Đầu vào:
        - Nhu cầu vật tư dự báo
        - Tồn kho hiện tại
        - Tồn kho an toàn
        - Thời gian cung ứng
        
        Đầu ra:
        - Trạng thái: An toàn / Cảnh báo / Nguy hiểm
        - Số lượng đề xuất nhập thêm
        """
        result = demand_df.copy()
        
        result['current_stock'] = result['DrugName'].map(
            lambda x: current_inventory.get(x, 0)
        )
        
        # Tồn kho an toàn (mặc định = 20% nhu cầu)
        if safety_stock:
            result['safety_stock'] = result['DrugName'].map(
                lambda x: safety_stock.get(x, 0)
            )
        else:
            result['safety_stock'] = result['total_safety'] * 0.2
        
        # Thời gian cung ứng
        if lead_time_days:
            result['lead_time_days'] = result['DrugName'].map(
                lambda x: lead_time_days.get(x, 7)
            )
        else:
            result['lead_time_days'] = 7
        
        # Tính thiếu hụt
        result['shortage'] = (result['total_safety'] + result['safety_stock']) - result['current_stock']
        result['shortage'] = result['shortage'].clip(lower=0)
        
        # Phân loại trạng thái: An toàn / Cảnh báo / Nguy hiểm
        def classify_status(row):
            if row['current_stock'] <= 0:
                return 'Nguy hiểm'
            coverage = row['current_stock'] / row['total_safety'] if row['total_safety'] > 0 else 999
            if coverage < 0.3:
                return 'Nguy hiểm'
            elif coverage < 0.7:
                return 'Cảnh báo'
            else:
                return 'An toàn'
        
        result['status'] = result.apply(classify_status, axis=1)
        
        # Sort: Nguy hiểm first
        status_order = {'Nguy hiểm': 0, 'Cảnh báo': 1, 'An toàn': 2}
        result['status_order'] = result['status'].map(status_order)
        result = result.sort_values(['status_order', 'shortage'], ascending=[True, False])
        result = result.drop(columns=['status_order'])
        
        return result
    
    def generate_procurement_suggestion(
        self,
        comparison_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Module 5: Đề xuất nhập kho.
        
        Đầu ra:
        - Trạng thái vật tư
        - Số lượng đề xuất nhập thêm
        - Danh sách vật tư cần ưu tiên
        """
        suggestions = []
        
        for _, row in comparison_df.iterrows():
            suggestion = {
                'DrugName': row['DrugName'],
                'UnitOfMeasure': row['UnitOfMeasure'],
                'current_stock': row['current_stock'],
                'predicted_demand': row['total_predicted'],
                'safety_demand': row['total_safety'],
                'safety_stock': row.get('safety_stock', 0),
                'shortage': row['shortage'],
                'status': row['status'],
                'lead_time_days': row.get('lead_time_days', 7),
            }
            
            if row['status'] == 'Nguy hiểm':
                suggestion['action'] = 'NHẬP GẤP'
                suggestion['order_quantity'] = round(row['shortage'] * 1.1)
                suggestion['priority'] = 'CAO'
                suggestion['note'] = f"Cần nhập gấp! Thiếu {row['shortage']:.0f} {row['UnitOfMeasure']}"
            elif row['status'] == 'Cảnh báo':
                suggestion['action'] = 'BỔ SUNG'
                suggestion['order_quantity'] = round(row['shortage'])
                suggestion['priority'] = 'TRUNG BÌNH'
                suggestion['note'] = f"Nên bổ sung {row['shortage']:.0f} {row['UnitOfMeasure']}"
            else:
                excess = row['current_stock'] - row['total_safety']
                suggestion['action'] = 'DUY TRÌ'
                suggestion['order_quantity'] = 0
                suggestion['priority'] = 'THẤP'
                if excess > row['total_safety'] * 0.5:
                    suggestion['action'] = 'GIẢM NHẬP'
                    suggestion['note'] = f"Tồn kho dư {excess:.0f} {row['UnitOfMeasure']}. Có thể giảm nhập."
                else:
                    suggestion['note'] = f"Tồn kho đủ. Duy trì mức hiện tại."
            
            suggestions.append(suggestion)
        
        return pd.DataFrame(suggestions)
    
    def get_top_critical_supplies(self, comparison_df: pd.DataFrame, top_n: int = 10) -> List[Dict]:
        """Lấy top N vật tư nguy hiểm nhất."""
        critical = comparison_df[comparison_df['status'].isin(['Nguy hiểm', 'Cảnh báo'])].head(top_n)
        return critical.to_dict('records')
