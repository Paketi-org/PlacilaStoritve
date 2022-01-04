from flask import Flask
from flask_restx import Resource, Api, fields, reqparse, abort, marshal, marshal_with
import logging
import subprocess
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics
from fluent import handler
import os
import json
import grpc
import unary_pb2_grpc as pb2_grpc
import unary_pb2 as pb2
import socket

app = Flask(__name__)

# Load configurations from the config file
def load_configurations():
    app.config.from_file('config.json', load=json.load)

    with open('config.json') as json_file:
        data = json.load(json_file)
        # Override variables defined in the environment over the ones from the config file
        for item in data:
            if os.environ.get(item):
                app.config[item] = os.environ.get(item)

load_configurations()


@app.route("/")
def welcome():
    return "Welcome!"

custom_format = {
  'name': '%(name_of_service)s',
  'method': '%(crud_method)s',
  'traffic': '%(directions)s',
  'ip': '%(ip_node)s',
  'status': '%(status)s',
  'code': '%(http_code)s',
}
logging.basicConfig(level=logging.INFO)
l = logging.getLogger('Placila')
h = handler.FluentHandler('Placila', host=app.config["FLUENT_IP"], port=int(app.config["FLUENT_PORT"]))
formatter = handler.FluentRecordFormatter(custom_format)
h.setFormatter(formatter)
l.addHandler(h)
l.info("Pripravljanje Placila Mikrostoritve", extra={"name_of_service": "Placila", "crud_method": None, "directions": None, "ip_node": None, "status": None, "http_code": None})

api = Api(app, version='1.0', doc='/placila/openapi', title='Placila API', description='Abstrakt Placila API',default_swagger_filename='openapi.json', default='Placila CRUD', default_label='koncne tocke in operacije')
placiloApiModel = api.model('ModelPlacila', {
    "id": fields.Integer(readonly=True, description='ID placila'),
    "id_placnika": fields.Integer(readonly=True, description='ID placnika placila'),
    "id_prejemnika": fields.Integer(readonly=True, description='ID prejemnika placila'),
    "znesek_eur": fields.String(readonly=True, description='Znesek placila v EUR'),
    "znesek_coin": fields.String(readonly=True, description='Znesek placila v bitcoin'),
    "status": fields.String(readonly=True, description='Status placila')
})
placilaApiModel = api.model('ModelPlacil', {"placila": fields.List(fields.Nested(placiloApiModel))})
ns = api.namespace('Placila CRUD', description='Placila koncne tocke in operacije')
posodobiModel = api.model('PosodobiPlacilo', {
    "atribut": fields.String,
    "vrednost": fields.String
})
metrics = PrometheusMetrics(app)

grpc_channel = grpc.insecure_channel('{}:{}'.format(app.config["GRPC_SERVER_IP"], app.config["GRPC_SERVER_PORT"]))
stub = pb2_grpc.convertToCryptoStub(grpc_channel)

def get_bitcoins(eur):
    """
    Client function to call the rpc for GetServerResponse
    """
    message = pb2.Message(message=eur)
    print(f'Sent request to convert {message} to bitcoins')
    return stub.convertToBitcoin(message)

def connect_to_database():
    return pg.connect(database=app.config["PGDATABASE"], user=app.config["PGUSER"], password=app.config["PGPASSWORD"],
                      port=app.config["DATABASE_PORT"], host=app.config["DATABASE_IP"])

def check_database_connection():
    conn = connect_to_database()
    if conn.poll() == extensions.POLL_OK:
        print ("POLL: POLL_OK")
    elif conn.poll() == extensions.POLL_READ:
        print ("POLL: POLL_READ")
    elif conn.poll() == extensions.POLL_WRITE:
        print ("POLL: POLL_WRITE")
    else:
        return 409
    return 200

def application_data():
    return {"maintainer": "Teodor Janez Podobnik",
            "git_repo": "https://github.com/Paketi-org/PlacilaStoritve.git"}

class PlaciloModel:
    def __init__(self, id, id_placnika, id_prejemnika, znesek_eur, znesek_coin, status):
        self.id = id
        self.id_placnika = id_placnika
        self.id_prejemnika = id_prejemnika
        self. znesek_eur = znesek_eur
        self. znesek_coin = znesek_coin
        self.status = status

placilaPolja = {
    "id": fields.Integer,
    "id_placnika": fields.Integer,
    "id_prejemnika": fields.Integer,
    "znesek_eur": fields.String,
    "znesek_coin": fields.String,
    "status": fields.String,
}

class Placilo(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = 'placila'
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("id_placnika", type=int)
        self.parser.add_argument("id_prejemnika", type=int)
        self.parser.add_argument("znesek_eur", type=str)
        self.parser.add_argument("znesek_coin", type=str)
        self.parser.add_argument("status", type=str)
        self.parser.add_argument("atribut", type=str)
        self.parser.add_argument("vrednost", type=str)

        super(Placilo, self).__init__(*args, **kwargs)

    @marshal_with(placiloApiModel)
    @ns.response(404, 'Placilo ni najden')
    @ns.doc("Vrni placilo")
    def get(self, id):
        """
        Vrni podatke placila glede na ID
        """
        l.info("Zahtevaj placilo z ID %s" % str(id), extra={"name_of_service": "Placila", "crud_method": "get", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            l.warning("Placilo z ID %s ni bil najden" % str(id), extra={"name_of_service": "Placila", "crud_method": "get", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "fail", "http_code": 404})

            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        placilo = PlaciloModel(
            id = d["id"],
            id_placnika = d["id_placnika"],
            id_prejemnika = d["id_prejemnika"],
            znesek_eur = d["znesek_eur"],
            znesek_coin = d["znesek_coin"], 
            status = d["status"].strip())

        l.info("Vrni placilo z ID %s" % str(id), extra={"name_of_service": "Placila", "crud_method": "get", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": 200})
        return placilo, 200

    @marshal_with(placiloApiModel)
    @ns.expect(posodobiModel)
    @ns.response(404, 'Placilo ni najden')
    @ns.doc("Vrni placilo")
    def put(self, id):
        """
        Posodobi podatke placila glede na ID
        """
        l.info("Posodobi placilo z ID %s" % str(id), extra={"name_of_service": "Placila", "crud_method": "put", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute("""UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(self.table_name, attribute, value, id))
        self.conn.commit()

        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            l.warning("Placilo z ID %s ni bil najden" % str(id), extra={"name_of_service": "Placila", "crud_method": "put", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "fail", "http_code": 404})
            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        placilo = PlaciloModel(
            id = d["id"],
            id_placnika = d["id_placnika"],
            id_prejemnika = d["id_prejemnika"],
            znesek_eur = d["znesek_eur"],
            znesek_coin = d["znesek_coin"],
            status = d["status"].strip())

        l.info("Placilo z ID %s posodobljeno" % str(id), extra={"name_of_service": "Placila", "crud_method": "put", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "success", "http_code": 200})

        return placilo, 200

    @ns.doc("Izbrisi placilo")
    @ns.response(404, 'Placilo ni najdeno')
    @ns.response(204, 'Placilo izbrisano')
    def delete(self, id):
        '''
        Izbrisi placilo glede na ID
        '''
        l.info("Izbrisi placilo z ID %s" % str(id), extra={"name_of_service": "Placila", "crud_method": "delete", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        self.cur.execute("SELECT * FROM placila")
        rows = self.cur.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

        if id not in ids:
            l.warning("Placilo z ID %s ni bil najden" % str(id), extra={"name_of_service": "Placila", "crud_method": "delete", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "fail", "http_code": 404})
            abort(404)
        else:
            self.cur.execute("DELETE FROM placila WHERE id = %s" % str(id))
            self.conn.commit()
            
        l.info("Placilo z ID %s izbrisano" % str(id), extra={"name_of_service": "Placila", "crud_method": "delete", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "success", "http_code": 204})
        return 204

class ListPlacil(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = 'placila'
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()
        self.cur.execute("select exists(select * from information_schema.tables where table_name=%s)", (self.table_name,))
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute('''CREATE TABLE placila (
                           id INT NOT NULL,
                           id_placnika INT NOT NULL,
                           id_prejemnika INT NOT NULL,
                           znesek_eur CHAR(20),
                           znesek_coin CHAR(20),
                           status CHAR(20)
                        )''')
        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int, required=True, help="ID plačila je obvezen")
        self.parser.add_argument("id_placnika", type=int, required=True, help="ID plačnika je obvezen")
        self.parser.add_argument("id_prejemnika", type=int, required=True, help="ID prejemnika je obvezen")
        self.parser.add_argument("znesek_eur", type=str, required=True, help="Znesek plačila v EUR je obvezen")
        self.parser.add_argument("status", type=str, required=True, help="Status plačila je obvezen")

        super(ListPlacil, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(placilaApiModel)
    @ns.doc("Vrni vsa placila")
    def get(self):
        '''
        Vrni vsa placila
        '''
        l.info("Zahtevaj placila", extra={"name_of_service": "Placila", "crud_method": "get", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        self.cur.execute("SELECT * FROM placila")
        rows = self.cur.fetchall()
        ds = {}
        i = 0
        for row in rows:
            ds[i] = {}
            for el, k in zip(row, placilaPolja):
                ds[i][k] = el
            i += 1

        placila = []
        for d in ds:
            placilo = PlaciloModel(
                id = ds[d]["id"],
                id_placnika = ds[d]["id_placnika"],
                id_prejemnika = ds[d]["id_prejemnika"],
                znesek_eur = ds[d]["znesek_eur"].strip(),
                znesek_coin = ds[d]["znesek_coin"].strip(),
                status = ds[d]["status"].strip())
            placila.append(placilo)

        l.info("Vrni placila", extra={"name_of_service": "Placila", "crud_method": "get", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "success", "http_code": 200})
        return {"placila": placila}, 200

    @marshal_with(placiloApiModel)
    @ns.expect(placiloApiModel)
    @ns.doc("Dodaj placilo")
    def post(self):
        '''
        Dodaj novo placilo
        '''
        l.info("Dodaj placilo", extra={"name_of_service": "Placila", "crud_method": "post", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        args = self.parser.parse_args()
        values = []
        for a in args.values():
            values.append(a)

        l.info("Pretvori v bitcoin", extra={"name_of_service": "Placila", "crud_method": "post", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": None, "http_code": None})
        bitcoins = str(get_bitcoins(args["znesek_eur"]))
        bitcoins = bitcoins[10:17]
        l.info("Pretvorjeno v bitcoine", extra={"name_of_service": "Placila", "crud_method": "post", "directions": "in", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "success", "http_code": None})
        values.insert(4, bitcoins)
        self.cur.execute('''INSERT INTO {0} (id, id_placnika, id_prejemnika, znesek_eur, znesek_coin, status)
                VALUES ({1}, {2}, {3}, '{4}', '{5}', '{6}')'''.format('placila', *values))
        self.conn.commit()

        placilo = PlaciloModel(
            id = args["id"],
            id_placnika = args["id_placnika"],
            id_prejemnika = args["id_prejemnika"],
            znesek_eur = args["znesek_eur"].strip(),
            znesek_coin = bitcoins,
            status = args["status"].strip())

        l.info("Placilo dodano", extra={"name_of_service": "Placila", "crud_method": "post", "directions": "out", "ip_node": socket.gethostbyname(socket.gethostname()), "status": "success", "http_code": 201})
        return placilo, 201 


health = HealthCheck()
envdump = EnvironmentDump()
health.add_check(check_database_connection)
envdump.add_section("application", application_data)
app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
api.add_resource(ListPlacil, "/placila")
api.add_resource(Placilo, "/placila/<int:id>")
app.run(host="0.0.0.0", port=5002)
h.close()
