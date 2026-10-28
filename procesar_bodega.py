import pyperclip
import time
from conexion_sap import saplogin, pymysql
from pathlib import Path
import os
import glob
import pandas as pd
from sqlalchemy import create_engine
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


base_bodega = Path(r"C:\xampp\htdocs\Calculadora_PV\PV\BODEGA")

salida_unicos_excel = base_bodega / "MATERIALES_BODEGA.xlsx"


def procesar_bodega(session, nombre_archivo, base_bodega):
    # INGRESA A LA LISTA PARA COPIAR LAS OFS y SALIR DE LA LISTA
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/usr/btn[0]").press()
    session.findById("wnd[1]/tbar[0]/btn[16]").press()
    session.findById("wnd[1]/tbar[0]/btn[24]").press()

    time.sleep(5)
    session.findById("wnd[0]/tbar[1]/btn[8]").press()
    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    print(f"Se procede a descargar la OF {nombre_archivo}")
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[1]/btn[45]").press()
    session.findById("wnd[1]/usr/sub/2/sub/2/1/rad[1,0]").selected = True
    session.findById("wnd[1]/usr/sub/2/sub/2/1/rad[1,0]").setFocus()
    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    time.sleep(2)

    print(f"Poniendo ruta de guardado: {base_bodega}")

    # GUARDADO DE ARCHIVO
    session.findById("wnd[1]/usr/ctxt[0]").text = str(base_bodega)
    session.findById("wnd[1]/usr/ctxt[1]").text = nombre_archivo
    session.findById("wnd[1]").sendVKey(0)

    session.findById("wnd[0]/tbar[0]/btn[3]").press()

    time.sleep(2)
    session.findById("wnd[0]/tbar[1]/btn[8]").press()
    time.sleep(5)
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/btn[15]").press()


def obtener_materiales_bodega():
    """Obtiene la lista plana de materiales únicos (series 32 y 33) desde MySQL."""
    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )
    materiales = []
    try:
        with conexion.cursor() as cursor:
            sql = """
                SELECT DISTINCT `N° Componentes` AS Componente 
                FROM vista_productiva_bom 
                WHERE `N° Componentes` IN (
                    SELECT codigo_material COLLATE utf8mb4_general_ci 
                    FROM maestro_codigos_32_33
                ) 
                ORDER BY `Componente` ASC;
            """
            cursor.execute(sql)
            filas = cursor.fetchall()
            materiales = [str(f[0]).strip() for f in filas if f[0]]
    finally:
        conexion.close()

    return materiales


def obtener_almacenes_permitidos():
    """Obtiene la lista de almacenes permitidos desde MySQL."""
    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )
    almacenes = []
    try:
        with conexion.cursor() as cursor:
            sql = "SELECT Codigo FROM `bodegas_productivas` ORDER BY `bodegas_productivas`.`Codigo` ASC;"
            cursor.execute(sql)
            filas = cursor.fetchall()
            almacenes = [str(f[0]).strip() for f in filas if f[0]]
    finally:
        conexion.close()

    return almacenes


def procesar_excel_productivo_2(
    carpeta_origen=base_bodega,  # Se pasa la carpeta con los .XLS de Bodega
    salida_unicos_excel=salida_unicos_excel,
    # Lista opcional de almacenes a filtrar, ej: ['0001', '0002']
    almacenes_permitidos=None
):
    # Lista para almacenar los DataFrames de cada archivo
    lista_dfs = []

    # Buscar todos los archivos .xls o .txt dentro de la carpeta
    patron_archivos = os.path.join(carpeta_origen, "*.XLS*")
    archivos_encontrados = glob.glob(patron_archivos)

    if not archivos_encontrados:
        raise FileNotFoundError(
            f"No se encontraron archivos .XLS en la carpeta '{carpeta_origen}'")

    print(
        f"Se encontraron {len(archivos_encontrados)} archivos para consolidar.")

    for archivo_origen in archivos_encontrados:
        header_row = None
        encoding_exitoso = None

        # 1. Encontrar la fila de encabezados
        for enc in ["utf-16", "latin1", "utf-8", "cp1252"]:
            try:
                with open(archivo_origen, "r", encoding=enc, errors="ignore") as f:
                    for i, line in enumerate(f):
                        linea_limpia = line.strip()
                        if (
                            "Número de material" in linea_limpia
                            or "Material" in linea_limpia
                            or "Alm." in linea_limpia
                            or "Doc.venta" in linea_limpia
                        ):
                            header_row = i
                            encoding_exitoso = enc
                            break
                if header_row is not None:
                    break
            except Exception:
                continue

        if header_row is None:
            print(
                f"[AVISO]: No se pudo detectar encabezado en '{archivo_origen}', se omite.")
            continue

        # 2. Leer el archivo
        try:
            df_temp = pd.read_csv(
                archivo_origen,
                sep="\t",
                encoding=encoding_exitoso,
                skiprows=header_row,
                engine="python",
                on_bad_lines="skip",
                dtype=str,
            )
        except Exception as e:
            print(f"[ERROR]: No se pudo leer '{archivo_origen}': {e}")
            continue

        if df_temp.empty:
            continue

        # A. Limpiar espacios en los nombres de las columnas
        df_temp.columns = [str(c).strip() for c in df_temp.columns]

        # B. Eliminar columnas vacías ('') y las que comienzan con 'Unnamed'
        columnas_validas = [
            c for c in df_temp.columns
            if c != "" and not c.startswith("Unnamed") and not c.startswith("nan")
        ]
        df_temp = df_temp.loc[:, columnas_validas].copy()

        # C. ELIMINAR DUPLICADOS EN EL DATAFRAME INDIVIDUAL (Vital para evitar InvalidIndexError)
        df_temp = df_temp.loc[:, ~
                              df_temp.columns.duplicated(keep="first")].copy()

        # D. Homologar nombres de columnas
        renombres_mb52 = {
            "Número de material": "Componente",
            "Alm.": "Almacén",
            "Alm": "Almacén",
            "Libre utilización": "Stock_Libre",
            "Valor libre util.": "Valor_Stock_Libre",
            "Ce.": "Centro"
        }
        df_temp.rename(columns=renombres_mb52, inplace=True)

        # E. Por si el renombre generó algún duplicado accidental, volver a limpiar
        df_temp = df_temp.loc[:, ~
                              df_temp.columns.duplicated(keep="first")].copy()
        df_temp.reset_index(drop=True, inplace=True)

        lista_dfs.append(df_temp)

    if not lista_dfs:
        raise ValueError("No se pudo procesar ningún archivo de bodega.")

    # 3. CONSOLIDAR TODOS LOS ARCHIVOS EN UN SOLO DATAFRAME
    df_consolidado = pd.concat(lista_dfs, ignore_index=True)
    df_consolidado.columns = df_consolidado.columns.astype(str).str.strip()
    df_consolidado = df_consolidado.loc[:, ~
                                        df_consolidado.columns.duplicated()].copy()

  # 3. FILTRAR POR ALMACÉN DE FORMA SEGURA
    if almacenes_permitidos and "Almacén" in df_consolidado.columns:
        almacenes_str = [str(a).strip() for a in almacenes_permitidos]

        # Al eliminar duplicados previamente, df_consolidado["Almacén"] ya es una Series válida
        mask = df_consolidado["Almacén"].fillna(
            "").astype(str).str.strip().isin(almacenes_str)
        df_consolidado = df_consolidado[mask].copy()

        print(
            f"[OK] Filtrado por almacén(es) {almacenes_str}. Filas resultantes: {len(df_consolidado)}")
    # 4. EXPORTAR A EXCEL (.xlsx)
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(salida_unicos_excel), exist_ok=True)

    with pd.ExcelWriter(salida_unicos_excel, engine='openpyxl') as writer:
        df_consolidado.to_excel(
            writer, sheet_name='Stock_Bodega_Filtrado', index=False)

    print(
        f"[ÉXITO] Archivo Excel generado en: {os.path.abspath(salida_unicos_excel)}")

    return df_consolidado

def insertar_bodegas_productivas():
    """
    Inserta la lista de almacenes/bodegas permitidos en la tabla bodegas_productivas.
    """
    bodegas = ['1032', '1029', '1030', '1027', '1003', '1018', '1010', '1001', '1014']
    
    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='calculadora_pv'
    )
    
    try:
        with conexion.cursor() as cursor:
            # INSERT IGNORE evita errores si el código de bodega ya existe
            sql = "INSERT IGNORE INTO `bodegas_productivas` (`Codigo`) VALUES (%s)"
            
            # Formatear la lista para executemany como lista de tuplas [(cod,), ...]
            datos = [(b,) for b in bodegas]
            
            cursor.executemany(sql, datos)
            filas_insertadas = cursor.rowcount
            
        conexion.commit()
        print(f"[OK] Proceso completado: {filas_insertadas} bodegas agregadas.")
        
    except Exception as e:
        print(f"[ERROR] Error al insertar bodegas: {e}")
        conexion.rollback()
    finally:
        conexion.close()

archivo_trabajo = salida_unicos_excel
# Ajusta el usuario, contraseña y puerto según tu configuración de XAMPP
USER_DB = "root"
PASSWORD_DB = ""  # Por defecto en XAMPP la clave viene vacía
HOST_DB = "localhost"
PORT_DB = "3306"
NOMBRE_DB = "calculadora_pv"

# URL de conexión SQLAlchemy
cadena_conexion = f"mysql+pymysql://{USER_DB}:{PASSWORD_DB}@{HOST_DB}:{PORT_DB}/{NOMBRE_DB}"


def guardar_en_mysql_bodegas():
    """Carga los DataFrames y los guarda como tablas en MySQL."""
    print("Iniciando conexión con MySQL (XAMPP)...")
    engine = create_engine(cadena_conexion)

    # 1. Cargar DataFrames
    print("Leyendo archivos Excel...")
    df_bodega = pd.read_excel(archivo_trabajo, dtype=str) if archivo_trabajo.exists() else None

    # 2. Insertar en MySQL
    with engine.begin() as conn:
        if df_bodega is not None:
            df_bodega.to_sql("maestro_bodegas", con=conn, if_exists="replace", index=False)
            print("  -> Tabla 'pedidos_pendientes_todos' guardada en MySQL.")


    print("¡Persistencia en MySQL completada con éxito!\n")
    return df_bodega

    '''
# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":

    session = saplogin()

    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "MB52"
    session.findById("wnd[0]").sendVKey(0)


# 2. Obtener la lista completa de 335 materiales
    materiales = obtener_materiales_bodega()
    total = len(materiales)
    tamano_bloque = 50

    print(f"Total de materiales a procesar: {total}")

    # 3. Iterar en lotes de 50 en 50 (Generará 7 bloques)
    for i in range(0, total, tamano_bloque):
        bloque = materiales[i : i + tamano_bloque]
        num_bloque = (i // tamano_bloque) + 1

        # Copiar solo el bloque actual de 50 elementos al portapapeles
        texto_portapapeles = "\r\n".join(bloque)
        pyperclip.copy(texto_portapapeles)

        nombre_archivo_lote = f"BOD_{num_bloque:03d}.XLS"
        print(
            f"Procesando lote {num_bloque:03d} de {len(bloque)} OFs -> {nombre_archivo_lote}"
        )

        print(f"\n[Bloque {num_bloque}] Procesando materiales del {i + 1} al {min(i + tamano_bloque, total)}...")

        # Ejecutar la extracción en SAP para este bloque
        procesar_bodega(session, nombre_archivo_lote, base_bodega)

        time.sleep(2) # Pausa de estabilización entre iteraciones
    

    # Obtener la lista de almacenes permitidos desde la base de datos
    almacenes_permitidos = obtener_almacenes_permitidos()

    print(f"Almacenes permitidos: {almacenes_permitidos}")

    procesar_excel_productivo_1(carpeta_origen=base_bodega,  # Se pasa la carpeta con los .XLS de Bodega
                                # Llamar a la función con la lista de almacenes permitidos
                                salida_unicos_excel=salida_unicos_excel, 
    
    guardar_en_mysql()
    '''