"""
AppDynamics API client module.
"""
import requests
import pandas as pd
from io import StringIO
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import quote
from auth import AppDAuthenticator
from utils import Logger


class AppDAPIClient:
    """Client for AppDynamics REST API calls."""
    
    def __init__(self, authenticator: AppDAuthenticator, logger: Optional[Logger] = None):
        self.authenticator = authenticator
        self.logger = logger
    
    def _make_request(self, method: str, url: str, **kwargs) -> Tuple[Optional[requests.Response], str]:
        """
        Make authenticated API request with error handling.
        
        Returns:
            Tuple of (response, status) where status is 'valid', 'error', or 'empty'
        """
        if not self.authenticator.ensure_authenticated():
            if self.logger:
                self.logger.error("Authentication not valid; cannot make request")
            return None, "error"
        
        session = self.authenticator.get_session()
        if not session:
            return None, "error"
        
        try:
            if self.logger:
                self.logger.debug(f"HTTP {method} {url}")
            response = session.request(method, url, verify=self.authenticator.verify_ssl, **kwargs)
            response.raise_for_status()
            if self.logger:
                self.logger.debug(f"HTTP {response.status_code} OK for {url}")
            return response, "valid"
        except requests.exceptions.HTTPError as err:
            error_map = {
                400: "Bad Request - The request was invalid.",
                401: "Unauthorized - Authentication failed.",
                403: "Forbidden - You don't have permission to access this resource.",
                404: "Not Found - The resource could not be found.",
                500: "Internal Server Error - Something went wrong on the server.",
            }
            error_explanation = error_map.get(err.response.status_code, "Unknown HTTP Error")
            if self.logger:
                self.logger.error(f"HTTP Error {err.response.status_code}: {error_explanation}")
            else:
                print(f"HTTP Error: {err.response.status_code} - {error_explanation}")
            return None, "error"
        except requests.exceptions.RequestException as err:
            if isinstance(err, requests.exceptions.ConnectionError):
                if self.logger:
                    self.logger.error("Connection Error: Failed to establish a new connection.")
                else:
                    print("Connection Error: Failed to establish a new connection.")
            else:
                if self.logger:
                    self.logger.error(f"Request Exception: {err}")
                else:
                    print(f"Request Exception: {err}")
            return None, "error"
        except Exception as err:
            if self.logger:
                self.logger.error(f"Unexpected Error: {type(err).__name__}: {err}")
            else:
                print(f"Unexpected Error: {type(err).__name__}: {err}")
            return None, "error"
    
    def _urlencode_string(self, text: str) -> str:
        """Make app, tier or node names URL compatible for REST calls."""
        if not isinstance(text, str):
            text = str(text)
        return quote(text, safe='/', encoding=None, errors=None)
    
    def get_applications(self, application_id: Optional[str] = None) -> Tuple[Optional[requests.Response], str]:
        """Get a list of all applications or a specific application."""
        if application_id:
            url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}?output=json"
        else:
            url = f"{self.authenticator.credentials.base_url}/controller/rest/applications?output=json"
        
        return self._make_request("GET", url)
    
    def get_tiers(self, application_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get tiers for a specific application."""
        url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/tiers?output=json"
        return self._make_request("GET", url)
    
    def get_app_nodes(self, application_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get all nodes in an application."""
        url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/nodes?output=json"
        return self._make_request("GET", url)
    
    def get_tier_nodes(self, application_id: str, tier_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get nodes in a specific tier."""
        url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/tiers/{tier_id}/nodes?output=json"
        return self._make_request("GET", url)
    
    def get_app_backends(self, application_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get backends for a specific application."""
        url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/backends?output=json"
        return self._make_request("GET", url)
    
    def get_business_transactions(self, application_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get business transactions for a specific application."""
        url = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/business-transactions"
        return self._make_request("GET", url)
    
    def get_health_rules(self, application_id: str) -> Tuple[Optional[requests.Response], str]:
        """Get health rules for a specific application."""
        url = f"{self.authenticator.credentials.base_url}/controller/alerting/rest/v1/applications/{application_id}/health-rules"
        return self._make_request("GET", url)
    
    def get_snapshots(self, application_id: str, duration_mins: int, 
                     first_in_chain: bool = True, need_exit_calls: bool = False, 
                     need_props: bool = False) -> Tuple[Optional[requests.Response], str]:
        """Get transaction snapshots for a specific application."""
        url = (f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/request-snapshots"
               f"?time-range-type=BEFORE_NOW&duration-in-mins={duration_mins}"
               f"&first-in-chain={str(first_in_chain).lower()}"
               f"&need-exit-calls={str(need_exit_calls).lower()}"
               f"&need-props={str(need_props).lower()}"
               f"&maximum-results=1000000")
        return self._make_request("GET", url)
    
    def get_servers(self) -> Tuple[Optional[requests.Response], str]:
        """Get all servers/machines."""
        url = f"{self.authenticator.credentials.base_url}/controller/sim/v2/user/machines"
        return self._make_request("GET", url)
    
    def get_sim_availability(self, hierarchy_list: list, host_id: str, 
                           server_type: str, duration_mins: int) -> Tuple[Optional[requests.Response], str]:
        """Get server availability metrics."""
        hierarchy = "%5C%7C".join(hierarchy_list)
        
        if server_type == "PHYSICAL":
            metric_path = (f"Application%20Infrastructure%20Performance%7CRoot%5C%7C{hierarchy}"
                          f"%7CIndividual%20Nodes%7C{host_id}%7CHardware%20Resources%7CMachine%7CAvailability")
        else:  # CONTAINER
            metric_path = (f"Application%20Infrastructure%20Performance%7CRoot%5C%7C{hierarchy}"
                          f"%7CIndividual%20Nodes%7C{host_id}%7CHardware%20Resources%7CCPU%7C%25Busy")
        
        url = (f"{self.authenticator.credentials.base_url}/controller/rest/applications/"
               f"Server%20%26%20Infrastructure%20Monitoring/metric-data"
               f"?metric-path={metric_path}&time-range-type=BEFORE_NOW"
               f"&duration-in-mins={duration_mins}&output=json")
        
        return self._make_request("GET", url)
    
    def get_apm_availability(self, object_type: str, app_name: str, tier_name: str, 
                           agent_type: str, node_name: str, duration_mins: int) -> Tuple[Optional[requests.Response], str]:
        """Get APM availability metrics for tier or node."""
        tier_name_encoded = self._urlencode_string(tier_name)
        app_name_encoded = self._urlencode_string(app_name)
        node_name_encoded = self._urlencode_string(node_name)
        
        if object_type == "node":
            if agent_type == "MACHINE_AGENT":
                metric_path = (f"Application%20Infrastructure%20Performance%7C{tier_name_encoded}"
                              f"%7CIndividual%20Nodes%7C{node_name_encoded}%7CAgent%7CMachine%7CAvailability")
            else:
                metric_path = (f"Application%20Infrastructure%20Performance%7C{tier_name_encoded}"
                              f"%7CIndividual%20Nodes%7C{node_name_encoded}%7CAgent%7CApp%7CAvailability")
        else:  # tier
            if agent_type == "MACHINE_AGENT":
                metric_path = f"Application%20Infrastructure%20Performance%7C{tier_name_encoded}%7CAgent%7CMachine%7CAvailability"
            else:
                metric_path = f"Application%20Infrastructure%20Performance%7C{tier_name_encoded}%7CAgent%7CApp%7CAvailability"
        
        url = (f"{self.authenticator.credentials.base_url}/controller/rest/applications/{app_name_encoded}/metric-data"
               f"?metric-path={metric_path}&time-range-type=BEFORE_NOW"
               f"&duration-in-mins={duration_mins}&rollup=false&output=json")
        
        return self._make_request("GET", url)

    def get_health_rule_violations(
        self,
        application_id: str,
        time_range_type: str = "BEFORE_NOW",
        duration_mins: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        output: str = "XML",
    ) -> Tuple[Optional[requests.Response], str]:
        """Get health rule violations for a specific application.

        Docs: https://docs.appdynamics.com/appd/24.x/latest/en/extend-splunk-appdynamics/splunk-appdynamics-apis/alert-and-respond-api/events-api
        Endpoint: /controller/rest/applications/{application_id}/problems/healthrule-violations
        """
        base = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/problems/healthrule-violations"

        params = {"time-range-type": time_range_type}
        if duration_mins is not None:
            params["duration-in-mins"] = str(duration_mins)
        if start_time is not None:
            params["start-time"] = str(start_time)
        if end_time is not None:
            params["end-time"] = str(end_time)
        if output:
            params["output"] = output

        # Build URL with query params
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{base}?{query}"
        return self._make_request("GET", url)

    def get_events(
        self,
        application_id: str,
        event_types: List[str],
        severities: List[str],
        time_range_type: str = "BEFORE_NOW",
        duration_mins: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        tier: Optional[str] = None,
        output: str = "XML",
    ) -> Tuple[Optional[requests.Response], str]:
        """Get events for a specific application.

        Endpoint: /controller/rest/applications/{application_id}/events
        Notes: Returns at most 600 events per request.
        """
        base = f"{self.authenticator.credentials.base_url}/controller/rest/applications/{application_id}/events"

        params: Dict[str, Any] = {
            "time-range-type": time_range_type,
            "event-types": ",".join(event_types) if event_types else "",
            "severities": ",".join(severities) if severities else "",
        }
        if duration_mins is not None:
            params["duration-in-mins"] = str(duration_mins)
        if start_time is not None:
            params["start-time"] = str(start_time)
        if end_time is not None:
            params["end-time"] = str(end_time)
        if tier:
            params["tier"] = self._urlencode_string(tier)
        if output:
            params["output"] = output

        query = "&".join([f"{k}={v}" for k, v in params.items() if v is not None and v != ""])
        url = f"{base}?{query}"
        return self._make_request("GET", url)

    def get_events_paginated(
        self,
        application_id: str,
        event_types: List[str],
        severities: List[str],
        duration_mins: int,
        tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all matching events using sliding windows to respect the 600-per-request cap.

        Strategy:
        - Use BEFORE_NOW with duration windows; if a window returns 600 rows, bisect the window to reduce size
        - Continue until windows produce < 600, then slide backward until total duration is covered
        - Parse XML to DataFrame via pandas.read_xml at the call-site; here we just fetch text
        """
        import time as _time
        import math as _math
        from io import StringIO as _StringIO
        import pandas as _pd

        all_events_df = _pd.DataFrame()

        # Start with the full duration; adaptively split if needed
        remaining = duration_mins
        while remaining > 0:
            window = min(remaining, 240)  # start with 4h windows to balance calls/results
            response, status = self.get_events(
                application_id=application_id,
                event_types=event_types,
                severities=severities,
                time_range_type="BEFORE_NOW",
                duration_mins=window,
                tier=tier,
                output="XML",
            )
            if status != "valid" or not response:
                break

            # Parse quickly to count rows
            try:
                xml_content = _StringIO(response.content.decode())
                df = _pd.read_xml(xml_content, xpath=".//event")
            except Exception:
                df = _pd.DataFrame()

            if df is None or df.empty:
                remaining -= window
                continue

            if len(df) >= 600 and window > 5:
                # Too many results; reduce window size and retry without consuming remaining time
                new_window = max(5, window // 2)
                if new_window == window:
                    new_window = 5
                # small delay to avoid rate-limits
                _time.sleep(0.2)
                # retry with smaller window
                response, status = self.get_events(
                    application_id=application_id,
                    event_types=event_types,
                    severities=severities,
                    time_range_type="BEFORE_NOW",
                    duration_mins=new_window,
                    tier=tier,
                    output="XML",
                )
                try:
                    xml_content = _StringIO(response.content.decode())
                    df = _pd.read_xml(xml_content, xpath=".//event")
                except Exception:
                    df = _pd.DataFrame()
                window = new_window

            all_events_df = _pd.concat([all_events_df, df])
            remaining -= window
            _time.sleep(0.2)

        # Return as list of dicts for caller flexibility
        return all_events_df.to_dict(orient="records")




