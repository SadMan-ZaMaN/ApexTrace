"""Start the web app with a file name:  python run.py   (same as: python -m app)

Then open http://127.0.0.1:5000 . Stop with Ctrl+C.
"""

from app import create_app

if __name__ == "__main__":
    # 127.0.0.1 = only this computer can open it (not the local network)
    create_app().run(host="127.0.0.1", port=5000, debug=False)
