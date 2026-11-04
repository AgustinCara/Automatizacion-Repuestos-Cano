# proveedores/proveedor_CLAVE.py
"""
PLANTILLA para un proveedor nuevo.

1. Guardar este archivo como  proveedor_<clave>.py  (ej. proveedor_pana.py).
2. Completar los datos marcados con  <<<  y armar los pasos.
3. Probar en tu PC:   python probar_proveedor.py <clave>
4. Mandarle el archivo al cliente: lo carga con el botón "Agregar proveedor".

OJO: este archivo lleva usuario y contraseña. NO subirlo al repo público.

Proveedor: <<< NOMBRE (www.sitio.com.ar)
Archivo:   <<< nombre del archivo que se guarda (ej. lista.txt)
Recorrido: <<< login -> menú -> descargas -> botón del archivo
"""
from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin


class ProveedorNuevo(FlujoWebMixin, BaseProveedor):  # <<< cambiar "Nuevo" por el nombre
    nombre_clave = "nuevo"            # <<< sin espacios ni mayúsculas, igual que en el nombre del archivo
    nombre_display = "Nuevo"          # <<< como se ve en la lista de la app
    usa_navegador = True              # False si se baja con un link directo, sin login

    # Se copia a config.json cuando el cliente importa el proveedor.
    # No pisa datos que ya existan (si el cliente cambió la contraseña, se respeta).
    config_inicial = {
        "login_url": "https://www.sitio.com.ar",   # <<< página de ingreso
        "usuario": "",                             # <<<
        "password": "",                            # <<<
        "nombre_archivo": "lista.txt",             # <<< nombre con que se guarda
        "carpeta": ""
        # Opcionales:
        # "download_page": "https://...",          # ir directo a la página del archivo
        # "selector_usuario": "input[name='usuario']",  # si no encuentra el campo usuario
        # "mostrar_navegador": True,               # ver el navegador mientras trabaja
    }

    def pasos(self, page, cfg):
        # 1. Ingresar con usuario y contraseña
        page = self.login(page, cfg, [cfg.get("login_url", "")])

        # 2. Llegar a la página del archivo. Dos formas:
        if cfg.get("download_page"):
            self.ir_a(page, cfg["download_page"])                 # a) dirección directa
        else:
            page = self.clic_texto(page, ["Descargas", "Descarga"])  # b) clic en menús por su texto

        # Otras acciones disponibles si el sitio las pide:
        #   self.tildar_todos(page)                  -> casilla "Seleccionar todos"
        #   self.elegir_opcion(page, "BBA")          -> elegir en una lista o casilla
        #   page = self.buscar_articulo(page, cfg, "AN1067")

        # 3. Descargar: primero busca links al archivo, después los botones con esos textos
        tmp = self.bajar_archivo(
            page, ["txt", "zip"],                    # <<< extensiones posibles del archivo
            pistas=["txt", "lista", "precio"],       # palabras que suele tener el link
            textos=["Descargar TXT", "Descargar"],   # <<< texto del botón, el más exacto primero
        )

        # 4. Guardar con el nombre final
        return self.guardar_final(tmp, cfg.get("nombre_archivo", "lista.txt"))
