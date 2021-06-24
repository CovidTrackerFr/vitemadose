import requests
import pyperclip

headers_mesoigner = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": 'Mesoigner apikey="m5pi0XJmMSGbSiYQpl5SBvHm0bPrScGy"',
}

r = requests.get("https://www.mesoigner.fr/api/v1/vaccination/centers/1722/2021-06-16", headers=headers_mesoigner)
print(r.json())
