from datetime import datetime
from pathlib import Path
import pymysql


class RegistrarEjecucion:

    def __init__(
        self, modulo="Procesamiento Masivo", usuario="SISTEMA_PYTHON"
    ):
        self.modulo = modulo
        self.usuario = usuario
        self.id_ejecucion = None
        self.fecha_inicio = None

    def __enter__(self):
        self.fecha_inicio = datetime.now()
        conexion = pymysql.connect(
            host="localhost",
            user="root",
            password="",
            database="calculadora_pv",
        )
        try:
            with conexion.cursor() as cursor:
                sql = """
                    INSERT INTO historial_ejecuciones 
                    (fecha_inicio, modulo, estado, usuario_origen) 
                    VALUES (%s, %s, 'EN PROCESO', %s)
                """
                cursor.execute(
                    sql, (self.fecha_inicio, self.modulo, self.usuario)
                )
                self.id_ejecucion = cursor.lastrowid
            conexion.commit()
        finally:
            conexion.close()

        print(
            f" [Historial]: Ejecución #{self.id_ejecucion} iniciada para '{self.modulo}'."
        )
        return self

    def finalizar(self, registros_procesados=0, estado="EXITOSO", error=None):
        fecha_fin = datetime.now()
        duracion = int((fecha_fin - self.fecha_inicio).total_seconds())

        conexion = pymysql.connect(
            host="localhost",
            user="root",
            password="",
            database="calculadora_pv",
        )
        try:
            with conexion.cursor() as cursor:
                sql = """
                    UPDATE historial_ejecuciones 
                    SET fecha_fin = %s, duracion_segundos = %s, estado = %s, 
                        registros_procesados = %s, mensaje_error = %s
                    WHERE id = %s
                """
                cursor.execute(
                    sql,
                    (
                        fecha_fin,
                        duracion,
                        estado,
                        registros_procesados,
                        str(error) if error else None,
                        self.id_ejecucion,
                    ),
                )

                # También actualizar la constante global de última sincronización
                fecha_str = fecha_fin.strftime("%d/%m/%Y %H:%M:%S")
                cursor.execute(
                    "UPDATE parametros_configuracion SET valor = %s WHERE clave = 'ULTIMA_SINCRONIZACION'",
                    (fecha_str,),
                )

            conexion.commit()
            print(
                f" [Historial]: Ejecución #{self.id_ejecucion} finalizada en {duracion}s con estado '{estado}'."
            )
        finally:
            conexion.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Captura errores no controlados automáticamente
            self.finalizar(estado="ERROR", error=exc_val)