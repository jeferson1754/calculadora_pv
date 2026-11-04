import pyperclip
import time
from conexion_sap import saplogin, pymysql
from pathlib import Path
import os
import glob
import json
import pandas as pd
from datetime import datetime
import pymysql

base_bodega = Path(r"C:\xampp\htdocs\Calculadora_PV")


def obtener_pedidos_pendientes():
    """Obtiene la lista de pedidos únicos (DISTINCT) desde MySQL."""
    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )
    pedidos = []
    try:
        with conexion.cursor() as cursor:
            sql = """
                           SELECT DISTINCT Componente FROM maestro_bodegas WHERE Componente IN ( SELECT codigo_material COLLATE utf8mb4_general_ci FROM maestro_codigos_32_33 ) ORDER BY `Componente` ASC;
                       """
            cursor.execute(sql)
            filas = cursor.fetchall()

            # Convierte los resultados a string plano y filtra valores nulos o vacíos
            pedidos = [str(f[0]).strip()
                       for f in filas if f[0] and str(f[0]).strip() != ""]

        print(
            f"[OK] Se obtuvieron {len(pedidos)} pedidos únicos desde la base de datos.")
    except Exception as e:
        print(f"[ERROR MYSQL] No se pudieron obtener los pedidos: {e}")
    finally:
        conexion.close()

    return pedidos

def asegurar_columna_valor_total(cursor):
    """Verifica si la columna 'Valor Total' existe en maestro_bodegas y la crea si es necesario."""
    sql_check = """
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
          AND TABLE_NAME = 'maestro_bodegas' 
          AND COLUMN_NAME = 'Valor_Total';
    """
    cursor.execute(sql_check)
    existe = cursor.fetchone()[0]

    if not existe:
        print("[INFO] Creando columna 'Valor Total' en la tabla maestro_bodegas...")
        sql_add = """
            ALTER TABLE `maestro_bodegas` 
            ADD COLUMN `Valor_Total` DECIMAL(15, 2) NULL DEFAULT 0.00;
        """
        cursor.execute(sql_add)
        print("[OK] Columna 'Valor_Total' creada con éxito.")

def actualizar_mysql_precios_materiales(lista_materiales):
    """
    Actualiza la columna 'Valor_Total' en la tabla maestro_bodegas
    utilizando el precio calculado en MM03 para cada código de material.
    """
    if not lista_materiales:
        print("[INFO] No hay registros de materiales para actualizar en MySQL.")
        return

    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )

    try:
        with conexion.cursor() as cursor:
            # Se usa TRIM(LEADING '0' FROM ...) para que '00000032001999' y '32001999' coincidan siempre
            
            asegurar_columna_valor_total(cursor)
            
            sql_update = """
                UPDATE maestro_bodegas
                SET `Valor_Total` = %s
                WHERE TRIM(LEADING '0' FROM Componente) = TRIM(LEADING '0' FROM %s);
            """

            total_actualizados = 0

            print(
                f"\n--- INICIANDO ACTUALIZACIÓN DE PRECIOS EN MYSQL ({len(lista_materiales)} MATERIALES) ---")

            for idx, reg in enumerate(lista_materiales, 1):
                # 1. Extraer el código y el precio unitario calculado
                # (Soporta tanto el diccionario retornado por procesar_transaccion como tuplas directas)
                codigo_mat = str(
                    reg.get('codigo', reg.get('Material', ''))).strip()
                precio_val = float(
                    reg.get('precio_calculado', reg.get('Valor_Total', 0.0)))

                if not codigo_mat:
                    continue

                # 2. Ejecutar la actualización en MySQL
                cursor.execute(sql_update, (precio_val, codigo_mat))

                # 3. Leer filas afectadas
                filas_afectadas = cursor.rowcount
                total_actualizados += filas_afectadas

                # 4. Formatear sentencia para depuración
                sql_depuracion = f"UPDATE maestro_bodegas SET `Valor_Total` = {precio_val} WHERE Componente = '{codigo_mat}';"
                
                print(sql_depuracion)  # Esto es solo para depuración, se puede comentar en producción

                # 5. Salida en consola
                if filas_afectadas > 0:
                    print(
                        f"[{idx}/{len(lista_materiales)}] [OK] Material: {codigo_mat} -> Valor_Total: ${precio_val:,.2f} ({filas_afectadas} posiciones actualizadas)")
                else:
                    print(
                        f"[{idx}/{len(lista_materiales)}] [OMITIDO] Material: {codigo_mat} -> No existe en la vista/tabla activa")

                print(f"    SQL: {sql_depuracion}\n")

            # 6. Guardar cambios
            conexion.commit()
            print(
                f"--- PROCESO FINALIZADO: {total_actualizados} REGISTROS AFECTADOS EN MYSQL ---\n")

    except Exception as e:
        print(f"[ERROR MYSQL] Falló la actualización de precios: {e}")
        conexion.rollback()
    finally:
        conexion.close()


def parse_num_sap(texto):
    """Limpia cadenas numéricas con formato SAP (ej: 1.234,50 -> 1234.5)."""
    if not texto:
        return 0.0
    t = str(texto).strip().replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def procesar_transaccion(session, codigo):

    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "MM03"
    session.findById("wnd[0]").sendVKey(0)

    codigo_str = str(codigo).strip()
    resultado = {
        "codigo": codigo_str,
        "control_precio": "",
        "cantidad_base": 1.0,
        "precio_estandar": 0.0,
        "precio_variable": 0.0,
        "precio_calculado": 0.0
    }

    try:
        # 1. Resetear pantalla e ir a la transacción MM03
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nMM03"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # 2. Escribir en Dynpro 4001 (Campo VBAK-VBELN)
        campo_pedido = session.findById("wnd[0]/usr/ctxt")
        campo_pedido.text = codigo_str

        # Presionar ENTER para pasar a la Dynpro 4021 (Resumen)
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.8)

        session.findById("wnd[1]/tbar[0]/btn[0]").press()

        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/usr/tabsTABSPR1/tabpSP24").select()
        session.findById("wnd[1]/usr/ctxt[0]").text = "6902"
        session.findById("wnd[1]/usr/ctxt[0]").caretPosition = 4
        session.findById("wnd[1]").sendVKey(0)

        print(f"[INFO] Consultando material {codigo_str} en MM03...")
        time.sleep(0.5)
# 5. Ruta base del subscreen de precios/contabilidad
        subscreen_path = "wnd[0]/usr/tabsTABSPR1/tabpSP24/ssub/1/2/sub/1/2/2/sub/1/2/2/1/tabsTABS/tabpPPLF/ssub/1/2/2/1/1/2/sub/1/2/2/1/1/2/1/"

        # Control de precio ('S' estándar, 'V' variable/medio variable)
        control_precio = session.findById(
            subscreen_path + "ctxt[0]").text.strip().upper()

        # Cantidad base (por la que se divide el precio en SAP)
        cantidad_base_raw = session.findById(
            subscreen_path + "txt[8]").text.strip()
        cantidad_base = parse_num_sap(cantidad_base_raw)
        if cantidad_base <= 0:
            cantidad_base = 1.0

        # Precios extraídos
        txt_estandar = session.findById(subscreen_path + "txt[4]").text.strip()
        txt_inter = session.findById(subscreen_path + "txt[6]").text.strip()

        precio_estandar = parse_num_sap(txt_estandar)
        precio_inter = parse_num_sap(txt_inter)

        # 6. Reglas de cálculo según Control de Precio (S vs V)
        precio_final = 0.0
        if control_precio == "S":
            precio_final = round(precio_estandar / cantidad_base, 2)
            print(
                f"[{codigo_str}] Control: 'S' (Estándar) -> {precio_estandar} / {cantidad_base} = {precio_final}")
        elif control_precio == "V":
            precio_final = round(precio_inter / cantidad_base, 2)
            print(
                f"[{codigo_str}] Control: 'V' (Medio Variable) -> {precio_inter} / {cantidad_base} = {precio_final}")
        else:
            # Fallback en caso de indicador distinto
            precio_final = round(
                (precio_estandar or precio_inter) / cantidad_base, 2)
            print(
                f"[{codigo_str}] Control no contemplado ('{control_precio}') -> Asignado fallback: {precio_final}")

        resultado.update({
            "control_precio": control_precio,
            "cantidad_base": cantidad_base,
            "precio_estandar": precio_estandar,
            "precio_variable": precio_inter,
            "precio_calculado": precio_final
        })

    except Exception as e:
        print(f"[ERROR] Error al procesar el material {codigo_str}: {e}")

    finally:
        # Volver al menú anterior para dejar la sesión limpia
        try:
            session.findById("wnd[0]/tbar[0]/btn[3]").press()
        except Exception:
            pass

    return resultado


# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    # 1. Conectar a la sesión activa de SAP GUI
    session = saplogin()

    if session:
        # 2. Obtener la lista de todos los pedidos únicos desde la base de datos MySQL
        #lista_pedidos = obtener_pedidos_pendientes()
        
        lista_pedidos = [
            "32001999", "32002076","32002140","32002144","32002145"
        ]
        
        if lista_pedidos: # O lista_materiales
            total = len(lista_pedidos)
            print(f"\n[INICIO] Procesando {total} materiales en SAP MM03 para cálculo de precios...\n")

            # 1. Lista para acumular los resultados calculados
            materiales_procesados = []

            for idx, ped in enumerate(lista_pedidos, 1):
                material_str = str(ped).strip()
                print(f"[{idx}/{total}] Procesando Material: {material_str}")

                # 2. Ejecutar la transacción en MM03 y CAPTURAR el retorno
                datos_mat = procesar_transaccion(session, material_str)

                # 3. Guardar en la lista solo si devolvió datos válidos
                if datos_mat and datos_mat.get("codigo"):
                    materiales_procesados.append(datos_mat)

            print("\n[FIN] Extracción de precios en SAP completada exitosamente.")

            # 4. Actualizar en MySQL todos los precios calculados
            if materiales_procesados:
                actualizar_mysql_precios_materiales(materiales_procesados)
            else:
                print("[AVISO] No se obtuvieron datos válidos para actualizar en MySQL.")

        else:
            print("[AVISO] No se encontraron materiales en la base de datos para procesar.")
    else:
        print("[ERROR] No se pudo establecer la conexión con SAP GUI.")
