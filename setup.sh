#!/bin/env bash

if ! command -v python3 &> /dev/null; then
    echo "python3 is not installed. Please install it and try again."
    exit 1
fi

if ! command -v ollama &> /dev/null; then
    read -p "Ollama is not installed. Would you like to install it? y/n (defaults to y): " INSTALL_OLLAMA
    INSTALL_OLLAMA=${INSTALL_OLLAMA:-y}
    if [[ "$INSTALL_OLLAMA" == "y" ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
        if ! command -v ollama &> /dev/null; then
            echo "Ollama installation failed. Please install it manually from https://ollama.com and try again."
            exit 1
        fi
        echo "✓ Ollama installed."
    else
        echo "Ollama is required. Please install it from https://ollama.com and try again."
        exit 1
    fi
fi

if [[ -f ".env" ]]; then
    echo ".env file already exists, exiting to avoid overwriting it."
    echo "Please remove the file if you want to use this script."
    exit 1
fi

spinner() {
    local pid=$1
    local msg=$2
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while kill -0 $pid 2>/dev/null; do
        for i in $(seq 0 9); do
            printf "\r${frames:$i:1} $msg"
            sleep 0.1
        done
    done
    printf "\r✓ $msg\n"
}
echo "Starting setup..."
echo "This script will automatically create a venv, install the required packages, and setup the .env file based on the options provided."
echo ""
python3 -m venv venv &
spinner $! "Creating venv.. this may take a while."
wait $!
venv/bin/python -m ensurepip --upgrade > /dev/null 2>&1 &
spinner $! "Ensuring pip is inside the venv..."
wait $!
venv/bin/python -m pip install -qq --upgrade pip &
spinner $! "Upgrading pip..."
wait $!
venv/bin/python -m pip install -qq -r requirements.txt &
spinner $! "Installing required packages..."
wait $!

get_vars() {
    read -p "Please input the bot token: " TOKEN
    while [[ -z "$TOKEN" ]]; do
        read -p "Please input the bot token: " TOKEN
        if [[ -z "$TOKEN" ]]; then
            echo "Bot token is required."
        fi
    done
    read -p "What model would you like to use? (default phi3:mini): " MODEL
    MODEL=${MODEL:-phi3:mini}
    read -p "What timezone should command logs be saved in? Timezones are in timezones.txt (default America/New_York): " TIMEZONE
    TIMEZONE=${TIMEZONE:-America/New_York}
    read -p 'What Ollama error message would you like to use? (default "I couldn'\''t process that."): ' ERROR_MSG
    ERROR_MSG=${ERROR_MSG:-I couldn\'t process that.}
    read -p "How many messages should be in the AIs memory? (default 10): " MEMORY_AMT
    MEMORY_AMT=${MEMORY_AMT:-10}
    read -p "Max character count for the URL fetch? (default 3000): " MAX_CHAR_URL
    MAX_CHAR_URL=${MAX_CHAR_URL:-3000}
    read -p "Show full system prompt when using the /model_info command? true/false (default true): " SHOW_FULL_SYS
    SHOW_FULL_SYS=${SHOW_FULL_SYS:-true}
    read -p "Use instructions from instructions.txt? true/false, set to false if using a custom model (default true): " USE_INSTRUCTIONS
    USE_INSTRUCTIONS=${USE_INSTRUCTIONS:-true}
    read -p "URL manager user IDs, comma separated (leave blank for none): " URL_MANAGER_IDS
    read -p "Install Playwright for JS page rendering fallback? y/n (default y): " PLAYWRIGHT
    PLAYWRIGHT=${PLAYWRIGHT:-y}
    read -p "Automatically pull the model and test the Ollama API? y/n (default y): " PULL_TEST_API
    PULL_TEST_API=${PULL_TEST_API:-y}
}
get_vars
if [[ "$PLAYWRIGHT" == "y" ]]; then
    venv/bin/pip install -qq playwright &
    spinner $! "Installing Playwright..."
    wait $!
    venv/bin/playwright install chromium > /dev/null 2>&1 &
    spinner $! "Installing Chromium..."
    wait $!
fi
if [[ "$PULL_TEST_API" == "y" ]]; then
    ollama pull $MODEL > /dev/null 2>&1 &
    spinner $! "Pulling Ollama model $MODEL..."
    wait $!
    if ! curl -s http://localhost:11434 &> /dev/null; then
        echo "Ollama is not running, starting it..."
        nohup ollama serve > /dev/null 2>&1 &
        sleep 2
        if ! curl -s http://localhost:11434 &> /dev/null; then
            echo "Failed to start Ollama. Please start it manually with 'ollama serve &'."
        fi
    fi
fi
if [[ $1 == "DEBUG" ]]; then
    echo "=== DEBUG ==="
    echo "MODEL set to $MODEL"
    echo "TIMEZONE set to $TIMEZONE"
    echo "ERROR_MSG set to $ERROR_MSG"
    echo "MEMORY_AMT set to $MEMORY_AMT"
    echo "MAX_CHAR_URL set to $MAX_CHAR_URL"
    echo "SHOW_FULL_SYS set to $SHOW_FULL_SYS"
    echo "USE_INSTRUCTIONS set to $USE_INSTRUCTIONS"
    echo "URL_MANAGER_IDS set to $URL_MANAGER_IDS"
    echo "PLAYWRIGHT set to $PLAYWRIGHT"
    echo "PULL_TEST_API set to $PULL_TEST_API"
else
    cat > .env << EOF
BOT_TOKEN=${TOKEN}
TIMEZONE=${TIMEZONE}
OLLAMA_MODEL=${MODEL}
OLLAMA_ERROR_MESSAGE=${ERROR_MSG}
MESSAGE_MEMORY=${MEMORY_AMT}
URL_FETCH_MAX_CHARS=${MAX_CHAR_URL}
URL_MANAGER_IDS=${URL_MANAGER_IDS}
SHOW_FULL_SYSTEM_PROMPT=${SHOW_FULL_SYS}
USE_INSTRUCTIONS=${USE_INSTRUCTIONS}
EOF
    echo "✓ .env file created."
fi
echo "Setup done! Use source venv/bin/activate then python3 chatbot.py to start the bot."
exit 0