"""Data Collector service for external API integration."""
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime
import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.environmental_data import EnvironmentalData
from app.models.disease_case import DiseaseCase
from app.models.system_log import SystemLog

logger = logging.getLogger(__name__)


class DataCollectorService:
    """Service for collecting data from external APIs."""
    
    # OpenWeather API configuration
    OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
    OPENWEATHER_AIR_POLLUTION_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_INTERVAL_SECONDS = 60
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = settings.OPENWEATHER_API_KEY
    
    def _log_system_error(self, module: str, message: str, stack_trace: Optional[str] = None):
        """Log system error to database."""
        try:
            log = SystemLog(
                log_level="ERROR",
                module_name=module,
                message=message,
                stack_trace=stack_trace
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log system error: {str(e)}")
    
    def _log_system_warning(self, module: str, message: str):
        """Log system warning to database."""
        try:
            log = SystemLog(
                log_level="WARNING",
                module_name=module,
                message=message
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log system warning: {str(e)}")
    
    def _log_system_info(self, module: str, message: str):
        """Log system info to database."""
        try:
            log = SystemLog(
                log_level="INFO",
                module_name=module,
                message=message
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log system info: {str(e)}")
    
    def _make_request_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
        description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request with retry mechanism.
        
        Retries up to MAX_RETRIES times with RETRY_INTERVAL_SECONDS between attempts.
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(f"Attempt {attempt}/{self.MAX_RETRIES}: {description}")
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"Successfully retrieved {description}")
                return data
                
            except Exception as e:
                error_msg = f"Attempt {attempt}/{self.MAX_RETRIES} failed for {description}: {str(e)}"
                logger.warning(error_msg)
                
                if attempt < self.MAX_RETRIES:
                    logger.info(f"Retrying in {self.RETRY_INTERVAL_SECONDS} seconds...")
                    time.sleep(self.RETRY_INTERVAL_SECONDS)
                else:
                    # Final attempt failed
                    final_error = f"Failed to retrieve {description} after {self.MAX_RETRIES} attempts"
                    logger.error(final_error)
                    self._log_system_error(
                        module="DataCollector",
                        message=final_error,
                        stack_trace=str(e)
                    )
                    return None
        
        return None
    
    def collect_weather_data(
        self,
        location: str,
        lat: float,
        lon: float
    ) -> Optional[EnvironmentalData]:
        """
        Collect weather data from OpenWeather API.
        
        Args:
            location: Location name (e.g., "Ho Chi Minh City")
            lat: Latitude
            lon: Longitude
        
        Returns:
            EnvironmentalData object if successful, None otherwise
        """
        if not self.api_key:
            error_msg = "OpenWeather API key not configured"
            logger.error(error_msg)
            self._log_system_error(
                module="DataCollector",
                message=error_msg
            )
            return None
        
        # Collect current weather data
        weather_url = f"{self.OPENWEATHER_BASE_URL}/weather"
        weather_params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric"  # Celsius
        }
        
        weather_data = self._make_request_with_retry(
            url=weather_url,
            params=weather_params,
            description=f"weather data for {location}"
        )
        
        if not weather_data:
            return None
        
        # Collect air pollution data
        air_pollution_url = self.OPENWEATHER_AIR_POLLUTION_URL
        air_params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key
        }
        
        air_data = self._make_request_with_retry(
            url=air_pollution_url,
            params=air_params,
            description=f"air pollution data for {location}"
        )
        
        # Extract data
        try:
            temperature = weather_data.get("main", {}).get("temp")
            humidity = weather_data.get("main", {}).get("humidity")
            
            # Rainfall in the last hour (if available)
            rainfall = None
            if "rain" in weather_data:
                rainfall = weather_data["rain"].get("1h", 0)
            
            # Air Quality Index (if available)
            air_quality_index = None
            if air_data and "list" in air_data and len(air_data["list"]) > 0:
                air_quality_index = air_data["list"][0].get("main", {}).get("aqi")
            
            # Create environmental data record
            env_data = EnvironmentalData(
                recorded_at=datetime.utcnow(),
                location=location,
                temperature=temperature,
                humidity=humidity,
                rainfall=rainfall,
                air_quality_index=air_quality_index,
                data_source="OpenWeather API"
            )
            
            self.db.add(env_data)
            self.db.commit()
            self.db.refresh(env_data)
            
            logger.info(
                f"Successfully collected and stored environmental data for {location}"
            )
            self._log_system_info(
                module="DataCollector",
                message=f"Collected environmental data for {location}: "
                        f"temp={temperature}°C, humidity={humidity}%, "
                        f"rainfall={rainfall}mm, AQI={air_quality_index}"
            )
            
            return env_data
            
        except Exception as e:
            error_msg = f"Failed to parse or store environmental data for {location}"
            logger.error(f"{error_msg}: {str(e)}")
            self._log_system_error(
                module="DataCollector",
                message=error_msg,
                stack_trace=str(e)
            )
            return None
    
    def collect_data_for_locations(self, locations: Dict[str, Dict[str, float]]) -> Dict[str, Optional[EnvironmentalData]]:
        """
        Collect environmental data for multiple locations.
        
        Args:
            locations: Dictionary mapping location names to {"lat": float, "lon": float}
        
        Returns:
            Dictionary mapping location names to EnvironmentalData objects (or None if failed)
        
        Example:
            locations = {
                "Ho Chi Minh City": {"lat": 10.8231, "lon": 106.6297},
                "Hanoi": {"lat": 21.0285, "lon": 105.8542}
            }
        """
        results = {}
        
        for location, coords in locations.items():
            lat = coords.get("lat")
            lon = coords.get("lon")
            
            if lat is None or lon is None:
                logger.warning(f"Skipping {location}: missing coordinates")
                results[location] = None
                continue
            
            data = self.collect_weather_data(location, lat, lon)
            results[location] = data
        
        return results
    
    def collect_disease_cases(
        self,
        health_dept_api_url: str,
        location: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Optional[DiseaseCase]]:
        """
        Collect disease case data from health department API.
        
        Args:
            health_dept_api_url: Base URL of the health department API
            location: Location name
            api_key: Optional API key for authentication
        
        Returns:
            Dictionary mapping disease types to DiseaseCase objects (or None if failed)
        
        Expected API response format:
        {
            "dengue_fever": {"cases": 150, "severity": "moderate"},
            "seasonal_flu": {"cases": 320, "severity": "high"},
            "respiratory_disease": {"cases": 89, "severity": "low"}
        }
        """
        # Prepare request parameters
        params = {}
        headers = {}
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Make request with retry mechanism
        data = self._make_request_with_retry(
            url=health_dept_api_url,
            params=params,
            description=f"disease case data for {location}"
        )
        
        if not data:
            return {
                "dengue_fever": None,
                "seasonal_flu": None,
                "respiratory_disease": None
            }
        
        results = {}
        disease_types = ["dengue_fever", "seasonal_flu", "respiratory_disease"]
        
        for disease_type in disease_types:
            try:
                disease_data = data.get(disease_type, {})
                case_count = disease_data.get("cases", 0)
                severity = disease_data.get("severity")
                
                # Validate case count is non-negative
                if case_count < 0:
                    logger.warning(
                        f"Invalid case count for {disease_type} at {location}: {case_count}. "
                        "Rejecting data."
                    )
                    results[disease_type] = None
                    continue
                
                # Create disease case record
                disease_case = DiseaseCase(
                    recorded_at=datetime.utcnow(),
                    disease_type=disease_type,
                    case_count=case_count,
                    location=location,
                    severity=severity,
                    data_source="Health Department API"
                )
                
                self.db.add(disease_case)
                self.db.flush()
                
                logger.info(
                    f"Collected disease case data for {disease_type} at {location}: "
                    f"{case_count} cases"
                )
                self._log_system_info(
                    module="DataCollector",
                    message=f"Collected {disease_type} data for {location}: "
                            f"{case_count} cases, severity={severity}"
                )
                
                results[disease_type] = disease_case
                
            except Exception as e:
                error_msg = f"Failed to parse or store {disease_type} data for {location}"
                logger.error(f"{error_msg}: {str(e)}")
                self._log_system_error(
                    module="DataCollector",
                    message=error_msg,
                    stack_trace=str(e)
                )
                results[disease_type] = None
        
        # Commit all disease case records
        try:
            self.db.commit()
            logger.info(f"Successfully stored disease case data for {location}")
        except Exception as e:
            self.db.rollback()
            error_msg = f"Failed to commit disease case data for {location}"
            logger.error(f"{error_msg}: {str(e)}")
            self._log_system_error(
                module="DataCollector",
                message=error_msg,
                stack_trace=str(e)
            )
            # Mark all results as failed
            for disease_type in disease_types:
                results[disease_type] = None
        
        return results
    
    def collect_disease_cases_for_locations(
        self,
        health_dept_api_url: str,
        locations: list[str],
        api_key: Optional[str] = None
    ) -> Dict[str, Dict[str, Optional[DiseaseCase]]]:
        """
        Collect disease case data for multiple locations.
        
        Args:
            health_dept_api_url: Base URL of the health department API
            locations: List of location names
            api_key: Optional API key for authentication
        
        Returns:
            Dictionary mapping location names to disease case results
        """
        results = {}
        
        for location in locations:
            # Construct location-specific URL if needed
            location_url = f"{health_dept_api_url}?location={location}"
            
            disease_cases = self.collect_disease_cases(
                health_dept_api_url=location_url,
                location=location,
                api_key=api_key
            )
            results[location] = disease_cases
        
        return results
