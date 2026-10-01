"""Pruebas de la ficha clinica del paciente (pagina HTML + PDF).

Cubre tres errores reales que dejaban el detalle del paciente en 500:
  1. url_for('ficha_clinica_pdf') sin ruta registrada -> BuildError.
  2. ev.fecha_creacion.strftime() sobre un valor que llega como texto.
  3. lo mismo con cn.aceptado_en.
Las fechas viajan entre microservicios como texto HTTP de Flask, no como
datetime, por eso se formatean con los filtros `fecha`/`fechahora`.
"""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from gateway.app import create_app  # noqa: E402

PACIENTE = {
    "id": 7,
    "nombre": "Ana",
    "apellido": "Quispe",
    "dni": "45678912",
    "telefono": "999888777",
    "email": "ana@ejemplo.pe",
    "sexo": "F",
    "direccion": "Av. Lima 123",
    "seguro": "SIS",
    "estado": "activo",
    # Tal como lo serializa Flask al viajar por HTTP entre microservicios.
    "fecha_nacimiento": "Sat, 04 May 1990 00:00:00 GMT",
    "creado_en": "2026-01-02 10:00:00",
}

HISTORIAL = [{
    "id": 1,
    "fecha_cita": "Sat, 01 Aug 2026 00:00:00 GMT",
    "hora_cita": "09:30:00",
    "terapeuta": "Dr. Ruiz",
    "especialidad": "Fisioterapia",
    "estado": "completada",
    "monto": 80.0,
    "metodo_pago": "yape",
    "estado_pago": "pagado",
}]

PAQUETES = [{
    "servicio_nombre": "Paquete 10 sesiones",
    "total_sesiones": 10,
    "sesiones_usadas": 3,
    "fecha_compra": "Sat, 01 Aug 2026 00:00:00 GMT",
    "fecha_vencimiento": None,
    "estado": "activo",
}]

EVALUACIONES = [{
    "fecha_creacion": "Sat, 01 Aug 2026 00:00:00 GMT",
    "terapeuta_nombre": "Dr. Ruiz",
    "motivo_consulta": "Dolor lumbar",
    "escala_dolor_eva": 7,
    "rango_movimiento": "Limitado",
    "objetivos_terapeuticos": "Recuperar movilidad",
}]

CONSENTIMIENTOS = [{
    "tipo": "Kinesiologico",
    "texto_version": "v1.0",
    "aceptado_en": "Fri, 02 Jan 2026 10:05:00 GMT",
    "ip_origen": "::1",
}]


class FichaClinicaTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as s:
            s["usuario_id"] = 1
            s["rol"] = "admin"
            s["usuario_nombre"] = "Admin"

    def _get(self, ruta):
        def fake_get(url, *args, **kwargs):
            if url.endswith("/paquetes"):
                return {"paquetes": PAQUETES}, 200
            if url.endswith("/evaluaciones"):
                return {"evaluaciones": EVALUACIONES}, 200
            if url.endswith("/consentimientos"):
                return {"consentimientos": CONSENTIMIENTOS}, 200
            return {"paciente": PACIENTE, "historial": HISTORIAL}, 200

        with patch("gateway.app.pacientes_client.get", side_effect=fake_get), \
                patch("gateway.app.log_accion"):
            return self.cliente.get(ruta)

    def test_detalle_paciente_renderiza(self):
        """La pagina no debe reventar ni con fechas en texto HTTP."""
        r = self._get("/pacientes/45678912")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ficha-clinica.pdf", r.get_data(as_text=True))

    def test_detalle_paciente_formatea_fechas(self):
        cuerpo = self._get("/pacientes/45678912").get_data(as_text=True)
        # dd/mm/YYYY, no el texto HTTP crudo de Flask.
        self.assertIn("04/05/1990", cuerpo)
        self.assertIn("01/08/2026", cuerpo)
        self.assertIn("02/01/2026 10:05", cuerpo)
        self.assertNotIn("Sat, 01 Aug 2026", cuerpo)

    def test_pdf_se_genera(self):
        r = self._get("/pacientes/45678912/ficha-clinica.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF-"))
        self.assertIn("inline", r.headers.get("Content-Disposition", ""))

    def test_pdf_sin_datos_no_rompe(self):
        def fake_get(url, *args, **kwargs):
            if url.endswith("/paquetes"):
                return {"paquetes": []}, 200
            if url.endswith("/evaluaciones"):
                return {"evaluaciones": []}, 200
            if url.endswith("/consentimientos"):
                return {"consentimientos": []}, 200
            return {"paciente": {"id": 1, "nombre": "Solo", "apellido": "Nombre",
                                 "dni": "11111111", "estado": "activo"},
                    "historial": []}, 200

        with patch("gateway.app.pacientes_client.get", side_effect=fake_get), \
                patch("gateway.app.log_accion"):
            r = self.cliente.get("/pacientes/11111111/ficha-clinica.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF-"))

    def test_pdf_requiere_sesion(self):
        with self.client_limpio() as c:
            r = c.get("/pacientes/45678912/ficha-clinica.pdf")
        self.assertEqual(r.status_code, 302)

    def client_limpio(self):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s.clear()
        return c


class FormatoFechaTest(unittest.TestCase):
    def test_formatos(self):
        from shared.fechas import fmt_fecha, fmt_hora
        self.assertEqual(fmt_fecha("Sat, 04 May 1990 00:00:00 GMT"), "04/05/1990")
        self.assertEqual(fmt_fecha("2026-01-02 10:00:00"), "02/01/2026")
        self.assertEqual(fmt_fecha("2026-01-02 10:00:00", con_hora=True), "02/01/2026 10:00")
        self.assertEqual(fmt_fecha(None), "")
        self.assertEqual(fmt_fecha(""), "")
        # Valor irreconocible: se devuelve tal cual, sin perder informacion.
        self.assertEqual(fmt_fecha("sin fecha"), "sin fecha")
        self.assertEqual(fmt_hora("09:30:00"), "09:30")

    def test_timedelta_de_mysql(self):
        from datetime import timedelta

        from shared.fechas import fmt_hora
        self.assertEqual(fmt_hora(timedelta(hours=9, minutes=30)), "09:30")


if __name__ == "__main__":
    unittest.main()
