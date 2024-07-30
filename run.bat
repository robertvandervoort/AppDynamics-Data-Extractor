@echo off

:: Check if virtual environment exists
if not exist "venv" (
    echo Virtual environment not found. Creating...
    python -m venv venv

    if errorlevel 1 (
        echo Failed to create virtual environment. Exiting.
        exit /b 1
    )

    :: Install requirements (since venv was just created)
    if exist "requirements.txt" (
        echo Installing requirements from requirements.txt...
        venv\Scripts\activate
        python -m pip install -r requirements.txt --disable-pip-version-check

        if errorlevel 1 (
            echo Failed to install requirements. Exiting.
            exit /b 1
        )
    )
) else (
    :: Activate the virtual environment
    venv\Scripts\activate

    :: Check if requirements are already installed
    python -m pip list --format=freeze --disable-pip-version-check > installed.txt
    findstr /V /G:"requirements.txt" installed.txt > missing.txt
    del installed.txt
    
    if not exist missing.txt (
        echo All requirements are already installed.
    ) else (
        echo Installing missing requirements from requirements.txt...
        python -m pip install -r requirements.txt --disable-pip-version-check

        if errorlevel 1 (
            echo Failed to install requirements. Exiting.
            exit /b 1
        )
    )
    del missing.txt
)

:: Execute Python script
streamlit run appd-extractor.py

:: Optionally, deactivate the virtual environment after the script finishes
deactivate
