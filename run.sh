
#!/usr/bin/env sh

# Check if running on Replit
if [ -n "$REPL_ID" ]; then
    # On Replit, just run streamlit directly
    python3 -m streamlit run appd-extractor.py
    exit 0
fi

VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"

# Rest of the original venv logic for non-Replit environments
if [ -d "$VENV_DIR" ]; then
    SHELL_TYPE="$(basename $SHELL)"
    case "$SHELL_TYPE" in
        zsh)
            source "$VENV_DIR"/bin/activate
            ;;
        bash | sh)
            . "$VENV_DIR"/bin/activate  
            ;;
        csh | tcsh)
            source "$VENV_DIR"/bin/activate.csh
            ;;
        *)
            echo "Unsupported shell type: $SHELL_TYPE"
            exit 1
            ;;
    esac

    if ! python3 -m pip list --format=freeze --disable-pip-version-check 2>/dev/null | grep -q -F -f "$REQUIREMENTS_FILE"; then 
        echo "Installing missing requirements from $REQUIREMENTS_FILE..."
        python3 -m pip install -r "$REQUIREMENTS_FILE" --disable-pip-version-check

        if [ $? -ne 0 ]; then
            echo "Failed to install requirements. Exiting."
            exit 1
        fi
    fi
else
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$VENV_DIR"

    if [ $? -ne 0 ]; then
        echo "Failed to create virtual environment. Exiting."
        exit 1
    fi

    if [ -f "$REQUIREMENTS_FILE" ]; then
        echo "Installing requirements from $REQUIREMENTS_FILE..."
        . "$VENV_DIR"/bin/activate 
        pip cache purge
        pip install --upgrade pip setuptools wheel
        python3 -m pip install -r "$REQUIREMENTS_FILE" --disable-pip-version-check

        if [ $? -ne 0 ]; then
            echo "Failed to install requirements. Exiting."
            exit 1
        fi
    fi
fi

python3 -m streamlit run appd-extractor.py
deactivate
