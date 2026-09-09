"""
Model Evaluation Utilities for Medical Supply Forecasting System

This module provides functions for evaluating machine learning model performance
using various metrics including MAE, RMSE, and MAPE.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def calculate_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate Mean Absolute Error (MAE).
    
    MAE measures the average magnitude of errors in predictions,
    without considering their direction.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        MAE value
    
    Example:
        >>> mae = calculate_mae(y_true, y_pred)
        >>> print(f"MAE: {mae:.2f}")
    """
    return mean_absolute_error(y_true, y_pred)


def calculate_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate Root Mean Squared Error (RMSE).
    
    RMSE measures the square root of the average squared differences
    between predicted and actual values. It penalizes larger errors more
    than MAE.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        RMSE value
    
    Example:
        >>> rmse = calculate_rmse(y_true, y_pred)
        >>> print(f"RMSE: {rmse:.2f}")
    """
    mse = mean_squared_error(y_true, y_pred)
    return np.sqrt(mse)


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-10) -> float:
    """
    Calculate Mean Absolute Percentage Error (MAPE).
    
    MAPE measures the average percentage difference between predicted
    and actual values. It's useful for understanding relative error.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
        epsilon: Small value to avoid division by zero
    
    Returns:
        MAPE value as a percentage (0-100)
    
    Example:
        >>> mape = calculate_mape(y_true, y_pred)
        >>> print(f"MAPE: {mape:.2f}%")
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # Avoid division by zero
    mask = np.abs(y_true) > epsilon
    
    if not np.any(mask):
        return 0.0
    
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    return mape


def calculate_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate R-squared (coefficient of determination).
    
    R² measures the proportion of variance in the dependent variable
    that is predictable from the independent variables.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        R² value (0-1, where 1 is perfect prediction)
    
    Example:
        >>> r2 = calculate_r2(y_true, y_pred)
        >>> print(f"R²: {r2:.4f}")
    """
    return r2_score(y_true, y_pred)


def calculate_smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate Symmetric Mean Absolute Percentage Error (SMAPE).
    
    SMAPE is a variation of MAPE that is symmetric and bounded between 0 and 200%.
    It's more robust when dealing with values close to zero.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        SMAPE value as a percentage (0-200)
    
    Example:
        >>> smape = calculate_smape(y_true, y_pred)
        >>> print(f"SMAPE: {smape:.2f}%")
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    numerator = np.abs(y_true - y_pred)
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
    
    # Avoid division by zero
    mask = denominator > 0
    
    if not np.any(mask):
        return 0.0
    
    smape = np.mean(numerator[mask] / denominator[mask]) * 100
    return smape


def calculate_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> Dict[str, float]:
    """
    Calculate all evaluation metrics at once.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        Dictionary containing all metrics:
        - mae: Mean Absolute Error
        - rmse: Root Mean Squared Error
        - mape: Mean Absolute Percentage Error
        - smape: Symmetric Mean Absolute Percentage Error
        - r2: R-squared
    
    Example:
        >>> metrics = calculate_all_metrics(y_true, y_pred)
        >>> print(f"MAE: {metrics['mae']:.2f}")
        >>> print(f"RMSE: {metrics['rmse']:.2f}")
        >>> print(f"MAPE: {metrics['mape']:.2f}%")
    """
    return {
        'mae': calculate_mae(y_true, y_pred),
        'rmse': calculate_rmse(y_true, y_pred),
        'mape': calculate_mape(y_true, y_pred),
        'smape': calculate_smape(y_true, y_pred),
        'r2': calculate_r2(y_true, y_pred)
    }


def evaluate_forecast_by_horizon(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    horizons: List[int] = [7, 14, 30]
) -> Dict[int, Dict[str, float]]:
    """
    Evaluate forecast accuracy at different time horizons.
    
    This is useful for understanding how model performance degrades
    over longer forecast periods.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
        horizons: List of forecast horizons to evaluate (in days)
    
    Returns:
        Dictionary mapping horizon to metrics dictionary
    
    Example:
        >>> results = evaluate_forecast_by_horizon(y_true, y_pred, [7, 14, 30])
        >>> print(f"7-day MAE: {results[7]['mae']:.2f}")
        >>> print(f"30-day MAE: {results[30]['mae']:.2f}")
    """
    results = {}
    
    for horizon in horizons:
        if len(y_true) >= horizon and len(y_pred) >= horizon:
            y_true_horizon = y_true[:horizon]
            y_pred_horizon = y_pred[:horizon]
            
            results[horizon] = calculate_all_metrics(y_true_horizon, y_pred_horizon)
    
    return results


def calculate_forecast_bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Calculate forecast bias (mean error).
    
    Positive bias indicates over-forecasting, negative indicates under-forecasting.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        Mean bias value
    
    Example:
        >>> bias = calculate_forecast_bias(y_true, y_pred)
        >>> if bias > 0:
        ...     print(f"Model over-forecasts by {bias:.2f} on average")
        ... else:
        ...     print(f"Model under-forecasts by {abs(bias):.2f} on average")
    """
    return np.mean(y_pred - y_true)


def calculate_coverage_probability(
    y_true: np.ndarray,
    y_pred_lower: np.ndarray,
    y_pred_upper: np.ndarray
) -> float:
    """
    Calculate coverage probability for prediction intervals.
    
    This measures what percentage of actual values fall within
    the predicted confidence intervals.
    
    Args:
        y_true: Array of true values
        y_pred_lower: Array of lower bound predictions
        y_pred_upper: Array of upper bound predictions
    
    Returns:
        Coverage probability (0-1)
    
    Example:
        >>> coverage = calculate_coverage_probability(y_true, lower_bounds, upper_bounds)
        >>> print(f"Coverage: {coverage*100:.1f}%")
    """
    within_interval = (y_true >= y_pred_lower) & (y_true <= y_pred_upper)
    return np.mean(within_interval)


def create_evaluation_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str = "Model",
    y_pred_lower: Optional[np.ndarray] = None,
    y_pred_upper: Optional[np.ndarray] = None
) -> Dict[str, any]:
    """
    Create a comprehensive evaluation report for a forecast model.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
        model_name: Name of the model being evaluated
        y_pred_lower: Optional array of lower bound predictions
        y_pred_upper: Optional array of upper bound predictions
    
    Returns:
        Dictionary containing:
        - model_name: Name of the model
        - metrics: Dictionary of all metrics
        - bias: Forecast bias
        - coverage: Coverage probability (if bounds provided)
        - sample_size: Number of predictions evaluated
    
    Example:
        >>> report = create_evaluation_report(y_true, y_pred, "XGBoost")
        >>> print(f"Model: {report['model_name']}")
        >>> print(f"MAE: {report['metrics']['mae']:.2f}")
        >>> print(f"RMSE: {report['metrics']['rmse']:.2f}")
    """
    report = {
        'model_name': model_name,
        'metrics': calculate_all_metrics(y_true, y_pred),
        'bias': calculate_forecast_bias(y_true, y_pred),
        'sample_size': len(y_true)
    }
    
    if y_pred_lower is not None and y_pred_upper is not None:
        report['coverage'] = calculate_coverage_probability(y_true, y_pred_lower, y_pred_upper)
    
    return report


def compare_models(
    y_true: np.ndarray,
    predictions: Dict[str, np.ndarray]
) -> pd.DataFrame:
    """
    Compare multiple models using evaluation metrics.
    
    Args:
        y_true: Array of true values
        predictions: Dictionary mapping model names to prediction arrays
    
    Returns:
        DataFrame with metrics for each model, sorted by MAE
    
    Example:
        >>> predictions = {
        ...     'XGBoost': xgb_predictions,
        ...     'LSTM': lstm_predictions,
        ...     'Prophet': prophet_predictions
        ... }
        >>> comparison = compare_models(y_true, predictions)
        >>> print(comparison)
    """
    results = []
    
    for model_name, y_pred in predictions.items():
        metrics = calculate_all_metrics(y_true, y_pred)
        metrics['model'] = model_name
        results.append(metrics)
    
    df = pd.DataFrame(results)
    
    # Reorder columns
    cols = ['model', 'mae', 'rmse', 'mape', 'smape', 'r2']
    df = df[cols]
    
    # Sort by MAE (lower is better)
    df = df.sort_values('mae')
    
    return df


def calculate_directional_accuracy(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> float:
    """
    Calculate directional accuracy (percentage of correct trend predictions).
    
    This measures how often the model correctly predicts whether values
    will increase or decrease.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
    
    Returns:
        Directional accuracy (0-1)
    
    Example:
        >>> dir_acc = calculate_directional_accuracy(y_true, y_pred)
        >>> print(f"Directional Accuracy: {dir_acc*100:.1f}%")
    """
    if len(y_true) < 2:
        return 0.0
    
    # Calculate differences
    true_diff = np.diff(y_true)
    pred_diff = np.diff(y_pred)
    
    # Check if signs match (both positive or both negative)
    correct_direction = np.sign(true_diff) == np.sign(pred_diff)
    
    return np.mean(correct_direction)


def plot_predictions_vs_actual(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    dates: Optional[pd.DatetimeIndex] = None,
    title: str = "Predictions vs Actual"
) -> Dict[str, any]:
    """
    Prepare data for plotting predictions vs actual values.
    
    Args:
        y_true: Array of true values
        y_pred: Array of predicted values
        dates: Optional datetime index for x-axis
        title: Title for the plot
    
    Returns:
        Dictionary containing plot data and metrics
    
    Example:
        >>> plot_data = plot_predictions_vs_actual(y_true, y_pred, dates)
        >>> # Use plot_data to create visualization in frontend
    """
    if dates is None:
        dates = pd.date_range(start='2024-01-01', periods=len(y_true), freq='D')
    
    metrics = calculate_all_metrics(y_true, y_pred)
    
    return {
        'title': title,
        'dates': dates.tolist() if hasattr(dates, 'tolist') else list(dates),
        'actual': y_true.tolist() if hasattr(y_true, 'tolist') else list(y_true),
        'predicted': y_pred.tolist() if hasattr(y_pred, 'tolist') else list(y_pred),
        'metrics': metrics
    }
