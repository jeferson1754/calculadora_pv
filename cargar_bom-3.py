
import win32com.client
import sys
import subprocess
import time
import config_sap
import io
import pandas as pd
import os
import pyperclip
from sqlalchemy import create_engine
from pathlib import Path

# Convertir la ruta a un objeto Path
base_dir = Path(r"C:\xampp\htdocs\Calculadora_PV\PV")
base_bom = Path(r"C:\xampp\htdocs\Calculadora_PV\BOM")

# Ahora el operador / funciona perfectamente
archivo_txt = base_dir / "CODIGOS_SAP_UNICOS.txt"
archivo_xlsx = base_dir / "CODIGOS_SAP_UNICOS.xlsx"



def dividir_lista(lista, tamano_lote):
    """Generador para dividir una lista en sublistas de un tamaño determinado."""
    for i in range(0, len(lista), tamano_lote):
        yield lista[i : i + tamano_lote]

def obtener_codigos_unicos():
    """Lee los códigos SAP únicos desde el TXT, Excel o BASE_PRODUCTIVA."""

    # 1. Intentar desde el TXT
    if archivo_txt.exists():
        with open(archivo_txt, "r", encoding="utf-8") as f:
            codigos = [
                linea.strip()
                for linea in f
                if linea.strip() and not linea.strip().startswith("#")
            ]
        return list(dict.fromkeys(codigos))

    # 2. Intentar desde el Excel de únicos
    if archivo_xlsx.exists():
        df = pd.read_excel(archivo_xlsx, dtype=str)
        col = df.columns[0]
        codigos = df[col].dropna().astype(str).str.strip().tolist()
        return list(dict.fromkeys(codigos))

    raise FileNotFoundError(
        "No se encontró ningún archivo de códigos SAP únicos."
    )


def saplogin():
    try:
        path = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"
        subprocess.Popen(path)
        time.sleep(1)
        SapGuiAuto = win32com.client.GetObject('SAPGUI')
        if not type(SapGuiAuto) == win32com.client.CDispatch:
            return

        application = SapGuiAuto.GetScriptingEngine
        if not type(application) == win32com.client.CDispatch:
            SapGuiAuto = None
            return

        # connection = application.OpenConnection("PRD [REVESOL]",True)
        connection = application.OpenConnection("SR  [SAP ROUTER]", True)
        session = connection.Children(0)
        if not type(session) == win32com.client.CDispatch:
            connection = None
            application = None
            SapGuiAuto = None
            return
    
    except:
        print(sys.exc_info())
        print(4)

    session.findById("wnd[0]/usr/txtRSYST-BNAME").text = config_sap.username
    session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = config_sap.password
    session.findById("wnd[0]").sendVKey(0)
    session.findById("wnd[0]").sendVKey(0)
    # session.findById("wnd[0]").resizeWorkingPane(98,16,False)
    return session




# --- EJECUCIÓN CORREGIDA PARA SAP ---
def procesar_descarga_por_lotes(session):
    # Límite por lote para el portapapeles de SAP GUI
    CANTIDAD_CODIGOS = 10

    """Obtiene los códigos únicos y los procesa en lotes de 60 hacia SAP GUI."""

    lista_of_madres = obtener_codigos_unicos()
    total_codigos = len(lista_of_madres)

    if not total_codigos:
        print("ADVERTENCIA: La lista de códigos está vacía.")
        return

    print(f"\nTotal de códigos a procesar: {total_codigos}")
    print(f"Tamaño de lote configurado: {CANTIDAD_CODIGOS}")
    print("--------------------------------------------------")
        

    for numero_lote, lote in enumerate(
        dividir_lista(lista_of_madres, CANTIDAD_CODIGOS), start=1
    ):
        
        texto_portapapeles = "\r\n".join(str(total_codigos).strip() for total_codigos in lote)

        # Copiar al portapapeles de Windows
        pyperclip.copy(texto_portapapeles)

        nombre_archivo_lote = f"BOM_{numero_lote:03d}.XLS"
        print(
            f"Procesando lote {numero_lote:03d} de {len(lote)} OFs -> {nombre_archivo_lote}"
        )

        
        # ENTRAMOS A LA TRANSACCIÓN
        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/tbar[0]/okcd").text = "ZMM_0002"
        session.findById("wnd[0]").sendVKey(0)

        # Llamar a la función que interactúa con la sesión de SAP GUI
        descargar_materiales(
            texto_ofs=texto_portapapeles,
            path=str(base_bom),
            session=session,
            nombre_archivo=nombre_archivo_lote,
        )
    



def descargar_materiales(texto_ofs, path, session, nombre_archivo):


    # INGRESA A LA LISTA PARA COPIAR LAS OFS y SALIR DE LA LISTA
    session.findById("wnd[0]/usr/btn%_S_MATNR_%_APP_%-VALU_PUSH").press()
    session.findById("wnd[1]/tbar[0]/btn[24]").press()
    session.findById("wnd[1]/tbar[0]/btn[8]").press()
    time.sleep(5)
    session.findById("wnd[0]/tbar[1]/btn[8]").press()
    time.sleep(5)

    print(f"Se procede a descargar la OF {nombre_archivo}")
    session.findById("wnd[0]").maximize
    session.findById("wnd[0]/tbar[1]/btn[45]").press()

    session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]").selected = True
    session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]").setFocus

    session.findById("wnd[1]/tbar[0]/btn[0]").press()


    #GUARDADO DE ARCHIVO
    session.findById("wnd[1]/usr/ctxtDY_PATH").text = path
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = nombre_archivo
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = 1
    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    session.findById("wnd[0]/tbar[0]/btn[3]").press()




# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    # Asegúrate de pasar tu objeto 'session' activo de SAP GUI
    session_sap = saplogin()
    procesar_descarga_por_lotes(session_sap)
    pass