# PasoAPaso 2.0

Asistente para personas que están aprendiendo a usar la computadora.
Proyecto de las clases de **Programación** y **Diseño Web**.

**Integrantes:** Kevin Cruz, Eduardo Antonio, Kevin Betanzo, Daniela Portillo y Yilber Padilla.

---

## 1. Qué cambió en la versión 2.0

La versión 1 era una app de escritorio que entendía órdenes con un diccionario de reglas.
La versión 2 conserva eso (es lo que hace posible mover el mouse y el teclado de verdad)
y le agrega una capa en línea:

| Antes (1.0) | Ahora (2.0) |
|---|---|
| Solo texto | **Voz primero** y texto como respaldo |
| Sin cuentas | **Registro e inicio de sesión** con teléfono, nombre y clave |
| Sin base de datos | **Base de datos SQLite** con usuarios, consultas, resultados y opiniones |
| Sin administrador | **Panel web privado** para ver usuarios, prompts, IA y exportar CSV |
| Solo reglas | **Gemini opcional** para entender frases que el diccionario no reconoce |
| Sin logo | **Splash con logo**, iconos y portal web |
| Todo local | **Servidor desplegable** (Docker / Render / Railway) y app que se conecta a él |

> **Importante:** una página web normal **no puede** mover el mouse ni presionar teclas en tu
> computadora; el navegador lo prohíbe por seguridad. Por eso PasoAPaso usa una arquitectura
> cliente-servidor: la **app de Windows** ejecuta y enseña, y el **servidor en línea** guarda
> las cuentas, el historial y el panel del administrador. Es la forma correcta y confiable de
> tener las dos cosas al mismo tiempo.

---

## 2. Cómo funciona

```
┌──────────────────────────────┐        HTTPS / HTTP        ┌─────────────────────────────┐
│  App de escritorio (Windows) │  ───────────────────────▶  │  Servidor Python (estándar)  │
│  · splash + login            │                            │  · API de cuentas y prompts  │
│  · chat de voz y texto       │  ◀───────────────────────  │  · SQLite (datos)            │
│  · pyautogui + panel guía    │        órdenes seguras      │  · panel /admin              │
└──────────────────────────────┘                            │  · Gemini (opcional)         │
                                                            └──────────────┬──────────────┘
                                                                           │
                                                                  ┌────────▼─────────┐
                                                                  │ Navegador        │
                                                                  │ portal + /admin  │
                                                                  └──────────────────┘
```

1. La persona **habla** o escribe lo que quiere hacer.
2. La app manda el texto al servidor.
3. El servidor primero usa las **reglas locales** (rápidas y gratis). Si no entiende, le pide a
   **Gemini** que traduzca la frase a una acción permitida. La respuesta se **valida** contra el
   catálogo: la IA nunca ejecuta nada por su cuenta.
4. La app recibe las órdenes y las ejecuta **en la computadora de la persona** con pyautogui,
   mostrando el panel que explica cada paso.
5. El resultado se guarda en la base de datos y aparece en el panel del administrador.

---

## 3. Requisitos

- Windows 10 u 11.
- Python 3.10 o más nuevo (marca **Add Python to PATH** al instalarlo).
- Internet para: crear la cuenta, guardar las consultas, usar la voz y consultar a Gemini.
- Micrófono (opcional, para el chat de voz).
- Nada de servidores externos obligatorios: el servidor usa **solo la biblioteca estándar**.

---

## 4. Instalación y primer uso

1. Abre una terminal en esta carpeta.
2. Instala los componentes (solo la primera vez):

   ```bat
   python -m pip install -r requirements.txt
   ```

3. Inicia la app con doble clic en **`iniciar.bat`** o con:

   ```bat
   python main.py
   ```

4. Verás el **logo de PasoAPaso** y luego la pantalla de acceso.
5. Crea una cuenta con:
   - tu nombre,
   - tu número de teléfono,
   - una clave de 4 a 8 números,
   - edad y ciudad (opcionales),
   - cuánto usas la computadora.

La app arranca su propio servidor en `http://127.0.0.1:8765` y guarda la base de datos en
`%APPDATA%\PasoAPaso\datos\pasoapaso.db`.

La casilla **«Recordarme en esta computadora»** es opcional y viene desmarcada: si la marcas,
la próxima vez entrarás directo; si no, la app siempre te pedirá tu teléfono y tu clave.

### Panel del administrador

Mientras la app está abierta, abre:

```
http://127.0.0.1:8765/admin
```

Credenciales iniciales:

```
Usuario: admin
Clave:   PasoAPaso2026
```

**Cámbialas** en **Mi clave** antes de mostrar el proyecto. También puedes definirlas en `.env`
antes del primer arranque. Si ya existe la base y quieres volver a aplicar la clave del `.env`,
usa `PASOAPASO_ADMIN_RESET=1` una vez.

---

## 5. El chat de voz

La pestaña **Hablar** es la predeterminada.

- Presiona el micrófono y habla.
- La app muestra lo que entendió y te pide confirmar antes de ejecutar.
- Puedes activar **«Leer los pasos en voz alta»** (usa la voz de Windows).
- **«Manos libres»** vuelve a escuchar cuando termina una demostración.
- Si no hay micrófono o faltan componentes, la pestaña **Escribir** funciona igual.

Componentes de voz:

```bat
python -m pip install SpeechRecognition sounddevice
```

El reconocimiento usa el servicio gratuito de Google (necesita internet). La voz de salida usa
Windows SAPI, que ya viene instalado.

---

## 6. La base de datos

Se usa **SQLite**, incluida en Python. No hay que instalar ni administrar ningún servidor de
base de datos. El archivo se crea solo.

**Ubicación por defecto:**

- App de escritorio: `%APPDATA%\PasoAPaso\datos\pasoapaso.db`
- Servidor independiente: `datos/pasoapaso.db` (o `PASOAPASO_DATOS`)
- Docker/Render: `/app/datos/pasoapaso.db`

**Tablas:**

| Tabla | Guarda |
|---|---|
| `usuarios` | teléfono, nombre, clave cifrada, edad, ciudad, experiencia, consentimiento, estado |
| `administradores` | usuario y clave cifrada del administrador |
| `prompts` | texto, origen (voz/texto/offline), estado, interpretación, acciones ejecutadas, IA usada, duración y error |
| `feedback` | si la consulta le sirvió a la persona y su comentario |
| `ajustes` | IA activa, registro abierto y otras opciones |

**Seguridad:**

- Las claves se guardan con **PBKDF2-SHA256** y sal aleatoria; no se pueden leer.
- Las sesiones usan **JWT firmados** con HMAC-SHA256.
- El panel del administrador usa una **cookie privada** aparte y **CSRF** en los formularios.
- Todas las consultas SQL usan parámetros (sin concatenar texto del usuario).
- Los intentos de acceso tienen un límite por IP.

**Respaldo:** copia el archivo `.db` cuando la app esté cerrada. Para restaurar, reemplázalo.

---

## 7. Panel del administrador

Incluye:

- **Resumen:** usuarios, consultas, porcentaje resuelto con IA, gráfico de 7 días y acciones más pedidas.
- **Usuarios:** búsqueda, ficha, historial, activar/desactivar, generar clave temporal y borrar cuenta.
- **Consultas:** filtros por texto, estado, origen y uso de IA; detalle de la interpretación, lo ejecutado, error y opinión.
- **Inteligencia artificial:** estado de la clave, modelo, activar/desactivar Gemini y cerrar el registro.
- **Exportar CSV:** todas las consultas para Excel.
- **Mi clave:** cambio de clave del administrador.

Todo el panel está en español y protegido: si no hay sesión de administrador, redirige al login.

---

## 8. Conectar Gemini (opcional)

1. Consigue una clave gratuita en <https://aistudio.google.com/>.
2. Copia `.env.example` como `.env` y completa:

   ```env
   GEMINI_API_KEY=tu_clave
   GEMINI_MODELO=gemini-2.5-flash
   ```

3. Reinicia el servidor o la app.

Si no hay clave, PasoAPaso sigue funcionando con las reglas locales. La IA **solo** se usa cuando
las reglas no entienden la frase. El texto de la orden es lo único que se envía a Gemini; no se
envían nombre, teléfono, clave ni datos de la cuenta. La respuesta de la IA se valida contra una
lista cerrada de acciones y campos permitidos.

En el panel puedes ver qué consultas usaron IA y apagarla sin romper la app.

---

## 9. Modo local y modo en línea

### Todo en una computadora (lo más fácil)

No configures nada. `iniciar.bat` arranca la app y su servidor local. El portal y el panel están en
`http://127.0.0.1:8765`.

### Servidor en la red local (para que otros lo vean)

```bat
servidor.bat
```

o:

```bat
python -m servidor --host 0.0.0.0 --port 8765
```

Luego abre `http://IP-DE-TU-PC:8765` desde otro dispositivo de la misma red. La app de escritorio
puede apuntar a esa dirección con `PASOAPASO_API_URL`.

### Servidor en internet (Render, Railway, Docker…)

La carpeta incluye `Dockerfile`, `Procfile`, `render.yaml` y `.env.example`.

**Render:**

1. Sube el proyecto a un repositorio de GitHub.
2. En Render, crea un **Web Service** con el Dockerfile.
3. Configura las variables:
   - `PASOAPASO_ADMIN_CLAVE` (una clave larga),
   - `GEMINI_API_KEY` (opcional),
   - `PASOAPASO_SECRETO` (Render puede generarla),
   - `PASOAPASO_DATOS=/app/datos`.
4. Agrega un **disco** montado en `/app/datos` para que la base no se borre al reiniciar.
5. Abre `https://tu-servicio.onrender.com/admin`.

**Docker:**

```bat
docker build -t pasoapaso .
docker run -p 8000:8000 -v pasoapaso_datos:/app/datos ^
  -e PASOAPASO_ADMIN_CLAVE=UnaClaveMuyLarga ^
  -e GEMINI_API_KEY=tu_clave ^
  pasoapaso
```

**Conectar la app de escritorio al servidor en internet:**

Crea `.env` (o una variable de Windows) con:

```env
PASOAPASO_API_URL=https://tu-servicio.onrender.com
```

Al abrir la app, ya no arranca el servidor local: usa el de internet. La app sigue ejecutando las
acciones en la PC; el servidor solo guarda y administra.

> **Nota honesta:** el servidor usa `http.server` de la biblioteca estándar, pensado para un
> proyecto escolar y pocos usuarios. Para una escuela completa con cientos de usuarios
> simultáneos convendría migrar a un servidor de producción y a PostgreSQL. La base y el diseño
> ya están separados para facilitar ese cambio.

---

## 10. Modo sin conexión

Si el servidor no responde, la app permite entrar en **modo local**:

- Usa las reglas locales para entender.
- Guarda las consultas en `%APPDATA%\PasoAPaso\pendientes.json`.
- Cuando vuelvas a entrar con tu cuenta y haya internet, las envía al servidor automáticamente.

Esto mantiene la promesa principal: **PasoAPaso puede enseñar aunque se caiga la red**.

---

## 11. Pruebas

```bat
python -m unittest discover -s pruebas -v
```

Cubren:

- teléfonos, claves, JWT, cookies y límites;
- interpretación de las frases de ejemplo;
- validación de las respuestas de la IA (incluidos intentos de abrir URLs peligrosas);
- ejecutor con acciones correctas, errores y cancelación;
- registro, login, perfil, interpretación, resultado, historial y CSV;
- portal web, CSRF, permisos y panel del administrador.

También se revisó que ninguna página quede con marcadores `{{...}}` sin reemplazar.

---

## 12. Estructura

```
PasoAPaso/
├── main.py                     Inicio de la app (splash → servidor → login → ventana)
├── iniciar.bat                 Inicio con doble clic
├── servidor.bat                Servidor solo (LAN / pruebas)
├── panel_admin.bat             Abre el panel en el navegador
├── requirements.txt            Componentes de la app y la voz
├── requirements-servidor.txt   El servidor no necesita dependencias
├── .env.example                Configuración de ejemplo
├── Dockerfile / Procfile / render.yaml
├── recursos/                   Logo, favicon y versiones para la web
├── servidor/
│   ├── config.py               Variables, rutas y secreto
│   ├── base_datos.py           SQLite, consultas y estadísticas
│   ├── seguridad.py            Claves, JWT, cookies, CSRF y límites
│   ├── servidor.py             HTTP, rutas base, seguridad de cabeceras
│   ├── rutas.py                API, portal, admin y CSV
│   ├── ia.py                   Reglas locales + Gemini + validación
│   ├── vistas.py              HTML y componentes
│   ├── plantillas/             Páginas del portal y del panel
│   └── estatico/              CSS y JS propios
├── pasoapaso/
│   ├── interfaz/               Splash, acceso, ventana principal, historial, panel
│   ├── nucleo/                 Intérprete, validador, ejecutor, cliente de nube, sesión
│   ├── utilidades/             Voz de entrada, voz de salida, teclado, Windows
│   ├── acciones/               Qué hace cada orden (apps, carpetas, navegador, pantalla)
│   └── datos/                  Catálogo de programas, sitios, ubicaciones y teclas
├── soporte/                    Página de ayuda (Bootstrap local)
├── pruebas/                    Pruebas automáticas
└── herramientas/               Generador del logo
```

---

## 13. Problemas conocidos y límites

- **La voz necesita internet** para reconocer (Google). Si falla, usa Escribir.
- **El reconocimiento de voz** puede confundir palabras; por eso la app pide confirmar.
- **YouTube** hace clic en una posición aproximada del primer video; se puede ajustar en
  `pasoapaso/configuracion.py` (`POSICION_PRIMER_VIDEO`) o desactivar con
  `REPRODUCIR_PRIMER_RESULTADO = False`.
- **SQLite** está pensado para una sola máquina o un servidor pequeño. Para muchos usuarios
  simultáneos, migrar a PostgreSQL.
- **La app solo funciona en Windows** porque usa atajos y APIs de Windows.
- Si la app se abre pero el panel no carga, revisa que el puerto 8765 esté libre. La app intenta
  los siguientes puertos y el login muestra la dirección que esté usando.
- Si olvidas la clave del administrador, cámbiala en `.env`, pon `PASOAPASO_ADMIN_RESET=1` y
  reinicia una vez.

---

## 14. Privacidad

- Solo se guarda lo necesario: nombre, teléfono, clave cifrada, datos opcionales y consultas.
- El administrador ve las consultas para mejorar las explicaciones.
- Cualquier persona puede pedir que se borre su cuenta; el portal tiene la opción y el panel
  permite hacerlo también.
- La voz se convierte en texto en el equipo; no se guardan audios.
- A Gemini solo se envía el texto de la orden cuando hace falta.

---

**PasoAPaso 2.0** · Hecho para aprender sin miedo a la computadora.
