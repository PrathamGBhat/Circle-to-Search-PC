pip install -r windows_requirements.txt
python -m venv venv
source ./venv/Scripts/activte

Setup docker before running
1. Go to backend/litellm
2. Add your api keys for gemini and groq and set litellm master key as "sk-1234" in docker-compose.yml (Only gemini and groq supported for now) 
3. Compose docker with command
  docker compose up -d
4. Start docker instance

How to add a new api key
1. First put the api key of provider in .env
2. Go to litellm_config.yaml and add the new entry similar to existing entries - also make sure to refer to models.litellm.ai for the expected name in litellm.model field
3. Go to manager.py, uncomment the restart_litellm() line and run manager.py
4. Go to windows tray icon, stop, start again
5. Done

Actual running
1. Create shortcut of control.pyw
2. Place it in startup apps
3. Optionally restart your computer or just execute control.pyw
4. Open your tray icons to see the icon 
5. Pressing start starts listener.py as the background process listening if you pressed hotkey
6. Ctrl + Shift + F9 to open chat interface
7. If you already copied something on your clipboard, it automatically attaches to prompt
NOTE: Images are supported but make sure you have a vision model in the backend to process those images and also sometimes rate limiting may prevent streaming response
SUGGESTION: Just use text based groq api key

Debugging:
1. Any error will be logged to log.txt