# AppDynamics-Data-Extractor
This tool simplifies the process of extracting and visualizing data from your AppDynamics environment. Whether you're using Mac, Linux, or Windows, getting started is a breeze. Use cases will be discussed further down this readme.

### Getting Started

1. **Clone the Repository:**

   * **Using Git:**
     ```bash
     git clone https://github.com/robertvandervoort/AppDynamics-Data-Extractor.git
     ```
   * **Using GitHub Desktop:**
     * Click the green "Code" button and choose "Open with GitHub Desktop."
     * Follow the prompts to clone the repository to your local machine.

2. **Rename secrets.yml.template to secrets.yml**

3. **Run the Extractor:**

   * **Mac/Linux:**
      * **Prerequisites:** Make sure you have `pip` (Python package installer) installed.
      * Open your terminal and navigate to the cloned repository's directory.
      * Execute the following command:
        ```bash
        ./run.sh
        ```
        or on Mac
        ```zsm
        source run.sh
        ```
        This script will:
          1. Create a virtual environment.
          2. Install required Python packages within the environment.
          3. Run the data extractor using Streamlit.
          4. Automatically deactivate the virtual environment when you terminate the script (control-c).

   * **Windows:**
      * Open your terminal and navigate to the cloned repository's directory.
      * Execute the following command:
        ```command prompt
        run.bat
        ```
        This script will perform the same steps as the `run.sh` script, but is tailored for Windows environments.

### Future Use

You can always launch the AppDynamics Data Extractor using the `run.sh` (Mac/Linux) or `run.bat` (Windows) scripts. This ensures the necessary environment setup and provides a convenient way to access the tool whenever you need it. Alternatively you can manually activate the python virtual environment and then execute the script with "streamlit run appd-extractor.py"

### Additional Notes

* Make sure you have valid AppDynamics credentials. You'll be prompted to enter these when running the extractor. The extractor uses API clients and not username / password combinations so you will need to create an API client in the administration section of your controller to use for this. The API client should have Administrator, Analytics Administrator and Account Owner roles. This is due to the scope of information gathered by this tool. It may run with lower permissions but some data may not be available. Instructions for creating an API client can be found here. https://docs.appdynamics.com/appd/24.x/24.7/en/extend-cisco-appdynamics/cisco-appdynamics-apis/api-clients
* The extractor will guide you through selecting the specific data you want to extract and visualize.
* If you do not select an application ID, the extractor will pull data for ALL applications on the controoler. This can take some time.
* By default, the tool captures the last hour of data for availability (if selected) and transaction snapshots (if selected). This can be adjusted in the UI.
* Enable debugging if you want to watch the tool work or if you run into issues. Debug output will be sent to the UI in Streamlit in a more digestible fashion, and in a more verbose fashion in the console window you launched it from. When contacting me / filing an issue, please have the debug output available.

### License Processing (BETA)

**Important:** License calculation functionality is currently in BETA status and is **disabled by default**. This feature can be enabled through the "Enable license processing?" checkbox in the user interface, but please be aware that:

* This is experimental functionality with known issues
* License calculations may not be accurate in all scenarios
* Performance may be impacted when enabled
* Results should be validated against your actual AppDynamics license usage
* The feature may be modified or removed in future versions based on user feedback

If you encounter issues with license processing, please disable this feature and report any problems through the project's issue tracker.