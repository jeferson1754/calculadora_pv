import pyperclip
import time
#from conexion_sap import saplogin, pymysql
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
            sql = "SELECT DISTINCT Pedido FROM `vista_productiva_bom` ORDER BY `vista_productiva_bom`.`Pedido` ASC;"
            cursor.execute(sql)
            filas = cursor.fetchall()
            
            # Convierte los resultados a string plano y filtra valores nulos o vacíos
            pedidos = [str(f[0]).strip() for f in filas if f[0] and str(f[0]).strip() != ""]
            
        print(f"[OK] Se obtuvieron {len(pedidos)} pedidos únicos desde la base de datos.")
    except Exception as e:
        print(f"[ERROR MYSQL] No se pudieron obtener los pedidos: {e}")
    finally:
        conexion.close()
        
    return pedidos

def extraer_filas_tabla_rechazo(session, codigo_pedido):
    """
    Recorre las filas de la tabla de rechazo en VA03 (Dynpro 4021)
    y omite registros vacíos o máscaras con guiones bajos ('______').
    """
    posiciones_rechazadas = []
    codigo_str = str(codigo_pedido).strip()

    try:
        tabla = session.findById(
            r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\08/ssub/2/3/sub/2/3/1/tblSAPMV45ATCTRL_UPOS_ABSAGE"
        )
        
        filas_visibles = tabla.Rows.Count

        for i in range(filas_visibles):
            try:
                # 1. Leer número de posición ('Pos.')
                pos_val = session.findById(
                    r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\08/ssub/2/3/sub/2/3/1/tblSAPMV45ATCTRL_UPOS_ABSAGE/txtVBAP-POSNR[0," + str(i) + "]"
                ).text.strip()

                # 2. Leer código de Material
                mat_val = session.findById(
                    r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\08/ssub/2/3/sub/2/3/1/tblSAPMV45ATCTRL_UPOS_ABSAGE/ctxtVBAP-MATNR[1," + str(i) + "]"
                ).text.strip()

                # 3. Leer Motivo de Rechazo
                motivo_val = session.findById(
                    r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\08/ssub/2/3/sub/2/3/1/tblSAPMV45ATCTRL_UPOS_ABSAGE/cmbVBAP-ABGRU[2," + str(i) + "]"
                ).text.strip()

                # Limpieza de guiones bajos de plantilla SAP
                pos_limpia = pos_val.replace('_', '').strip()
                motivo_limpio = motivo_val.replace('_', '').strip()

                # FILTRO DE VALIDACIÓN: Ignorar si la posición está vacía o el motivo no existe
                if not pos_limpia:
                    break # Si ya no hay número de posición, llegamos al final real de la tabla

                if motivo_limpio != "":
                    item = {
                        "Pedido": codigo_str,
                        "PosPed": pos_limpia,
                        "Material": mat_val,
                        "Motivo_Rechazo": motivo_val # Guarda la descripción completa del motivo
                    }
                    posiciones_rechazadas.append(item)
                    print(f"  [RECHAZADO] Pedido: {codigo_str} | Pos: {pos_limpia} | Mat: {mat_val} | Motivo: {motivo_val}")

            except Exception:
                # Intento genérico si falla el ID extendido
                try:
                    pos_gen = session.findById(f"{tabla.id}/txt[0,{i}]").text.strip().replace('_', '')
                    motivo_gen = session.findById(f"{tabla.id}/cmb[2,{i}]").text.strip().replace('_', '')

                    if pos_gen and motivo_gen != "":
                        posiciones_rechazadas.append({
                            "Pedido": codigo_str,
                            "PosPed": pos_gen,
                            "Material": "",
                            "Motivo_Rechazo": motivo_gen
                        })
                except Exception:
                    break

    except Exception as e:
        print(f"[AVISO] Error al procesar tabla de posiciones en pedido {codigo_str}: {e}")

    return posiciones_rechazadas

def ejecutar_auditoria_diaria_va03(session, lista_pedidos, carpeta_base="PV/AUDITORIA"):
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    os.makedirs(carpeta_base, exist_ok=True)
    ruta_json = os.path.join(carpeta_base, f"rechazados_{fecha_hoy}.json")
    ruta_txt = os.path.join(carpeta_base, f"rechazados_{fecha_hoy}.txt")

    # 1. CARGAR REGISTROS HISTÓRICOS DEL DÍA SI YA EXISTE EL ARCHIVO JSON
    todos_los_rechazados = []
    if os.path.exists(ruta_json):
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                todos_los_rechazados = json.load(f)
            print(f"[HISTORIAL] Se cargaron {len(todos_los_rechazados)} registros previos del archivo JSON de hoy.")
        except Exception as e:
            print(f"[AVISO] No se pudo leer el archivo JSON existente, se creará uno nuevo: {e}")
            todos_los_rechazados = []

    NUEVOS_RECHAZADOS = []
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando auditoría de {len(lista_pedidos)} pedidos...")

    for idx, codigo in enumerate(lista_pedidos, 1):
        # Extraer string plano del pedido
        codigo_str = str(codigo.get('Pedido') if isinstance(codigo, dict) else codigo).strip()
        print(f"  [{idx}/{len(lista_pedidos)}] Consultando VA03 - Pedido: {codigo_str}...")

        # Extraer posiciones rechazadas desde SAP
        rechazados_pedido = extraer_filas_tabla_rechazo(session, codigo_str)
        
        if rechazados_pedido:
            if isinstance(rechazados_pedido, dict):
                rechazados_pedido = [rechazados_pedido]
                
            for item in rechazados_pedido:
                ped_limpio = str(item['Pedido']['Pedido'] if isinstance(item.get('Pedido'), dict) else item.get('Pedido', codigo_str)).strip()
                pos_limpia = str(item.get('PosPed', '')).strip()
                
                nuevo_reg = {
                    "Pedido": ped_limpio,
                    "PosPed": pos_limpia,
                    "Material": str(item.get('Material', '')).strip(),
                    "Motivo_Rechazo": str(item.get('Motivo_Rechazo', '')).strip()
                }

                # CONTROL DE DUPLICADOS: Verificar si la posición ya existía en la lista de hoy
                ya_existe = any(r['Pedido'] == ped_limpio and r['PosPed'] == pos_limpia for r in todos_los_rechazados)
                
                if not ya_existe:
                    todos_los_rechazados.append(nuevo_reg)
                    NUEVOS_RECHAZADOS.append(nuevo_reg)

        time.sleep(0.3)

    # 2. GUARDAR JSON CONSOLIDADO REESCRIBIENDO LA LISTA COMPLETA ACUMULADA
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(todos_los_rechazados, f, ensure_ascii=False, indent=4)

    # 3. GUARDAR EN EL TXT EN MODO APPEND ('a') O CREAR CABECERA SI ES NUEVO
    txt_existe = os.path.exists(ruta_txt)
    with open(ruta_txt, "a", encoding="utf-8") as f:
        if not txt_existe:
            f.write("FECHA_PROCESO\tPEDIDO\tPOSICION\tMATERIAL\tMOTIVO_RECHAZO\n")
        
        for reg in NUEVOS_RECHAZADOS:
            f.write(f"{fecha_hoy}\t{reg['Pedido']}\t{reg['PosPed']}\t{reg['Material']}\t{reg['Motivo_Rechazo']}\n")

    print(f"\n[OK] Auditoría completada. Se añadieron {len(NUEVOS_RECHAZADOS)} registros nuevos.")
    print(f" -> Total acumulado del día en JSON: {len(todos_los_rechazados)} posiciones.")
    print(f" -> Archivo JSON: {ruta_json}")
    print(f" -> Archivo TXT:  {ruta_txt}")

    # 4. ACTUALIZAR EN MYSQL ÚNICAMENTE LOS REGISTROS NUEVOS
    if NUEVOS_RECHAZADOS:
        actualizar_mysql_desde_lista(NUEVOS_RECHAZADOS)
    else:
        print("[INFO] No se encontraron nuevas posiciones de rechazo para actualizar en MySQL.")

    return todos_los_rechazados

def actualizar_mysql_desde_lista(lista_rechazados):
    """Actualiza en lote la columna Motivo_Rechazo en MySQL con depuración correcta."""
    if not lista_rechazados:
        print("[INFO] No hay registros para actualizar en MySQL.")
        return

    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )
    
    try:
        with conexion.cursor() as cursor:
            sql_update = """
                UPDATE vista_productiva_bom 
                SET Motivo_Rechazo = %s 
                WHERE Pedido = %s AND `Pos._PD` = %s;
            """

            total_actualizados = 0

            print(f"\n--- INICIANDO ACTUALIZACIÓN EN MYSQL ({len(lista_rechazados)} REGISTROS) ---")

            for idx, reg in enumerate(lista_rechazados, 1):
                # 1. Extraer correctamente los valores planos
                pedido_val = reg['Pedido']['Pedido'] if isinstance(reg['Pedido'], dict) else reg['Pedido']
                pos_val = str(reg['PosPed']).strip()
                motivo_val = str(reg['Motivo_Rechazo']).strip()

                # 2. EJECUTAR PRIMERO LA CONSULTA EN MYSQL
                cursor.execute(sql_update, (
                    motivo_val,
                    pedido_val,
                    pos_val
                ))

                # 3. LEER FILAS AFECTADAS DESPUÉS DE EJECUTAR
                filas_afectadas = cursor.rowcount
                total_actualizados += filas_afectadas

                # 4. Formatear la sentencia traducida para print de depuración
                sql_depuracion = f"UPDATE vista_productiva_bom SET Motivo_Rechazo = '{motivo_val}' WHERE Pedido = '{pedido_val}' AND `Pos._PD` = '{pos_val}';"

                # 5. Imprimir resultado real según filas_afectadas
                if filas_afectadas > 0:
                    print(f"[{idx}/{len(lista_rechazados)}] [OK] Pedido: {pedido_val} | Pos: {pos_val} -> Motivo: '{motivo_val}' ({filas_afectadas} fila actualizada)")
                else:
                    print(f"[{idx}/{len(lista_rechazados)}] [OMITIDO] Pedido: {pedido_val} | Pos: {pos_val} -> No se encontró coincidencia en MySQL")

                print(f"    SQL Ejecutada: {sql_depuracion}\n")

            # 6. Confirmar cambios en la base de datos (un solo commit al final)
            conexion.commit()
            print(f"--- PROCESO FINALIZADO: {total_actualizados} REGISTROS AFECTADOS EN MYSQL ---\n")

    except Exception as e:
        print(f"[ERROR MYSQL] Falló la actualización: {e}")
        conexion.rollback()
    finally:
        conexion.close()
        
def procesar_transaccion(session, codigo):
    
        
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "va03"
    session.findById("wnd[0]").sendVKey(0)
    
    codigo_str = str(codigo).strip()
    motivo_rechazo = ""

    try:
        # 1. Resetear pantalla e ir a la transacción VA03
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nVA03"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # 2. Escribir en Dynpro 4001 (Campo VBAK-VBELN)
        campo_pedido = session.findById("wnd[0]/usr/ctxt[0]")
        campo_pedido.text = codigo_str
        
        # Presionar ENTER para pasar a la Dynpro 4021 (Resumen)
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.8)

        # 3. Hacer clic en la pestaña "Motivo de rechazo" (Dynpro 4021)
        # Se intenta por ID técnico directo o navegando en los tabs de la Dynpro 4021
        pestaña_ok = False
        
        # Opción A: ID Directo Dynpro 4021
        for id_tab in [
            r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\08",
            r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\07",
            r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\06"
        ]:
            try:
                session.findById(id_tab).select()
                pestaña_ok = True
                break
            except Exception:
                continue

        # Opción B: Búsqueda por el texto visual del botón "Motivo de rechazo"
        if not pestaña_ok:
            try:
                tabstrip = session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW")
                for tab in tabstrip.Children:
                    if "rechazo" in str(tab.Text).lower():
                        tab.select()
                        pestaña_ok = True
                        break
            except Exception:
                pass

        time.sleep(0.5)

        # 4. Extraer el valor del motivo de rechazo en la posición (Fila 0)
  # Dentro de tu función de procesamiento tras hacer clic en la pestaña "Motivo de rechazo":
        if pestaña_ok:
            # Capturar todas las filas de la tabla
            rechazados_pedido = extraer_filas_tabla_rechazo(session, codigo_str)
            
            # Guardar en .json y .txt
            ejecutar_auditoria_diaria_va03(session, rechazados_pedido)

    except Exception as e:
        print(f"[ERROR] No se pudo procesar el pedido {codigo_str}: {e}")

    print(f"Codigo:{codigo_str} - Motivo Rechazo: {motivo_rechazo}")
    
    session.findById("wnd[0]/tbar[0]/btn[3]").press()

    return motivo_rechazo

'''
# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    # 1. Conectar a la sesión activa de SAP GUI
    session = saplogin()

    if session:
        # 2. Obtener la lista de todos los pedidos únicos desde la base de datos MySQL
        lista_pedidos = obtener_pedidos_pendientes()

        if lista_pedidos:
            total = len(lista_pedidos)
            print(f"\n[INICIO] Procesando {total} pedidos individualmente en SAP VA03...\n")
            
            for idx, ped in enumerate(lista_pedidos, 1):
                pedido_str = str(ped).strip()
                print(f"[{idx}/{total}] Procesando Pedido: {pedido_str}")
            
                # 3. Ejecutar la auditoría de motivo de rechazo sobre todos los pedidos
                procesar_transaccion(session, pedido_str)
            
            print("\n[FIN] Sincronización de pedidos en SAP completada exitosamente.")
        else:
            print("[AVISO] No se encontraron pedidos en la base de datos para procesar.")
    else:
        print("[ERROR] No se pudo establecer la conexión con SAP GUI.")
'''