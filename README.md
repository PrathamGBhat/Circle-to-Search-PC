pip install -r windows_requirements.txt

Setup docker before running
1. Go to backend/litellm
2. Add your api keys for gemini and groq and set litellm master key as "sk-1234" in docker-compose.yml (Only gemini and groq supported for now) 
3. Compose docker with command
  docker compose up -d
4. Start docker instance

Actual running
1. Run windows/control.pyw
2. Start process
3. Can close control.pyw as its a separate process from listener.py
4. listener.py runs as the background process
5. Take screenshot from snipping tool and copy image
6. Ctrl + Shift + F9 to open chat interface

How to add a new api key
1. First put the api key of provider in .env
2. Go to litellm_config.yaml and add the new entry similar to existing entries - also make sure to refer to models.litellm.ai for the expected name in litellm.model field
3. Go to manager.py, uncomment the restart_litellm() line and run manager.py
4. Go to windows tray icon, stop, start again
5. Done
