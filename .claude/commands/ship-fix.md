# Ship Fix -- Compra Saldo Claro GT

Publica un fix o mejora ya implementada siguiendo SIEMPRE la misma secuencia: version bump -> sincronizar SDD/agente/skills -> compilar -> smoke test -> subir a GitHub. Usar este skill en vez de encadenar `/bump-version`, `/build-exe` y `/github-push` a mano para que la documentacion nunca quede desincronizada del codigo.

**Precondicion:** el fix/feature ya esta implementado en el codigo y pasa `python -m py_compile` sobre los archivos tocados. Este skill NO diagnostica ni implementa el cambio -- solo lo publica. Si todavia no esta claro cual es la causa raiz o el fix, usar primero `/diagnose-automation` y/o `/python-maestro`.

Argumento: $ARGUMENTS -- descripcion breve del fix en español (se usa para el Changelog y el commit) y opcionalmente el tipo de bump ("major"/"minor"/"patch", default "patch").

## Pasos

### 1. Version bump (mismo criterio que `/bump-version`)

1. Leer `VERSION = "x.y.z"` en `version.py`.
2. Determinar tipo: cambio incompatible en el flujo de compra -> major; nueva funcionalidad compatible -> minor; correccion de bug/endurecimiento de un selector/patron -> patch (default).
3. Editar `version.py` con la nueva version.
4. Editar `README.md`:
   - Badge de version (linea ~5).
   - Nueva entrada al INICIO de `## Changelog`, con la fecha de hoy y una descripcion completa del fix (causa raiz + que cambio), estilo de las entradas ya existentes (V0.7.6-V0.7.9 son buena referencia de nivel de detalle).

### 2. Sincronizar SDD + agente + skills (el paso que NO cubre ningun otro skill -- NUNCA omitirlo)

Revisar y actualizar lo que aplique de esta lista. No todos los archivos requieren cambio en cada fix, pero los 3 numeros de version SIEMPRE deben quedar alineados con `version.py`:

- **`.claude/specs/feature-specs.md`**: actualizar el header (version, fecha, version del documento +0.1) y la seccion de la feature afectada -- agregar un bullet nuevo marcado `**(Vx.y.z)**` describiendo el fix, o enmendar el bullet anterior si el fix corrige/reemplaza ese mismo mecanismo (no dejar descripciones obsoletas que ya no reflejen el codigo actual).
- **`.claude/specs/architecture.md`**: actualizar "Version de referencia". Si el fix introduce o corrige un **patron reutilizable** (no un ajuste puntual de un selector), agregar una nueva `## ADR-0XX` (siguiente numero disponible) o una `### Enmienda Vx.y.z` dentro de la ADR relacionada existente, con Contexto/Decision/Consecuencias igual que las ADR previas. Si el fix es puntual y no generaliza a nada mas, NO crear ADR nueva -- basta con el bullet en `feature-specs.md`.
- **`.claude/specs/project-spec.md`**: actualizar los 3 lugares con numero de version (header, tabla "Estado Actual", titulo "Capacidades actuales (vX.Y.Z)") y agregar/actualizar el bullet correspondiente en la lista de capacidades si el fix es visible a ese nivel.
- **`.claude/agents/python-desktop-engineer.md`**: actualizar "Version actual" y el header "Patrones de Confiabilidad (... acumulados hasta VX.Y.Z)". Si el fix establece un patron de confiabilidad nuevo (algo que un fix FUTURO deberia replicar), agregar un bullet nuevo a esa lista describiendo el patron en abstracto, no solo el caso puntual.
- **`.claude/commands/diagnose-automation.md`**: si el fix toca `automation.py`/`gui.py` y el patron es verificable con un check si/no sobre el codigo (como los 9 existentes), agregar una fila nueva a la tabla del reporte y su instruccion correspondiente en "Archivos a revisar". Si el fix no es ese tipo de patron (ej. un cambio de copy/UI), omitir este archivo.

Regla general: cada archivo de esta lista que mencione un numero de version debe quedar en `x.y.z` (la nueva). Un fix que NO introduce un patron reutilizable puede saltarse `architecture.md`/`python-desktop-engineer.md`/`diagnose-automation.md`, pero `version.py`, `README.md` y `feature-specs.md` se actualizan SIEMPRE.

### 3. Compilar (`/build-exe`, invocacion directa para agente)

```
pyinstaller --onefile --noconsole --icon="<ruta-absoluta-del-ico>" --name="ComprasClaroGT" --distpath="." --workpath="build_tmp" --specpath="build_tmp" main.py
```

Limpiar `ComprasClaroGT.exe` y `build_tmp/` previos antes de compilar; limpiar `build_tmp/` despues. Si `pyinstaller` no esta en PATH, buscar el ejecutable directo (ej. `%APPDATA%\Python\Python3XX\Scripts\pyinstaller.exe` en una instalacion `pip install --user`) -- NUNCA reintentar con `python -m pyinstaller` si ese fallo con "No module named pyinstaller".

### 4. Smoke test seguro (SIEMPRE, nunca omitir)

1. `Move-Item config.json config.json.bak_test` (si `config.json` existe).
2. Lanzar `ComprasClaroGT.exe` en background, esperar ~5-6s.
3. Confirmar que el proceso sigue vivo (`Get-Process -Id ...`).
4. Matar el proceso de prueba.
5. Restaurar `config.json` a su nombre original de inmediato -- en CUALQUIER escenario (exito o fallo del paso 3), nunca dejar `config.json.bak_test` sin restaurar al terminar este skill.

### 5. Subir a GitHub (`/github-push`)

1. `gh auth status` -- si la cuenta activa no es `erickson558`, `gh auth switch --hostname github.com --user erickson558` primero.
2. `git status` / `git diff --stat` para revisar cambios.
3. Stagear EXPLICITAMENTE solo los archivos tocados en los pasos 1, 2 y el fix en si (nunca `git add -A`/`git add .`). Confirmar que no aparece tracked ningun `config.json`, `log*.txt`, `*.exe`, `build_tmp/`, `playwright-browsers/`.
4. Commit con Conventional Commits describiendo causa raiz + fix, incluyendo `(Vx.y.z)`, y coautoria de Claude.
5. `git push origin main`.
6. Recordar: el push dispara `release.yml` automaticamente (build en CI + tag `v{VERSION}` + GitHub Release publico) -- no hace falta `/github-release` manual salvo que el workflow falle.

### 6. Reportar

Version anterior -> nueva version (y tipo de bump), archivos de codigo modificados, archivos de documentacion sincronizados, resultado del smoke test, tamaño del `.exe`, hash del commit y confirmacion de que `release.yml` quedo disparado.

## Cuando NO usar este skill

- El fix todavia no esta implementado o su causa raiz no esta clara -- usar `/diagnose-automation` y/o `/python-maestro` primero.
- Se quiere compilar/probar localmente SIN publicar nada (ej. solo verificar que compila) -- usar `/build-exe` suelto.
- Se necesita re-disparar un release fallido sin cambios de codigo nuevos -- usar `/github-release` directamente.
