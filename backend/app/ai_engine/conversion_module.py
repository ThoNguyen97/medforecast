"""
Conversion Module for Medical Supply Forecasting System

This module converts disease case forecasts to supply requirements using
configurable conversion ratios. It supports default ratios and disease-specific
overrides loaded from the database.
"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.conversion_ratio import ConversionRatio
from app.models.medical_supply import MedicalSupply
from .config import DEFAULT_CONVERSION_RATIOS


# Configure logging
logger = logging.getLogger(__name__)


class ConversionModule:
    """
    Convert disease case forecasts to medical supply requirements.
    
    This class handles the conversion of predicted disease cases to specific
    supply requirements using configurable conversion ratios. It supports:
    - Loading conversion ratios from database
    - Applying default ratios when no custom ratio exists
    - Disease-specific ratio overrides
    - Calculating requirements for multiple supply types
    
    Attributes:
        db: Database session
        conversion_ratios: Dictionary mapping (disease_type, supply_name) to ratio
        supply_name_to_id: Dictionary mapping supply names to supply IDs
    
    Example:
        >>> module = ConversionModule(db_session)
        >>> module.load_conversion_ratios()
        >>> requirements = module.calculate_requirements(
        ...     disease_type="dengue_fever",
        ...     predicted_cases=100,
        ...     forecast_date=date(2024, 1, 15)
        ... )
    """
    
    def __init__(self, db: Session):
        """
        Initialize the conversion module.
        
        Args:
            db: Database session for loading conversion ratios
        """
        self.db = db
        self.conversion_ratios: Dict[tuple, float] = {}
        self.supply_name_to_id: Dict[str, int] = {}
        
        logger.info("Initialized ConversionModule")
    
    def load_conversion_ratios(self) -> Dict[tuple, float]:
        """
        Load conversion ratios from database.
        
        Loads all conversion ratios from the database and builds a mapping
        of (disease_type, supply_name) to ratio. Also loads supply name to ID
        mapping for later use.
        
        Returns:
            Dictionary mapping (disease_type, supply_name) to conversion ratio
        
        Example:
            >>> module.load_conversion_ratios()
            {('dengue_fever', 'masks'): 2.0, ('dengue_fever', 'gloves'): 4.0, ...}
        """
        logger.info("Loading conversion ratios from database")
        
        try:
            # Query all conversion ratios with their associated supplies
            ratios = self.db.query(
                ConversionRatio.disease_type,
                ConversionRatio.ratio,
                ConversionRatio.supply_id,
                MedicalSupply.name
            ).join(
                MedicalSupply,
                ConversionRatio.supply_id == MedicalSupply.id
            ).all()
            
            # Build conversion ratios dictionary
            self.conversion_ratios = {}
            self.supply_name_to_id = {}
            
            for disease_type, ratio, supply_id, supply_name in ratios:
                # Store conversion ratio
                key = (disease_type, supply_name)
                self.conversion_ratios[key] = float(ratio)
                
                # Store supply name to ID mapping
                self.supply_name_to_id[supply_name] = supply_id
            
            logger.info(f"Loaded {len(self.conversion_ratios)} conversion ratios from database")
            
            # Log loaded ratios by disease type
            disease_types = set(disease_type for disease_type, _ in self.conversion_ratios.keys())
            for disease_type in disease_types:
                disease_ratios = {
                    supply_name: ratio 
                    for (dt, supply_name), ratio in self.conversion_ratios.items() 
                    if dt == disease_type
                }
                logger.info(f"  {disease_type}: {len(disease_ratios)} ratios")
            
            return self.conversion_ratios
            
        except Exception as e:
            logger.error(f"Error loading conversion ratios from database: {str(e)}")
            raise
    
    def get_conversion_ratio(
        self,
        disease_type: str,
        supply_name: str
    ) -> Optional[float]:
        """
        Get conversion ratio for a specific disease type and supply.
        
        Looks up the conversion ratio in the following order:
        1. Database-loaded disease-specific ratio
        2. Default ratio from config for the disease type
        3. None if no ratio is found
        
        Args:
            disease_type: Type of disease (e.g., 'dengue_fever')
            supply_name: Name of medical supply (e.g., 'masks')
        
        Returns:
            Conversion ratio as float, or None if not found
        
        Example:
            >>> module.get_conversion_ratio('dengue_fever', 'masks')
            2.0
        """
        # First, check database-loaded ratios (disease-specific overrides)
        key = (disease_type, supply_name)
        if key in self.conversion_ratios:
            return self.conversion_ratios[key]
        
        # Second, check default ratios from config
        if disease_type in DEFAULT_CONVERSION_RATIOS:
            disease_defaults = DEFAULT_CONVERSION_RATIOS[disease_type]
            if supply_name in disease_defaults:
                return disease_defaults[supply_name]
        
        # No ratio found
        logger.warning(
            f"No conversion ratio found for disease_type='{disease_type}', "
            f"supply_name='{supply_name}'"
        )
        return None
    
    def calculate_requirements(
        self,
        disease_type: str,
        predicted_cases: int,
        forecast_date: pd.Timestamp,
        supply_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Calculate supply requirements for predicted disease cases.
        
        Calculates the required quantity of each medical supply based on
        predicted case counts and conversion ratios. If supply_types is not
        specified, calculates for all supplies with defined ratios.
        
        Args:
            disease_type: Type of disease (e.g., 'dengue_fever')
            predicted_cases: Number of predicted disease cases
            forecast_date: Date of the forecast
            supply_types: Optional list of supply names to calculate for.
                         If None, calculates for all supplies with ratios.
        
        Returns:
            List of dictionaries containing supply requirements:
            [
                {
                    'supply_name': 'masks',
                    'supply_id': 1,
                    'required_quantity': 200,
                    'disease_type': 'dengue_fever',
                    'forecast_date': date(2024, 1, 15),
                    'conversion_ratio': 2.0
                },
                ...
            ]
        
        Example:
            >>> requirements = module.calculate_requirements(
            ...     disease_type='dengue_fever',
            ...     predicted_cases=100,
            ...     forecast_date=pd.Timestamp('2024-01-15')
            ... )
            >>> len(requirements)
            6
        """
        logger.info(
            f"Calculating supply requirements for {disease_type}: "
            f"{predicted_cases} cases on {forecast_date.date()}"
        )
        
        requirements = []
        
        # Determine which supplies to calculate for
        if supply_types is None:
            # Get all supplies for this disease type from loaded ratios
            supply_types = set()
            
            # Add supplies from database ratios
            for (dt, supply_name) in self.conversion_ratios.keys():
                if dt == disease_type:
                    supply_types.add(supply_name)
            
            # Add supplies from default ratios
            if disease_type in DEFAULT_CONVERSION_RATIOS:
                supply_types.update(DEFAULT_CONVERSION_RATIOS[disease_type].keys())
            
            supply_types = list(supply_types)
        
        # Calculate requirements for each supply type
        for supply_name in supply_types:
            # Get conversion ratio
            ratio = self.get_conversion_ratio(disease_type, supply_name)
            
            if ratio is None:
                logger.warning(
                    f"Skipping {supply_name}: no conversion ratio found for {disease_type}"
                )
                continue
            
            # Calculate required quantity
            required_quantity = int(predicted_cases * ratio)
            
            # Get supply ID (may be None if not in database)
            supply_id = self.supply_name_to_id.get(supply_name)
            
            # Create requirement record
            requirement = {
                'supply_name': supply_name,
                'supply_id': supply_id,
                'required_quantity': required_quantity,
                'disease_type': disease_type,
                'forecast_date': forecast_date.date() if hasattr(forecast_date, 'date') else forecast_date,
                'conversion_ratio': ratio
            }
            
            requirements.append(requirement)
            
            logger.debug(
                f"  {supply_name}: {predicted_cases} cases × {ratio} = {required_quantity} units"
            )
        
        logger.info(f"Calculated {len(requirements)} supply requirements")
        
        return requirements
    
    def calculate_requirements_for_forecast(
        self,
        disease_type: str,
        predictions: np.ndarray,
        forecast_dates: pd.DatetimeIndex,
        supply_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Calculate supply requirements for multiple forecast dates.
        
        Calculates requirements for each date in the forecast period.
        This is useful for multi-day forecasts.
        
        Args:
            disease_type: Type of disease
            predictions: Array of predicted case counts for each date
            forecast_dates: Array of forecast dates
            supply_types: Optional list of supply names to calculate for
        
        Returns:
            List of requirement dictionaries for all dates and supplies
        
        Example:
            >>> predictions = np.array([100, 105, 110, 115, 120, 125, 130])
            >>> dates = pd.date_range('2024-01-15', periods=7)
            >>> requirements = module.calculate_requirements_for_forecast(
            ...     disease_type='dengue_fever',
            ...     predictions=predictions,
            ...     forecast_dates=dates
            ... )
            >>> len(requirements)  # 7 days × 6 supplies = 42
            42
        """
        logger.info(
            f"Calculating supply requirements for {len(predictions)} forecast dates"
        )
        
        all_requirements = []
        
        # Calculate requirements for each forecast date
        for i, (date, predicted_cases) in enumerate(zip(forecast_dates, predictions)):
            requirements = self.calculate_requirements(
                disease_type=disease_type,
                predicted_cases=int(predicted_cases),
                forecast_date=date,
                supply_types=supply_types
            )
            
            all_requirements.extend(requirements)
        
        logger.info(
            f"Calculated {len(all_requirements)} total supply requirements "
            f"across {len(predictions)} dates"
        )
        
        return all_requirements
    
    def get_default_ratios(self, disease_type: str) -> Dict[str, float]:
        """
        Get default conversion ratios for a disease type.
        
        Returns the default ratios defined in the config file for the
        specified disease type.
        
        Args:
            disease_type: Type of disease
        
        Returns:
            Dictionary mapping supply names to default ratios
        
        Example:
            >>> module.get_default_ratios('dengue_fever')
            {'masks': 2.0, 'gloves': 4.0, 'test_kits': 1.0, ...}
        """
        return DEFAULT_CONVERSION_RATIOS.get(disease_type, {})
    
    def get_all_ratios_for_disease(self, disease_type: str) -> Dict[str, float]:
        """
        Get all conversion ratios for a disease type.
        
        Returns both database-loaded and default ratios, with database
        ratios taking precedence.
        
        Args:
            disease_type: Type of disease
        
        Returns:
            Dictionary mapping supply names to conversion ratios
        
        Example:
            >>> module.get_all_ratios_for_disease('dengue_fever')
            {'masks': 2.0, 'gloves': 4.0, 'test_kits': 1.0, ...}
        """
        # Start with default ratios
        all_ratios = self.get_default_ratios(disease_type).copy()
        
        # Override with database ratios
        for (dt, supply_name), ratio in self.conversion_ratios.items():
            if dt == disease_type:
                all_ratios[supply_name] = ratio
        
        return all_ratios
