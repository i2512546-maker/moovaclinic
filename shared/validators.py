# ============================================================
# Validadores compartidos (FASE 2).
# Unifican la validacion de datos de paciente/cita que antes se
# duplicaba en citas_service y pacientes_service.
# ============================================================

import re

NOMBRE_RE = re.compile(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ ]{2,60}")
DNI_RE = re.compile(r"\d{8}")
TELEFONO_RE = re.compile(r"\d{9}")


def validar_nombre(valor):
    """Valida nombre o apellido. Devuelve un mensaje de error o None si OK."""
    if not NOMBRE_RE.fullmatch(valor or ""):
        return "Nombre/apellido inválido, solo letras y espacios (2-60)"
    return None


def validar_dni(dni):
    """Valida DNI de 8 digitos. Devuelve un mensaje de error o None si OK."""
    if not DNI_RE.fullmatch(dni or ""):
        return "DNI inválido, debe tener 8 dígitos"
    return None


def normalizar_telefono(telefono):
    """Quita espacios/guiones y el prefijo +51. Devuelve el numero limpio."""
    tel = re.sub(r"[\s\-]", "", telefono or "")
    if tel.startswith("+51"):
        tel = tel[3:]
    return tel


def validar_telefono(telefono):
    """Valida telefono (9 digitos despues de quitar +51/espacios/guiones).
    Devuelve un mensaje de error o None si OK."""
    if not TELEFONO_RE.fullmatch(normalizar_telefono(telefono)):
        return "Teléfono inválido, debe tener 9 dígitos"
    return None


def validar_datos_paciente(nombre, apellido, dni, telefono):
    """Valida nombre, apellido, dni y telefono. Devuelve None si todo OK,
    o el primer mensaje de error encontrado."""
    for valor, etiqueta in ((nombre, "Nombre"), (apellido, "Apellido")):
        err = validar_nombre(valor)
        if err:
            return err.replace("Nombre/apellido", etiqueta)
    err = validar_dni(dni)
    if err:
        return err
    return validar_telefono(telefono)