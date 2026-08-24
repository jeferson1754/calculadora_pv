import requests

url = "https://valindprd.valvulasindustriales.com:8443/sap/bc/rest/comex/oc/cabcab?sap-client=300"

datos = {
    "Pedido": "123456",
    "Material": "ABC123"
}

respuesta = requests.get(
    url,
    json=datos,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json"
    },
    timeout=30
)

print("HTTP:", respuesta.status_code)
print(respuesta.text)