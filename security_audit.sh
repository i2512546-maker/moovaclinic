#!/usr/bin/env bash
# ============================================================
# Auditoría de seguridad — Moova Clinic
# Corre esto DENTRO de la carpeta del repo (branch-jarib)
# Requiere: python3 + pip
# ============================================================
set -uo pipefail

echo "============================================"
echo " 1/6 — Instalando herramientas de análisis"
echo "============================================"
pip install --quiet bandit pip-audit semgrep detect-secrets 2>&1 | tail -5

echo ""
echo "============================================"
echo " 2/6 — Bandit: vulnerabilidades en código Python"
echo "        (SQLi, debug mode, uso inseguro de crypto, etc.)"
echo "============================================"
bandit -r . -x ./.git,./node_modules -f txt -o reporte_bandit.txt
cat reporte_bandit.txt

echo ""
echo "============================================"
echo " 3/6 — pip-audit: dependencias con CVEs conocidos"
echo "============================================"
find . -iname "requirements*.txt" -not -path "./.git/*" -exec sh -c \
  'echo "--- {} ---"; pip-audit -r "{}" || true' \;

echo ""
echo "============================================"
echo " 4/6 — detect-secrets: credenciales olvidadas en el código"
echo "        o en el historial de commits"
echo "============================================"
detect-secrets scan --all-files > .secrets_baseline.json 2>/dev/null
python3 -c "
import json
data = json.load(open('.secrets_baseline.json'))
results = data.get('results', {})
if not results:
    print('No se encontraron secretos obvios en el código actual.')
else:
    for f, findings in results.items():
        for item in findings:
            print(f\"  ⚠ {f}: posible {item['type']} en línea {item['line_number']}\")
"

echo ""
echo "============================================"
echo " 5/6 — Semgrep: patrones de vulnerabilidad OWASP"
echo "        (inyección, XSS, auth rota, deserialización, etc.)"
echo "============================================"
semgrep --config p/owasp-top-ten --config p/flask --quiet . 2>&1 | tee reporte_semgrep.txt

echo ""
echo "============================================"
echo " 6/6 — Checklist manual (no automatizable con certeza)"
echo "============================================"
echo "Revisa a mano estos puntos, el análisis estático no los detecta con seguridad:"
echo ""
echo "[ ] ¿Todas las rutas que modifican datos (POST/PUT/DELETE) verifican"
echo "    el rol del usuario en sesión (admin/terapeuta/paciente), no solo"
echo "    que esté logueado?"
echo "[ ] ¿Los formularios (login, crear cita, pagos) tienen protección CSRF"
echo "    (Flask-WTF o token manual)?"
echo "[ ] ¿debug=True está deshabilitado en el despliegue de producción real"
echo "    (aunque esté en el código, revisa la variable de entorno FLASK_ENV)?"
echo "[ ] ¿SECRET_KEY está fijo y es EL MISMO en los 7 servicios en producción"
echo "    (revisa el .env real de cada servicio desplegado, no el .example)?"
echo "[ ] ¿Los endpoints de pagos (Yape/Plin) validan el monto en el servidor,"
echo "    o confían en un valor que manda el navegador?"
echo "[ ] ¿Hay límite de intentos de login (protección contra fuerza bruta)?"
echo "[ ] ¿Los cursores de MySQL usan parámetros (%s) o interpolación directa"
echo "    de texto en TODAS las queries, no solo las que revisé por muestreo?"
echo ""
echo "============================================"
echo " Reportes guardados en:"
echo "   reporte_bandit.txt"
echo "   reporte_semgrep.txt"
echo "   .secrets_baseline.json"
echo "============================================"