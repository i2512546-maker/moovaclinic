# ============================================================
# Tests de S2: limite de intentos de login en el gateway.
#
# Dos partes:
#   1. LimitadorIntentos e ip_del_request, probados con el reloj
#      adelantado a mano (sin dormir).
#   2. La ruta /login del gateway, con el cliente de prueba y el
#      cliente del modulo de autenticacion parcheado.
# ============================================================

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "clave-de-prueba")
os.environ.setdefault("API_KEY", "clave-api")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway.app import (  # noqa: E402
    MENSAJE_LOGIN_BLOQUEADO,
    MENSAJE_LOGIN_INVALIDO,
)
from gateway.app import (
    create_app as crear_gateway,
)
from shared.rate_limit import LimitadorIntentos, ip_del_request  # noqa: E402

MINUTO = 60.0
HORA = 60 * MINUTO


def _claves(ip="1.1.1.1", correo="ana@moova.pe"):
    return (f"ip:{ip}", f"correo:{correo}")


class _PeticionFalsa:
    """Sustituto minimo de flask.request para probar ip_del_request."""

    def __init__(self, remote_addr=None, **headers):
        self.remote_addr = remote_addr
        self.headers = headers


class LimitadorTest(unittest.TestCase):
    """Logica pura del contador, sin Flask ni red."""

    def setUp(self):
        self.lim = LimitadorIntentos(max_intentos=3, ventana_min=10, bloqueo_min=15)

    def test_no_bloquea_antes_del_maximo(self):
        for i in range(2):
            nuevo = self.lim.registrar_fallo(_claves(), ahora=i)
            self.assertFalse(nuevo)
        bloqueado, _ = self.lim.bloqueado(_claves(), ahora=2)
        self.assertFalse(bloqueado)
        self.assertEqual(self.lim.intentos_restantes(_claves(), ahora=2), 1)

    def test_bloquea_al_llegar_al_maximo(self):
        for i in range(3):
            ultimo = self.lim.registrar_fallo(_claves(), ahora=i)
        self.assertTrue(ultimo)
        bloqueado, expira = self.lim.bloqueado(_claves(), ahora=3)
        self.assertTrue(bloqueado)
        # El bloqueo nace en el fallo que lo dispara (t=2) y dura 15 min.
        self.assertEqual(expira, 2 + 15 * MINUTO)

    def test_el_bloqueo_caduca(self):
        for i in range(3):
            self.lim.registrar_fallo(_claves(), ahora=i)
        fin = 2 + 15 * MINUTO  # el bloqueo nace en el ultimo fallo (t=2)
        self.assertTrue(self.lim.bloqueado(_claves(), ahora=fin - 0.001)[0])
        self.assertFalse(self.lim.bloqueado(_claves(), ahora=fin)[0])

    def test_los_fallos_antiguos_dejan_de_contar(self):
        # Tres fallos, pero separados mas de la ventana (10 min).
        self.lim.registrar_fallo(_claves(), ahora=0)
        self.lim.registrar_fallo(_claves(), ahora=11 * MINUTO)
        self.lim.registrar_fallo(_claves(), ahora=22 * MINUTO)
        self.assertEqual(self.lim.fallos(_claves(), ahora=22 * MINUTO + 1), 1)
        self.assertFalse(self.lim.bloqueado(_claves(), ahora=22 * MINUTO + 1)[0])

    def test_una_ventana_completa_si_bloquea(self):
        # Tres fallos DENTRO de la ventana: el primero queda justo en el
        # borde y aun cuenta.
        for i in range(3):
            self.lim.registrar_fallo(_claves(), ahora=i * 2 * MINUTO)
        self.assertTrue(self.lim.bloqueado(_claves(), ahora=5 * MINUTO)[0])

    def test_la_ip_bloqueada_corta_a_todos_los_correos_de_ese_ip(self):
        for correo in ("a@x.pe", "b@x.pe", "c@x.pe"):
            self.lim.registrar_fallo(_claves(ip="9.9.9.9", correo=correo), ahora=0)
        bloqueado, _ = self.lim.bloqueado(
            _claves(ip="9.9.9.9", correo="nuevo@x.pe"), ahora=1
        )
        self.assertTrue(bloqueado)

    def test_el_correo_bloqueado_corta_desde_cualquier_ip(self):
        for ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            self.lim.registrar_fallo(_claves(ip=ip, correo="m@x.pe"), ahora=0)
        bloqueado, _ = self.lim.bloqueado(
            _claves(ip="8.8.8.8", correo="m@x.pe"), ahora=1
        )
        self.assertTrue(bloqueado)

    def test_el_contador_de_correo_no_se_contamina_con_otro_correo(self):
        for _ in range(2):
            self.lim.registrar_fallo(_claves(correo="uno@x.pe"), ahora=0)
        # Otra clave de correo (aunque comparta IP): su cuenta esta a cero.
        self.assertEqual(self.lim.fallos(("correo:dos@x.pe",), ahora=1), 0)
        self.assertEqual(self.lim.intentos_restantes(("correo:dos@x.pe",), ahora=1), 3)
        # Y la del correo que si fallo sigue donde estaba.
        self.assertEqual(self.lim.fallos(("correo:uno@x.pe",), ahora=1), 2)

    def test_el_exito_borra_el_historial(self):
        for i in range(2):
            self.lim.registrar_fallo(_claves(), ahora=i)
        self.lim.registrar_exito(_claves())
        self.assertEqual(self.lim.fallos(_claves(), ahora=10), 0)
        self.assertEqual(self.lim.intentos_restantes(_claves(), ahora=10), 3)
        self.assertFalse(self.lim.bloqueado(_claves(), ahora=10)[0])

    def test_reiniciar_lo_deja_como_al_principio(self):
        for i in range(3):
            self.lim.registrar_fallo(_claves(), ahora=i)
        self.lim.reiniciar()
        self.assertFalse(self.lim.bloqueado(_claves(), ahora=3)[0])
        self.assertEqual(self.lim.intentos_restantes(_claves(), ahora=3), 3)


class IpDelRequestTest(unittest.TestCase):
    def test_sin_proxy_usa_remote_addr(self):
        p = _PeticionFalsa(remote_addr="203.0.113.9")
        self.assertEqual(ip_del_request(p, confiar_en_proxy=False), "203.0.113.9")

    def test_el_header_se_ignora_si_no_hay_proxy(self):
        # El cliente puede mandar el header inventado; sin TRUST_PROXY
        # no se le hace caso.
        p = _PeticionFalsa(remote_addr="203.0.113.9", **{"X-Forwarded-For": "8.8.8.8"})
        self.assertEqual(ip_del_request(p, confiar_en_proxy=False), "203.0.113.9")

    def test_con_proxy_toma_el_primer_valor(self):
        p = _PeticionFalsa(
            remote_addr="10.0.0.1",
            **{"X-Forwarded-For": "198.51.100.7, 10.0.0.2, 10.0.0.3"},
        )
        self.assertEqual(ip_del_request(p, confiar_en_proxy=True), "198.51.100.7")

    def test_con_proxy_espacios_de_mas_no_molestan(self):
        p = _PeticionFalsa(remote_addr="10.0.0.1", **{"X-Forwarded-For": "  198.51.100.7 , 10.0.0.2"})
        self.assertEqual(ip_del_request(p, confiar_en_proxy=True), "198.51.100.7")

    def test_con_proxy_sin_header_cae_a_remote_addr(self):
        p = _PeticionFalsa(remote_addr="10.0.0.1")
        self.assertEqual(ip_del_request(p, confiar_en_proxy=True), "10.0.0.1")

    def test_con_proxy_header_vacio_cae_a_remote_addr(self):
        p = _PeticionFalsa(remote_addr="10.0.0.1", **{"X-Forwarded-For": "   "})
        self.assertEqual(ip_del_request(p, confiar_en_proxy=True), "10.0.0.1")

    def test_sin_remote_addr_no_devuelve_none(self):
        p = _PeticionFalsa(remote_addr=None)
        self.assertEqual(ip_del_request(p, confiar_en_proxy=False), "0.0.0.0")


class LoginRutaTest(unittest.TestCase):
    """La ruta /login del gateway con el limite puesto en marcha."""

    def setUp(self):
        self.app = crear_gateway()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.limite = self.app.extensions["rate_limit"]

    # -- utilidades --

    def _auth_falso(self, exito=False):
        def falso(*_args, **_kwargs):
            if exito:
                return {
                    "success": True,
                    "usuario": {
                        "id": 7,
                        "nombre": "Ana Torres",
                        "correo": "ana@moova.pe",
                        "rol": "admin",
                    },
                }, 200
            return {"error": "Correo o contrasena incorrectos."}, 401
        return falso

    def _intentar(self, correo="ana@moova.pe", clave="clave-mala", ip="203.0.113.5", **cabeceras):
        return self.client.post(
            "/login",
            data={"correo": correo, "clave": clave},
            environ_base={"REMOTE_ADDR": ip},
            headers=cabeceras,
        )

    def _pagina(self, respuesta):
        """La clave mala re-renderiza la plantilla con el flash dentro;
        el bloqueo si redirige y el flash queda en la sesion. Se mira
        en el sitio donde haya quedado cada uno."""
        if respuesta.status_code == 302:
            with self.client.session_transaction() as s:
                return " ".join(texto for _nivel, texto in s.get("_flashes", []))
        return respuesta.get_data(as_text=True)

    def _bloquear(self, veces=5, **kwargs):
        """Rellena el contador con fallos. Quien llama es el que tiene
        que haber parcheado auth_client.post, para que el mock que se
        mire sea siempre el mismo."""
        for _ in range(veces):
            self._intentar(**kwargs)

    # -- corte por numero de intentos --

    def test_los_primeros_intentos_llegan_al_modulo_auth(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso()) as post:
            respuesta = self._intentar()
        self.assertEqual(post.call_count, 1)
        self.assertIn(MENSAJE_LOGIN_INVALIDO, self._pagina(respuesta))

    def test_a_partir_del_maximo_no_se_llama_al_modulo_auth(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso()) as post:
            for _ in range(5):
                self._intentar()
            self.assertEqual(post.call_count, 5)
            respuesta = self._intentar()
            # Ni una llamada mas: el corte va antes.
            self.assertEqual(post.call_count, 5)
        self.assertIn(MENSAJE_LOGIN_BLOQUEADO, self._pagina(respuesta))

    # -- corte por IP --

    def test_una_ip_que_prueba_varios_correos_queda_cortada(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso()) as post:
            for i in range(5):
                self._intentar(correo=f"intento{i}@moova.pe", ip="198.51.100.1")
            respuesta = self._intentar(correo="otro@moova.pe", ip="198.51.100.1")
            self.assertEqual(post.call_count, 5)
        self.assertIn(MENSAJE_LOGIN_BLOQUEADO, self._pagina(respuesta))

    def test_otra_ip_sigue_libre_cuando_se_corta_por_ip(self):
        with patch("gateway.app.auth_client.post", side_effect=self._auth_falso()) as post:
            self._bloquear(veces=5, ip="198.51.100.1")
            self._intentar(correo="otro@moova.pe", ip="203.0.113.50")
            self.assertEqual(post.call_count, 6)

    # -- corte por correo --

    def test_un_correo_desde_varias_ips_queda_cortado(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso()) as post:
            for i in range(5):
                self._intentar(ip=f"198.51.100.{i + 10}")
            respuesta = self._intentar(ip="8.8.8.8")
            self.assertEqual(post.call_count, 5)
        self.assertIn(MENSAJE_LOGIN_BLOQUEADO, self._pagina(respuesta))

    def test_el_exito_limpia_el_contador(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso(exito=True)):
            for _ in range(3):
                self._intentar()
        claves = _claves(ip="203.0.113.5", correo="ana@moova.pe")
        self.assertEqual(self.limite.fallos(claves), 0)
        self.assertFalse(self.limite.bloqueado(claves)[0])

    # -- mensaje generico --

    def test_el_mensaje_no_revela_si_el_usuario_existe(self):
        with patch("gateway.app.auth_client.post", side_effect=self._auth_falso()):
            pagina = self._pagina(self._intentar(correo="nadie-existe@moova.pe"))
        self.assertIn(MENSAJE_LOGIN_INVALIDO, pagina)
        bajado = MENSAJE_LOGIN_INVALIDO.lower()
        for prohibido in ("no existe", "no encontrado", "usuario", "clave mala"):
            self.assertNotIn(prohibido, bajado)

    def test_el_mensaje_de_bloqueo_no_dice_que_el_correo_no_existe(self):
        with patch("gateway.app.auth_client.post", side_effect=self._auth_falso()):
            self._bloquear(veces=5)
            pagina = self._pagina(self._intentar())
        self.assertIn(MENSAJE_LOGIN_BLOQUEADO, pagina)
        self.assertNotIn("no existe", MENSAJE_LOGIN_BLOQUEADO.lower())
        self.assertNotEqual(MENSAJE_LOGIN_BLOQUEADO, MENSAJE_LOGIN_INVALIDO)

    # -- X-Forwarded-For --

    def test_sin_trust_proxy_el_header_no_hace_nada(self):
        with patch("gateway.app.auth_client.post",
                   side_effect=self._auth_falso()) as post:
            for i in range(5):
                # Cada intento con un X-Forwarded-For distinto: si se
                # creyera el header, nunca se llegaria al maximo.
                self._intentar(ip="203.0.113.5", correo=f"intento{i}@moova.pe",
                               **{"X-Forwarded-For": f"8.8.8.{i}"})
            respuesta = self._intentar(ip="203.0.113.5", correo="nuevo@moova.pe",
                                       **{"X-Forwarded-For": "9.9.9.9"})
            self.assertEqual(post.call_count, 5)
        self.assertIn(MENSAJE_LOGIN_BLOQUEADO, self._pagina(respuesta))

    def test_con_trust_proxy_se_cuenta_por_el_header(self):
        with patch("gateway.app.TRUST_PROXY", True), \
                patch("gateway.app.auth_client.post", side_effect=self._auth_falso()) as post:
            # El REMOTE_ADDR es el proxy en todos los casos; lo que va
            # cambiando es el X-Forwarded-For.
            for i in range(5):
                self._intentar(ip="10.0.0.1", correo=f"intento{i}@moova.pe",
                               **{"X-Forwarded-For": f"8.8.8.{i}"})
            respuesta = self._intentar(ip="10.0.0.1", correo="nuevo@moova.pe",
                                       **{"X-Forwarded-For": "7.7.7.7"})
            # La sexta SI llega: cada cliente venia de una IP distinta.
            self.assertEqual(post.call_count, 6)
        self.assertNotIn(MENSAJE_LOGIN_BLOQUEADO, self._pagina(respuesta))


if __name__ == "__main__":
    unittest.main()
