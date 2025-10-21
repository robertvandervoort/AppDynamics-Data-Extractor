"""
Streamlit UI components for AppDynamics Data Extractor.
"""
import streamlit as st
import pandas as pd
from typing import List, Optional, Dict, Any
from config import SecretsManager


def render_credentials_form(secrets_manager: SecretsManager) -> Dict[str, str]:
    """Render credentials input form."""
    secrets = secrets_manager.load_secrets()
    selected_account = ""
    api_client_name = ""
    api_key = ""
    
    if secrets:
        selected_account = secrets[0].get("account", "")
        api_client_name = secrets[0].get("api-client-name", "")
        api_key = secrets[0].get("api-key", "")
        account_options = [secret["account"] for secret in secrets] + ["Enter Manually"]
        selected_account = st.selectbox(
            "Account Name", 
            options=account_options, 
            index=account_options.index(selected_account) if selected_account in account_options else 0
        )
        
        if selected_account == "Enter Manually":
            account_name = st.text_input("Account Name", value="")
        else:
            account_name = selected_account
        
        # Populate fields dynamically based on account name
        api_client_name = ""
        api_key = ""
        for secret in secrets:
            if secret["account"] == account_name:
                api_client_name = secret.get("api-client-name", "")
                api_key = secret.get("api-key", "")
                break
    else:
        account_name = st.text_input("Account Name", value="")
    
    return {
        "account_name": account_name,
        "api_client_name": api_client_name,
        "api_key": api_key,
        "selected_account": selected_account
    }


def render_application_selection(applications_df: pd.DataFrame) -> List[str]:
    """Render application selection multiselect."""
    if applications_df.empty:
        return []
    
    # Create a list of tuples (app_id, app_name)
    app_names = [(row['app_id'], row['app_name']) for _, row in applications_df.iterrows()]
    
    # Insert "ALL APPS" at the beginning
    app_names.insert(0, ("ALL", "ALL APPS"))
    
    # Extract only the app_name for display in the multi-select
    display_names = [name for _, name in app_names]
    
    # Create the multi-select list
    selected_apps = st.multiselect("Select applications:", display_names)
    
    # Get the selected app_ids (including "ALL APPS" if selected)
    selected_app_ids = [app_id for app_id, name in app_names if name in selected_apps]
    
    return selected_app_ids


def render_configuration_form(config) -> Dict[str, Any]:
    """Render configuration form."""
    with st.form("config_form"):
        st.subheader("Configuration")
        
        # APM options
        retrieve_apm = st.checkbox("Retrieve APM (App, tiers, nodes, etc)?", value=True)
        
        if retrieve_apm:
            st.subheader("APM options")
            calc_apm_availability = st.checkbox("Analyze tier and node availability?", value=True)
            apm_metric_duration_mins = st.number_input(
                "How far to look back for APM availability? (mins)", 
                value=config.default_apm_metric_duration, min_value=0
            )
            
            pull_snapshots = st.checkbox("Retrieve transaction snapshots?", value=False)
            
            if pull_snapshots:
                st.subheader("Snapshot options")
                snapshot_duration_mins = st.number_input(
                    "How far to look back for snapshots? (mins)", 
                    value=config.default_snapshot_duration, min_value=0, max_value=20159
                )
                first_in_chain = st.checkbox("Capture only first in chain snapshots?", value=config.first_in_chain)
                need_exit_calls = st.checkbox("Return exit call data with snapshots?", value=config.need_exit_calls)
                need_props = st.checkbox("Return data collector data with snapshots?", value=config.need_props)
            else:
                snapshot_duration_mins = 0
                first_in_chain = config.first_in_chain
                need_exit_calls = config.need_exit_calls
                need_props = config.need_props
        else:
            calc_apm_availability = False
            apm_metric_duration_mins = 0
            pull_snapshots = False
            snapshot_duration_mins = 0
            first_in_chain = config.first_in_chain
            need_exit_calls = config.need_exit_calls
            need_props = config.need_props
        
        # Server options
        retrieve_servers = st.checkbox("Retrieve all machine agent data?", value=True)
        
        if retrieve_servers:
            st.subheader("Servers")
            calc_machine_availability = st.checkbox("Analyze server availability?", value=True)
            machine_metric_duration_mins = st.number_input(
                "How far to look back for machine availability? (mins)", 
                value=config.default_machine_metric_duration, min_value=0
            )
        else:
            calc_machine_availability = False
            machine_metric_duration_mins = 0
        
        # Events section
        st.subheader("Events")
        retrieve_health_rule_violations = st.checkbox("Get health rule violations?", value=False)

        if retrieve_health_rule_violations:
            with st.expander("Health Rule Violation Options", expanded=True):
                hrv_duration_mins = st.number_input(
                    "How far to look back for violations? (mins)",
                    value=config.default_event_duration, min_value=0
                )
                # HRV endpoint doesn't filter by severity at query; keep UI simple
                hrv_severities = ["WARN", "ERROR"]
        else:
            hrv_duration_mins = 0
            hrv_severities = []

        retrieve_general_events = st.checkbox("Get general events?", value=False)

        if retrieve_general_events:
            with st.expander("General Event Options", expanded=True):
                from config.event_types import EVENT_TYPES, SEVERITY_LEVELS

                event_duration_mins = st.number_input(
                    "How far to look back for events? (mins)",
                    value=config.default_event_duration, min_value=0
                )

                selected_event_types: List[str] = []
                for category, types in EVENT_TYPES.items():
                    st.write(f"**{category}**")
                    for event_type in types:
                        if st.checkbox(event_type, value=False, key=f"event_{event_type}"):
                            selected_event_types.append(event_type)

                event_severities = st.multiselect(
                    "Severity levels",
                    options=SEVERITY_LEVELS,
                    default=["WARN", "ERROR"]
                )
        else:
            event_duration_mins = 0
            selected_event_types = []
            event_severities = []

        retrieve_custom_events = st.checkbox("Get custom events?", value=False)

        if retrieve_custom_events:
            with st.expander("Custom Event Options", expanded=True):
                from config.event_types import SEVERITY_LEVELS
                custom_event_duration_mins = st.number_input(
                    "How far to look back for custom events? (mins)",
                    value=config.default_event_duration, min_value=0
                )
                custom_event_severities = st.multiselect(
                    "Severity levels",
                    options=SEVERITY_LEVELS,
                    default=["INFO", "WARN", "ERROR"]
                )
        else:
            custom_event_duration_mins = 0
            custom_event_severities = []

        # Debug options
        debug_output = st.checkbox("Debug output?", value=False)
        snes_sounds = False
        if debug_output:
            snes_sounds = st.checkbox("8-bit my debug!", value=False)
        
        # License processing option
        enable_license_processing = st.checkbox("Enable license processing?", value=False)
        
        # Submit button
        submitted = st.form_submit_button("Extract Data")
        
        return {
            "retrieve_apm": retrieve_apm,
            "retrieve_servers": retrieve_servers,
            "calc_apm_availability": calc_apm_availability,
            "calc_machine_availability": calc_machine_availability,
            "pull_snapshots": pull_snapshots,
            "apm_metric_duration_mins": apm_metric_duration_mins,
            "machine_metric_duration_mins": machine_metric_duration_mins,
            "snapshot_duration_mins": snapshot_duration_mins,
            "first_in_chain": first_in_chain,
            "need_exit_calls": need_exit_calls,
            "need_props": need_props,
            "debug_output": debug_output,
            "snes_sounds": snes_sounds,
            "enable_license_processing": enable_license_processing,
            "submitted": submitted,
            # events
            "retrieve_health_rule_violations": retrieve_health_rule_violations,
            "hrv_duration_mins": hrv_duration_mins,
            "hrv_severities": hrv_severities,
            "retrieve_general_events": retrieve_general_events,
            "event_duration_mins": event_duration_mins,
            "selected_event_types": selected_event_types,
            "event_severities": event_severities,
            "retrieve_custom_events": retrieve_custom_events,
            "custom_event_duration_mins": custom_event_duration_mins,
            "custom_event_severities": custom_event_severities,
        }


def render_debug_info(df: pd.DataFrame, df_name: str, num_lines: int = 10):
    """Render debug information for a DataFrame."""
    st.subheader(f"Debug Info: {df_name}")
    st.write(f"Shape (rows, cols): {df.shape}")
    st.write(f"First {num_lines} rows:")
    st.write(df.head(num_lines).to_markdown(index=False, numalign='left', stralign='left'))


def render_progress_status(message: str, expanded: bool = True):
    """Render progress status with optional expansion."""
    return st.status(message, expanded=expanded)


def render_results_summary(data: Dict[str, pd.DataFrame]):
    """Render summary of extracted data."""
    st.subheader("Extraction Summary")
    
    summary_data = []
    for name, df in data.items():
        if not df.empty:
            summary_data.append({
                "Data Type": name.replace('_', ' ').title(),
                "Records": len(df),
                "Columns": len(df.columns)
            })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.warning("No data was extracted.")



