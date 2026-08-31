from pathlib import Path
import pandas as pd

# --- RUTAS DE TRABAJO ---
base_dir = Path(r"C:\xampp\htdocs\Calculadora_PV\PV")
archivo_productiva = base_dir / "BASE_PRODUCTIVA.xlsx"
archivo_bom = base_dir / "BASE_BOM.xlsx"
archivo_salida = base_dir / "BASE_PRODUCTIVA_BOM.xlsx"


def a_numero(val):
    """Convierte cadenas de texto numéricas de SAP (con coma o punto) a float."""
    if not val or str(val).lower() == "nan":
        return 0.0
    val_clean = str(val).strip()
    if "," in val_clean:
        val_clean = val_clean.replace(".", "").replace(",", ".")
    try:
        return float(val_clean)
    except ValueError:
        return 0.0


def vincular_bases():
    if not archivo_productiva.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo_productiva}")
    if not archivo_bom.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo_bom}")

    print("Cargando BASE_PRODUCTIVA y BASE_BOM...")
    df_prod = pd.read_excel(archivo_productiva, dtype=str)
    df_bom = pd.read_excel(archivo_bom, dtype=str)

    # 1. Limpieza de nombres de columnas
    df_prod.columns = df_prod.columns.astype(str).str.strip()
    df_bom.columns = df_bom.columns.astype(str).str.strip()

    # Rellenar nulos
    for col in df_prod.columns:
        df_prod[col] = df_prod[col].fillna("").astype(str).str.strip()
    for col in df_bom.columns:
        df_bom[col] = df_bom[col].fillna("").astype(str).str.strip()

    # Depurar duplicados en BASE_PRODUCTIVA
    subset_prod = [c for c in ["Pedido", "PosPed", "Material"] if c in df_prod.columns]
    if subset_prod:
        df_prod.drop_duplicates(subset=subset_prod, keep="first", inplace=True)

    # Depurar duplicados en BASE_BOM (BÚSQUEDA SEGURA DE COLUMNAS EXISTENTES)
    columnas_posibles_bom = ["Material", "N° Componentes", "Componente", "Nivel Explosión", "Pos.", "PosBOM"]
    subset_bom = [c for c in columnas_posibles_bom if c in df_bom.columns]
    
    # Solo ejecutar drop_duplicates si encontró al menos una columna válida
    if subset_bom:
        df_bom.drop_duplicates(subset=subset_bom, keep="first", inplace=True)

    # 2. Conversión a formato numérico
    col_cant_ped = "Ctd.ped." if "Ctd.ped." in df_prod.columns else "CtdPed"
    df_prod["Ctd_Ped_Num"] = df_prod[col_cant_ped].apply(a_numero) if col_cant_ped in df_prod.columns else 1.0

    col_cant_bom = "Cantidad" if "Cantidad" in df_bom.columns else "CantidadBOM"
    df_bom["Cantidad_BOM_Num"] = df_bom[col_cant_bom].apply(a_numero) if col_cant_bom in df_bom.columns else 1.0

    # 3. Cruce/Merge por el Código SAP de Material
    print("Realizando el cruce entre BASE_PRODUCTIVA y BASE_BOM...")
    df_cruce = pd.merge(
        df_prod, df_bom, on="Material", how="inner", suffixes=("_PD", "_BOM")
    )

    # 4. Restauración de la columna 'Origen' (Convenio de Precio)
    if "Origen_PD" in df_cruce.columns:
        df_cruce["Origen"] = df_cruce["Origen_PD"]
    elif "ConvenioPrecio_PD" in df_cruce.columns:
        df_cruce["Origen"] = df_cruce["ConvenioPrecio_PD"]

    # 5. Cálculo: Cantidad Total Requerida
    df_cruce["Cantidad_Total_Requerida"] = (
        df_cruce["Ctd_Ped_Num"] * df_cruce["Cantidad_BOM_Num"]
    ).round(4)

    # Clean aux
    df_cruce.drop(columns=["Ctd_Ped_Num", "Cantidad_BOM_Num"], inplace=True, errors="ignore")

    # 6. Depuración final segura
    subset_final = [c for c in ["Pedido", "PosPed", "Material", "N° Componentes", "Nivel Explosión", "Origen"] if c in df_cruce.columns]
    if subset_final:
        df_cruce.drop_duplicates(subset=subset_final, keep="first", inplace=True)

    # Guardar
    df_cruce.to_excel(archivo_salida, index=False)
    
    print("\n==================================================")
    print(f"¡ÉXITO! Vinculación completada. Se generaron {len(df_cruce)} filas cruzadas.")
    print(f"Archivo resultante guardado en: {archivo_salida}")
    print("==================================================")

if __name__ == "__main__":
    try:
        vincular_bases()
    except Exception as e:
        print(f"\n[ERROR]: {e}")