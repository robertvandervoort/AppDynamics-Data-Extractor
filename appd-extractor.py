import streamlit as st
import pandas as pd

import datetime
from io import StringIO
import xml.etree.ElementTree as ET
import requests
import json
import urllib.parse
import time
import sys

#--- CONFIGURATION SECTION ---
# Verify SSL certificates - should only be set false for on-prem controllers. Use this if the script fails right off the bat and gives you errors to the point..
VERIFY_SSL = True

#manages token expiration - do not change these values
last_token_fetch_time = ""
token_expiration = 300
expiration_buffer = 30

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

    if __session__ is None:
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
    
    # Replace spaces with '%20'
    text = text.replace(' ', '%20')

    # Encode the string using the 'safe' scheme
    safe_characters = '-_.!~*\'()[]+:;?,/=$&%'
    encoded_text = urllib.parse.quote(text, safe=safe_characters)

    return encoded_text

#@handle_rest_errors
def get_metric(object_type, app, tier, agenttype, node):
    """fetches last known agent availability info from tier or node level."""
    if DEBUG:
        print(f"        --- Begin get_metric({object_type},{app},{tier},{agenttype},{node})")

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
        metric_path = "Application%20Infrastructure%20Performance%7C" + tier + "%7CAgent%7CApp%7CAvailability"
        
    # If the machine agents were assigned a tier, the tier reads as an app agent. The availability data would be here instead
    # metric_path = "Application%20Infrastructure%20Performance%7C" + tier_name + "%7CAgent%7CMachine%7CAvailability"
    # future enhancement will reflect the number and last seen for machine agent tiers.

    metric_url = BASE_URL + "/controller/rest/applications/" + app + "/metric-data?metric-path=" + metric_path + "&time-range-type=BEFORE_NOW&duration-in-mins=" + str(METRIC_DURATION_MINS) + "&rollup=" + METRIC_ROLLUP + "&output=json"
                                
    #get metric data
    if DEBUG:
        print("        --- metric url: " + metric_url)

    metric_response = requests.get(
        metric_url,
        headers = __session__.headers,
        verify = VERIFY_SSL
    )

    print(f"Metric response raw: {metric_response}")
    return metric_response

def convert_epoch_timestamp(timestamp):
    """used for converting AppD timestamps to human readable form"""
    #if DEBUG:
    #    print(f"        --- Performing datetime calculation on value: {timestamp}")
    
    #convert EPOCH to human readable datetime - we have to divide by 1000 because we show EPOCH in ms not seconds
    epoch = (timestamp/1000)
    dt = datetime.datetime.fromtimestamp(epoch)
    return dt

def handle_metric_response(metric_data, metric_data_status):
    """Processes returned metric JSON data"""
    if DEBUG:
        print("        --- handle_metric_response() - Handling metric data...")
        print(f"        --- handle_metric_response() - metric_data: {metric_data}")
        print(f"        --- handle_metric_response() - metric_data type: {type(metric_data)}")
        print(f"        --- handle_metric_response() - metric_data_status: {metric_data_status}")

    if metric_data_status == "valid":
        if metric_data == []:
            dt = "METRIC DATA NOT FOUND IN TIME RANGE"
            print(dt)
            return dt, metric_data_status

        if metric_data[-1]['metricName'] == "METRIC DATA NOT FOUND":
            dt = "METRIC DATA NOT FOUND IN TIME RANGE"
            print(dt)
            return dt, metric_data_status

        elif metric_data[-1]['metricValues'][-1]['startTimeInMillis']:
            last_start_time_millis = metric_data[-1]['metricValues'][-1]['startTimeInMillis']
            dt = convert_epoch_timestamp(last_start_time_millis)
            value = metric_data[-1]['metricValues'][-1]['current']
            if DEBUG:
                print(f"            --- dt: {dt} value: {value}")
            return dt, value

    elif metric_data_status == "empty":
        dt = "EMPTY RESPONSE"
        return dt, metric_data_status
    
    elif metric_data_status == "error":
        dt = "ERROR"
        return dt, metric_data_status
    
    elif metric_data == []:
        dt = "EMPTY RESPONSE"
        return dt, metric_data_status

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
            
            #pass error and exceptions from the response along to the main code
            if data_status != "valid":
                if DEBUG:
                    print(f"        --- response data is not valid. status = {data_status}")

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
        if not data:
            if DEBUG:
                print("            --- The resulting JSON object judged as empty")
                print(f"            --- data: {data}")
            data_status = "empty"
    
        return data, data_status

    except json.JSONDecodeError:
        # The data is not valid JSON.
        if DEBUG:
            print("            --- The data is not valid JSON.")
        return None, "error"

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

    #if DEBUG:
    #    print(applications_response.text)

    return applications_response

def refresh_applications():
    st.write("Retrieving applications...")
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
    snapshots_url = BASE_URL + "/controller/rest/applications/" + str(application_id) + "/request-snapshots?time-range-type=BEFORE_NOW&duration-in-mins=" + str(METRIC_DURATION_MINS) + "&first-in-chain=false&need-exit-calls=true&need-props=true&maximum-results=1000000&output=json"

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
    print("length of bts_response")
    print (len(bts_response.content.strip()))
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

def debug_df(df, df_name, num_lines=10):
    """Displays DataFrame information in a more readable way."""
    st.subheader(f"Debug Info: {df_name}")  # Use subheader instead of nested expander
    st.write(f"Shape: {df.shape}")
    st.write(f"Columns: {df.columns.to_list()}")
    st.write(f"First {num_lines} rows:")
    st.write(df.head(num_lines).to_markdown(index=False, numalign='left', stralign='left'))

# --- MAIN (Streamlit UI) ---
st.title("AppDynamics Data Extractor (not DEXTER)")

# --- user config form
with st.form("config_form"):
    account_name = st.text_input("Account Name", value="")
    api_client = st.text_input("API client name", value="")
    api_key = st.text_input("API Key", type="password", value="")
    
    application_id = st.text_input("Application ID (optional)", value="")
    
    calc_availability = st.checkbox("Analyze availability?", value=False)
    metric_duration_mins = st.text_input("How far to look back for data / snapshots (mins)", value="60")
    #add this back at some point maybe
    #metric_rollup = st.checkbox("Rollup metrics?", value=False)
    pull_snapshots = st.checkbox("Get Snapshots?", value=False)
    debug_output = st.checkbox("Debug output?", value=False)

    # Submit button
    submitted = st.form_submit_button("Extract Data")

if submitted:
    # Update global variables with user input
    global APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, APPDYNAMICS_API_CLIENT_SECRET, \
        APPLICATION_ID, DEBUG, METRIC_DURATION_MINS, PULL_SNAPSHOTS, CALC_AVAILABILITY
    print(f"account_name={account_name}, api_client={api_client}, api_key={api_key}, a[[;ocatopm_id={application_id}]]")
    APPDYNAMICS_ACCOUNT_NAME = account_name
    APPDYNAMICS_API_CLIENT = api_client
    APPDYNAMICS_API_CLIENT_SECRET = api_key
    APPLICATION_ID = application_id
    DEBUG = debug_output
    
    if calc_availability:
        CALC_AVAILABILITY = True
    else:
        CALC_AVAILABILITY = False

    METRIC_DURATION_MINS = metric_duration_mins

    # add this back at some point maybe
    #if metric_rollup:
    #    METRIC_ROLLUP = "true"
    #else:
    METRIC_ROLLUP = "false"

    if pull_snapshots:
        PULL_SNAPSHOTS = True
    else:
        PULL_SNAPSHOTS = False

    # Replace with the desired output file path and name or leave as it to create dynamically (recommended)
    OUTPUT_EXCEL_FILE = APPDYNAMICS_ACCOUNT_NAME+"_analysis_"+datetime.date.today().strftime("%m-%d-%Y")+".xlsx"

    # Set the base URL for the AppDynamics REST API
    # --- replace this with your on-prem controller URL if you're on prem
    BASE_URL = "https://"+APPDYNAMICS_ACCOUNT_NAME+".saas.appdynamics.com"

    # --- MAIN application code
    with st.status("Extracting data...", expanded=True) as status:
        st.write(f"Logging into controller at {BASE_URL}...")
        authenticate("initial")

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

            st.session_state['applications_df'] = applications_df  # Store in session state

            if DEBUG:
                debug_df(applications_df, "applications_df")

            # Initialize empty DataFrames for aggregate storage
            information_df = pd.DataFrame()
            all_bts_df = pd.DataFrame()
            all_tiers_df = pd.DataFrame()
            all_nodes_df = pd.DataFrame()
            all_backends_df = pd.DataFrame()
            all_healthRules_df = pd.DataFrame()
            all_snapshots_df = pd.DataFrame()
            all_snapshots_merged_df = pd.DataFrame()

            #get current date and time and build info sheet - shoutout to Peter Wivagg for the suggestion
            now = datetime.datetime.now()
            current_date_time = now.strftime("%Y-%m-%d %H:%M:%S")

            information_df = pd.DataFrame({
                "setting": ["RUN_DATE","BASE_URL", "APPDYNAMICS_ACCOUNT_NAME", "APPDYNAMICS_API_CLIENT", "APPDYNAMICS_API_CLIENT_SECRET", "APPLICATION_ID", "METRIC_DURATION_MINS", "METRIC_ROLLUP", "PULL_SNAPSHOTS"],
                "value": [current_date_time, BASE_URL, APPDYNAMICS_ACCOUNT_NAME, APPDYNAMICS_API_CLIENT, "xxx", APPLICATION_ID, METRIC_DURATION_MINS, METRIC_ROLLUP, PULL_SNAPSHOTS]
            })

            # Process each application
            for _, application in applications_df.iterrows():
                #initialize DataFrames
                bts_df = pd.DataFrame()
                tiers_df = pd.DataFrame()
                nodes_df = pd.DataFrame()
                backends_df = pd.DataFrame()
                healthRules_df = pd.DataFrame()
                snapshots_df = pd.DataFrame()
                
                app_id = application["app_id"]
                app_name = application["app_name"]

                # Get and process business transactions
                st.write(f"Retrieving business transactions for {app_name}...")
                bts_response = get_bts(app_id)
                bts_data, bts_status = bts_response
                
                if bts_status == "valid":
                    bts_df['app_id'] = app_id
                    bts_df = pd.DataFrame(bts_data)
                    bts_df = bts_df.rename(columns={
                        "id": "bt_id",
                        "name": "bt_name"
                    })
                    
                    all_bts_df = pd.concat([all_bts_df, bts_df])

                    if DEBUG:
                        print(f"App id:{app_id}")
                        debug_df(bts_df, "bts_df")
                        #input("PRESS ANY KEY")
                elif bts_status == "empty":
                    bts_df = pd.DataFrame()
                    if DEBUG:
                        print("BT DATAFRAME EMPTY")
                
                # Get and process tiers
                st.write(f"Retrieving tiers for {app_name}...")
                tiers_response = get_tiers(app_id)
                tiers, tiers_status = validate_json(tiers_response)
                if tiers_status == "valid":
                    tiers_df = pd.DataFrame(tiers)
                    tiers_df['app_id'] = app_id
                    tiers_df = tiers_df.rename(columns={
                        "id": "tier_id",
                        "name": "tier_name"
                    })

                    all_tiers_df = pd.concat([all_tiers_df, tiers_df])

                    if DEBUG:
                        debug_df(tiers_df, "tiers_df")
                        #input("PRESS ANY KEY")

                # Get and process nodes
                st.write(f"Retrieving nodes for {app_name}...")
                nodes_response = get_app_nodes(app_id)
                nodes, nodes_status = validate_json(nodes_response)
                if nodes_status == "valid":
                    nodes_df = pd.DataFrame(nodes)
                    nodes_df['app_id'] = app_id
                    nodes_df = nodes_df.rename(columns={
                        "id": "node_id",
                        "name": "node_name"
                    })

                    if CALC_AVAILABILITY:
                        # Function to apply to each row
                        
                        def get_last_seen(row):
                            availability_response = get_metric("node", app_name, row['tierName'], row['agentType'], row['node_name'])
                            availability_data, availability_data_status = validate_json(availability_response)

                            if availability_data_status == "valid":
                                last_seen, _ = handle_metric_response(availability_data, availability_data_status)
                                return last_seen
                            else:
                                return None  # or a default value if desired

                        # Apply the function and create the new column
                        nodes_df['last_seen'] = nodes_df.apply(get_last_seen, axis=1)

                        # (Optional) Filter out rows where last_seen is None
                        # nodes_df = nodes_df.dropna(subset=['last_seen'])

                    all_nodes_df = pd.concat([all_nodes_df, nodes_df])

                    if DEBUG:
                        debug_df(nodes_df, "nodes_df")
                        #input("PRESS ANY KEY")

                # Get and process backends
                st.write(f"Retrieving backends for {app_name}...")
                backends_response = get_app_backends(app_id)
                backends, backends_status = validate_json(backends_response)
                if backends_status == "valid":
                    backends_df = pd.DataFrame(backends)
                    backends_df['app_id'] = app_id
                    backends_df = backends_df.rename(columns={
                        "id": "backend_id",
                        "name": "backend_name"
                    })

                    all_backends_df = pd.concat([all_backends_df, backends_df])

                    if DEBUG:
                        debug_df(backends_df, "backends_df")
                        #input("PRESS ANY KEY")

                # Get and process snapshots
                if PULL_SNAPSHOTS:
                    st.write(f"Retrieving snapshots for {app_name}...")
                    snapshots_response = get_snapshots(app_id)
                    snapshots, snapshots_status = validate_json(snapshots_response)
                    if snapshots_status == "valid":
                        snapshots_df = pd.DataFrame(snapshots)
                        snapshots_df['app_id'] = app_id
                        if DEBUG:
                            #input("main code - snapshots status is valid")
                            print()
                            debug_df(snapshots_df, "snapshots_df")
                        all_snapshots_df = pd.concat([all_snapshots_df, snapshots_df])
                        #if DEBUG:
                            #debug_df(all_snapshots_df, "all_snapshots_df")
                            #input("main code - snapshots status is valid")

                    elif snapshots_status == "empty":
                        print ("            --- No snapshots returned")
                        st.write(f"No snapshots found for {app_name}.")

            #merge the things
            # Join the DataFrames as needed
            if not all_snapshots_df.empty:
                st.write("Performing merge on snapshots data...")
                all_snapshots_merged_df = pd.merge(
                    all_snapshots_df, all_tiers_df, left_on="applicationComponentId", right_on="tier_id", how="left", suffixes=(None, "_tier")
                ).merge(
                    all_nodes_df, left_on="applicationComponentNodeId", right_on="node_id", how="left", suffixes=(None, "_node")
                ).merge(
                    all_bts_df, left_on="businessTransactionId", right_on="bt_id", how="left", suffixes=(None, "_bt")
                ).merge(
                    applications_df, left_on="applicationId", right_on="app_id", how="left", suffixes=(None, "_app")
                )

                #drop the redundant columns
                if DEBUG:
                    print("Removing redundant columns from merge...")
                else:
                    st.write("Removing redundant columns from merge...")
                
                all_snapshots_merged_df.drop(columns=['app_id_tier','app_id_node','app_id_app','app_id','bt_id','entryPointTypeString'], inplace=True)
            else:
                st.write("all_snapshots_df is empty, skipping merge...")
                if DEBUG:
                    print("all_snapshots_df is empty, skipping merge...")

            #change the output file name to include app name if this is against a single app
            if len(applications_df) == 1:
                OUTPUT_EXCEL_FILE = APPDYNAMICS_ACCOUNT_NAME+"-"+(applications_df["app_name"].iloc[0]).replace(" ", "_")+"-analysis_"+datetime.date.today().strftime("%m-%d-%Y")+".xlsx"

            st.write(f"Writing ourput to file: {OUTPUT_EXCEL_FILE}")
            if DEBUG:
                print(f"Writing ourput to file: {OUTPUT_EXCEL_FILE}")
            
            # --- Write to Excel with formatting ---
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

                df_to_sheet_map = {}

                for df_name, df in [
                    ("Info", information_df),
                    ("Applications", applications_df),
                    ("BTs", all_bts_df),
                    ("Tiers", all_tiers_df),
                    ("Nodes", all_nodes_df),
                    ("Backends", all_backends_df),
                    ("Snapshots", all_snapshots_merged_df),
                ]:
                    if not df.empty:
                        print(f"Writing {df_name} DataFrame...")
                        df.to_excel(writer, sheet_name=df_name, index=False)
                        
                        # Get the worksheet and apply formatting
                        worksheet = writer.sheets[df_name]

                        # Auto-adjust column widths and add formatting
                        for col_num, value in enumerate(df.columns.values):
                            column_length = max(df[value].astype(str).map(len).max(), len(value))
                            worksheet.set_column(col_num, col_num, column_length + 3)
                            worksheet.write(0, col_num, value, header_format)  # Format header
                            
                        # Apply alternating row colors (starting from the second row)
                        for row_num in range(1, df.shape[0] + 1):
                            if row_num % 2 == 1:
                                worksheet.set_row(row_num, cell_format=odd_row_format)
                            else:
                                worksheet.set_row(row_num, cell_format=even_row_format)
                st.write("*Finished.* :sunglasses:")
                if DEBUG:
                    print("Finished.")

        else:
            if application_id != "":
                st.write(f"No application data found for {application_id}")
            else:
                st.write("No application data found.")
    status.update(label="Extraction complete!", state="complete", expanded=False)