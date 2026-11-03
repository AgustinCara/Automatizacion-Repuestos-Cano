# proveedores/proveedor_cedicor.py
"""
Proveedor: CEDICOR (www.cedicor.com.ar)
Archivo:   CEDICOR.CSV
Recorrido: login -> flecha en el nombre -> Precios -> tildar todos -> descargar Excel
           -> se convierte a CSV automáticamente
"""
from pathlib import Path

from proveedores.base import BaseProveedor
from proveedores._web import FlujoWebMixin, excel_a_csv


class ProveedorCedicor(FlujoWebMixin, BaseProveedor):
    nombre_clave = "cedicor"
    nombre_display = "Cedicor"

    def pasos(self, page, cfg):
        page = self.login(page, cfg, ["https://www.cedicor.com.ar"])
        # "Precios" está en el menú que se abre con la flecha del nombre:
        # clic_texto abre los menús desplegables solo si no lo ve.
        page = self.clic_texto(page, ["Precios", "Lista de precios"])
        self.tildar_todos(page)
        tmp = self.bajar_archivo(
            page, ["xlsx", "xls", "csv", "zip"], pistas=["excel", "xls"],
            textos=["Descargar Excel", "Exportar a Excel", "Excel", "Descargar"],
        )
        excel = Path(self.guardar_final(tmp, "_cedicor_excel.xlsx", acepta_html=True))
        salida = self._destino / cfg.get("nombre_archivo", "CEDICOR.CSV")
        filas = excel_a_csv(
            excel, salida,
            separador=cfg.get("separador_csv", ";"),
            decimal=cfg.get("decimal_csv", ","),
            encoding=cfg.get("encoding_csv", "cp1252"),
        )
        excel.unlink(missing_ok=True)
        self.log(f"Excel convertido a CSV ({filas} filas)")
        return str(salida)
