import os
import pandas as pd
from pathlib import Path

# --- RUTAS DE TRABAJO ---
base_dir = Path(r"C:\xampp\htdocs\Calculadora_PV/PV")
carpeta_lotes = base_dir / "BOM"
salida_bom = base_dir / "BASE_BOM.xlsx"
archivo_bom_filtrada = base_dir / "BASE_BOM_FILTRADA.xlsx"

def filtrar_columnas_bom():
    if not salida_bom.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo origen: {salida_bom}"
        )

    print(f"Leyendo archivo consolidado: {salida_bom.name}...")
    df_bom = pd.read_excel(salida_bom, dtype=str)

    # Limpiar espacios en los nombres de las columnas
    df_bom.columns = df_bom.columns.astype(str).str.strip()

    print("\nColumnas disponibles en el archivo cargado:")
    print(list(df_bom.columns))

    # Mapeo flexible para asegurar captura de Cantidad y UMB
    alias_columnas = {
        "Material": "Material",
        "Texto breve de material": "Texto breve de material",
        "Nivel Explosión": "Nivel Explosión",
        "Pos.": "Pos.",
        "N° Componentes": "N° Componentes",
        "Desc. Componente": "Desc. Componente",
        "Cantidad": [c for c in df_bom.columns if "Cantidad" in c][0]
        if any("Cantidad" in c for c in df_bom.columns)
        else "Cantidad",
        "UMB": [c for c in df_bom.columns if "UMB" in c][0]
        if any("UMB" in c for c in df_bom.columns)
        else "UMB",
        "Ce.": [c for c in df_bom.columns if "Ce." in c][0]
        if any("Ce." in c for c in df_bom.columns)
        else "Ce.",
        "Alm.": [c for c in df_bom.columns if "Alm." in c][0]
        if any("Alm." in c for c in df_bom.columns)
        else "Alm.",
        
    }

    # Filtrar solo las columnas existentes
    cols_existentes = [
        col for col in alias_columnas.values() if col in df_bom.columns
    ]

    if not cols_existentes:
        raise ValueError(
            "No se pudieron hacer coincidir las columnas solicitadas."
        )

    df_filtrado = df_bom[cols_existentes].copy()

    # Renombrar a los nombres estándar finales
    renombres = {v: k for k, v in alias_columnas.items() if v in df_bom.columns}
    df_filtrado.rename(columns=renombres, inplace=True)

    # Limpieza de espacios en celdas de datos
    for col in df_filtrado.columns:
        df_filtrado[col] = df_filtrado[col].fillna("").astype(str).str.strip()

    # Guardar archivo filtrado definitivo
    df_filtrado.to_excel(archivo_bom_filtrada, index=False)

    print("\n==================================================")
    print(
        f"¡ÉXITO! Se filtraron las {len(df_filtrado.columns)} columnas requeridas con {len(df_filtrado)} registros."
    )
    print("Columnas finales en el archivo:")
    print(list(df_filtrado.columns))
    print(f"\nArchivo final guardado en:\n{salida_bom}")
    print("==================================================")

def detectar_encabezado_y_codificacion(ruta_archivo):
    """Prueba codificaciones para hallar la fila donde comienza la tabla del BOM."""
    codificaciones = ["utf-16", "latin1", "utf-8", "cp1252"]
    
    for enc in codificaciones:
        try:
            with open(ruta_archivo, "r", encoding=enc, errors="ignore") as f:
                for i, line in enumerate(f):
                    # Buscamos 'Material' y algún otro campo característico de la BOM
                    if "Material" in line and ("Cantidad" in line or "Pos" in line or "UMB" in line):
                        return i, enc
        except Exception:
            continue
            
    return None, None


def cargar_archivo_bom_lote(ruta_archivo):
    """Lee un lote individual de BOM detectando dinámicamente su formato."""
    
    header_row, encoding_detectado = detectar_encabezado_y_codificacion(ruta_archivo)

    if header_row is None:
        return None

    try:
        df = pd.read_csv(
            ruta_archivo,
            sep="\t",
            encoding=encoding_detectado,
            skiprows=header_row,
            engine="python",
            on_bad_lines="skip",
            dtype=str
        )

        # Limpiar espacios en blanco de nombres de columnas
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception as e:
        print(f"  [Error al leer {ruta_archivo.name}]: {e}")
        return None


def procesar_todos_los_lotes_bom():
    if not carpeta_lotes.exists():
        raise FileNotFoundError(f"No existe la carpeta de descargas: {carpeta_lotes}")

    # Buscar tanto BOM_*.XLS como MATERIALES_LOTE_*.XLS
    archivos_lotes = sorted(list(carpeta_lotes.glob("*.XLS")) + list(carpeta_lotes.glob("*.xls")))

    if not archivos_lotes:
        raise FileNotFoundError(f"No se encontraron archivos .XLS en {carpeta_lotes}")

    dataframes_lotes = []

    for archivo in archivos_lotes:
        print(f"Procesando: {archivo.name}...")
        df_lote = cargar_archivo_bom_lote(archivo)

        if df_lote is None or df_lote.empty:
            print(f"  [Omitido] No se hallaron encabezados válidos en {archivo.name}")
            continue

        # Filtrar solo columnas válidas que contengan datos reales (excluir columnas vacías creadas por tabuladores extra)
        cols_validas = [c for c in df_lote.columns if c and not c.startswith("Unnamed")]
        df_filtrado = df_lote[cols_validas].copy()

        dataframes_lotes.append(df_filtrado)

    if not dataframes_lotes:
        raise Exception("No se pudo extraer información válida de ningún lote.")

    # Consolidar todos los DataFrames
    base_bom = pd.concat(dataframes_lotes, ignore_index=True)

    # Limpiar espacios en blanco de todas las celdas
    for col in base_bom.columns:
        base_bom[col] = base_bom[col].astype(str).str.strip()

    # Eliminar filas repetidas que coincidan con la fila de encabezados
    primer_col = base_bom.columns[0]
    base_bom = base_bom[base_bom[primer_col] != primer_col].copy()

    # Guardar BASE_BOM.xlsx
    base_bom.to_excel(salida_bom, index=False)

    print("\n==================================================")
    print(f"¡ÉXITO! BASE_BOM generada con {len(base_bom)} filas de componentes.")
    print(f"Columnas detectadas en la BASE_BOM:")
    print(list(base_bom.columns[:10]))  # Muestra las primeras 10 columnas
    print(f"Archivo guardado en: {salida_bom}")
    print("==================================================")
    filtrar_columnas_bom()

if __name__ == "__main__":
    try:
        procesar_todos_los_lotes_bom()
    except Exception as e:
        print(f"\n[ERROR]: {e}")