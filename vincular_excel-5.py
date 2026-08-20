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

    # 1. Limpieza de nombres de columnas y celdas
    df_prod.columns = df_prod.columns.str.strip()
    df_bom.columns = df_bom.columns.str.strip()

    for col in df_prod.columns:
        df_prod[col] = df_prod[col].fillna("").astype(str).str.strip()
    for col in df_bom.columns:
        df_bom[col] = df_bom[col].fillna("").astype(str).str.strip()

    df_prod.drop_duplicates(
        subset=["Pedido", "PosPed", "Material"], keep="first", inplace=True
    )

    # Eliminar duplicados en BASE_BOM por Producto Padre + Componente + Nivel + Posición BOM
    subset_bom = [
        c
        for c in ["Material", "N° Componentes", "Componente", "Nivel Explosión", "Pos."]
        if c in df_bom.columns
    ]
    df_bom.drop_duplicates(subset=subset_bom, keep="first", inplace=True)

    # 2. Conversión a formato numérico para poder multiplicar
    df_prod["Ctd_Ped_Num"] = df_prod["Ctd.ped."].apply(a_numero)
    df_bom["Cantidad_BOM_Num"] = df_bom["Cantidad"].apply(a_numero)

    # 3. Cruce/Merge por el Código SAP de Material
    # BASE_PRODUCTIVA (Material) <---> BASE_BOM (Material)
    print("Realizando el cruce entre BASE_PRODUCTIVA y BASE_BOM...")
    df_cruce = pd.merge(
        df_prod, df_bom, on="Material", how="inner", suffixes=("_PD", "_BOM")
    )

    # 4. Cálculo: Cantidad Total Requerida del Componente por Pedido
    # Cantidad Total = (Cantidad Pedida del Producto) * (Cantidad Unitaria del Componente en BOM)
    df_cruce["Cantidad_Total_Requerida"] = (
        df_cruce["Ctd_Ped_Num"] * df_cruce["Cantidad_BOM_Num"]
    ).round(4)

    # 5. Eliminar columnas auxiliares numéricas
    df_cruce.drop(columns=["Ctd_Ped_Num", "Cantidad_BOM_Num"], inplace=True)

    # DEPURACIÓN FINAL EN LA BASE VINCULADA
    subset_final = ["Pedido", "PosPed", "Material", "N° Componentes", "Nivel Explosión"]
    subset_existentes = [c for c in subset_final if c in df_cruce.columns]
    df_cruce.drop_duplicates(subset=subset_existentes, keep="first", inplace=True)

    # Guardar
    df_cruce.to_excel(archivo_salida, index=False)
    print(f"¡Éxito! Archivo guardado con {len(df_cruce)} filas únicas en:\n{archivo_salida}")

    print("\n==================================================")
    print(
        f"¡ÉXITO! Vinculación completada. Se generaron {len(df_cruce)} filas cruzadas."
    )
    print(f"Archivo resultante guardado en: {archivo_salida}")
    print("==================================================")


if __name__ == "__main__":
    try:
        vincular_bases()
    except Exception as e:
        print(f"\n[ERROR]: {e}")