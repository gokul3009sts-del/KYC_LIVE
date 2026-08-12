"""
run.py — Development server entry point.

For production, use gunicorn instead of this file:
    gunicorn -w 3 -b 127.0.0.1:5000 --timeout 120 "run:app"

Debug mode follows FLASK_ENV in .env — it is NOT hardcoded on, so it
cannot accidentally stay enabled once FLASK_ENV=production is set.
"""
from app import create_app
from app.config import config

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=config.DEBUG,
        use_reloader=config.DEBUG,
    )
