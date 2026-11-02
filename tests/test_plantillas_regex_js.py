import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLAS = sorted((RAIZ / "templates").glob("*.html"))
REGEX_DOBLE_BARRA = re.compile(r"/[^/\n]*\\\\[dswDSW][^/\n]*/[a-z]*\.test\(")


class RegexJsEnPlantillasTest(unittest.TestCase):
    def test_hay_plantillas_que_revisar(self):
        self.assertTrue(PLANTILLAS)

    def test_ninguna_regex_usa_doble_barra_invertida(self):
        errores = []
        for ruta in PLANTILLAS:
            for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
                if REGEX_DOBLE_BARRA.search(linea):
                    errores.append(f"{ruta.name}:{n}: {linea.strip()}")
        self.assertEqual(errores, [], "Regex con doble barra invertida:\n" + "\n".join(errores))

    def test_citas_valida_dni_con_ocho_digitos(self):
        html = (RAIZ / "templates" / "citas.html").read_text(encoding="utf-8")
        self.assertIn(r"/^\d{8}$/.test(dni)", html)


if __name__ == "__main__":
    unittest.main()
