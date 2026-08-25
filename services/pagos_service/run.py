if __name__ == "__main__":
    from services.pagos_service.app import create_app
    app = create_app()
    app.run(host="0.0.0.0", port=5004, debug=True)
