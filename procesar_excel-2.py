from pathlib import Path
import pandas as pd

# --- RUTAS DE TRABAJO ---
base_dir = Path(r"C:\xampp\htdocs\Calculadora_PV\PV")
archivo_origen = base_dir / "BASE_PEDIDOS_ORIGINAL.XLS"

salida_trabajo = base_dir / "BASE_TRABAJO.xlsx"
salida_revision_37 = base_dir / "BASE_REVISION_37.xlsx"
salida_productiva = base_dir / "BASE_PRODUCTIVA.xlsx"
salida_unicos_txt = base_dir / "CODIGOS_SAP_UNICOS.txt"
salida_unicos_excel = base_dir / "CODIGOS_SAP_UNICOS.xlsx"

columnas_requeridas = [
    "Nombre",
    "Pedido",
    "PosPed",
    "Valor neto",
    "Mon.",
    "Ctd.ped.",
    "Material",
    "Fecha Probable",
]

# 1. Encontrar la fila de encabezados
header_row = None
with open(archivo_origen, "r", encoding="utf-16", errors="ignore") as f:
    for i, line in enumerate(f):
        if "Nombre" in line and "Pedido" in line:
            header_row = i
            break

if header_row is None:
    raise ValueError(
        "No se pudo detectar la fila de encabezados en el archivo."
    )

# 2. Leer el CSV
df = pd.read_csv(
    archivo_origen,
    sep="\t",
    encoding="utf-16",
    skiprows=header_row,
    engine="python",
    on_bad_lines="skip",
    dtype=str,
)

# Limpiar nombres de columnas
df.columns = df.columns.str.strip()


# 3. Función de limpieza estricta
def limpiar_texto(val):
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    return val_str


# Aplicar limpieza a todas las columnas
for col in df.columns:
    df[col] = df[col].apply(limpiar_texto)

df_trabajo = df[columnas_requeridas].copy()

# Guardar BASE_TRABAJO (Aquí SÍ se repiten los materiales porque son múltiples pedidos)
df_trabajo.to_excel(salida_trabajo, index=False)

# =========================================================================
# SEPARACIÓN DE MATERIALES 37xx
# =========================================================================
es_37 = df_trabajo["Material"].str.startswith("37")

base_revision_37 = df_trabajo[es_37].copy()
base_productiva = df_trabajo[~es_37].copy()

base_revision_37["Estado"] = "REVISIÓN MATERIAL 37"
base_productiva["Estado"] = "PRODUCTIVO"

# Guardar bases de pedidos (Aquí SÍ se repiten los materiales)
base_revision_37.to_excel(salida_revision_37, index=False)
base_productiva.to_excel(salida_productiva, index=False)

# =========================================================================
# OBTENCIÓN DE LA LISTA DE CÓDIGOS SAP ÚNICOS (SIN REPETIDOS)
# =========================================================================
# Extraemos la serie de materiales, quitamos vacíos y eliminamos duplicados
codigos_unicos_series = (
    base_productiva["Material"]
    .replace("", pd.NA)
    .dropna()
    .drop_duplicates()
    .sort_values()
)

# Convertir a lista de Python
codigos_sap_unicos = codigos_unicos_series.tolist()

# Opción A: Guardar en archivo TXT (Ideal para copiar y pegar en SAP ZMM_0002)
with open(salida_unicos_txt, "w", encoding="utf-8") as f:
    for codigo in codigos_sap_unicos:
        f.write(f"{codigo}\n")

# Opción B: Guardar en Excel de códigos únicos sin duplicados
df_unicos = pd.DataFrame({"Material_Unico": codigos_sap_unicos})
df_unicos.to_excel(salida_unicos_excel, index=False)

print("\n--- RESUMEN DE PROCESAMIENTO ---")
print(f"1. Total registros en BASE_TRABAJO: {len(df_trabajo)}")
print(f"2. Total registros en BASE_PRODUCTIVA: {len(base_productiva)}")
print(
    f"3. CÓDIGOS ÚNICOS PARA ZMM_0002: {len(codigos_sap_unicos)} (¡Sin duplicados!)"
)
print(f"\nArchivo TXT listo para SAP: {salida_unicos_txt}")
print(f"Archivo Excel de únicos: {salida_unicos_excel}")