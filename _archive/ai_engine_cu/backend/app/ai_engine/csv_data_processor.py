"""
CSV Data Processor for Medical Supply Forecasting System

Module này đọc file CSV dữ liệu bệnh viện và trích xuất:
- Số ca bệnh theo tháng (theo NhomBenh)
- Lượng thuốc/vật tư tiêu thụ theo tháng
- Tỷ lệ tiêu thụ vật tư trung bình trên mỗi ca bệnh (conversion ratio thực tế)

File CSV có cấu trúc:
- MaDinhDanh, SoTiepNhan, AdmissionDate, DischargeDate, LengthOfStay
- DistrictCode, District, AgeInterval, Gender
- Final_ICD10_Code, NhomBenh, TenBenhCuThe, DiagnosisType
- DrugCategory, DrugCode, DrugName, TenNhomDuoc, TenHoatChat
- TotalQuantityUsed, UnitOfMeasure, SoNgay, LieuDung, IsYLenhVTYT
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Mapping ICD code (mã bệnh) từ tên bệnh tiếng Việt
NHOM_BENH_MAPPING = {
    "Viêm phế quản cấp": "J20",
    "Nhiễm trùng đường hô hấp trên cấp": "J06",
    "Viêm họng cấp": "J02",
    "Viêm xoang cấp": "J01",
}

# Reverse mapping: ICD code → tên bệnh
DISEASE_TYPE_TO_NHOM_BENH = {v: k for k, v in NHOM_BENH_MAPPING.items()}


class CSVDataProcessor:
    """
    Đọc và xử lý file CSV dữ liệu bệnh viện.
    
    Trích xuất dữ liệu theo tháng:
    - Số ca bệnh (unique SoTiepNhan) theo NhomBenh
    - Lượng thuốc/vật tư tiêu thụ (TotalQuantityUsed) theo DrugName
    - Tỷ lệ vật tư/ca bệnh (conversion ratio thực tế)
    
    Example:
        >>> processor = CSVDataProcessor()
        >>> processor.load_csv_files(['/path/to/data_HM_2025_1.csv'])
        >>> monthly_cases = processor.get_monthly_cases()
        >>> monthly_supply = processor.get_monthly_supply_consumption()
    """
    
    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.monthly_cases: Optional[pd.DataFrame] = None
        self.monthly_supply: Optional[pd.DataFrame] = None
        self.conversion_ratios: Optional[pd.DataFrame] = None
        
    def load_csv_files(self, file_paths: List[str]) -> pd.DataFrame:
        """
        Load và merge nhiều file CSV.
        
        Args:
            file_paths: Danh sách đường dẫn file CSV
            
        Returns:
            DataFrame chứa toàn bộ dữ liệu
        """
        logger.info(f"Loading {len(file_paths)} CSV files...")
        
        dfs = []
        for path in file_paths:
            if not os.path.exists(path):
                logger.warning(f"File not found: {path}")
                continue
                
            logger.info(f"Reading: {path}")
            df = pd.read_csv(
                path,
                encoding='utf-8',
                dtype={
                    'TotalQuantityUsed': str,
                    'SoNgay': str,
                    'LieuDung': str,
                    'IsYLenhVTYT': str,
                    'LengthOfStay': str,
                    'SubICD_Count': str,
                }
            )
            dfs.append(df)
            logger.info(f"  → {len(df):,} rows loaded")
        
        if not dfs:
            raise ValueError("No CSV files loaded successfully")
        
        self.raw_data = pd.concat(dfs, ignore_index=True)
        
        # Parse dates
        self.raw_data['AdmissionDate'] = pd.to_datetime(
            self.raw_data['AdmissionDate'], format='%m/%d/%Y', errors='coerce'
        )
        
        # Parse numeric columns
        self.raw_data['TotalQuantityUsed'] = pd.to_numeric(
            self.raw_data['TotalQuantityUsed'], errors='coerce'
        ).fillna(0)
        
        self.raw_data['IsYLenhVTYT'] = pd.to_numeric(
            self.raw_data['IsYLenhVTYT'], errors='coerce'
        ).fillna(0).astype(int)
        
        # Add year-month column
        self.raw_data['YearMonth'] = self.raw_data['AdmissionDate'].dt.to_period('M')
        
        # Map disease types
        self.raw_data['DiseaseType'] = self.raw_data['NhomBenh'].map(NHOM_BENH_MAPPING)
        
        logger.info(f"Total loaded: {len(self.raw_data):,} rows")
        logger.info(f"Date range: {self.raw_data['AdmissionDate'].min()} → {self.raw_data['AdmissionDate'].max()}")
        
        return self.raw_data
    
    def get_monthly_cases(self) -> pd.DataFrame:
        """
        Tính số ca bệnh theo tháng và nhóm bệnh.
        
        Mỗi ca bệnh = 1 unique SoTiepNhan (1 lượt khám/nhập viện).
        
        Returns:
            DataFrame với columns: [YearMonth, DiseaseType, NhomBenh, case_count]
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load_csv_files() first.")
        
        # Count unique admissions per month per disease group
        monthly = (
            self.raw_data
            .dropna(subset=['AdmissionDate', 'NhomBenh'])
            .groupby(['YearMonth', 'NhomBenh', 'DiseaseType'])['SoTiepNhan']
            .nunique()
            .reset_index()
            .rename(columns={'SoTiepNhan': 'case_count'})
        )
        
        # Sort by date
        monthly = monthly.sort_values('YearMonth').reset_index(drop=True)
        
        self.monthly_cases = monthly
        logger.info(f"Monthly cases computed: {len(monthly)} rows")
        
        return monthly
    
    def get_monthly_supply_consumption(self) -> pd.DataFrame:
        """
        Tính lượng thuốc/vật tư tiêu thụ theo tháng.
        
        Returns:
            DataFrame với columns: [YearMonth, DrugName, DrugCategory, 
                                    TenNhomDuoc, IsYLenhVTYT, total_quantity, 
                                    UnitOfMeasure, unique_patients]
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load_csv_files() first.")
        
        # Aggregate supply consumption per month
        monthly = (
            self.raw_data
            .dropna(subset=['AdmissionDate', 'DrugName'])
            .groupby(['YearMonth', 'DrugName', 'DrugCategory', 'TenNhomDuoc', 'IsYLenhVTYT', 'UnitOfMeasure'])
            .agg(
                total_quantity=('TotalQuantityUsed', 'sum'),
                unique_patients=('SoTiepNhan', 'nunique')
            )
            .reset_index()
        )
        
        monthly = monthly.sort_values(['YearMonth', 'total_quantity'], ascending=[True, False])
        
        self.monthly_supply = monthly
        logger.info(f"Monthly supply consumption computed: {len(monthly)} rows")
        
        return monthly
    
    def get_conversion_ratios_from_data(self) -> pd.DataFrame:
        """
        Tính conversion ratio thực tế từ dữ liệu.
        
        Conversion ratio = Tổng lượng vật tư sử dụng / Tổng số ca bệnh
        (tính theo nhóm bệnh và loại vật tư)
        
        Returns:
            DataFrame với columns: [NhomBenh, DiseaseType, DrugName, 
                                    ratio_per_case, UnitOfMeasure]
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load_csv_files() first.")
        
        # Get total cases per disease group per month
        cases_per_month = (
            self.raw_data
            .dropna(subset=['AdmissionDate', 'NhomBenh'])
            .groupby(['YearMonth', 'NhomBenh'])['SoTiepNhan']
            .nunique()
            .reset_index()
            .rename(columns={'SoTiepNhan': 'case_count'})
        )
        
        # Get total supply per disease group per month
        supply_per_month = (
            self.raw_data
            .dropna(subset=['AdmissionDate', 'NhomBenh', 'DrugName'])
            .groupby(['YearMonth', 'NhomBenh', 'DrugName', 'UnitOfMeasure'])['TotalQuantityUsed']
            .sum()
            .reset_index()
            .rename(columns={'TotalQuantityUsed': 'total_quantity'})
        )
        
        # Merge to calculate ratio
        merged = supply_per_month.merge(cases_per_month, on=['YearMonth', 'NhomBenh'])
        merged['ratio_per_case'] = merged['total_quantity'] / merged['case_count']
        
        # Average ratio across all months
        avg_ratios = (
            merged
            .groupby(['NhomBenh', 'DrugName', 'UnitOfMeasure'])
            .agg(
                ratio_per_case=('ratio_per_case', 'mean'),
                std_ratio=('ratio_per_case', 'std'),
                months_observed=('YearMonth', 'count')
            )
            .reset_index()
        )
        
        # Add disease type mapping
        avg_ratios['DiseaseType'] = avg_ratios['NhomBenh'].map(NHOM_BENH_MAPPING)
        
        # Sort by ratio descending
        avg_ratios = avg_ratios.sort_values(
            ['NhomBenh', 'ratio_per_case'], ascending=[True, False]
        ).reset_index(drop=True)
        
        self.conversion_ratios = avg_ratios
        logger.info(f"Conversion ratios computed: {len(avg_ratios)} drug/supply types")
        
        return avg_ratios
    
    def get_monthly_summary(self) -> pd.DataFrame:
        """
        Tạo bảng tổng hợp theo tháng cho model training.
        
        Returns:
            DataFrame với columns: [YearMonth, year, month, 
                                    cases_respiratory, cases_flu, cases_viral, cases_dengue,
                                    total_cases]
        """
        if self.monthly_cases is None:
            self.get_monthly_cases()
        
        # Pivot to get cases per disease type per month
        pivot = self.monthly_cases.pivot_table(
            index='YearMonth',
            columns='DiseaseType',
            values='case_count',
            aggfunc='sum',
            fill_value=0
        ).reset_index()
        
        # Rename columns
        col_mapping = {
            'respiratory_disease': 'cases_respiratory',
            'seasonal_flu': 'cases_flu',
            'viral_infection': 'cases_viral',
            'dengue_fever': 'cases_dengue',
        }
        pivot = pivot.rename(columns=col_mapping)
        
        # Ensure all disease columns exist
        for col in col_mapping.values():
            if col not in pivot.columns:
                pivot[col] = 0
        
        # Add total cases
        case_cols = [c for c in col_mapping.values() if c in pivot.columns]
        pivot['total_cases'] = pivot[case_cols].sum(axis=1)
        
        # Add year and month columns
        pivot['year'] = pivot['YearMonth'].dt.year
        pivot['month'] = pivot['YearMonth'].dt.month
        
        return pivot
    
    def get_top_supplies_by_disease(
        self, 
        nhom_benh: str, 
        top_n: int = 30
    ) -> pd.DataFrame:
        """
        Lấy top N vật tư/thuốc tiêu thụ nhiều nhất cho 1 nhóm bệnh.
        
        Args:
            nhom_benh: Tên nhóm bệnh (VD: "Bệnh lý hô hấp")
            top_n: Số lượng top items
            
        Returns:
            DataFrame với top supplies
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load_csv_files() first.")
        
        disease_data = self.raw_data[self.raw_data['NhomBenh'] == nhom_benh]
        
        top_supplies = (
            disease_data
            .groupby(['DrugName', 'DrugCategory', 'UnitOfMeasure', 'IsYLenhVTYT'])
            .agg(
                total_quantity=('TotalQuantityUsed', 'sum'),
                unique_patients=('SoTiepNhan', 'nunique'),
                frequency=('TotalQuantityUsed', 'count')
            )
            .reset_index()
            .sort_values('total_quantity', ascending=False)
            .head(top_n)
        )
        
        return top_supplies
