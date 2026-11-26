# Claude Switcher

Cambia de cuenta en Claude Desktop como en el móvil: cada cuenta inicia sesión **una sola vez** y después cambias con un clic, sin volver a autenticarte.

## Cómo funciona
Claude Desktop guarda tu sesión en su carpeta de datos. Claude Switcher guarda una copia por cuenta; al cambiar, cierra Claude, intercambia la carpeta y lo vuelve a abrir (unos 3–5 segundos). Tu configuración de MCP/extensiones (`claude_desktop_config.json`) se comparte entre todas las cuentas.

## Requisitos
- Python 3.8+ (Mac: `python3` del sistema o de python.org · Windows: python.org, marca "Add to PATH").

## Primer uso
1. Abre Claude Desktop con la cuenta en la que ya estás.
2. Abre la app: doble clic en **Abrir Claude Switcher (Mac).command** o **(Windows).bat**.
   - Mac: la primera vez, clic derecho → Abrir (por Gatekeeper). Si dice "sin permiso": `chmod +x "Abrir Claude Switcher (Mac).command"`.
3. Pulsa **Guardar cuenta actual** y ponle nombre (ej. `personal`).
4. Pulsa **＋ Añadir cuenta**, ponle nombre (ej. `trabajo`). Claude se abre limpio: inicia sesión con esa cuenta. Listo, queda guardada.

Repite el paso 4 para cada cuenta.

## Día a día
- **Clic** en una cuenta → cambia.
- **⌘1…⌘9** (Mac) / **Ctrl+1…9** (Windows) → atajo a cada cuenta.
- **Clic derecho** → renombrar o eliminar.

## Desde terminal (opcional)
```
python3 claude_switcher.py list
python3 claude_switcher.py switch trabajo
python3 claude_switcher.py new cliente-x
```

## Dónde se guardan las sesiones
- Mac: `~/Library/Application Support/Claude-Switcher/profiles/`
- Windows: `%APPDATA%\Claude-Switcher\profiles\`

Contienen tus sesiones iniciadas: no compartas esa carpeta.

## Notas
- Las conversaciones viven en la nube de cada cuenta; no se mezclan.
- Si una sesión caduca (p. ej. Anthropic la cierra por tiempo), solo esa cuenta pedirá login de nuevo.
- Si Claude se instaló en una ruta poco común, edita `state.json` en la carpeta de arriba y rellena `"data_dir"` (carpeta de datos de Claude) y/o `"launch_cmd"` (comando para abrirlo).
