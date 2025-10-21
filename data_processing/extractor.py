"""
Main data extraction and processing logic.
"""
import pandas as pd
import datetime
from typing import Dict, List, Optional, Tuple
from api import AppDAPIClient
from utils import validate_json, validate_and_parse_xml, determine_availability, calculate_licenses, construct_snapshot_link, parse_event_entities, Logger


class AppDDataExtractor:
    """Main class for extracting and processing AppDynamics data."""
    
    def __init__(self, api_client: AppDAPIClient, config, logger: Logger | None = None):
        self.api_client = api_client
        self.config = config
        self.data = {}
        self.logger = logger
    
    def extract_applications(self, application_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Extract applications data."""
        if self.logger:
            self.logger.info("Retrieving applications...")
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
        if self.logger:
            self.logger.info(f"Retrieving business transactions for app {application_id}...")
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
        if self.logger:
            self.logger.info(f"Retrieving tiers for app {application_id}...")
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
        if self.logger:
            self.logger.info(f"Retrieving nodes for app {application_id}...")
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
        if self.logger:
            self.logger.info(f"Retrieving backends for app {application_id}...")
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
        if self.logger:
            self.logger.info(f"Retrieving health rules for app {application_id}...")
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
        if self.logger:
            self.logger.info(f"Retrieving snapshots for app {application_id}...")
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
        if self.logger:
            self.logger.info("Retrieving servers...")
        response, status = self.api_client.get_servers()
        if status != "valid":
            return pd.DataFrame()
        
        data, data_status = validate_json(response)
        if data_status != "valid":
            return pd.DataFrame()
        
        return pd.DataFrame(data)

    def extract_health_rule_violations(self, application_id: str, app_name: str, duration_mins: int) -> pd.DataFrame:
        """Extract health rule violations for an application."""
        if self.logger:
            self.logger.info(f"Retrieving health rule violations for app {application_id}...")
        response, status = self.api_client.get_health_rule_violations(
            application_id=application_id,
            time_range_type="BEFORE_NOW",
            duration_mins=duration_mins,
            output="XML",
        )
        if status != "valid" or not response:
            return pd.DataFrame()

        df, df_status = validate_and_parse_xml(response, xpath=".//policy-violation")
        if df_status != "valid" or df.empty:
            return pd.DataFrame()

        df = pd.DataFrame(df)
        df['app_id'] = application_id
        df['app_name'] = app_name
        # rename id for clarity
        if 'id' in df.columns:
            df.rename(columns={'id': 'violation_id'}, inplace=True)

        # convert times if present
        for col in [
            'startTimeInMillis', 'detectedTimeInMillis', 'endTimeInMillis'
        ]:
            if col in df.columns:
                try:
                    df[col.replace('InMillis', '')] = pd.to_datetime(df[col], unit='ms', errors='coerce')
                except Exception:
                    pass

        return df

    def extract_general_events(
        self,
        application_id: str,
        app_name: str,
        event_types: list,
        severities: list,
        duration_mins: int,
        tier: str | None = None,
    ) -> pd.DataFrame:
        """Extract general events for an application, handling pagination limits."""
        try:
            records = self.api_client.get_events_paginated(
                application_id=application_id,
                event_types=event_types,
                severities=severities,
                duration_mins=duration_mins,
                tier=tier,
            )
        except Exception:
            records = []

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df['app_id'] = application_id
        df['app_name'] = app_name

        # Standardize columns where possible
        if 'id' in df.columns:
            df.rename(columns={'id': 'event_id'}, inplace=True)
        if 'eventTime' in df.columns:
            try:
                df['eventTime'] = pd.to_datetime(df['eventTime'], unit='ms', errors='coerce')
            except Exception:
                pass

        # Flatten entity structures to readable strings when present
        for col in ['affectedEntities', 'triggeredEntity']:
            if col in df.columns:
                df[col] = df[col].apply(parse_event_entities)

        return df

    def extract_custom_events(
        self,
        application_id: str,
        app_name: str,
        severities: list,
        duration_mins: int,
        tier: str | None = None,
    ) -> pd.DataFrame:
        """Extract custom events (eventtype=CUSTOM)."""
        return self.extract_general_events(
            application_id=application_id,
            app_name=app_name,
            event_types=["CUSTOM"],
            severities=severities,
            duration_mins=duration_mins,
            tier=tier,
        )
    
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
                        pull_snapshots: bool = False,
                        # events
                        retrieve_health_rule_violations: bool = False,
                        retrieve_general_events: bool = False,
                        retrieve_custom_events: bool = False,
                        event_duration_mins: int = 60,
                        event_types: Optional[List[str]] = None,
                        event_severities: Optional[List[str]] = None,
                        custom_event_severities: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
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
            'license_usage': pd.DataFrame(),
            'health_rule_violations': pd.DataFrame(),
            'general_events': pd.DataFrame(),
            'custom_events': pd.DataFrame(),
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
                self.config.default_snapshot_duration if pull_snapshots else 0,
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

                    # Events extraction per app
                    if retrieve_health_rule_violations:
                        hrv_df = self.extract_health_rule_violations(app_id, app_name, event_duration_mins)
                        if not hrv_df.empty:
                            all_data['health_rule_violations'] = pd.concat([all_data['health_rule_violations'], hrv_df])

                    if retrieve_general_events and event_types:
                        ge_df = self.extract_general_events(
                            app_id,
                            app_name,
                            event_types=event_types,
                            severities=event_severities or ["WARN", "ERROR"],
                            duration_mins=event_duration_mins,
                        )
                        if not ge_df.empty:
                            all_data['general_events'] = pd.concat([all_data['general_events'], ge_df])

                    if retrieve_custom_events:
                        ce_df = self.extract_custom_events(
                            app_id,
                            app_name,
                            severities=custom_event_severities or ["INFO", "WARN", "ERROR"],
                            duration_mins=event_duration_mins,
                        )
                        if not ce_df.empty:
                            all_data['custom_events'] = pd.concat([all_data['custom_events'], ce_df])
        
        if retrieve_servers:
            all_data['servers'] = self.extract_servers()
            if not all_data['servers'].empty and calc_machine_availability:
                all_data['servers'] = self.add_availability_data(all_data['servers'], "server", self.config.default_machine_metric_duration)
        
        # Note: License calculation is moved to main.py after column renaming
        
        return all_data
