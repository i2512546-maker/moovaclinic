# ============================================================
# Limite de intentos de login en memoria (S2)
#
# Responde a "no hay limite de intentos de login": con la sesion y el
# CSRF de por medio aun asi se puede probar clave tras clave contra
# /login sin que nada se lo impida.
#
# Dos contadores INDEPENDIENTES y ambos tienen que pasar:
#
#   ip:<ip>       corta a quien fuerza muchas claves desde un equipo.
#   usuario:<correo> corta a quien fuerza un correo desde muchas IPs
#                 (botnets, proxys, cambiando de red).
#
# SIN dependencias nuevas y SIN base de datos: todo vive en un dict de
# este proceso, protegido por un candado para los hilos de gunicorn.
# Eso significa que cada worker tiene su propia cuenta y que un
# reinicio del servicio lo pone a cero. Esta limitacion esta descrita
# en el README; si un dia hace falta compartirla entre procesos, aqui
# toca reemplazar el almacenamiento, no tocar la logica.
# ============================================================

import threading
import time


def ip_del_request(request, confiar_en_proxy=False):
    """IP real del cliente para contabilizar intentos.

    Detras de un proxy (nginx, el balanceador de Render) `remote_addr`
    es la IP del proxy y TODAS las peticiones parecen venir del mismo
    sitio, lo que dejaria el limite por IP inutil. En ese caso se toma
    el PRIMER valor de X-Forwarded-For, que es el que anoto el proxy
    con la IP del cliente original.

    Solo si `confiar_en_proxy` (TRUST_PROXY=1): sin eso, cualquier
    cliente puede mandar el header con una IP inventada y quedarse sin
    contador, que es exactamente el hueco que se quiere cerrar.
    """
    if confiar_en_proxy:
        xff = request.headers.get("X-Forwarded-For") or ""
        primera = xff.split(",")[0].strip() if xff else ""
        if primera:
            return primera
    return request.remote_addr or "0.0.0.0"


class LimitadorIntentos:
    """Cuenta fallos por clave dentro de una ventana y bloquea al
    llegar al maximo.

    `ahora` es opcional en cada metodo: los tests adelantan el reloj en
    vez de dormir.
    """

    def __init__(self, max_intentos, ventana_min, bloqueo_min):
        self.max_intentos = int(max_intentos)
        self.ventana_min = float(ventana_min) * 60
        self.bloqueo_min = float(bloqueo_min) * 60
        self._fallos = {}    # clave -> [timestamp, ...]
        self._bloqueos = {}  # clave -> timestamp de fin de bloqueo
        self._candado = threading.Lock()

    # ---------------- consulta ----------------

    def bloqueado(self, claves, ahora=None):
        """(bloqueado, expira_en) si CUALQUIERA de las claves esta
        bloqueada ahora. Purga tambien los bloqueos ya vencidos."""
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            self._purgar(ahora)
            for clave in claves:
                expira = self._bloqueos.get(clave)
                if expira is not None and expira > ahora:
                    return True, expira
            return False, None

    def fallos(self, claves, ahora=None):
        """Fallos que se estan contando dentro de la ventana.

        Se mide en la clave mas adelantada, no se suman: la IP y el
        correo del mismo intento son dos medidas del mismo hecho, y
        sumarlos daria el doble de fallos reales.
        """
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            self._purgar(ahora)
            return max((len(self._fallos.get(c, ())) for c in claves), default=0)

    def intentos_restantes(self, claves, ahora=None):
        """Cuanto falta en la clave mas adelantada antes de bloquear
        (>= 0)."""
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            self._purgar(ahora)
            contados = max((len(self._fallos.get(c, ())) for c in claves), default=0)
            return max(0, self.max_intentos - contados)

    # ---------------- registro ----------------

    def registrar_fallo(self, claves, ahora=None):
        """Anota un fallo en cada clave. Devuelve True si con este fallo
        alguna clave acaba de pasar a bloqueada."""
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            self._purgar(ahora)
            bloqueo_nuevo = False
            for clave in claves:
                cuenta = list(self._fallos.get(clave, ()))
                cuenta.append(ahora)
                corte = ahora - self.ventana_min
                cuenta = [t for t in cuenta if t >= corte]
                self._fallos[clave] = cuenta
                if len(cuenta) >= self.max_intentos:
                    # El bloqueo empieza en el fallo que lo desencadena
                    # y dura bloqueo_min desde AHI.
                    self._bloqueos[clave] = ahora + self.bloqueo_min
                    bloqueo_nuevo = True
            return bloqueo_nuevo

    def registrar_exito(self, claves):
        """Borra el historial de esas claves al entrar bien. Sin esto,
        cinco typos de la manana dejarian al usuario real bloqueado
        por un rato."""
        with self._candado:
            for clave in claves:
                self._fallos.pop(clave, None)
                self._bloqueos.pop(clave, None)

    def reiniciar(self):
        """Vacia todo (tests y arranque)."""
        with self._candado:
            self._fallos.clear()
            self._bloqueos.clear()

    # ---------------- interno ----------------

    def _purgar(self, ahora):
        """Limpia lo que ya vencio. Se llama siempre bajo el candado."""
        corte_fallos = ahora - self.ventana_min
        for clave in [k for k, v in self._fallos.items() if not v or v[-1] < corte_fallos]:
            del self._fallos[clave]
        for clave in [k for k, v in self._bloqueos.items() if v <= ahora]:
            del self._bloqueos[clave]
