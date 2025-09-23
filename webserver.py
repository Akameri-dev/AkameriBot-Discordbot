
# webserver.py - Versión mejorada
from flask import Flask 
import os
import threading

app = Flask('')

@app.route('/')
def index():
    return 'Bot is alive!'

@app.route('/health')
def health():
    return 'OK', 200

def run():
    port = int(os.environ.get('PORT', 8000))

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def keep_alive():
    server = threading.Thread(target=run)
    server.daemon = True
    server.start()
    