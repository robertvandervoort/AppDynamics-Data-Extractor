"""
Data validation utilities.
"""
import json
import pandas as pd
from io import StringIO
from typing import Any, Tuple, Optional
import requests


def validate_json(response: Any) -> Tuple[Optional[Any], str]:
    """
    Validate JSON response and handle empty sets from API requests.
    
    Args:
        response: Response object, tuple, dict, or other data to validate
        
    Returns:
        Tuple of (data, status) where status is 'valid', 'empty', or 'error'
    """
    if not response:
        return None, "empty"
    
    try:
        if isinstance(response, tuple):
            # Unpack response tuple
            data, data_status = response
            
            if data_status != "valid":
                return None, data_status
            
            # Convert response data to JSON
            data = data.json()
            
        elif isinstance(response, requests.Response):
            data = response.json()
            data_status = "valid"
            
        elif isinstance(response, dict):
            # Handle dictionaries directly
            data = response
            data_status = "valid"
        else:
            return None, "error"
        
        # Check for empty JSON object
        if not data or data == [] or data == "":
            return None, "empty"
        
        return data, data_status
        
    except json.JSONDecodeError:
        return None, "error"
    except Exception:
        return None, "error"


def validate_and_parse_xml(response: requests.Response, xpath: str) -> Tuple[pd.DataFrame, str]:
    """
    Validate XML response and convert it to a pandas DataFrame.
    
    Args:
        response: The requests.Response object containing the XML data
        xpath: The XPath expression to locate the parent of the repeating elements
        
    Returns:
        Tuple of (DataFrame, status) where status is 'valid', 'empty', or 'error'
    """
    try:
        if not response.content.decode().strip():
            return pd.DataFrame(), "empty"
        
        xml_content = StringIO(response.content.decode())
        df = pd.read_xml(xml_content, xpath=xpath)
        
        if df.empty:
            return df, "empty"
        else:
            return df, "valid"
            
    except Exception as e:
        print(f"An exception occurred converting XML to DataFrame: {type(e).__name__}: {e}")
        return pd.DataFrame(), "error"


def determine_availability(metric_data: list, metric_data_status: str) -> Tuple[Optional[int], Optional[Any]]:
    """
    Process returned metric JSON data to extract availability information.
    
    Args:
        metric_data: List of metric data from API
        metric_data_status: Status of the metric data
        
    Returns:
        Tuple of (epoch_time, value) or (None, None) if no data
    """
    if not metric_data or metric_data[-1]['metricName'] == "METRIC DATA NOT FOUND":
        return None, None
    
    if metric_data[-1]['metricValues'][-1]['startTimeInMillis']:
        last_start_time_millis = metric_data[-1]['metricValues'][-1]['startTimeInMillis']
        value = metric_data[-1]['metricValues'][-1]['current']
        return last_start_time_millis, value
    
    return None, None




