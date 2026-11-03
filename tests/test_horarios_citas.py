import os
import unittest
from datetime import datetime

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")
os.environ.setdefault("API_KEY", "clave-interna-de-pruebas")

from shared.fechas import ZONA_LIMA
from shared.horarios import (
    autoasignar,
    contar_ocupados,
    generar_slots,
    slots_libres,
    validar_slot,
)


class HorariosTest(unittest.TestCase):
    def test_generar_slots_10_a_18(self):
        self.assertEqual(generar_slots(), [
            "10:00", "11:00", "12:00", "13:00", "14:00",
            "15:00", "16:00", "17:00",
        ])

    def test_validar_slot(self):
        self.assertTrue(validar_slot("10:00"))
        self.assertTrue(validar_slot("17:00"))
        self.assertFalse(validar_slot("09:00"))
        self.assertFalse(validar_slot("18:00"))
        self.assertFalse(validar_slot("10:30"))
        self.assertFalse(validar_slot("xx:yy"))

    def test_slot_lleno(self):
        ocupados = ["10:00"]
        self.assertEqual(slots_libres(ocupados, "2026-11-03", None), [
            "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
        ])

    def test_autoasignar(self):
        self.assertEqual(autoasignar(["10:00", "11:00"], "2026-11-03", None), "12:00")

    def test_dia_lleno(self):
        ocupados = generar_slots()
        self.assertEqual(slots_libres(ocupados, "2026-11-03", None), [])
        self.assertIsNone(autoasignar(ocupados, "2026-11-03", None))

    def test_slots_pasados_hoy(self):
        ahora = datetime(2026, 11, 3, 12, 30, tzinfo=ZONA_LIMA)
        libres = slots_libres([], "2026-11-03", ahora)
        self.assertNotIn("10:00", libres)
        self.assertNotIn("11:00", libres)
        self.assertNotIn("12:00", libres)
        self.assertIn("13:00", libres)

    def test_contar_ocupados(self):
        self.assertEqual(contar_ocupados(["10:00", "10:00", "11:00"]), {"10:00": 2, "11:00": 1})


if __name__ == "__main__":
    unittest.main()
