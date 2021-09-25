import json

f = open("C:\\Users\\Shane\\Documents\\GitHub\\dogepush\\id.json","r")
a = json.load(f)
print(a["api"])

