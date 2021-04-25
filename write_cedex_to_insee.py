import json

path_in = "data/input/correspondance-code-cedex-code-insee.json"
path_out = "data/input/cedex_to_insee.json"

data = json.load(open(path_in))

dict_cedex_to_insee = {
    datum["fields"]["code"]: {
        "insee": datum["fields"]["insee"],
        "ville": datum["fields"].get("nom_com"),
        "nom": datum["fields"].get("nom_epci"),
    } for datum in data if "insee" in datum["fields"]}


dict_cedex_to_insee = {k: dict_cedex_to_insee[k] for k in sorted(dict_cedex_to_insee)}

json_out = json.dumps(dict_cedex_to_insee, indent=2)

with open(path_out, "w") as f:
    f.write(json_out)
