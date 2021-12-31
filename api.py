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

custom_format = {
  'name': '%(name_of_service)s',
  'method': '%(crud_method)s',
  'traffic': '%(directions)s',
  'type': '%(levelname)s',
}
logging.basicConfig(level=logging.INFO)
l = logging.getLogger('fluent.test')
h = handler.FluentHandler('Placila', host=app.config["FLUENT_IP"], port=app.config["FLUENT_PORT"])
formatter = handler.FluentRecordFormatter(custom_format)
h.setFormatter(formatter)
l.addHandler(h)
l.info("Pripravljanje Placila Mikrostoritve", extra={"name_of_service": "Placila", "crud_method": None, "directions": None})

def connect_to_database():
    return pg.connect(database=app.config["DATABASE_NAME"], user=app.config["DATABASE_USER"], password=app.config["DATABASE_PASSWORD"],
                      port=app.config["DATABASE_PORT"], host=app.config["DATABASE_IP"])


api = Api(app, version='1.0', doc='/openapi', title='Placila API', description='Abstrakt Placila API',default_swagger_filename='openapi.json', default='Placila CRUD', default_label='koncne tocke in operacije')
placiloApiModel = api.model('ModelPlacila', {
    "id": fields.Integer(readonly=True, description='ID placila'),
    "id_placnika": fields.Integer(readonly=True, description='ID placnika placila'),
    "id_prejemnika": fields.Integer(readonly=True, description='ID prejemnika placila'),
    "status": fields.String(readonly=True, description='Status placila')
})
placilaApiModel = api.model('ModelPlacil', {"placila": fields.List(fields.Nested(placiloApiModel))})
ns = api.namespace('Placila CRUD', description='Placila koncne tocke in operacije')
posodobiModel = api.model('PosodobiPlacilo', {
    "atribut": fields.String,
    "vrednost": fields.String
})

def create_app():
    metrics = PrometheusMetrics(app)
    health = HealthCheck()
    envdump = EnvironmentDump()
    health.add_check(check_database_connection)
    health.add_check(test_microservice)
    envdump.add_section("application", application_data)
    app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
    app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
    api.add_resource(ListPlacil, "/placila")
    api.add_resource(Placilo, "/placila/<int:id>")

def test_microservice():
    process = subprocess.Popen('python api_test.py', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if 'OK' in str(stderr):
        return 200
    else:
        return 409

def check_database_connection():
    conn = connect_too_database()
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
    def __init__(self, id, id_placnika, id_prejemnika, status):
        self.id = id
        self.id_placnika = id_placnika
        self.id_prejemnika = id_prejemnika
        self.status = status

placilaPolja = {
    "id": fields.Integer,
    "id_placnika": fields.Integer,
    "id_prejemnika": fields.Integer,
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
        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        placilo = PlaciloModel(
            id = d["id"],
            id_placnika = d["id_placnika"],
            id_prejemnika = d["id_prejemnika"],
            status = d["status"].strip())

        return placilo, 200

    @marshal_with(placiloApiModel)
    @ns.expect(posodobiModel)
    @ns.response(404, 'Placilo ni najden')
    @ns.doc("Vrni placilo")
    def put(self, id):
        """
        Posodobi podatke placila glede na ID
        """
        l.info("Posodobi placilo z ID %s" % str(id), extra={"name_of_service": "Placila", "crud_method": "put", "directions": "in"})
        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute("""UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(self.table_name, attribute, value, id))
        self.conn.commit()

        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        placilo = PlaciloModel(
            id = d["id"],
            id_placnika = d["id_placnika"],
            id_prejemnika = d["id_prejemnika"],
            status = d["status"].strip())

        return placilo, 200

    @ns.doc("Izbrisi placilo")
    @ns.response(404, 'Placilo ni najdeno')
    @ns.response(204, 'Placilo izbrisano')
    def delete(self, id):
        '''
        Izbrisi placilo glede na ID
        '''
        self.cur.execute("SELECT * FROM placila")
        rows = self.cur.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

        if id not in ids:
            abort(404)
        else:
            self.cur.execute("DELETE FROM placila WHERE id = %s" % str(id))
            self.conn.commit()
            
        return 201

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
                           status CHAR(10)
                        )''')
        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int, required=True, help="ID plačila je obvezen")
        self.parser.add_argument("id_placnika", type=int, required=True, help="ID plačnika je obvezen")
        self.parser.add_argument("id_prejemnika", type=int, required=True, help="ID prejemnika je obvezen")
        self.parser.add_argument("status", type=str, required=True, help="Status plačila je obvezen")

        super(ListPlacil, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(placilaApiModel)
    @ns.doc("Vrni vsa placila")
    def get(self):
        '''
        Vrni vsa placila
        '''
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
                status = ds[d]["status"].strip())
            placila.append(placilo)

        return {"placila": placila}, 200

    @marshal_with(placiloApiModel)
    @ns.expect(placiloApiModel)
    @ns.doc("Dodaj placilo")
    def post(self):
        '''
        Dodaj novo placilo
        '''
        args = self.parser.parse_args()
        values = []
        for a in args.values():
            values.append(a)
        self.cur.execute('''INSERT INTO {0} (id, id_placnika, id_prejemnika, status)
                VALUES ({1}, {2}, {3}, '{4}')'''.format('placila', *values))
        self.conn.commit()

        placilo = PlaciloModel(
            id = args["id"],
            id_placnika = args["id_placnika"],
            id_prejemnika = args["id_prejemnika"],
            status = args["status"].strip())

        return placilo, 201 


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=5002)
    h.close()
