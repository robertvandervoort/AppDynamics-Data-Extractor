@echo off

if not exist "venv" (
    echo Virtual environment not found. Creating...
    python -m venv venv

    if errorlevel 1 (
        echo Failed to create virtual environment. Exiting.
        exit /b 1
    )

    if exist "requirements.txt" (
        echo Installing requirements from requirements.txt...
        venv\Scripts\activate
        python -m pip install -r requirements.txt --disable-pip-version-check

        if errorlevel 1 (
            echo Failed to install requirements. Exiting.
            exit /b 1
        )
    )

    REM Disable telemetry and run in headless mode to avoid email prompts
    set STREAMLIT_SERVER_HEADLESS=true
    streamlit run appd-extractor.py --server.headless true

) else (
    echo Activating the virtual environment...
    venv\Scripts\activate

    if exist "requirements.txt" (
        echo Installing any missing requirements from requirements.txt...
        venv\Scripts\activate
        python -m pip install -r requirements.txt --disable-pip-version-check

        if errorlevel 1 (
            echo Failed to install requirements. Exiting.
            exit /b 1
        )
    )

    REM Disable telemetry and run in headless mode to avoid email prompts
    set STREAMLIT_SERVER_HEADLESS=true
    streamlit run appd-extractor.py --server.headless true
)

