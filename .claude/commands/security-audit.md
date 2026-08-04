# Security Audit -- Compra Saldo Claro GT

Ejecuta una revision de seguridad completa del proyecto usando el checklist de `.claude/agents/security-reviewer.md`.

Argumento opcional: $ARGUMENTS (area especifica a enfocar, ej. "credenciales", "release.yml", "dependencias")

## Cuando usar

- Antes de cada release publico
- Despues de agregar una dependencia nueva a `requirements.txt`
- Despues de tocar manejo de credenciales, `subprocess`, o `.github/workflows/release.yml`
- Cuando el usuario pida explicitamente "revisa vulnerabilidades" / "es seguro esto"

## Pasos

1. Leer el checklist completo en `.claude/agents/security-reviewer.md` (5 categorias: credenciales, ejecucion de codigo, dependencias/supply chain, integridad de distribucion, GitHub Actions/CI)
2. Revisar el codigo fuente (`*.py`) con Grep para los patrones prohibidos: `shell=True`, `os\.system`, `eval\(`, `exec\(`, `pickle\.`, `subprocess.*shell=True`
3. Revisar que ningun log/notify interpole `password`/`billing_cvv`/el dict `config` completo
4. Confirmar `.gitignore` sigue cubriendo: `config.json`, `log.txt`, `log.txt.1`, `debug.log`, `comprasclaro.txt`, `*.exe`, `*.spec`, `build_tmp/`, `playwright-browsers/`
5. Revisar `.github/workflows/release.yml`: permisos minimos (`contents: write` solamente), generacion de SHA-256 presente, sin secretos impresos en logs
6. Si $ARGUMENTS especifica un area, profundizar solo ahi; si no, cubrir las 5 categorias
7. Producir el reporte en el formato definido en `security-reviewer.md`

## Reglas
- No recomendar hardening desproporcionado (esta es una app de escritorio de un solo usuario, no un servicio expuesto)
- Priorizar hallazgos reales sobre teoricos
- Cualquier fix propuesto debe pasar por `/python-maestro` (analisis -> correccion -> validacion -> version -> commit) si toca codigo
- Reportar tambien lo que YA esta correcto (no solo problemas) para no repetir analisis en la proxima auditoria
