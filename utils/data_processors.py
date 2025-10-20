"""
Data processing utilities.
"""
import math
import pandas as pd
from typing import Dict, Any, List


def calculate_licenses(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate license usage based on agent types and server configurations.
    
    Args:
        df: DataFrame containing node and server data
        
    Returns:
        DataFrame with license usage calculations
    """
    license_data = []
    
    agent_types = [
        'APP_AGENT', 'DOT_NET_APP_AGENT', 'NODEJS_APP_AGENT', 'PYTHON_APP_AGENT',
        'PHP_APP_AGENT', 'GOLANG_SDK', 'WMB_AGENT', 'MACHINE_AGENT', 
        'DOT_NET_MACHINE_AGENT', 'NATIVE_WEB_SERVER', 'NATIVE_SDK'
    ]
    
    for agent_type in agent_types:
        if agent_type == 'NATIVE_SDK':
            agent_df = df[df['Node - Agent Type'] == agent_type]
            sap_abap_df = agent_df[agent_df['App Agent Version'].str.contains('with HTTP SDK', na=False)]
            cpp_df = agent_df[~agent_df['App Agent Version'].str.contains('with HTTP SDK', na=False)]
            
            sap_abap_licenses = sap_abap_df['hostId'].nunique()
            cpp_licenses = cpp_df['hostId'].nunique() // 3
            if cpp_df['hostId'].nunique() % 3 > 0:
                cpp_licenses += 1
            
            license_data.append({'Agent Type': 'SAP ABAP Agent', 'Licenses Required': sap_abap_licenses})
            license_data.append({'Agent Type': 'C++ Agent', 'Licenses Required': cpp_licenses})
            
        else:
            agent_df = df[df['Node - Agent Type'] == agent_type]
            container_df = agent_df[agent_df['Server Type'] == 'CONTAINER']
            physical_df = agent_df[agent_df['Server Type'] == 'PHYSICAL']
            
            if agent_type in ['DOT_NET_APP_AGENT', 'PYTHON_APP_AGENT', 'WMB_AGENT', 'NATIVE_SDK', 
                              'MACHINE_AGENT', 'DOT_NET_MACHINE_AGENT', 'NATIVE_WEB_SERVER']:
                container_licenses = container_df['hostId'].nunique()
                physical_licenses = physical_df['hostId'].nunique()
            elif agent_type in ['APP_AGENT', 'PHP_APP_AGENT']:
                container_licenses = container_df['Node Name'].nunique()
                physical_licenses = physical_df['Node Name'].nunique()
            elif agent_type == 'NODEJS_APP_AGENT':
                container_licenses = 0
                physical_licenses = 0
                for host_id in agent_df['hostId'].unique():
                    host_df = agent_df[agent_df['hostId'] == host_id]
                    container_host_df = host_df[host_df['Server Type'] == 'CONTAINER']
                    physical_host_df = host_df[host_df['Server Type'] == 'PHYSICAL']
                    container_licenses += (container_host_df['Node Name'].nunique() // 10)
                    if container_host_df['Node Name'].nunique() % 10 > 0:
                        container_licenses += 1
                    physical_licenses += (physical_host_df['Node Name'].nunique() // 10)
                    if physical_host_df['Node Name'].nunique() % 10 > 0:
                        physical_licenses += 1
            elif agent_type == 'GOLANG_SDK':
                container_licenses = (container_df['Node Name'].nunique() // 3)
                if container_df['Node Name'].nunique() % 3 > 0:
                    container_licenses += 1
                physical_licenses = (physical_df['Node Name'].nunique() // 3)
                if physical_df['Node Name'].nunique() % 3 > 0:
                    physical_licenses += 1
            
            microservices_licenses = math.ceil(container_licenses / 5)
            standard_licenses = physical_licenses
            
            # Use friendly names
            if agent_type != "NATIVE_SDK":
                friendly_name = {
                    'APP_AGENT': 'Java Agent',
                    'DOT_NET_APP_AGENT': '.NET Agent',
                    'NODEJS_APP_AGENT': 'NodeJS Agent',
                    'PYTHON_APP_AGENT': 'Python Agent',
                    'PHP_APP_AGENT': 'PHP Agent',
                    'GOLANG_SDK': 'Go Agent',
                    'WMB_AGENT': 'IIB Agent',
                    'MACHINE_AGENT': 'Machine Agent',
                    'DOT_NET_MACHINE_AGENT': '.NET Machine Agent',
                    'NATIVE_WEB_SERVER': 'Apache Agent'
                }.get(agent_type, agent_type)
                
                license_data.append({
                    'Agent Type': friendly_name,
                    'Container Nodes': container_df.shape[0],
                    'Physical Nodes': physical_df.shape[0],
                    'Physical Licenses (Mixed)': physical_licenses,
                    'Microservices Licenses (Mixed)': microservices_licenses,
                    'Standard Licenses': standard_licenses
                })
    
    return pd.DataFrame(license_data)


def parse_properties(data: Any, prefix: str) -> pd.Series:
    """
    Parse properties data into individual columns with prefix.
    
    Args:
        data: Dictionary or list data to parse
        prefix: Prefix to add to column names
        
    Returns:
        Series containing parsed data
    """
    if isinstance(data, dict):
        result = pd.Series(dtype='object')
        
        # Group all the disks together
        disk_data = {k: v for k, v in data.items() if k.startswith('Disk|')}
        if disk_data:
            result["Disk"] = str(disk_data)
        
        # Parse remaining data
        remaining_data = {k: v for k, v in data.items() if not k.startswith('Disk|')}
        result = pd.concat([result, pd.Series(remaining_data)])
        return result
    
    elif isinstance(data, list) and len(data) == 0:
        return pd.Series(dtype='object')
    else:
        return pd.Series(dtype='object')


def construct_snapshot_link(row: pd.Series, base_url: str) -> str:
    """
    Create deep link for snapshot data.
    
    Args:
        row: DataFrame row containing snapshot data
        base_url: Base URL for the AppDynamics controller
        
    Returns:
        Deep link URL for the snapshot
    """
    request_guid = str(row['requestGUID'])
    app_id = str(row['applicationId'])
    bt_id = str(row['businessTransactionId'])
    
    server_start_time = row['serverStartTime']
    a = server_start_time - 1800000
    b = server_start_time + 1800000
    sst_begin = str(a)
    sst_end = str(b)
    
    snapshot_link = (f"{base_url}/controller/#/location=APP_SNAPSHOT_VIEWER"
                    f"&requestGUID={request_guid}&application={app_id}"
                    f"&businessTransaction={bt_id}"
                    f"&rsdTime=Custom_Time_Range.BETWEEN_TIMES.{sst_end}.{sst_begin}.60"
                    f"&tab=overview&dashboardMode=force")
    
    return snapshot_link




