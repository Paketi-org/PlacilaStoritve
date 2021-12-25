import requests

BASE = "http://172.25.1.5:5002/"

r1 = requests.get(BASE + "/placila")
print(r1.json())

'''
r4 = requests.post(BASE + "/placila", {"id": 1, "id_placnika": 2, "id_prejemnika": 3, "status": "neplacano"})
#print(r4.json())

r3 = requests.get(BASE + "/placila")
print(r3.json())

r4 = requests.delete(BASE + "/placila/1")
#print(r4.json())

r3 = requests.get(BASE + "/placila")
print(r3.json())

r4 = requests.post(BASE + "/placila", {"id": 1, "id_placnika": 2, "id_prejemnika": 3, "status": "placano"})
r4 = requests.post(BASE + "/placila", {"id": 2, "id_placnika": 2, "id_prejemnika": 3, "status": "neplacano"})

r3 = requests.get(BASE + "/placila")
print(r3.json())

r4 = requests.delete(BASE + "/placila/1")

r3 = requests.get(BASE + "/placila")
print(r3.json())

r6 = requests.get(BASE + "/placila/2")
print(r6.json())
'''
