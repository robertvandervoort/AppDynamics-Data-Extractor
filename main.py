"""
Main application entry point for AppDynamics Data Extractor.
"""
import streamlit as st
import pandas as pd
import datetime
import os
import sys
import subprocess
import gc
from typing import Dict, List, Optional

# Import our modular components
from config import AppConfig, APICredentials, SecretsManager, get_config
from auth import AppDAuthenticator
from api import AppDAPIClient
from data_processing import AppDDataExtractor
from ui import (
    render_credentials_form, render_application_selection, render_configuration_form,
    render_debug_info, render_progress_status, render_results_summary
)
from utils import validate_json, Logger


def play_sound(file_path: str):
    """Play sound file using pygame."""
    try:
        import pygame
        pygame.mixer.init()
        sound = pygame.mixer.Sound(file_path)
        sound.play()
    except Exception as e:
        print(f"Error playing sound: {e}")


def write_excel_output(data: Dict[str, pd.DataFrame], output_file: str, config: AppConfig):
    """Write data to Excel file with formatting."""
    try:
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Define formats
            header_format = workbook.add_format({
                'bg_color': '#ADD8E6',
                'bold': True,
                'align': 'left',
                'border': 1,
                'font_size': 14
            })
            odd_row_format = workbook.add_format({
                'bg_color': '#C2C2C2',
                'border': 1
            })
            even_row_format = workbook.add_format({
                'border': 1
            })
            
            # Sheet mapping
            sheet_mapping = [
                ("Info", "information"),
                ("License Usage", "license_usage"),
                ("Applications", "applications"),
                ("BTs", "business_transactions"),
                ("Tiers", "tiers"),
                ("Nodes", "nodes"),
                ("Backends", "backends"),
                ("Health Rules", "health_rules"),
                ("Snapshots", "snapshots"),
                ("Servers", "servers"),
                ("Health Rule Violations", "health_rule_violations"),
                ("General Events", "general_events"),
                ("Custom Events", "custom_events"),
            ]
            
            for sheet_name, data_key in sheet_mapping:
                df = data.get(data_key, pd.DataFrame())
                
                if not df.empty:
                    # Convert column names to strings
                    df.columns = df.columns.astype(str)

                    # Sort columns alphabetically
                    column_order = sorted(df.columns)
                    df = df[column_order]

                    # Replace NaNs only in object columns to avoid dtype warnings
                    obj_cols = df.select_dtypes(include=['object']).columns
                    if len(obj_cols) > 0:
                        df[obj_cols] = df[obj_cols].fillna('')
                    
                    # Write to Excel
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Get worksheet and apply formatting
                    worksheet = writer.sheets[sheet_name]
                    
                    # Auto-adjust column widths and add formatting
                    for col_num, value in enumerate(df.columns.values):
                        try:
                            column_length = max(df[value].astype(str).map(len).max(), len(value))
                        except:
                            column_length = 10
                        
                        # Set max column length
                        if column_length > 50:
                            column_length = 50
                        
                        worksheet.set_column(col_num, col_num, column_length + 2)
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Apply alternating row colors (except for Snapshots)
                    if sheet_name != "Snapshots":
                        for row_num in range(1, df.shape[0] + 1):
                            if row_num % 2 == 1:
                                worksheet.set_row(row_num, cell_format=odd_row_format)
                            else:
                                worksheet.set_row(row_num, cell_format=even_row_format)
                    
                    # Special formatting for Snapshots sheet
                    if sheet_name == "Snapshots" and 'userExperience' in df.columns:
                        for row_num in range(1, df.shape[0] + 1):
                            user_experience = df.loc[row_num - 1, 'userExperience']
                            
                            color_map = {
                                'NORMAL': '#90EE90',
                                'ERROR': '#FA3B37',
                                'SLOW': '#FFFF80',
                                'VERY_SLOW': '#FC9C2D',
                                'STALL': '#FF69CD'
                            }
                            
                            if user_experience in color_map:
                                cell_format = workbook.add_format({'bg_color': color_map[user_experience], 'border': 1})
                                for col_num in range(df.shape[1]):
                                    cell_value = df.loc[row_num - 1, df.columns[col_num]]
                                    
                                    # Handle list values
                                    if isinstance(cell_value, list):
                                        if len(cell_value) > 0:
                                            cell_value = str(cell_value[0])
                                        else:
                                            cell_value = ""
                                    
                                    worksheet.write(row_num, col_num, cell_value, cell_format)
                else:
                    st.write(f"{sheet_name} empty, skipping write.")
            
            st.write("*Finished.* :sunglasses:")
            
    except PermissionError:
        st.warning(f"Unable to write to {output_file}. Please check permissions.")
        return False
    except Exception as e:
        st.error(f"An error occurred while writing the file: {e}")
        return False
    
    return True


def main():
    """Main application function."""
    st.title("AppDynamics Data Extractor")
    st.markdown('<h2 text-align: center>not DEXTER</h2>', unsafe_allow_html=True)
    
    # Initialize configuration and secrets manager
    config = get_config()
    secrets_manager = SecretsManager()
    
    # Render credentials form
    credentials = render_credentials_form(secrets_manager)
    
    # Connect button
    connect_button = st.button("Connect")
    
    # Handle connection
    if connect_button:
        if not credentials["account_name"] or not credentials["api_client_name"] or not credentials["api_key"]:
            st.error("Please fill in all credential fields.")
            return
        
        # Create API credentials and authenticator
        api_credentials = APICredentials(
            account_name=credentials["account_name"],
            api_client=credentials["api_client_name"],
            api_secret=credentials["api_key"]
        )
        
        authenticator = AppDAuthenticator(api_credentials, config.verify_ssl)
        
        if authenticator.authenticate():
            # Get applications
            # Create logger with a temporary UI writer (patched after status is created)
            logger = Logger(debug=config.debug)
            api_client = AppDAPIClient(authenticator, logger=logger)
            response, status = api_client.get_applications()
            
            if status == "valid":
                data, data_status = validate_json(response)
                if data_status == "valid":
                    applications_df = pd.DataFrame(data)
                    applications_df = applications_df.rename(columns={"id": "app_id", "name": "app_name"})
                    st.session_state['applications_df'] = applications_df
                    st.session_state['api_client'] = api_client
                    st.session_state['config'] = config
                    st.success("Connected successfully!")
                    st.rerun()
                else:
                    st.error("Failed to retrieve applications.")
            else:
                st.error("Failed to connect to AppDynamics.")
        else:
            st.error("Authentication failed. Please check your credentials.")
    
    # Application selection
    if 'applications_df' in st.session_state:
        applications_df = st.session_state['applications_df']
        selected_app_ids = render_application_selection(applications_df)
        
        st.info("***Note: license usage analysis (BETA) requires APM and server data***")
        
        # Configuration form
        config_data = render_configuration_form(config)
        
        # Save credentials button
        if st.button("Save Credentials"):
            if secrets_manager.add_or_update_secret(
                credentials["account_name"],
                credentials["api_client_name"],
                credentials["api_key"]
            ):
                st.success("Credentials saved!")
            else:
                st.error("Failed to save credentials.")
        
        # Main extraction logic
        if config_data["submitted"] and (config_data["retrieve_apm"] or config_data["retrieve_servers"]):
            if config_data["snes_sounds"]:
                play_sound("sounds/smb_jump-small.wav")
            
            # Validate inputs
            if config_data["retrieve_apm"] and not selected_app_ids and not config_data["retrieve_servers"]:
                st.error("❌ **Application Selection Required**")
                st.error("You must select at least one application to continue with APM data extraction.")
                st.info("💡 **Tip:** Use the 'Select applications' dropdown above to choose which applications to analyze.")
                return
            
            # Update configuration
            config.debug = config_data["debug_output"]
            config.snes_sounds = config_data["snes_sounds"]
            config.default_apm_metric_duration = config_data["apm_metric_duration_mins"]
            config.default_machine_metric_duration = config_data["machine_metric_duration_mins"]
            config.default_snapshot_duration = config_data["snapshot_duration_mins"]
            config.first_in_chain = config_data["first_in_chain"]
            config.need_exit_calls = config_data["need_exit_calls"]
            config.need_props = config_data["need_props"]
            
            # Create output directory if it doesn't exist
            output_dir = "output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Generate output filename
            output_file = os.path.join(output_dir, f"{credentials['account_name']}_analysis_{datetime.date.today().strftime('%m-%d-%Y')}.xlsx")
            
            # Get API client from session state
            api_client = st.session_state.get('api_client')
            if not api_client:
                st.error("Please connect first.")
                return
            
            # Create data extractor
            extractor = AppDDataExtractor(api_client, config, logger=logger)
            
            # Process data
            with render_progress_status("Extracting data...", expanded=True) as status:
                # Connect logger to UI as soon as status exists
                logger.attach_ui_writer(lambda msg: status.write(msg))
                # Also maintain a scrolling text area for logs
                log_container = st.empty()
                logger.attach_ui_writer(lambda msg: log_container.write(msg))
                st.write(f"Logging into controller at {api_client.authenticator.credentials.base_url}...")
                
                # Extract all data
                all_data = extractor.process_all_data(
                    application_ids=selected_app_ids if selected_app_ids else None,
                    retrieve_apm=config_data["retrieve_apm"],
                    retrieve_servers=config_data["retrieve_servers"],
                    calc_apm_availability=config_data["calc_apm_availability"],
                    calc_machine_availability=config_data["calc_machine_availability"],
                    pull_snapshots=config_data["pull_snapshots"],
                    # events
                    retrieve_health_rule_violations=config_data["retrieve_health_rule_violations"],
                    retrieve_general_events=config_data["retrieve_general_events"],
                    retrieve_custom_events=config_data["retrieve_custom_events"],
                    event_duration_mins=(
                        config_data["event_duration_mins"]
                        if config_data["retrieve_general_events"] or config_data["retrieve_custom_events"]
                        else (config_data["hrv_duration_mins"] if config_data["retrieve_health_rule_violations"] else 60)
                    ),
                    event_types=config_data.get("selected_event_types"),
                    event_severities=config_data.get("event_severities"),
                    custom_event_severities=config_data.get("custom_event_severities"),
                )
                
                # Convert epoch timestamps to datetime
                for key, df in all_data.items():
                    if not df.empty and key in ['tiers', 'nodes', 'servers']:
                        if key == 'tiers' and 'Last Seen Tier' in df.columns:
                            df['Last Seen Tier'] = pd.to_datetime(df['Last Seen Tier'], unit='ms')
                            df['Last Seen Tier'] = df['Last Seen Tier'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                        elif key == 'nodes' and 'Last Seen Node' in df.columns:
                            df['Last Seen Node'] = pd.to_datetime(df['Last Seen Node'], unit='ms')
                            df['Last Seen Node'] = df['Last Seen Node'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                        elif key == 'servers' and 'Last Seen Server' in df.columns:
                            df['Last Seen Server'] = pd.to_datetime(df['Last Seen Server'], unit='ms')
                            df['Last Seen Server'] = df['Last Seen Server'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                
                # Merge snapshots data if available
                if not all_data['snapshots'].empty and not all_data['applications'].empty:
                    if not all_data['tiers'].empty and not all_data['nodes'].empty and not all_data['business_transactions'].empty:
                        st.write("Merging snapshots data...")
                        
                        all_snapshots_merged_df = pd.merge(
                            all_data['snapshots'], all_data['tiers'], 
                            left_on="applicationComponentId", right_on="tier_id", 
                            how="left", suffixes=(None, "_tier")
                        ).merge(
                            all_data['nodes'], left_on="applicationComponentNodeId", 
                            right_on="node_id", how="left", suffixes=(None, "_node")
                        ).merge(
                            all_data['business_transactions'], left_on="businessTransactionId", 
                            right_on="bt_id", how="left", suffixes=(None, "_bt")
                        ).merge(
                            all_data['applications'], left_on="applicationId", 
                            right_on="app_id", how="left", suffixes=(None, "_app")
                        )
                        
                        # Clean up merged data
                        columns_to_drop = [
                            'accountGuid', 'app_id_tier', 'app_id_node', 'app_id_app',
                            'app_name_app', 'app_name_node', 'agentType_node', 'applicationId',
                            'appAgentPresent', 'bt_id', 'description', 'description_app',
                            'entryPointTypeString', 'id', 'ipAddresses', 'localID',
                            'nodeUniqueLocalId', 'numberOfNodes', 'serverStartTime',
                            'tierId_bt', 'tierName_bt'
                        ]
                        all_snapshots_merged_df.drop(columns=columns_to_drop, inplace=True, errors='ignore')
                        
                        # Convert timestamps
                        all_snapshots_merged_df['start_time'] = pd.to_datetime(all_snapshots_merged_df['serverStartTime'], unit='ms', errors="ignore")
                        all_snapshots_merged_df['local_start_time'] = pd.to_datetime(all_snapshots_merged_df['localStartTime'], unit='ms', errors="ignore")
                        all_snapshots_merged_df['start_time'] = all_snapshots_merged_df['start_time'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                        all_snapshots_merged_df['local_start_time'] = all_snapshots_merged_df['local_start_time'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                        
                        all_data['snapshots'] = all_snapshots_merged_df
                        
                        # Clean up memory
                        del all_snapshots_merged_df
                        gc.collect()
                
                # Merge nodes and servers if both are available
                if (config_data["retrieve_apm"] and config_data["retrieve_servers"] and 
                    not all_data['nodes'].empty and not all_data['servers'].empty):
                    
                    st.write("Merging node and machine data...")
                    
                    all_nodes_merged_df = pd.merge(
                        all_data['nodes'], all_data['servers'], 
                        left_on="machineName-cleaned", right_on="name", 
                        how="left", suffixes=(None, "_servers")
                    )
                    
                    # Clean up memory
                    del all_data['nodes']
                    gc.collect()
                    
                    # Normalize data if enabled
                    if config.normalize_data:
                        try:
                            from utils.data_processors import parse_properties
                            
                            columns_to_parse = ['properties', 'memory', 'cpus']
                            for col in columns_to_parse:
                                if col in all_nodes_merged_df.columns:
                                    parsed_df = all_nodes_merged_df[col].apply(parse_properties, args=(col,))
                                    all_nodes_merged_df = all_nodes_merged_df.join(parsed_df)
                                    all_nodes_merged_df.drop(columns=[col], inplace=True)
                            
                            # Extract specific values
                            if 'Physical' in all_nodes_merged_df.columns:
                                all_nodes_merged_df['Physical'] = all_nodes_merged_df['Physical'].apply(
                                    lambda x: x['sizeMb'] if isinstance(x, dict) and 'sizeMb' in x else x
                                )
                            if 'Swap' in all_nodes_merged_df.columns:
                                all_nodes_merged_df['Swap'] = all_nodes_merged_df['Swap'].apply(
                                    lambda x: x['sizeMb'] if isinstance(x, dict) and 'sizeMb' in x else x
                                )
                        except Exception as e:
                            st.write(f"An error occurred while parsing columns: {e}")
                    
                    # Rename columns for better readability
                    column_renames = {
                        'agentType': 'Node - Agent Type',
                        'appAgentVersion': 'App Agent Version',
                        'app_name': 'Application Name',
                        'AppDynamics|Agent|Agent version': 'Machine Agent Version',
                        'AppDynamics|Agent|Build Number': 'Machine Agent Build #',
                        'AppDynamics|Agent|Install Directory': 'Machine Agent Path',
                        'AppDynamics|Machine Type': 'Machine Agent Type',
                        'Bios|Version': 'BIOS Version',
                        'node_name': 'Node Name',
                        'OS|Architecture': 'OS Arch',
                        'OS|Kernel|Release': 'OS Version',
                        'OS|Kernel|Name': 'OS Name',
                        'Physical': 'RAM MB',
                        'Swap': 'SWAP MB',
                        'Processor|Logical Core Count': 'CPU Logical Cores',
                        'Processor|Physical Core Count': 'CPU Physical Cores',
                        'tierName': 'Tier Name',
                        'Total|CPU|Logical Processor Count': 'CPU Total Logical Cores',
                        'type_servers': 'Server Type',
                        'type': 'Tier Type',
                        'volumes': 'Volumes',
                        'vCPU': 'CPU vCPU'
                    }
                    all_nodes_merged_df.rename(columns=column_renames, inplace=True, errors='ignore')
                    
                    # Drop unnecessary columns
                    columns_to_drop = [
                        'agentConfig', 'AppDynamics|Agent|JVM Info', 'AppDynamics|Agent|Agent Pid',
                        'AppDynamics|Agent|Machine Info', 'controllerConfig', 'ipAddresses',
                        'machineAgentVersion', 'nodeUniqueLocalId'
                    ]
                    all_nodes_merged_df.drop(columns=columns_to_drop, inplace=True, errors='ignore')
                    
                    all_data['nodes'] = all_nodes_merged_df
                    
                    # Generate license usage after column renaming
                    if config_data["enable_license_processing"] and not all_nodes_merged_df.empty:
                        st.write("Generating license usage information...")
                        from utils.data_processors import calculate_licenses
                        all_data['license_usage'] = calculate_licenses(all_nodes_merged_df)
                    else:
                        if not config_data["enable_license_processing"]:
                            st.write("Skipping license usage reporting - license processing is disabled.")
                        else:
                            st.write("Skipping license usage reporting - no merged node data available.")
                        all_data['license_usage'] = pd.DataFrame()
                else:
                    # No merged data available
                    if config_data["enable_license_processing"]:
                        st.write("Skipping license usage reporting - please run with both APM and server data options checked.")
                    else:
                        st.write("Skipping license usage reporting - license processing is disabled.")
                    all_data['license_usage'] = pd.DataFrame()
                
                # Write output
                absolute_path = os.path.abspath(output_file)
                st.write(f"Writing output to file: {output_file}")
                st.info(f"📁 **Full path:** `{absolute_path}`")
                
                if write_excel_output(all_data, output_file, config):
                    status.update(label="Extraction complete!", state="complete", expanded=False)
                    
                    # Open the Excel file
                    try:
                        if sys.platform == "win32":
                            os.startfile(output_file)
                        elif sys.platform == "darwin":  # macOS
                            subprocess.call(["open", output_file])
                        else:  # Linux or other Unix-like systems
                            # Try xdg-open first, then fall back to other methods
                            try:
                                subprocess.call(["xdg-open", output_file])
                            except FileNotFoundError:
                                # Fallback: try to open with default application
                                try:
                                    subprocess.call(["xdg-open", output_file], check=False)
                                except:
                                    # If all else fails, just inform the user where the file is
                                    absolute_path = os.path.abspath(output_file)
                                    print(f"Excel file created: {output_file}")
                                    st.info(f"✅ **Excel file created:** `{absolute_path}`")
                    except Exception as e:
                        absolute_path = os.path.abspath(output_file)
                        print(f"Could not automatically open Excel file: {e}")
                        print(f"Excel file created: {output_file}")
                        st.info(f"✅ **Excel file created:** `{absolute_path}`")
                else:
                    status.update(label="Extraction failed!", state="error", expanded=True)


if __name__ == "__main__":
    main()
