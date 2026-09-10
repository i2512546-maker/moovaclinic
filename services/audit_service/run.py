if __name__ == "__main__":
    from services.audit_service.app import create_app
    app = create_app()
    app.run(host="0.0.0.0", port=5006, debug=True)