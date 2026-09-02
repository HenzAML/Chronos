import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app import create_app

app = create_app()

if __name__ == "__main__":
    # 5000 is taken by macOS ControlCenter (AirPlay Receiver), which answers 403
    # instead of refusing the connection - so default to 5001 and allow override.
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=True)
