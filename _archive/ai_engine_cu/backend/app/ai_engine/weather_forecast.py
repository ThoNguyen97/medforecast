"""
Weather Forecast Module - Dự báo thời tiết tháng tiếp theo

Module này lấy dự báo thời tiết từ OpenWeatherMap API hoặc
ước tính từ dữ liệu lịch sử khi không có API key.

Theo sơ đồ luồng: Song song với phân tích tương quan,
cần dự báo thời tiết tháng tiếp theo để làm input cho model.

Hai chế độ:
1. API mode: Gọi OpenWeatherMap API lấy forecast 30 ngày
2. Historical mode: Ước tính từ dữ liệu cùng tháng các năm trước
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# OpenWeatherMap API config
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
DEFAULT_LOCATION = {
    'lat': 10.8231,  # TP.HCM
    'lon': 106.6297,
    'city': 'Ho Chi Minh City'
}

# Historical average weather data for TP.HCM (fallback khi không có API)
# Source: Climate data for Ho Chi Minh City
HCMC_MONTHLY_WEATHER = {
    1:  {'temp': 26.0, 'humidity': 70, 'rainfall': 14, 'aqi': 90},
    2:  {'temp': 27.0, 'humidity': 68, 'rainfall': 4, 'aqi': 85},
    3:  {'temp': 28.5, 'humidity': 69, 'rainfall': 11, 'aqi': 95},
    4:  {'temp': 29.5, 'humidity': 72, 'rainfall': 50, 'aqi': 100},
    5:  {'temp': 29.0, 'humidity': 78, 'rainfall': 218, 'aqi': 80},
    6:  {'temp': 28.0, 'humidity': 82, 'rainfall': 312, 'aqi': 75},
    7:  {'temp': 27.5, 'humidity': 83, 'rainfall': 294, 'aqi': 70},
    8:  {'temp': 27.5, 'humidity': 83, 'rainfall': 270, 'aqi': 72},
    9:  {'temp': 27.5, 'humidity': 84, 'rainfall': 327, 'aqi': 75},
    10: {'temp': 27.0, 'humidity': 83, 'rainfall': 267, 'aqi': 80},
    11: {'temp': 27.0, 'humidity': 78, 'rainfall': 116, 'aqi': 85},
    12: {'temp': 26.0, 'humidity': 74, 'rainfall': 48, 'aqi': 88},
}


class WeatherForecast:
    """
    Dự báo thời tiết tháng tiếp theo.
    
    Cung cấp dữ liệu thời tiết dự báo cho model dự báo ca bệnh.
    
    Example:
        >>> weather = WeatherForecast()
        >>> forecast = weather.get_forecast(target_month=6, target_year=2026)
        >>> print(forecast)
        {'temp': 28.0, 'humidity': 82, 'rainfall': 312, 'aqi': 75, 'source': 'historical_average'}
    """
    
    def __init__(self, api_key: Optional[str] = None, location: Optional[Dict] = None):
        """
        Args:
            api_key: OpenWeatherMap API key (optional)
            location: Dict với lat, lon, city
        """
        self.api_key = api_key or OPENWEATHER_API_KEY
        self.location = location or DEFAULT_LOCATION
        
    def get_forecast(
        self,
        target_month: int,
        target_year: int = None
    ) -> Dict[str, float]:
        """
        Lấy dự báo thời tiết cho tháng mục tiêu.
        
        Thử API trước, nếu không có thì dùng historical average.
        
        Args:
            target_month: Tháng cần dự báo (1-12)
            target_year: Năm (default: năm hiện tại)
            
        Returns:
            Dict {'temp': float, 'humidity': float, 'rainfall': float, 
                  'aqi': float, 'source': str}
        """
        if target_year is None:
            target_year = datetime.now().year
        
        # Try API first
        if self.api_key:
            try:
                api_result = self._fetch_from_api(target_month, target_year)
                if api_result:
                    return api_result
            except Exception as e:
                logger.warning(f"API fetch failed: {e}. Falling back to historical data.")
        
        # Fallback: historical average
        return self._get_historical_average(target_month)
    
    def get_current_month_weather(self, month: Optional[int] = None) -> Dict[str, float]:
        """
        Lấy thời tiết tháng hiện tại (hoặc tháng chỉ định).
        
        Dùng cho prev_month_weather input.
        
        Args:
            month: Tháng cần lấy (default: tháng hiện tại)
            
        Returns:
            Dict thời tiết
        """
        if month is None:
            month = datetime.now().month
        
        # Try API for current/recent weather
        if self.api_key:
            try:
                return self._fetch_current_from_api()
            except Exception as e:
                logger.warning(f"Current weather API failed: {e}")
        
        return self._get_historical_average(month)
    
    def _fetch_from_api(self, target_month: int, target_year: int) -> Optional[Dict]:
        """
        Fetch weather forecast from OpenWeatherMap API.
        
        Uses Climate Forecast API or 30-day forecast.
        """
        try:
            import requests
            
            # OpenWeatherMap 30-day forecast (requires paid plan)
            # Fallback to 5-day forecast + historical for estimation
            url = (
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?lat={self.location['lat']}&lon={self.location['lon']}"
                f"&appid={self.api_key}&units=metric"
            )
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Aggregate forecast data
                temps = []
                humidities = []
                rain_total = 0
                
                for item in data.get('list', []):
                    temps.append(item['main']['temp'])
                    humidities.append(item['main']['humidity'])
                    if 'rain' in item:
                        rain_total += item['rain'].get('3h', 0)
                
                if temps:
                    result = {
                        'temp': round(np.mean(temps), 1),
                        'humidity': round(np.mean(humidities), 1),
                        'rainfall': round(rain_total * 6, 1),  # Extrapolate to monthly
                        'aqi': 80.0,  # AQI needs separate API call
                        'source': 'openweathermap_api'
                    }
                    
                    logger.info(f"Weather forecast from API: {result}")
                    return result
            
            logger.warning(f"API returned status {response.status_code}")
            return None
            
        except ImportError:
            logger.warning("requests library not available for API calls")
            return None
        except Exception as e:
            logger.error(f"API error: {e}")
            return None
    
    def _fetch_current_from_api(self) -> Dict[str, float]:
        """Fetch current weather from API."""
        try:
            import requests
            
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?lat={self.location['lat']}&lon={self.location['lon']}"
                f"&appid={self.api_key}&units=metric"
            )
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'temp': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'rainfall': data.get('rain', {}).get('1h', 0) * 24 * 30,
                    'aqi': 80.0,
                    'source': 'openweathermap_current'
                }
        except Exception as e:
            logger.warning(f"Current weather API failed: {e}")
        
        return self._get_historical_average(datetime.now().month)
    
    def _get_historical_average(self, month: int) -> Dict[str, float]:
        """
        Trả về thời tiết trung bình lịch sử cho tháng chỉ định.
        
        Dữ liệu climate trung bình nhiều năm cho TP.HCM.
        """
        weather = HCMC_MONTHLY_WEATHER.get(month, HCMC_MONTHLY_WEATHER[1])
        
        result = {
            'temp': weather['temp'],
            'humidity': weather['humidity'],
            'rainfall': weather['rainfall'],
            'aqi': weather['aqi'],
            'source': 'historical_average'
        }
        
        logger.info(f"Using historical average for month {month}: {result}")
        return result
    
    def get_all_months_weather(self) -> Dict[int, Dict]:
        """
        Trả về thời tiết trung bình cho tất cả 12 tháng.
        
        Dùng cho training model khi không có weather API.
        """
        return {
            month: self._get_historical_average(month)
            for month in range(1, 13)
        }
    
    def build_weather_dataframe(self, months: List) -> 'pd.DataFrame':
        """
        Tạo DataFrame thời tiết cho danh sách YearMonth.
        
        Args:
            months: List of Period objects (YearMonth)
            
        Returns:
            DataFrame với columns [YearMonth, temp, humidity, rainfall, aqi]
        """
        import pandas as pd
        
        records = []
        for ym in months:
            month_num = ym.month
            weather = self._get_historical_average(month_num)
            records.append({
                'YearMonth': ym,
                'temp': weather['temp'],
                'humidity': weather['humidity'],
                'rainfall': weather['rainfall'],
                'aqi': weather['aqi']
            })
        
        return pd.DataFrame(records)
