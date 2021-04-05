import json
import pandas as pd
from departements import to_departement_number, import_departements
import matplotlib.pyplot as plt
import numpy as np

def my_fmt(x):
    print(x)
    return '{:.4f}%\n({:.0f})'.format(x, total*x/100)



centre_disponibles = pd.DataFrame()
centres_indisponibles = pd.DataFrame()
centres_all = pd.DataFrame()

for code in import_departements():
    data = open(f'data/output/{code}.json', 'r')
    data_json = json.load(data)
    centre_disponibles = centre_disponibles.append(
        pd.DataFrame.from_dict(data_json["centres_disponibles"]))
    centres_indisponibles = centres_indisponibles.append(
        pd.DataFrame.from_dict(data_json["centres_indisponibles"]))
    data.close()

centres_all = pd.concat([centre_disponibles, centres_indisponibles])




centres_all['prochain_rdv'] = centres_all['prochain_rdv'].apply(
    lambda x: "Disponibles" if not pd.isnull(x) else "Indisponibles")

total = centres_all['prochain_rdv'].count()
print(total)

centres_all['prochain_rdv'].value_counts().plot(
    kind='pie', autopct=my_fmt, title='Centre disponibles')

plt.show()
