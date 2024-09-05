import streamlit as st
import pandas as pd
import yaml
import math
import datetime
import os
from io import StringIO
import xml.etree.ElementTree as ET
import requests
import json
import urllib.parse
import time
import sys
import subprocess
import gc
import pygame

#--- CONFIGURATION SECTION ---
SNES = False
DEBUG = False

# Verify SSL certificates - should only be set false for on-prem controllers. Use this if the script fails right off the bat and gives you errors to the point..
VERIFY_SSL = True

#manages token expiration - do not change these values
last_token_fetch_time = ""
token_expiration = 300
expiration_buffer = 30

def load_secrets():
    """Loads API credentials from secrets.yml if it exists."""
    try:
        with open("secrets.yml", "r") as file:
            secrets_data = yaml.safe_load(file)
            return secrets_data.get("secrets", [])  # Default to empty list if not found
    except FileNotFoundError:
        return []  # Return an empty list if the file doesn't exist

def save_secrets(secrets_data):
    """Saves API credentials to secrets.yml."""
    with open("secrets.yml", "w") as file:
        yaml.dump({"secrets": secrets_data}, file, default_flow_style=False)

def authenticate(state):
    """get XCSRF token for use in this session"""
    if state == "reauth":
        print("Obtaining a freah authentication token.")
    if state == "initial":
        print("Begin login.")
    
    connect(APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, APPDYNAMICS_API_CLIENT_SECRET)
    return

def is_token_valid():
    """Checks if the access token is valid and not expired."""
    if DEBUG:
        print("    --- Checking token validity...")

    if __session__ is None or not __session__:
        if DEBUG:
            print("    --- __session__ not found or empty.")
        return False

    # Conservative buffer (e.g., 30 seconds before expiration)
    if DEBUG:
        print(f"    --- __session__: {__session__}")
    return time.time() < (token_expiration + last_token_fetch_time - expiration_buffer)

def connect(account, apiclient, secret):
    """Connects to the AppDynamics API and retrieves an OAuth token."""
    global __session__, last_token_fetch_time, token_expiration
    __session__ = requests.Session()

    url = f"{BASE_URL}/controller/api/oauth/access_token?grant_type=client_credentials&client_id={apiclient}@{account}&client_secret={secret}"
    payload = {} 
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    print(f"Logging into the controller at: {BASE_URL}")

    @handle_rest_errors  # Apply the error handling decorator
    def make_auth_request():
        response = __session__.request(
            "POST",
            url,
            headers=headers,
            data=payload,
            verify=VERIFY_SSL
        )
        return response

    auth_response, status = make_auth_request()
    if DEBUG:
        print(f"Authentication response:{auth_response} = {status}")

    # Assuming auth_response isn't None if no errors occurred
    if status == "valid":
        if auth_response:
            json_response = auth_response.json()
            last_token_fetch_time = time.time()
            token_expiration = json_response['expires_in']
    else:
        print(f"Unable to log in at: {BASE_URL}")
        print("Please check your controller URL and try again.")
        sys.exit(9)

    __session__.headers['X-CSRF-TOKEN'] = json_response['access_token']
    __session__.headers['Authorization'] = f'Bearer {json_response["access_token"]}'
    
    print("Authenticated with controller.")
    
    if DEBUG:
        print(f"Last token fetch time: {last_token_fetch_time}")
        print(f"Token expires in: {json_response['expires_in']}")
        print(f"Session headers: {__session__.headers}")
    
    return True

def handle_rest_errors(func):
    """for handling REST calls"""
    def inner_function(*args, **kwargs):
        error_map = {
            400: "Bad Request - The request was invalid.",
            401: "Unauthorized - Authentication failed.",
            403: "Forbidden - You don't have permission to access this resource.",
            404: "Not Found - The resource could not be found.",
            500: "Internal Server Error - Something went wrong on the server.",
        }

        try:
            response = func(*args, **kwargs)
            response.raise_for_status()
            return response, "valid"
        except requests.exceptions.HTTPError as err:
            error_code = err.response.status_code
            error_explanation = error_map.get(error_code, "Unknown HTTP Error")
            print(f"HTTP Error: {error_code} - {error_explanation}")
            return error_explanation, "error"
        except requests.exceptions.RequestException as err:
            if isinstance(err, requests.exceptions.ConnectionError):
                print("Connection Error: Failed to establish a new connection.")
                return err, "error"
            else: 
                print(f"Request Exception: {err}") 
                return err, "error"
        except Exception:  
            error_type, error_value, _ = sys.exc_info() 
            print(f"Unexpected Error: {error_type.__name__}: {error_value}")
            return error_value, "error"

    return inner_function

def urlencode_string(text):
    """make app, tier or node names URL compatible for the REST call"""
    #if the type is not string, make it one
    if not isinstance(text, str):
        print(f"converting {text} to a string.")
        text = str(text)
    
    encoded_text = urllib.parse.quote(text, safe='/', encoding=None, errors=None)

    return encoded_text

@handle_rest_errors
def get_SIM_availability(hierarchy_list, hostId, type):
    """fetches last known server agent availability info. returns requests.Response object"""
    if DEBUG:
        print(f"        --- Begin get_SIM_availability({hierarchy_list}, {hostId})")
    
    #PHYSICAL server URL example
    #https://customer1.saas.appdynamics.com/controller/rest/applications/Server%20%26%20Infrastructure%20Monitoring/metric-data?metric-path=Application%20Infrastructure%20Performance%7CRoot%5C%7CAppName%5C%7COwners%5C%7CEnvironment%7CIndividual%20Nodes%7C<hostId>%7CHardware%20Resources%7CMachine%7CAvailability&time-range-type=BEFORE_NOW&duration-in-mins=60
    #CONTAINER server URL example - have to use CPU
    #https://customer1.saas.appdynamics.com/controller/rest/applications/Server%20%26%20Infrastructure%20Monitoring/metric-data?metric-path=Application%20Infrastructure%20Performance%7CRoot%5C%7CContainers%7CIndividual%20Nodes%7C<hostId>%7CHardware%20Resources%7CCPU%7C%25Busy&time-range-type=BEFORE_NOW&duration-in-mins=60


    #convert the hierarchy from the machine agent data into a URL encoded string
    hierarchy = "%5C%7C".join(hierarchy_list)

    #build the metric url using the hierarchy, hostId and metric duration
    if type == "PHYSICAL": #use availability metric
        metric_url = BASE_URL + "/controller/rest/applications/Server%20%26%20Infrastructure%20Monitoring/metric-data?metric-path=Application%20Infrastructure%20Performance%7CRoot%5C%7C" + hierarchy + "%7CIndividual%20Nodes%7C" + hostId + "%7CHardware%20Resources%7CMachine%7CAvailability&time-range-type=BEFORE_NOW&duration-in-mins=" + str(MACHINE_METRIC_DURATION_MINS) + "&output=json"
    elif type == "CONTAINER": #use CPU busy since availability metric doesn't exist
        metric_url = BASE_URL + "/controller/rest/applications/Server%20%26%20Infrastructure%20Monitoring/metric-data?metric-path=Application%20Infrastructure%20Performance%7CRoot%5C%7C" + hierarchy + "%7CIndividual%20Nodes%7C" + hostId + "%7CHardware%20Resources%7CCPU%7C%25Busy&time-range-type=BEFORE_NOW&duration-in-mins=" + str(MACHINE_METRIC_DURATION_MINS) + "&output=json"
    if DEBUG:
        print(f"        --- SIM availability metric url: {metric_url}")

    metric_response = requests.get(
        metric_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )
    
    return metric_response

@handle_rest_errors
def get_apm_availability(object_type, app, tier, agenttype, node):
    """fetches last known agent availability info from tier or node level. returns requests.Response object"""
    if DEBUG:
        print(f"        --- Begin get_apm_availability({object_type},{app},{tier},{agenttype},{node})")

    tier = urlencode_string(tier)
    app = urlencode_string(app)
    node = urlencode_string(node)

    if object_type == "node":
        print("        --- Querying node availability.")
        if agenttype == "MACHINE_AGENT":
            metric_path = "Application%20Infrastructure%20Performance%7C" + tier + "%7CIndividual%20Nodes%7C" + node + "%7CAgent%7CMachine%7CAvailability"
        else:
            metric_path = "Application%20Infrastructure%20Performance%7C" + tier + "%7CIndividual%20Nodes%7C" + node + "%7CAgent%7CApp%7CAvailability"
    
    elif object_type == "tier":
        print("        --- Querying tier availability.")
        if agenttype == "MACHINE_AGENT":
            metric_path = "Application%20Infrastructure%20Performance%7C" + tier + "%7CAgent%7CMachine%7CAvailability"
        else:
            metric_path = "Application%20Infrastructure%20Performance%7C" + tier + "%7CAgent%7CApp%7CAvailability"

    metric_url = BASE_URL + "/controller/rest/applications/" + app + "/metric-data?metric-path=" + metric_path + "&time-range-type=BEFORE_NOW&duration-in-mins=" + str(APM_METRIC_DURATION_MINS) + "&rollup=" + METRIC_ROLLUP + "&output=json"
                                
    #get metric data
    if DEBUG:
        print("        --- metric url: " + metric_url)

    metric_response = requests.get(
        metric_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    return metric_response

def return_apm_availability(metric_response):
    '''validate the returned APM availability response, extracts the metric data and returns the last seen time and count'''
    data, status = validate_json(metric_response)

    if status != "valid":
        if DEBUG:
            print(f"            --- Validation of APM availability data failed. Status: {status} Data: {data}")
        return "", ""

    if status == "valid":
        # Check if any dictionary in the list has 'metricName' equal to 'METRIC DATA NOT FOUND' and jump out early if so
        condition = any(d['metricName'] == 'METRIC DATA NOT FOUND' for d in data)

        if condition:
            print("            --- Metric data not found!")
            return "", ""
        
        try:
            epoch, value = determine_availability(data, status)
            return epoch, value
        
        except Exception as e:
            st.write(f"Unexpected error during validation: of APM availability data: {e}")
            print(f"            --- Unexpected error during validation: of APM availability data: {e}")
            print(f"            --- status: {status} data: {data}")
            return "", ""      

def validate_json(response):
    """validation function to parse into JSON and catch empty sets returned from our API requests"""
    if not response:
        if DEBUG:
            print("        ---- No response was passed for validation.")
        return None, "empty"

    try:
        if DEBUG:
            if isinstance(response, requests.Response):  
                if response.headers.get('content-type') == 'application/json':
                    print(f"        --- validate_json() - incoming response type:: {type(response)}, length: {len(response.json())}")
                else:
                    print(f"        --- validate_json() - incoming response type:: {type(response)}, length: {len(response.content)}")
            else:
                print(f"        --- validate_json() - incoming response type:: {type(response)}, length: {len(response)}")
        
        if isinstance(response, tuple): 
            #unpack response
            data, data_status = response
            
            #handle error and exceptions from the response
            if data_status != "valid":
                if DEBUG:
                    st.write(f"Response validation error! status = {data_status}, data = {data}")
                    print(f"        --- response data is not valid. status = {data_status}, data = {data}")
                return None, data_status

            else:
                if DEBUG:
                    print(f"        --- response data is valid. status = {data_status}")
                
                #convert response data to JSON
                data = data.json()
        
        elif isinstance(response, requests.Response):  
            data = response.json()
            data_status = "valid"

        elif isinstance(response, dict):  
            # Handle dictionaries directly
            data = response
            data_status = "valid"
            
        # check for empty JSON object
        if not data or data == [] or data == "":
            if DEBUG:
                print(f"            --- The resulting JSON object is empty. data = {data}")
            return None, "empty"
    
        #if the data made it this far, then...
        return data, data_status

    except json.JSONDecodeError:
        # The data is not valid JSON.
        if DEBUG:
            print("            --- The data is not valid JSON.")
            print(response.text)
        return None, "error"

def determine_availability(metric_data, metric_data_status):
    """Processes returned metric JSON data"""
    if DEBUG:
        print("        --- handle_metric_response() - Handling metric data...")
        print(f"        --- handle_metric_response() - metric_data: {metric_data}")
        print(f"        --- handle_metric_response() - metric_data type: {type(metric_data)}")
        print(f"        --- handle_metric_response() - metric_data_status: {metric_data_status}")
    
    if metric_data[-1]['metricName'] == "METRIC DATA NOT FOUND":
        if DEBUG:
            print("METRIC DATA NOT FOUND IN TIME RANGE")
            return None, None
    
    if metric_data[-1]['metricValues'][-1]['startTimeInMillis']:
        last_start_time_millis = metric_data[-1]['metricValues'][-1]['startTimeInMillis']
        value = metric_data[-1]['metricValues'][-1]['current']
        if DEBUG:
            print(f"            --- startTimeInMillis: {last_start_time_millis} current: {value}")

        return last_start_time_millis, value
    
    elif metric_data == []:
        if DEBUG:
            print("METRIC DATA CAME BACK WITH EMPTY DICTIONARY")

        return None, None

    else:
        return None, None

@handle_rest_errors
def get_applications():
    """Get a list of all applications"""
    print("--- Fetching applications...")
    
    if not is_token_valid():
        authenticate("reauth")

    if application_id:
        #chosen when user supplied an app id in the config
        applications_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "?output=json"
        if DEBUG:
            print("    --- from "+applications_url)
    else:
        applications_url = BASE_URL + "/controller/rest/applications?output=json"
        if DEBUG:
            print("--- from "+applications_url)
    
    applications_response = requests.get(
        applications_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    return applications_response

def refresh_applications():
    global APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, APPDYNAMICS_API_CLIENT_SECRET, BASE_URL, application_id
    APPDYNAMICS_ACCOUNT_NAME = account_name
    APPDYNAMICS_API_CLIENT = api_client
    APPDYNAMICS_API_CLIENT_SECRET = api_key
    BASE_URL = "https://"+APPDYNAMICS_ACCOUNT_NAME+".saas.appdynamics.com"
    application_id = None

    authenticate("initial")
    
    with st.spinner('Retrieving applications...'):  
        applications_response = get_applications()
        applications, applications_status = validate_json(applications_response)

    if applications_status == "valid":
        applications_df = pd.DataFrame(applications)
        applications_df = applications_df.rename(columns={
            "id": "app_id",
            "name": "app_name"
        })

        st.session_state['applications_df'] = applications_df  # Store in session state

        if DEBUG:
            debug_df(applications_df, "applications_df")
    
    st.rerun()

@handle_rest_errors
def get_tiers(application_id):
    """Gets the tiers in the application"""  
    tiers_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/tiers?output=json"
    
    if DEBUG:
        print("    --- Fetching tiers from: "+ tiers_url)
    else:
        print("    --- Fetching tiers...")

    if not is_token_valid():
        authenticate("reauth")

    tiers_response = requests.get(
        tiers_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )
    #if DEBUG:
    #    print(f"    --- get_tiers response: {tiers_response.text}")

    return tiers_response

@handle_rest_errors
def get_app_nodes(application_id):
    """Gets all nodes in an app"""
    nodes_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/nodes?output=json"
    if DEBUG:
        print(f"        --- Fetching node data from {nodes_url}.")
    else:
        print("        --- Fetching nodes from app.")

    if not is_token_valid():
        authenticate("reauth")

    nodes_response = requests.get(
        nodes_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    #if DEBUG:
    #    print(f"    --- get_app_nodes response: {nodes_response.text}")

    return nodes_response

@handle_rest_errors
def get_tier_nodes(application_id, tier_id):
    """Gets the nodes in a tier"""
    nodes_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/tiers/" + str(tier_id) + "/nodes?output=json"
    if DEBUG:
        print(f"        --- Fetching node data from {nodes_url}.")
    else:
        print("        --- Fetching nodes from tier.")

    if not is_token_valid():
        authenticate("reauth")
        
    nodes_response = requests.get(
        nodes_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    #if DEBUG:
    #    print(f"    --- get_tier_nodes response: {nodes_response.text}")
    
    return nodes_response

@handle_rest_errors
def get_app_backends(application_id):
    """Gets the backends in an app"""
    backends_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/backends?output=json"
    if DEBUG:
        print(f"        --- Fetching backend data from {backends_url}.")
    else:
        print(f"        --- Fetching backends from application: {application_id}.")

    if not is_token_valid():
        authenticate("reauth")

    backends_response = requests.get(
        backends_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    #if DEBUG:
    #    print(f"    --- get_backends response: {backends_response.text}")
    
    return backends_response

@handle_rest_errors
def get_snapshots(application_id):
    """Gets snapshot data from an application"""
    snapshots_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/request-snapshots?time-range-type=BEFORE_NOW&duration-in-mins=" + str(SNAPSHOT_DURATION_MINS) + "&first-in-chain=" + FIRST_IN_CHAIN + "&need-exit-calls=" + NEED_EXIT_CALLS + "&need-props=" + NEED_PROPS + "&maximum-results=1000000&output=json"

    if DEBUG:
        print("    --- Fetching snapshots from: "+ snapshots_url)
    else:
        print("    --- Fetching snapshots...")

    if not is_token_valid():
        authenticate("reauth")

    snapshots_response = requests.get(
        snapshots_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )
    #if DEBUG:
    #    print(f"    --- get_snapshots response: {snapshots_response.text}")

    return snapshots_response

#@handle_rest_errors
def get_bts(application_id): 
    '''retrieves business transactions list from the application'''
    bts_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/business-transactions"

    if DEBUG:
        print("    --- Fetching bts from: "+ bts_url)
    else:
        print("    --- Fetching bts...")

    if not is_token_valid():
        authenticate("reauth")

    bts_response = requests.get(
        bts_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )
    if DEBUG:
        print(f"    --- get_bts response: {bts_response.text}")

    #check for empty dataset
    if DEBUG:
        print(f"length of bts_response {(len(bts_response.content.strip()))}")
    
    if not bts_response.content.decode().strip():  # Check for empty XML (after decoding)
        return pd.DataFrame(), "empty"
    
    else:
        try:
            # Parse the XML content to get the root
            xml_content = StringIO(bts_response.content.decode())
            root = ET.parse(xml_content).getroot()
            
            # Check if there are any child elements with data
            if not root.findall(".//*"):  # This checks for any descendant elements (not just direct children)
                return pd.DataFrame(), "empty"

            # Specify the root element using xpath
            bts_df = pd.read_xml(StringIO(bts_response.text), xpath=".//business-transaction")
            return bts_df, "valid"

        except Exception as e:
            error_type, error_value, _ = sys.exc_info()
            print(f"An exception occurred converting business transaction XML to dataframe: {error_type.__name__}: {error_value}")
            return None, "error"

@handle_rest_errors
def get_healthRules(application_id):
    '''retrieves health rules from application(s)'''
    healthRules_url = BASE_URL + "/controller/alerting/rest/v1/applications/" + str(application_id) + "/health-rules"

    if DEBUG:
        print(f"    --- Fetching health rules from: {healthRules_url}")
    else:
        print("    --- Fetching health rules...")

    if not is_token_valid():
        authenticate("reauth")

    healthRules_response = requests.get(
        healthRules_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )
    #if DEBUG:
    #    print(f"    --- get_healthRules response: {healthRules_response.text}")

    return healthRules_response    

@handle_rest_errors
def get_servers():
    '''Get a list of all servers'''
    servers_url = BASE_URL + "/controller/sim/v2/user/machines"
    if DEBUG:
        print(f"    --- Retrieving Servers from {servers_url}")
    else:
        print("    --- Retrieving Servers...")

    if not is_token_valid():
        authenticate("reauth")

    servers_response = requests.get(
        servers_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    return servers_response

def calculate_licenses(df):
    license_data = []

    for agent_type in ['APP_AGENT', 'DOT_NET_APP_AGENT', 'NODEJS_APP_AGENT', 'PYTHON_APP_AGENT',
                       'PHP_APP_AGENT', 'GOLANG_SDK', 'WMB_AGENT', 'MACHINE_AGENT', 'DOT_NET_MACHINE_AGENT', 
                       'NATIVE_WEB_SERVER', 'NATIVE_SDK']:

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

            #use the names everyone knows
            if agent_type != "NATIVE_SDK":
                if agent_type == 'APP_AGENT':
                    agent_type = 'Java Agent'
                if agent_type == 'DOT_NET_APP_AGENT':
                    agent_type = '.NET Agent'
                if agent_type == 'NODEJS_APP_AGENT':
                    agent_type = 'NodeJS Agent'
                if agent_type == 'PYTHON_APP_AGENT':
                    agent_type = 'Python Agent'
                if agent_type == 'PHP_APP_AGENT':
                    agent_type = "PHP Agent"
                if agent_type == 'GOLANG_SDK':
                    agent_type = 'Go Agent'
                if agent_type == 'WMB_AGENT':
                    agent_type = 'IIB Agent'
                if agent_type == 'MACHINE_AGENT':
                    agent_type = 'Machine Agent'
                if agent_type == 'DOT_NET_MACHINE_AGENT':
                    agent_type = '.NET Machine Agent'
                if agent_type == 'NATIVE_WEB_SERVER':
                    agent_type = 'Apache Agent'    
                
            license_data.append({
                'Agent Type': agent_type,
                'Container Nodes': container_df.shape[0],
                'Physical Nodes': physical_df.shape[0],
                'Physical Licenses (Mixed)': physical_licenses,
                'Microservices Licenses (Mixed)': microservices_licenses,
                'Standard Licenses': standard_licenses
            })

    license_usage_df = pd.DataFrame(license_data)
    return license_usage_df

def debug_df(df, df_name, num_lines=10):
    """Displays DataFrame information in a more readable way."""
    if SNES:
        play_sound("sounds/smb_coin.wav")

    st.subheader(f"Debug Info: {df_name}")  # Use subheader instead of nested expander
    st.write(f"Shape (rows, cols): {df.shape}")
    #st.write(f"Columns: {df.columns.to_list()}")
    st.write(f"First {num_lines} rows:")
    st.write(df.head(num_lines).to_markdown(index=False, numalign='left', stralign='left'))

def play_sound(file_path):
    '''file = realtive path and filename to wave file, wait (Boolean) wait for the file to finish playing or not'''
    try:
        pygame.mixer.init()
        sound = pygame.mixer.Sound(file_path)
        sound.play()

    except Exception as e:
        print(f"Error playing sound: {e}")

# --- MAIN (Streamlit UI) ---
st.title("AppDynamics Data Extractor")
st.markdown('<h2 text-align: center>not DEXTER</h2>', unsafe_allow_html=True)

# --- Load secrets and set initial values ---
secrets = load_secrets()
selected_account = ""
api_client_name = ""
api_key = ""

#load up accounts and creds if they exist
if secrets:
    selected_account = secrets[0].get("account", "")
    api_client_name = secrets[0].get("api-client-name", "")
    api_key = secrets[0].get("api-key", "")
    account_options = [secret["account"] for secret in secrets] + ["Enter Manually"]
    selected_account = st.selectbox("Account Name", options=account_options, index=account_options.index(selected_account) if selected_account in account_options else 0)

    # Input/select behavior
    if selected_account == "Enter Manually":
        account_name = st.text_input("Account Name", value="")
    else:
        account_name = selected_account  # Use the selected value directly

    # Populate fields dynamically based on account name
    api_client_name = ""  # Reset to empty
    api_key = ""
    for secret in secrets:
        if secret["account"] == account_name:
            api_client_name = secret.get("api-client-name", "")
            api_key = secret.get("api-key", "")
            break

connect_button = st.button("Connect")

#conditional multiselect populator
if 'applications_df' in st.session_state:
    applications_df = st.session_state['applications_df']

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

    if selected_app_ids:
        application_id = ""
        #st.write("You selected app_ids:", selected_app_ids)

"***Note: license usage analysis (BETA) requires APM and server data***"
retrieve_apm = st.checkbox("Retrieve APM (App, tiers, nodes, etc)?", value=True)    
retrieve_servers = st.checkbox("Retrieve all machine agent data?", value=True)
if retrieve_apm:
    pull_snapshots = st.checkbox("Retrieve transaction snapshots?", value=False)
else:
    pull_snapshots = False

# --- User config form ---
with st.form("config_form"):
    if not secrets:
        account_name = st.text_input("Account Name", value="")
    api_client = st.text_input("API client name", value=api_client_name)
    api_key = st.text_input("API client secret", type="password", value=api_key)

    # Save button
    save_button = st.form_submit_button("Save Credentials")
    
    if 'applications_df' not in st.session_state:
        application_id = st.text_input("Application ID (optional)", value="")
    
    if retrieve_apm:
        "### APM options"
        calc_apm_availability = st.checkbox("Analyze tier and node availability?", value=True)
        apm_metric_duration_mins = st.text_input("How far to look back for APM availability? (mins)", value="60")
        #add this back at some point maybe
        #metric_rollup = st.checkbox("Rollup metrics?", value=False)
    
    if pull_snapshots:
        "### Snapshot options"
        snapshot_duration_mins = st.text_input("How far to look back for snapshots? (mins)", value="60")
        first_in_chain = st.checkbox("Capture only first in chain snapshots?", value=True)
        need_exit_calls = st.checkbox("Return exit call data with snapshots?", value=False)
        need_props = st.checkbox("Return data collector data with snapshots?", value=False)
    
    if retrieve_servers:
        "### Servers"
        calc_machine_availability = st.checkbox("Analyze server availability?", value=True)
        if calc_machine_availability:
            machine_metric_duration_mins = st.text_input("How far to look back for machine availability? (mins)", value="60")
        #normalize = st.checkbox("Break out server properties into columns?", value=False)
        #normalize = True
    
    # Submit button
    submitted = st.form_submit_button("Extract Data")

debug_output = st.checkbox("Debug output?", value=False)
if debug_output:
    SNES = st.checkbox("8-bit my debug!")

if connect_button:
    global APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, APPDYNAMICS_API_CLIENT_SECRET, \
        APPLICATION_ID, METRIC_DURATION_MINS, PULL_SNAPSHOTS, FIRST_IN_CHAIN, \
        CALC_APM_AVAILABILITY
    
    # Update global variables with user input
    APPDYNAMICS_ACCOUNT_NAME = account_name
    APPDYNAMICS_API_CLIENT = api_client
    APPDYNAMICS_API_CLIENT_SECRET = api_key
    APPLICATION_ID = ""

    st.write("Connecting to retrieve applications list...")
    print("Connecting to retrieve applications list...")
    refresh_applications()
    
if save_button:
    # Update secrets.yml with user input
    new_secrets = []
    for secret in secrets:
        if secret["account"] == account_name:
            secret["api-client-name"] = api_client
            secret["api_key"] = api_key
        new_secrets.append(secret)
    if account_name not in account_options:  # Add only if it's a new account
        new_secrets.append({
            "account": account_name,
            "api-client-name": api_client,
            "api-key": api_key
        })
    save_secrets(new_secrets)
    st.success("Credentials saved!")

# --- Main application code ---
if submitted and (retrieve_apm or retrieve_servers):
    if SNES:
        play_sound("sounds/smb_jump-small.wav")
                
    # Update global variables with user input
    APPDYNAMICS_ACCOUNT_NAME = account_name
    APPDYNAMICS_API_CLIENT = api_client
    APPDYNAMICS_API_CLIENT_SECRET = api_key
    
    if retrieve_apm:
        if not selected_app_ids:
            if not application_id:
                APPLICATION_ID = ""
            else:
                APPLICATION_ID = application_id

        if not selected_app_ids and application_id == "" and not retrieve_servers:
            st.write("You must select an application or an application_id to continue.")
            st.rerun()
        if selected_app_ids:
            APPLICATION_ID = ""

        if calc_apm_availability:
            CALC_APM_AVAILABILITY = calc_apm_availability
            APM_METRIC_DURATION_MINS = apm_metric_duration_mins
        else:
            CALC_APM_AVAILABILITY = False
            APM_METRIC_DURATION_MINS = 0
        
        if pull_snapshots:
            PULL_SNAPSHOTS = pull_snapshots
            SNAPSHOT_DURATION_MINS = snapshot_duration_mins

            if first_in_chain:
                FIRST_IN_CHAIN = "true"
            else:
                FIRST_IN_CHAIN = "false"

            if need_exit_calls:
                NEED_EXIT_CALLS = "true"
            else:
                NEED_EXIT_CALLS = "false"
            
            if need_props:
                NEED_PROPS = "true"
            else:
                NEED_PROPS = "false"    

    if retrieve_servers:    
        if calc_machine_availability:
            CALC_MACHINE_AVAILABILITY = calc_machine_availability
            MACHINE_METRIC_DURATION_MINS = machine_metric_duration_mins
        else:
            CALC_MACHINE_AVAILABILITY = False
            MACHINE_METRIC_DURATION_MINS = 0
        
        #NORMALIZE = normalize
        NORMALIZE = True                                
    
    DEBUG = debug_output
    
    # add this back at some point maybe
    #if metric_rollup:
    #    METRIC_ROLLUP = "true"
    #else:
    METRIC_ROLLUP = "false"

    # Replace with the desired output file path and name or leave as it to create dynamically (recommended)
    OUTPUT_EXCEL_FILE = APPDYNAMICS_ACCOUNT_NAME+"_analysis_"+datetime.date.today().strftime("%m-%d-%Y")+".xlsx"

    # Set the base URL for the AppDynamics REST API
    # --- replace this with your on-prem controller URL if you're on prem
    BASE_URL = "https://"+APPDYNAMICS_ACCOUNT_NAME+".saas.appdynamics.com"

    # --- MAIN application code
    # set this for later to keep the status window open if there are errors
    keep_status_open = False

    with st.status("Extracting data...", expanded=True) as status:
        st.write(f"Logging into controller at {BASE_URL}...")
        authenticate("initial")

        # Initialize empty DataFrame
        information_df = pd.DataFrame()
        license_usage_df = pd.DataFrame()
        applications_df = pd.DataFrame()
        bts_df = pd.DataFrame()
        tiers_df = pd.DataFrame()
        nodes_df = pd.DataFrame()
        backends_df = pd.DataFrame()
        healthRules_df = pd.DataFrame()
        snapshots_df = pd.DataFrame()

        all_bts_df = pd.DataFrame()
        all_tiers_df = pd.DataFrame()
        all_nodes_df = pd.DataFrame()
        all_nodes_merged_df = pd.DataFrame()
        all_backends_df = pd.DataFrame()
        all_healthRules_df = pd.DataFrame()
        all_snapshots_df = pd.DataFrame()
        all_snapshots_merged_df = pd.DataFrame()
        all_servers_df = pd.DataFrame()
        all_servers_merged_df = pd.DataFrame()
        all_apm_merged_df = pd.DataFrame()

        if retrieve_apm:
            # Get applications for processing
            st.write("Retrieving applications...")
            applications_response = get_applications()
            applications, applications_status = validate_json(applications_response)

            if applications_status == "valid":
                applications_df = pd.DataFrame(applications)
                applications_df = applications_df.rename(columns={
                    "id": "app_id",
                    "name": "app_name"
                })
                
                if selected_app_ids:
                    # Filter the DataFrame based on selected_app_ids
                    if "ALL" in selected_app_ids:
                        applications_df = applications_df  # Keep all rows
                    else:
                        applications_df = applications_df[applications_df['app_id'].isin(selected_app_ids)]

                if DEBUG:
                    debug_df(applications_df, "applications_df")

                st.write(f"Found {applications_df.shape[0]} applications.")

                if SNES:
                    play_sound("sounds/smb_coin.wav")
                
                #get current date and time and build info sheet - shoutout to Peter Wivagg for the suggestion
                now = datetime.datetime.now()
                current_date_time = now.strftime("%Y-%m-%d %H:%M:%S")

                information_df = pd.DataFrame({
                    "setting": ["RUN_DATE","BASE_URL", "APPDYNAMICS_ACCOUNT_NAME", "APPDYNAMICS_API_CLIENT", "APPDYNAMICS_API_CLIENT_SECRET", "Selected Apps", "or application id", "APM availability (mins)", "Machine availability (mins)", "METRIC_ROLLUP", "Retrieve snapshots"],
                    "value": [current_date_time, BASE_URL, APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, "xxx", selected_apps, APPLICATION_ID, APM_METRIC_DURATION_MINS, MACHINE_METRIC_DURATION_MINS, METRIC_ROLLUP, PULL_SNAPSHOTS]
                })

                # Process each application
                st.write(f"Processing applications...")

                for _, application in applications_df.iterrows():
                    app_id = application["app_id"]
                    app_name = application["app_name"]

                    # Get and process business transactions
                    st.write(f"Retrieving business transactions for {app_name}...")
                    bts_response = get_bts(app_id)
                    bts_data, bts_status = bts_response
                    
                    if bts_status == "valid":
                        if SNES:
                            play_sound("sounds/smb_coin.wav")
                            
                        bts_df['app_id'] = app_id
                        bts_df = pd.DataFrame(bts_data)
                        bts_df = bts_df.rename(columns={
                            "id": "bt_id",
                            "name": "bt_name"
                        })

                        if DEBUG:
                            print(f"App id:{app_id}")
                            debug_df(bts_df, "bts_df")

                        st.write(f"Found {bts_df.shape[0]} business transactions.")
                        
                        if SNES:
                            play_sound("sounds/smb_coin.wav")

                        all_bts_df = pd.concat([all_bts_df, bts_df])

                    elif bts_status == "empty":
                        st.write(f"No business transactions found for {app_name}.")
                    
                    # Get and process tiers
                    st.write(f"Retrieving tiers for {app_name}...")
                    tiers_response = get_tiers(app_id)
                    tiers, tiers_status = validate_json(tiers_response)
                    if tiers_status == "valid":
                        tiers_df = pd.DataFrame(tiers)
                        tiers_df['app_id'] = app_id
                        tiers_df['app_name'] = app_name
                        tiers_df = tiers_df.rename(columns={
                            "id": "tier_id",
                            "name": "tier_name"
                        })
                        
                        if DEBUG:
                            debug_df(tiers_df, "tiers_df")
                            #input("PRESS ANY KEY")

                        st.write(f"Found {tiers_df.shape[0]} tiers.")
                        if SNES:
                            play_sound("sounds/smb_coin.wav")

                        if CALC_APM_AVAILABILITY:
                            print(f"Calculating availability for {tiers_df.shape[0]} tiers.")
                            st.write(f"Calculating availability for {tiers_df.shape[0]} tiers.")
                            
                            # Function to apply to each row
                            def get_last_seen(row):
                                response = get_apm_availability("tier", app_name, row['tier_name'], row['agentType'], "")
                                epoch, value = return_apm_availability(response)
                                return epoch, value
                                
                            result_series = tiers_df.apply(get_last_seen, axis=1)  # Get Series of tuples

                            # Extract values from the Series of tuples
                            tiers_df['Last Seen Tier'] = result_series.str[0]
                            tiers_df['Last Seen Tier - Node Count'] = result_series.str[1]

                            # (Optional) Filter out rows where 'Last Seen' is None
                            # tiers_df = toers_df.dropna(subset=['Last Seen Tier'])

                        all_tiers_df = pd.concat([all_tiers_df, tiers_df])

                    # Get and process nodes
                    st.write(f"Retrieving nodes for {app_name}...")
                    nodes_response = get_app_nodes(app_id)
                    nodes, nodes_status = validate_json(nodes_response)
                    if nodes_status == "valid":
                        nodes_df = pd.DataFrame(nodes)
                        nodes_df['app_id'] = app_id
                        nodes_df['app_name'] = app_name
                        nodes_df = nodes_df.rename(columns={
                            "id": "node_id",
                            "name": "node_name"
                        })

                        #cleanup the machine name removing -java-MA
                        nodes_df['machineName-cleaned'] = nodes_df['machineName'].astype(str).str.replace('-java-MA$', '', regex=True)

                        if DEBUG:
                            debug_df(nodes_df, "nodes_df")
                            #input("PRESS ANY KEY")
                        
                        st.write(f"Found {nodes_df.shape[0]} nodes for {app_name}.")
                        
                        if SNES:
                            play_sound("sounds/smb_coin.wav")
                
                        if CALC_APM_AVAILABILITY:
                            print(f"Calculating availability for {nodes_df.shape[0]} nodes.")
                            st.write(f"Calculating availability for {nodes_df.shape[0]} nodes.")

                            # Function to apply to each row
                            def get_last_seen(row):
                                response = get_apm_availability("node", app_name, row['tierName'], row['agentType'], row['node_name'])
                                epoch, value = return_apm_availability(response)
                                return epoch
                                
                            # Apply the function and create the new column
                            nodes_df['Last Seen Node'] = nodes_df.apply(get_last_seen, axis=1)

                            # (Optional) Filter out rows where last_seen is None
                            # nodes_df = nodes_df.dropna(subset=['last_seen'])

                        all_nodes_df = pd.concat([all_nodes_df, nodes_df])

                        if SNES:
                            play_sound("sounds/smb_powerup.wav")
                    
                    else:
                        st.write(f"No nodes found for: {app_name} status: {nodes_status}")

                    # Get and process backends
                    st.write(f"Retrieving backends for {app_name}...")
                    backends_response = get_app_backends(app_id)
                    backends, backends_status = validate_json(backends_response)
                    if backends_status == "valid":
                        backends_df = pd.DataFrame(backends)
                        backends_df['app_id'] = app_id
                        backends_df['app_name'] = app_name
                        backends_df = backends_df.rename(columns={
                            "id": "backend_id",
                            "name": "backend_name"
                        })
                        
                        if DEBUG:
                            debug_df(backends_df, "backends_df")
                            #input("PRESS ANY KEY")
                    
                        st.write(f"Found {backends_df.shape[0]} backends for {app_name}.")
                        
                        all_backends_df = pd.concat([all_backends_df, backends_df])

                        if SNES:
                            play_sound("sounds/smb_coin.wav")

                    else:
                        st.write(f"No backends found for: {app_name} status: {backends_status}")

                    # Get and process health rules
                    st.write(f"Retrieving health rules for {app_name}...")
                    healthRules_response = get_healthRules(app_id)
                    healthRules, healthRules_status = validate_json(healthRules_response)
                    if healthRules_status == "valid":
                        healthRules_df = pd.DataFrame(healthRules)
                        healthRules_df['app_id'] = app_id
                        healthRules_df['app_name'] = app_name
                        
                        if DEBUG:
                            debug_df(healthRules_df, "healthRules_df")

                        st.write(f"Found {healthRules_df.shape[0]} health rules for {app_name}.")

                        all_healthRules_df = pd.concat([all_healthRules_df, healthRules_df])

                        if SNES:
                            play_sound("sounds/smb_coin.wav")

                    else:
                        st.write(f"No health rules found for: {app_name} status: {healthRules_status}")

                    # Get and process snapshots
                    if PULL_SNAPSHOTS:
                        st.write(f"Retrieving snapshots for {app_name}...")
                        snapshots_response = get_snapshots(app_id)
                        snapshots, snapshots_status = validate_json(snapshots_response)
                        if snapshots_status == "valid":
                            snapshots_df = pd.DataFrame(snapshots)
                            snapshots_df['app_id'] = app_id
                            
                            if DEBUG:
                                debug_df(snapshots_df, "snapshots_df")

                            st.write(f"Found {snapshots_df.shape[0]} for {app_name}.")
                            
                            def contruct_snapshot_link(row):
                                #make the id fields strings so they can be concatenated into a URL
                                request_guid = str(row['requestGUID'])
                                app_id = str(row['app_id'])
                                bt_id = str(row['businessTransactionId'])
                                
                                serverStartTime = row['serverStartTime']
                                a = serverStartTime-1800000
                                b = serverStartTime+1800000
                                sst_begin = str(a)
                                sst_end = str(b)

                                snapshot_link = BASE_URL + "/controller/#/location=APP_SNAPSHOT_VIEWER&requestGUID=" + request_guid + "&application=" + app_id + "&businessTransaction=" + bt_id + "&rsdTime=Custom_Time_Range.BETWEEN_TIMES." + sst_end + "." + sst_begin + ".60" + "&tab=overview&dashboardMode=force"
                                
                                return snapshot_link

                            # create deep links for the snapshots
                            st.write(f"Creating deep links for snapshots in {app_name}...")
                            print(f"Creating deep links for snapshots in {app_name}...")
                            if SNES:
                                play_sound("sounds/smb_kick.wav")

                            snapshots_df['snapshot_link'] = snapshots_df.apply(contruct_snapshot_link, axis=1)

                            all_snapshots_df = pd.concat([all_snapshots_df, snapshots_df])

                            if SNES:
                                play_sound("sounds/smb_1-up.wav")

                        elif snapshots_status == "empty":
                            print ("            --- No snapshots returned")
                            st.write(f"No snapshots found for {app_name}.")
            else:
                st.write(f"No application data found. status: {applications_status} data:{applications}")
                
        if retrieve_servers:
            # get ALL the servers and containers
            st.write(f"Retrieving servers...")
            servers_response = get_servers()
            servers, servers_status = validate_json(servers_response)
            
            if servers_status == "valid":
                all_servers_df = pd.DataFrame(servers)

                if DEBUG:
                    debug_df(all_servers_df, "all_servers_df")
                
                if SNES:
                            play_sound("sounds/smb_coin.wav")
                
                st.write(f"Found {all_servers_df.shape[0]} servers.")

                if CALC_MACHINE_AVAILABILITY:
                    st.write(f"Determining availability for each of {all_servers_df.shape[0]} servers. Please be patient...")              
                    
                    # Function to apply to each row
                    def get_last_seen(row):
                        response = get_SIM_availability(row['hierarchy'], row['hostId'], row['type'])
                        epoch, _ = return_apm_availability(response)
                        return epoch
                    
                    # Apply the function and create the new column
                    all_servers_df['Last Seen Server'] = all_servers_df.apply(get_last_seen, axis=1)

                    # (Optional) Filter out rows where last_seen is None
                    # all_server_df = nodes_df.dropna(subset=['Last Seen Server'])

            else:
                st.write(f"No servers returned. Status: {servers_status}")
                print(f"        --- No servers returned. Status: {servers_status} Response: {servers}")

        #Convert epoch timestamps to datetime
        if retrieve_apm:
            if CALC_APM_AVAILABILITY:
                if not all_snapshots_df.empty:
                    st.write("Converting snapshot epoch timestamps to datetimes...")
                    print("Converting snapshot epoch timestamps to datetimes...")
                    if SNES:
                        play_sound("sounds/smb_kick.wav")

                    all_snapshots_df['start_time'] = pd.to_datetime(all_snapshots_df['serverStartTime'], unit='ms', errors="ignore")
                    all_snapshots_df['local_start_time'] = pd.to_datetime(all_snapshots_df['localStartTime'], unit='ms', errors="ignore") 

                    # If you need to format them to a specific string representation
                    all_snapshots_df['start_time'] = all_snapshots_df['start_time'].dt.strftime('%m/%d/%Y %I:%M:%S %p') 
                    all_snapshots_df['local_start_time'] = all_snapshots_df['local_start_time'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
                
                if not all_nodes_df.empty:
                    st.write("Converting tier epoch timestamps to datetimes...")
                    print("Converting tier epoch timestamps to datetimes...")
                    if SNES:
                        play_sound("sounds/smb_kick.wav")

                    if DEBUG:
                        debug_df(all_tiers_df, "all_tiers_df - post availability checks")

                    all_tiers_df['Last Seen Tier'] = pd.to_datetime(all_tiers_df['Last Seen Tier'], unit='ms')
                    
                    st.write("Converting node epoch timestamps to datetimes...")
                    print("Converting node epoch timestamps to datetimes...")
                    if SNES:
                        play_sound("sounds/smb_kick.wav")

                    if DEBUG:
                        debug_df(all_nodes_df, "all_nodes_df - post avaialability checks")

                    all_nodes_df['Last Seen Node'] = pd.to_datetime(all_nodes_df['Last Seen Node'], unit='ms') 

                    # format them to a specific string representation
                    all_tiers_df['Last Seen Tier'] = all_tiers_df['Last Seen Tier'].dt.strftime('%m/%d/%Y %I:%M:%S %p') 
                    all_nodes_df['Last Seen Node'] = all_nodes_df['Last Seen Node'].dt.strftime('%m/%d/%Y %I:%M:%S %p')
            
        if retrieve_servers:
            if CALC_MACHINE_AVAILABILITY:
                if not all_servers_df.empty:
                    st.write("Converting server epoch timestamps to datetimes...")
                    print("Converting server epoch timestamps to datetimes...")
                    if SNES:
                        play_sound("sounds/smb_kick.wav")

                    if DEBUG:
                        debug_df(all_servers_df, "all_servers_df - post availability checks")

                    all_servers_df['Last Seen Server'] = pd.to_datetime(all_servers_df['Last Seen Server'], unit='ms')
                    all_servers_df['Last Seen Server'] = all_servers_df['Last Seen Server'].dt.strftime('%m/%d/%Y %I:%M:%S %p')    

        #merge things
        st.write("Performing merge on data to make it human-friendly...")
        # Merge the snapshots data with app, bt, tier and node data
        if not all_snapshots_df.empty and not applications_df.empty and not all_tiers_df.empty and not all_nodes_df.empty and not all_bts_df.empty:
            if DEBUG:
                st.write("Performing merge on snapshots data...")
                print("Performing merge on snapshots data...")

            all_snapshots_merged_df = pd.merge(
                all_snapshots_df, all_tiers_df, left_on="applicationComponentId", right_on="tier_id", how="left", suffixes=(None, "_tier")
            ).merge(
                all_nodes_df, left_on="applicationComponentNodeId", right_on="node_id", how="left", suffixes=(None, "_node")
            ).merge(
                all_bts_df, left_on="businessTransactionId", right_on="bt_id", how="left", suffixes=(None, "_bt")
            ).merge(
                applications_df, left_on="applicationId", right_on="app_id", how="left", suffixes=(None, "_app")
            )  

            #delete the all_snapshots_df to free up RAM
            if DEBUG:
                st.write("purging all_snapshots_df and performing GC to free RAM...")
                print("purging all_snapshots_df and performing GC to free RAM...")
            del all_snapshots_df
            gc.collect()

            #drop the redundant columns
            if DEBUG:
                print("Removing redundant columns from merge...")
                st.write("Doing some cleanup...")
              
            all_snapshots_merged_df.drop(columns=[
                'accountGuid',
                'app_id_tier',
                'app_id_node',
                'app_id_app',
                'app_name_app',
                'app_name_node',
                'agentType_node',
                'applicationId',
                'appAgentPresent',
                'bt_id',
                'description',
                'description_app',
                'entryPointTypeString',
                'id',
                'ipAddresses',
                'localID',
                'nodeUniqueLocalId',
                'numberOfNodes',
                'serverStartTime',
                'tierId_bt',
                'tierName_bt']
            , inplace=True, errors='ignore')
            
        else:
            if DEBUG:
                st.write("all_snapshots_df is empty, skipping merge...")
                print("all_snapshots_df is empty, skipping merge...")

        #merge node and server data 
        if retrieve_apm and retrieve_servers and not all_nodes_df.empty and not all_servers_df.empty:
            if DEBUG:
                st.write("Performing merge on servers data...")
                print("        --- Merging node and machine data.")
            
            st.write("Merging node and machine data...")
            
            all_nodes_merged_df = pd.merge (
                all_nodes_df, all_servers_df, left_on="machineName-cleaned", right_on="name", how="left", suffixes=(None, "_servers")
            )
            
            #delete the all_nodes_df to free up RAM
            if DEBUG:
                st.write("purging all_nodes_df and performing GC to free RAM...")
                print("purging all_nodes_df and performing GC to free RAM...")
            del all_nodes_df
            gc.collect()

            if NORMALIZE:
                def parse_properties(data, prefix):
                    """
                    Parses the data (dictionary or list) into individual columns, prefixing the column names.
                    Handles the 'Disk' key specially, keeping its sub-properties in a single 'Disk' column.

                    Args:
                        data (dict or list or None): The data to be parsed.
                        prefix (str): The prefix to add to the column names.

                    Returns:
                        pd.Series: A Series containing the parsed data, with NaN values for missing keys and prefixed column names.
                    """

                    if isinstance(data, dict):
                        result = pd.Series(dtype='object')

                        # Group all the disks together
                        disk_data = {k: v for k, v in data.items() if k.startswith('Disk|')}
                        if disk_data:
                            #result[prefix + "|Disk"] = [disk_data]
                            result["Disk"] = str(disk_data)

                        # Parse the remaining data (excluding 'Disk' sub-properties)
                        remaining_data = {k: v for k, v in data.items() if not k.startswith('Disk|')}
                        #result = pd.concat([result, pd.Series(remaining_data).add_prefix(prefix + "|")])
                        result = pd.concat([result, pd.Series(remaining_data)])
                        return result

                    elif isinstance(data, list) and len(data) == 0:  # Empty list
                        return pd.Series(dtype='object')  # Empty Series
                    else:  # None or other unexpected values
                        return pd.Series(dtype='object')  # Empty Series

                try:
                    columns_to_parse = ['properties', 'memory', 'cpus']  # Add more column names if needed

                    for col in columns_to_parse:
                        # Parse the column into individual columns with prefix
                        if DEBUG:
                            st.write(f"Attempting to parse {col}")
                            print(f"Attempting to parse {col}")
                        
                        parsed_df = all_nodes_merged_df[col].apply(parse_properties, args=(col,))

                        # Join the parsed DataFrame back to the original DataFrame
                        if DEBUG:
                            st.write(f"Attempting join of {col} data to all_nodes_merged_df...")
                            print(f"Attempting join of {col} data to all_nodes_merged_df...")

                        all_nodes_merged_df = all_nodes_merged_df.join(parsed_df)

                        # Drop the original column
                        if DEBUG:
                            st.write(f"Dropping the source column {col}.")
                            print(f"Dropping the source column {col}.")
                        
                        all_nodes_merged_df.drop(columns=[col], inplace=True)
                    
                    #extract the goodies and leave the rest
                    all_nodes_merged_df['Physical'] = all_nodes_merged_df['Physical'].apply(lambda x: x['sizeMb'] if isinstance(x, dict) and 'sizeMb' in x else x)
                    all_nodes_merged_df['Swap'] = all_nodes_merged_df['Swap'].apply(lambda x: x['sizeMb'] if isinstance(x, dict) and 'sizeMb' in x else x)
                    

                except Exception as e:
                    st.write(f"An error occurred while parsing columns: {e}")
                    print(f"An error occurred while parsing columns: {e}")

            else:
                if DEBUG:
                    st.write("All nodes merged with corresponding server data.")
                    print("All nodes merged with corresponding server data.")
                    debug_df(all_nodes_merged_df, "all_nodes_merged_df")

            #drop unnecessary columns
            if DEBUG:
                st.write("Dropping unneeded columns from all_nodes_merged_df...")
            all_nodes_merged_df.drop(columns=[
                'agentConfig',
                'AppDynamics|Agent|JVM Info',
                'AppDynamics|Agent|Agent Pid',
                'AppDynamics|Agent|Machine Info',
                'controllerConfig',
                'ipAddresses',
                'machineAgentVersion',
                'nodeUniqueLocalId'
            ], inplace=True, errors='ignore')

            #do some renaming
            if DEBUG:
                st.write("Renaming columns to be more readable in all_nodes_merged_df...")
            all_nodes_merged_df.rename(columns={
                'agentType':'Node - Agent Type',
                'appAgentVersion':'App Agent Version',
                'app_name':'Application Name',
                'AppDynamics|Agent|Agent version':'Machine Agent Version',
                'AppDynamics|Agent|Build Number':'Machine Agent Build #',
                'AppDynamics|Agent|Install Directory':'Machine Agent Path',
                'AppDynamics|Machine Type':'Machine Agent Type',
                'Bios|Version':'BIOS Version',
                'node_name':'Node Name',
                'OS|Architecture':'OS Arch',
                'OS|Kernel|Release':'OS Version',
                'OS|Kernel|Name':'OS Name',
                'Physical':'RAM MB',
                'Swap':'SWAP MB',
                'Processor|Logical Core Count':'CPU Logical Cores',
                'Processor|Physical Core Count':'CPU Physical Cores',
                'tierName':'Tier Name',
                'Total|CPU|Logical Processor Count':'CPU Total Logical Cores',
                'type_servers':'Server Type',
                'type':'Tier Type',
                'volumes':'Volumes',
                'vCPU': 'CPU vCPU'
            }, inplace=True, errors='ignore') 
 
        #generate licensing df
        if retrieve_apm and retrieve_servers and not all_nodes_merged_df.empty:
            st.write("Generating license usage information...")
            # Apply the function and display the result
            license_usage_df = calculate_licenses(all_nodes_merged_df)
            debug_df(license_usage_df, "license_usage_df")
        else:
            st.write("Skipping license usage reporting - please run with retrieve servers option checked.")
    
        #--- start the output of all this data

        #change the output file name to include app name if this is being run against a single app
        if len(applications_df) == 1:
            OUTPUT_EXCEL_FILE = APPDYNAMICS_ACCOUNT_NAME+"-"+(applications_df["app_name"].iloc[0]).replace(" ", "_")+"-analysis_"+datetime.date.today().strftime("%m-%d-%Y")+".xlsx"

        st.write(f"Writing ourput to file: {OUTPUT_EXCEL_FILE}")
        if DEBUG:
            print(f"Writing ourput to file: {OUTPUT_EXCEL_FILE}")
        
        # --- Write to Excel with formatting ---
        try:
            with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine='xlsxwriter') as writer:
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
                    })  # Light gray
                even_row_format = workbook.add_format({
                    'border': 1
                    })  # White

                #df to sheet mapping
                for df_name, df in [
                    ("Info", information_df),
                    ("License Usage", license_usage_df),
                    ("Applications", applications_df),
                    ("BTs", all_bts_df),
                    ("Tiers", all_tiers_df),
                    ("Nodes", all_nodes_merged_df),
                    ("Backends", all_backends_df),
                    ("Health Rules", all_healthRules_df),
                    ("Snapshots", all_snapshots_merged_df),
                    ("Servers", all_servers_df)
                ]:
                    #handle case where user didn't pull servers and thus the merge never happened
                    if all_nodes_merged_df.empty and df_name == "Nodes":
                        df = all_nodes_df

                    if not df.empty:
                        if not df_name == "License Usage":
                            if DEBUG:
                                print(f"Ordering {df_name}...")
                                st.write(f"Ordering {df_name}...")

                            #convert all column names to strings
                            if DEBUG:
                                st.write(f"Converting column names in {df_name} to strings...")
                                print(f"Converting column names in {df_name} to strings...")
                            
                            df.columns = df.columns.astype(str)

                            # Get a list of column names in alphabetical order
                            if DEBUG:
                                st.write("Getting list of sorted column names...")
                                print("Getting list of sorted column names...")
                            
                            column_order = sorted(df.columns)

                            # Reorder the DataFrame's columns
                            if DEBUG:
                                st.write("Reordering the columns...")
                                print("Reordering the columns...")
                            
                            df = df[column_order]

                            # Replace NaNs with empty strings before writing to Excel
                            df.fillna('', inplace=True)
                        
                        else:
                            #ensure column headers are stings
                            df.columns = df.columns.astype(str)
                            # Replace NaNs with empty strings before writing to Excel
                            df.fillna('', inplace=True)

                        if DEBUG:
                            print(f"Writing {df_name} DataFrame...")
                            st.write(f"Writing {df_name} DataFrame...")

                        df.to_excel(writer, sheet_name=df_name, index=False)
                        
                        # Get the worksheet and apply formatting
                        worksheet = writer.sheets[df_name]

                        # Auto-adjust column widths and add formatting
                        for col_num, value in enumerate(df.columns.values):
                            try:
                                column_length = max(df[value].astype(str).map(len).max(), len(value))
                            except:
                                column_length = 10
                            
                            #set a max column length
                            if column_length > 50:
                                column_length = 50

                            worksheet.set_column(col_num, col_num, column_length + 2)
                            worksheet.write(0, col_num, value, header_format)  # Format header
                                    
                        # Apply alternating row colors (starting from the second row) except for the Snapshots sheet
                        if not df_name == "Snapshots":
                            for row_num in range(1, df.shape[0] + 1):
                                if row_num % 2 == 1:
                                    worksheet.set_row(row_num, cell_format=odd_row_format)
                                else:
                                    worksheet.set_row(row_num, cell_format=even_row_format)
                            
                        # Coloring snapshot rows based on userExperience
                        if df_name == "Snapshots":
                            for row_num in range(1, df.shape[0] + 1):
                                user_experience = df.loc[row_num - 1, 'userExperience']

                                if user_experience == 'NORMAL':
                                    fill_color = '#90EE90' 
                                elif user_experience == 'ERROR':
                                    fill_color = '#FA3B37' 
                                elif user_experience == 'SLOW':
                                    fill_color = '#FFFF80' 
                                elif user_experience == 'VERY_SLOW':
                                    fill_color = '#FC9C2D' 
                                elif user_experience == 'STALL':
                                    fill_color = '#FF69CD'
                                else:
                                    continue 

                                cell_format = workbook.add_format({'bg_color': fill_color, 'border': 1})
                                for col_num in range(df.shape[1]):
                                    cell_value = df.loc[row_num - 1, df.columns[col_num]]
                                    
                                    # Handle any list values
                                    if isinstance(cell_value, list):
                                        if len(cell_value) > 0:
                                            cell_value = str(cell_value[0])  # Or any other appropriate conversion
                                        else:
                                            cell_value = ""  # Or any other default value you prefer for empty lists
                                    

                                    worksheet.write(row_num, col_num, cell_value, cell_format)
                        
                    else:
                        st.write(f"{df_name} empty, skipping write.")

                st.write("*Finished.* :sunglasses:")
                if DEBUG:
                    print("Finished.")

        except PermissionError:
            st.warning(f"Unable to write to {OUTPUT_EXCEL_FILE}. Please check permissions.")
            keep_status_open = True

        except Exception as e:
            st.error(f"An error occurred while writing the file: {e}")
            keep_status_open = True

    status.update(label="Extraction complete!", state="complete", expanded=keep_status_open)

    # Open the Excel file
    if sys.platform == "win32":
        os.startfile(OUTPUT_EXCEL_FILE) 
    elif sys.platform == "darwin":  # macOS
        subprocess.call(["open", OUTPUT_EXCEL_FILE])
    else:  # Linux or other Unix-like systems
        subprocess.call(["xdg-open", OUTPUT_EXCEL_FILE])