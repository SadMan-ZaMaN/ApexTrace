"""Start the local server:  .venv\\Scripts\\python.exe -m app   then open http://127.0.0.1:5000"""

from app import create_app

if __name__ == "__main__":
    # 127.0.0.1 = only this computer can open it (not the local network)
    create_app().run(host="127.0.0.1", port=5000, debug=False)
