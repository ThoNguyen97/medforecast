"""
Feature Engineering Utilities for Medical Supply Forecasting System

This module provides functions for creating features from historical data
for use in machine learning models.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


def create_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lag_periods: List[int] = [7, 14, 30]
) -> pd.DataFrame:
    """
    Create lag features for time series data.
    
    Args:
        df: DataFrame with time series data
        target_col: Name of the target column to create lags for
        lag_periods: List of lag periods (e.g., [7, 14, 30] for 7, 14, 30 days)
    
    Returns:
        DataFrame with added lag features
    
    Example:
        >>> df = create_lag_features(df, 'case_count', [7, 14, 30])
        >>> # Creates columns: case_count_lag_7, case_count_lag_14, case_count_lag_30
    """
    df_copy = df.copy()
    
    for lag in lag_periods:
        col_name = f"{target_col}_lag_{lag}"
        df_copy[col_name] = df_copy[target_col].shift(lag)
    
    return df_copy


def create_rolling_statistics(
    df: pd.DataFrame,
    target_col: str,
    windows: List[int] = [7, 14, 30],
    stats: List[str] = ['mean', 'std', 'min', 'max']
) -> pd.DataFrame:
    """
    Create rolling window statistics for time series data.
    
    Args:
        df: DataFrame with time series data
        target_col: Name of the target column to calculate statistics for
        windows: List of window sizes (e.g., [7, 14, 30] for 7, 14, 30 days)
        stats: List of statistics to calculate ('mean', 'std', 'min', 'max', 'median')
    
    Returns:
        DataFrame with added rolling statistics features
    
    Example:
        >>> df = create_rolling_statistics(df, 'case_count', [7, 14], ['mean', 'std'])
        >>> # Creates columns: case_count_rolling_7_mean, case_count_rolling_7_std, etc.
    """
    df_copy = df.copy()
    
    for window in windows:
        for stat in stats:
            col_name = f"{target_col}_rolling_{window}_{stat}"
            
            if stat == 'mean':
                df_copy[col_name] = df_copy[target_col].rolling(window=window).mean()
            elif stat == 'std':
                df_copy[col_name] = df_copy[target_col].rolling(window=window).std()
            elif stat == 'min':
                df_copy[col_name] = df_copy[target_col].rolling(window=window).min()
            elif stat == 'max':
                df_copy[col_name] = df_copy[target_col].rolling(window=window).max()
            elif stat == 'median':
                df_copy[col_name] = df_copy[target_col].rolling(window=window).median()
    
    return df_copy


def create_seasonality_features(
    df: pd.DataFrame,
    date_col: str = 'date'
) -> pd.DataFrame:
    """
    Create seasonality features from date column.
    
    Args:
        df: DataFrame with date column
        date_col: Name of the date column
    
    Returns:
        DataFrame with added seasonality features:
        - year, month, day, day_of_week, day_of_year
        - week_of_year, quarter
        - is_weekend, is_month_start, is_month_end
        - sin/cos transformations for cyclical features
    
    Example:
        >>> df = create_seasonality_features(df, 'recorded_at')
        >>> # Creates columns: month, day_of_week, is_weekend, etc.
    """
    df_copy = df.copy()
    
    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df_copy[date_col]):
        df_copy[date_col] = pd.to_datetime(df_copy[date_col])
    
    # Basic date features
    df_copy['year'] = df_copy[date_col].dt.year
    df_copy['month'] = df_copy[date_col].dt.month
    df_copy['day'] = df_copy[date_col].dt.day
    df_copy['day_of_week'] = df_copy[date_col].dt.dayofweek
    df_copy['day_of_year'] = df_copy[date_col].dt.dayofyear
    df_copy['week_of_year'] = df_copy[date_col].dt.isocalendar().week
    df_copy['quarter'] = df_copy[date_col].dt.quarter
    
    # Boolean features
    df_copy['is_weekend'] = df_copy['day_of_week'].isin([5, 6]).astype(int)
    df_copy['is_month_start'] = df_copy[date_col].dt.is_month_start.astype(int)
    df_copy['is_month_end'] = df_copy[date_col].dt.is_month_end.astype(int)
    
    # Cyclical encoding for month and day_of_week
    df_copy['month_sin'] = np.sin(2 * np.pi * df_copy['month'] / 12)
    df_copy['month_cos'] = np.cos(2 * np.pi * df_copy['month'] / 12)
    df_copy['day_of_week_sin'] = np.sin(2 * np.pi * df_copy['day_of_week'] / 7)
    df_copy['day_of_week_cos'] = np.cos(2 * np.pi * df_copy['day_of_week'] / 7)
    
    return df_copy


def create_trend_features(
    df: pd.DataFrame,
    date_col: str = 'date'
) -> pd.DataFrame:
    """
    Create trend features based on time progression.
    
    Args:
        df: DataFrame with date column
        date_col: Name of the date column
    
    Returns:
        DataFrame with added trend features:
        - days_since_start: Number of days since the first date
        - linear_trend: Normalized linear trend (0 to 1)
    
    Example:
        >>> df = create_trend_features(df, 'recorded_at')
        >>> # Creates columns: days_since_start, linear_trend
    """
    df_copy = df.copy()
    
    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df_copy[date_col]):
        df_copy[date_col] = pd.to_datetime(df_copy[date_col])
    
    # Sort by date
    df_copy = df_copy.sort_values(date_col)
    
    # Days since start
    min_date = df_copy[date_col].min()
    df_copy['days_since_start'] = (df_copy[date_col] - min_date).dt.days
    
    # Linear trend (normalized)
    max_days = df_copy['days_since_start'].max()
    if max_days > 0:
        df_copy['linear_trend'] = df_copy['days_since_start'] / max_days
    else:
        df_copy['linear_trend'] = 0
    
    return df_copy


def create_interaction_features(
    df: pd.DataFrame,
    feature_pairs: List[Tuple[str, str]]
) -> pd.DataFrame:
    """
    Create interaction features by multiplying pairs of features.
    
    Args:
        df: DataFrame with features
        feature_pairs: List of tuples containing feature names to interact
    
    Returns:
        DataFrame with added interaction features
    
    Example:
        >>> df = create_interaction_features(df, [('temperature', 'humidity')])
        >>> # Creates column: temperature_x_humidity
    """
    df_copy = df.copy()
    
    for feat1, feat2 in feature_pairs:
        if feat1 in df_copy.columns and feat2 in df_copy.columns:
            col_name = f"{feat1}_x_{feat2}"
            df_copy[col_name] = df_copy[feat1] * df_copy[feat2]
    
    return df_copy


def prepare_features_for_forecasting(
    disease_cases_df: pd.DataFrame,
    environmental_df: Optional[pd.DataFrame] = None,
    date_col: str = 'recorded_at',
    target_col: str = 'case_count',
    lag_periods: List[int] = [7, 14, 30],
    rolling_windows: List[int] = [7, 14, 30]
) -> pd.DataFrame:
    """
    Comprehensive feature preparation pipeline for disease forecasting.
    
    This function combines all feature engineering steps:
    1. Lag features
    2. Rolling statistics
    3. Seasonality features
    4. Trend features
    5. Environmental features (if provided)
    6. Interaction features
    
    Args:
        disease_cases_df: DataFrame with disease case data
        environmental_df: Optional DataFrame with environmental data
        date_col: Name of the date column
        target_col: Name of the target column (case count)
        lag_periods: List of lag periods for lag features
        rolling_windows: List of window sizes for rolling statistics
    
    Returns:
        DataFrame with all engineered features
    
    Example:
        >>> features_df = prepare_features_for_forecasting(
        ...     disease_cases_df=cases_df,
        ...     environmental_df=env_df,
        ...     target_col='case_count'
        ... )
    """
    # Start with disease cases data
    df = disease_cases_df.copy()
    
    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col])
    
    # Sort by date
    df = df.sort_values(date_col)
    
    # Create lag features
    df = create_lag_features(df, target_col, lag_periods)
    
    # Create rolling statistics
    df = create_rolling_statistics(df, target_col, rolling_windows, ['mean', 'std', 'min', 'max'])
    
    # Create seasonality features
    df = create_seasonality_features(df, date_col)
    
    # Create trend features
    df = create_trend_features(df, date_col)
    
    # Merge environmental data if provided (skip if empty DataFrame)
    if environmental_df is not None and len(environmental_df) > 0:
        env_df = environmental_df.copy()
        
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(env_df[date_col]):
            env_df[date_col] = pd.to_datetime(env_df[date_col])
        
        # Merge on date
        df = df.merge(
            env_df[[date_col, 'temperature', 'humidity', 'rainfall', 'air_quality_index']],
            on=date_col,
            how='left'
        )
        
        # Create interaction features with environmental data
        interaction_pairs = [
            ('temperature', 'humidity'),
            ('temperature', 'rainfall'),
            ('humidity', 'rainfall')
        ]
        df = create_interaction_features(df, interaction_pairs)
    
    return df


def split_train_test(
    df: pd.DataFrame,
    date_col: str = 'recorded_at',
    test_size: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split time series data into train and test sets.
    
    Args:
        df: DataFrame with time series data
        date_col: Name of the date column
        test_size: Proportion of data to use for testing (default 0.2)
    
    Returns:
        Tuple of (train_df, test_df)
    
    Example:
        >>> train_df, test_df = split_train_test(df, 'recorded_at', 0.2)
    """
    df_sorted = df.sort_values(date_col)
    split_idx = int(len(df_sorted) * (1 - test_size))
    
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    
    return train_df, test_df


def handle_missing_values(
    df: pd.DataFrame,
    strategy: str = 'forward_fill',
    fill_value: Optional[float] = None
) -> pd.DataFrame:
    """
    Handle missing values in feature DataFrame.
    
    Args:
        df: DataFrame with potential missing values
        strategy: Strategy for handling missing values:
            - 'forward_fill': Forward fill missing values
            - 'backward_fill': Backward fill missing values
            - 'mean': Fill with column mean
            - 'median': Fill with column median
            - 'constant': Fill with constant value
            - 'drop': Drop rows with missing values
        fill_value: Value to use when strategy is 'constant'
    
    Returns:
        DataFrame with missing values handled
    
    Example:
        >>> df = handle_missing_values(df, strategy='forward_fill')
    """
    df_copy = df.copy()
    
    if strategy == 'forward_fill':
        df_copy = df_copy.ffill()
    elif strategy == 'backward_fill':
        df_copy = df_copy.bfill()
    elif strategy == 'mean':
        df_copy = df_copy.fillna(df_copy.mean())
    elif strategy == 'median':
        df_copy = df_copy.fillna(df_copy.median())
    elif strategy == 'constant':
        if fill_value is not None:
            df_copy = df_copy.fillna(fill_value)
        else:
            df_copy = df_copy.fillna(0)
    elif strategy == 'drop':
        df_copy = df_copy.dropna()
    
    return df_copy
