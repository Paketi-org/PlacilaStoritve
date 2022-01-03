import json
import unittest
import requests

class TestAPI(unittest.TestCase):

    def setUp(self):
        self.placila = "http://localhost:5002/"
        self.maxDiff = None

    def test_1_post_placila(self):
        resp = requests.post(self.placila + "/placila", {"id": 1, "id_placnika": 2, "id_prejemnika": 3, "znesek_eur": "10.00", "status": "neplacano"})
        self.assertEqual(resp.status_code, 201)

    def test_2_put_placila(self):
        resp = requests.put(self.placila + "/placila/1", {"atribut": "status", "vrednost": "placano"})
        self.assertEqual(resp.status_code, 200)

    def test_3_delete_placilo(self):
        resp = requests.delete(self.placila + "/placila/1")
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
