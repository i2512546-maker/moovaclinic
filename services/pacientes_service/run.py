import os

if __name__ == "__main__":
    from services.pacientes_service.app import create_app
    app = create_app()
    debug = os.getenv("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(host="0.0.0.0", port=5002, debug=debug)
