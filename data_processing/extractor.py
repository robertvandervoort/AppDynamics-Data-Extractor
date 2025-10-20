"""
Main data extraction and processing logic.
"""
import pandas as pd
import datetime
from typing import Dict, List, Optional, Tuple
from api import AppDAPIClient
from utils import validate_json, validate_and_parse_xml, determine_availability, calculate_licenses, construct_snapshot_link


class AppDDataExtractor:
    """Main class for extracting and processing AppDynamics data."""
    
    def __init__(self, api_client: AppDAPIClient, config):
        self.api_client = api_client
        self.config = config
        self.data = {}
    
    def extract_applications(self, application_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Extract applications data."""
        if application_ids and len(application_ids) == 1 and application_ids[0] != "ALL":
            response, status = self.api_client.get_applications(application_ids[0])
        else:
            response, status = self.api_client.get_applications()
        
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df = df.rename(columns={"id": "app_id", "name": "app_name"})
        
        if application_ids and "ALL" not in application_ids:
            df = df[df['app_id'].isin(application_ids)]
        
        return df
    
    def extract_business_transactions(self, application_id: str) -> pd.DataFrame:
        """Extract business transactions for an application."""
        response, status = self.api_client.get_business_transactions(application_id)
        if status != "valid":
            return pd.DataFrame()
        
        try:
            data, data_status = validate_and_parse_xml(response, xpath=".//business-transaction")
            if data_status != "valid":
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['app_id'] = application_id
            df = df.rename(columns={"id": "bt_id", "name": "bt_name"})
            return df
        except Exception as e:
            print(f"Error parsing business transactions XML: {e}")
            return pd.DataFrame()
    
    def extract_tiers(self, application_id: str, app_name: str) -> pd.DataFrame:
        """Extract tiers for an application."""
        response, status = self.api_client.get_tiers(application_id)
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['app_id'] = application_id
        df['app_name'] = app_name
        df = df.rename(columns={"id": "tier_id", "name": "tier_name"})
        return df
    
    def extract_nodes(self, application_id: str, app_name: str) -> pd.DataFrame:
        """Extract nodes for an application."""
        response, status = self.api_client.get_app_nodes(application_id)
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['app_id'] = application_id
        df['app_name'] = app_name
        df = df.rename(columns={"id": "node_id", "name": "node_name"})
        
        # Clean up machine name
        df['machineName-cleaned'] = df['machineName'].astype(str).str.replace('-java-MA$', '', regex=True)
        return df
    
    def extract_backends(self, application_id: str, app_name: str) -> pd.DataFrame:
        """Extract backends for an application."""
        response, status = self.api_client.get_app_backends(application_id)
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['app_id'] = application_id
        df['app_name'] = app_name
        df = df.rename(columns={"id": "backend_id", "name": "backend_name"})
        return df
    
    def extract_health_rules(self, application_id: str, app_name: str) -> pd.DataFrame:
        """Extract health rules for an application."""
        response, status = self.api_client.get_health_rules(application_id)
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['app_id'] = application_id
        df['app_name'] = app_name
        return df
    
    def extract_snapshots(self, application_id: str, duration_mins: int) -> pd.DataFrame:
        """Extract snapshots for an application."""
        response, status = self.api_client.get_snapshots(
            application_id, duration_mins, 
            self.config.first_in_chain, 
            self.config.need_exit_calls, 
            self.config.need_props
        )
        if status != "valid":
            return pd.DataFrame()
        
        try:
            data, data_status = validate_and_parse_xml(response, xpath="//request-segment-data")
            if data_status != "valid":
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['app_id'] = application_id
            
            # Create deep links
            df['snapshot_link'] = df.apply(
                lambda row: construct_snapshot_link(row, self.api_client.authenticator.credentials.base_url), 
                axis=1
            )
            return df
        except Exception as e:
            print(f"Error parsing snapshots XML: {e}")
            return pd.DataFrame()
    
    def extract_servers(self) -> pd.DataFrame:
        """Extract servers/machines data."""
        response, status = self.api_client.get_servers()
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        return pd.DataFrame(data)
    
    def add_availability_data(self, df: pd.DataFrame, data_type: str, 
                            duration_mins: int) -> pd.DataFrame:
        """Add availability data to a DataFrame."""
        if df.empty:
            return df
        
        def get_availability(row):
            if data_type == "tier":
                response, status = self.api_client.get_apm_availability(
                    "tier", row['app_name'], row['tier_name'], 
                    row['agentType'], "", duration_mins
                )
            elif data_type == "node":
                response, status = self.api_client.get_apm_availability(
                    "node", row['app_name'], row['tierName'], 
                    row['agentType'], row['node_name'], duration_mins
                )
            else:  # server
                response, status = self.api_client.get_sim_availability(
                    row['hierarchy'], row['hostId'], row['type'], duration_mins
                )
            
            if status == "valid":
                data, data_status = validate_json(response)
                if data_status == "valid":
                    return determine_availability(data, data_status)
            
            return None, None
        
        if data_type in ["tier", "node"]:
            result_series = df.apply(get_availability, axis=1)
            if data_type == "tier":
                df['Last Seen Tier'] = result_series.str[0]
                df['Last Seen Tier - Node Count'] = result_series.str[1]
            else:
                df['Last Seen Node'] = result_series.str[0]
        else:  # server
            df['Last Seen Server'] = df.apply(lambda row: get_availability(row)[0], axis=1)
        
        return df
    
    def process_all_data(self, application_ids: Optional[List[str]] = None, 
                        retrieve_apm: bool = True, retrieve_servers: bool = True,
                        calc_apm_availability: bool = True, calc_machine_availability: bool = True,
                        pull_snapshots: bool = False) -> Dict[str, pd.DataFrame]:
        """Process all data extraction based on configuration."""
        
        # Initialize data containers
        all_data = {
            'applications': pd.DataFrame(),
            'business_transactions': pd.DataFrame(),
            'tiers': pd.DataFrame(),
            'nodes': pd.DataFrame(),
            'backends': pd.DataFrame(),
            'health_rules': pd.DataFrame(),
            'snapshots': pd.DataFrame(),
            'servers': pd.DataFrame(),
            'license_usage': pd.DataFrame()
        }
        
        # Create information sheet
        now = datetime.datetime.now()
        current_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        all_data['information'] = pd.DataFrame({
            "setting": [
                "RUN_DATE", "BASE_URL", "APPDYNAMICS_ACCOUNT_NAME", "APPDYNAMICS_API_CLIENT",
                "Selected Apps", "or application id", "APM availability (mins)", 
                "Machine availability (mins)", "metric_rollup", "Retrieve snapshots", 
                "Snapshot range (mins)"
            ],
            "value": [
                current_date_time, self.api_client.authenticator.credentials.base_url,
                self.api_client.authenticator.credentials.account_name,
                self.api_client.authenticator.credentials.api_client,
                application_ids, "", 
                self.config.default_apm_metric_duration if calc_apm_availability else 0,
                self.config.default_machine_metric_duration if calc_machine_availability else 0,
                self.config.metric_rollup, pull_snapshots,
                self.config.default_snapshot_duration if pull_snapshots else 0
            ]
        })
        
        if retrieve_apm:
            # Extract applications
            all_data['applications'] = self.extract_applications(application_ids)
            
            if not all_data['applications'].empty:
                # Process each application
                for _, application in all_data['applications'].iterrows():
                    app_id = application["app_id"]
                    app_name = application["app_name"]
                    
                    # Extract data for this application
                    bts_df = self.extract_business_transactions(app_id)
                    if not bts_df.empty:
                        all_data['business_transactions'] = pd.concat([all_data['business_transactions'], bts_df])
                    
                    tiers_df = self.extract_tiers(app_id, app_name)
                    if not tiers_df.empty:
                        if calc_apm_availability:
                            tiers_df = self.add_availability_data(tiers_df, "tier", self.config.default_apm_metric_duration)
                        all_data['tiers'] = pd.concat([all_data['tiers'], tiers_df])
                    
                    nodes_df = self.extract_nodes(app_id, app_name)
                    if not nodes_df.empty:
                        if calc_apm_availability:
                            nodes_df = self.add_availability_data(nodes_df, "node", self.config.default_apm_metric_duration)
                        all_data['nodes'] = pd.concat([all_data['nodes'], nodes_df])
                    
                    backends_df = self.extract_backends(app_id, app_name)
                    if not backends_df.empty:
                        all_data['backends'] = pd.concat([all_data['backends'], backends_df])
                    
                    health_rules_df = self.extract_health_rules(app_id, app_name)
                    if not health_rules_df.empty:
                        all_data['health_rules'] = pd.concat([all_data['health_rules'], health_rules_df])
                    
                    if pull_snapshots:
                        snapshots_df = self.extract_snapshots(app_id, self.config.default_snapshot_duration)
                        if not snapshots_df.empty:
                            all_data['snapshots'] = pd.concat([all_data['snapshots'], snapshots_df])
        
        if retrieve_servers:
            all_data['servers'] = self.extract_servers()
            if not all_data['servers'].empty and calc_machine_availability:
                all_data['servers'] = self.add_availability_data(all_data['servers'], "server", self.config.default_machine_metric_duration)
        
        # Note: License calculation is moved to main.py after column renaming
        
        return all_data
