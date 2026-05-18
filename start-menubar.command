#!/bin/bash
# Start the Levity Voice menu bar app.
# Double-click this file in Finder, or run it from Terminal.

VENV="$HOME/.levity-voice/venv/bin/python"
SCRIPT="$HOME/.levity-voice/menubar.py"

if [ ! -f "$VENV" ]; then
    echo "Error: Virtual environment not found at $VENV"
    echo "Run: cd ~/.levity-voice && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    read -p "Press Enter to close..."
    exit 1
fi

if [ ! -f "$SCRIPT" ]; then
    echo "Error: menubar.py not found at $SCRIPT"
    read -p "Press Enter to close..."
    exit 1
fi

echo "Starting Levity Voice menu bar app..."
"$VENV" "$SCRIPT" &
MENU_PID=$!
echo "Menu bar app started (PID $MENU_PID)"
sleep 1

# Check if it's still running
if kill -0 "$MENU_PID" 2>/dev/null; then
    echo "Running successfully. You can close this window."
else
    echo "Error: Menu bar app exited unexpectedly."
    echo "Check the console for errors."
    read -p "Press Enter to close..."
    exit 1
fi
