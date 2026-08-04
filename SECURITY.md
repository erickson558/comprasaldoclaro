# Política de Seguridad

## Versiones Soportadas

Este es un proyecto personal de código abierto mantenido por un único desarrollador. Solo se da soporte de seguridad a la **última versión publicada** en [Releases](https://github.com/erickson558/comprasaldoclaro/releases).

## Reportar una Vulnerabilidad

Si encuentras una vulnerabilidad de seguridad en este proyecto:

1. **No la publiques como Issue público.**
2. Repórtala de forma privada usando [GitHub Security Advisories](https://github.com/erickson558/comprasaldoclaro/security/advisories/new) para este repositorio, o contacta directamente al mantenedor.
3. Incluye: pasos para reproducir, impacto potencial y versión afectada.

Al ser un proyecto mantenido en tiempo libre, no hay un SLA formal de respuesta, pero los reportes se atienden lo antes posible.

## Verificación de Integridad del Ejecutable

Cada [Release](https://github.com/erickson558/comprasaldoclaro/releases) publica `ComprasClaroGT.exe` junto a `ComprasClaroGT.exe.sha256`. Antes de ejecutar el binario descargado, verifica que el hash coincide:

```powershell
Get-FileHash .\ComprasClaroGT.exe -Algorithm SHA256
```

Compara el resultado contra el contenido de `ComprasClaroGT.exe.sha256` publicado en el mismo release. Si no coinciden, **no ejecutes el archivo** y reporta el hallazgo.

## Manejo de Credenciales

- Esta aplicación almacena tus credenciales de Mi Claro GT (correo, contraseña, CVV de tarjeta guardada) en `config.json`, **en texto plano, en tu propia máquina**. Nunca se envían a ningún servidor de terceros ni se incluyen en los logs (`log.txt`).
- `config.json` está excluido de Git (`.gitignore`) — nunca debe subirse a un repositorio ni compartirse al reportar un bug.
- Si compartes `log.txt` para depurar un problema, revisa su contenido antes: no debería contener tu contraseña ni CVV, pero sí puede contener tu correo y número de teléfono configurado.

## Alcance

Este proyecto automatiza una interacción de un usuario contra un sitio web de terceros (Mi Claro Guatemala) usando credenciales propias del usuario. No expone servicios de red, no acepta conexiones entrantes y no procesa entrada de usuarios remotos — el modelo de amenaza relevante es principalmente: (1) integridad del binario distribuido, (2) manejo local de credenciales, y (3) dependencias de terceros (Playwright, CustomTkinter, PyInstaller).
