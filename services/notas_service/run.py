if __name__ == "__main__":
    from services.notas_service.app import create_app
    app = create_app()
    app.run(host="0.0.0.0", port=5005, debug=True)
