from flask import Flask
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from configparser import ConfigParser
import psycopg2 as pg
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics

def create_app():
    app = Flask(__name__)
    api = Api(app)
    metrics = PrometheusMetrics(app)
    health = HealthCheck()
    envdump = EnvironmentDump()
    health.add_check(check_database_connection)
    envdump.add_section("application", application_data)
    app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
    app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
    api.add_resource(ListPlacil, "/placila")
    api.add_resource(Placilo, "/placila/<int:id>")

    return app

def check_database_connection():
    conn = pg.connect('')
    if conn.poll() == extensions.POLL_OK:
        print ("POLL: POLL_OK")
    if conn.poll() == extensions.POLL_READ:
        print ("POLL: POLL_READ")
    if conn.poll() == extensions.POLL_WRITE:
        print ("POLL: POLL_WRITE")
    return True, "Database connection OK"

def application_data():
    return {"maintainer": "Teodor Janez Podobnik",
            "git_repo": "https://github.com/Paketi-org/PlacilaStoritve.git"}

placilaPolja = {
    "id": fields.Integer,
    "id_placnika": fields.Integer,
    "id_prejemnika": fields.Integer,
    "status": fields.String,
}

class Placilo(Resource):
    def __init__(self):
        self.table_name = 'placila'
        self.conn = pg.connect('')
        self.cur = self.conn.cursor()

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("id_placnika", type=int)
        self.parser.add_argument("id_prejemnika", type=int)
        self.parser.add_argument("status", type=str)
        self.parser.add_argument("atribut", type=str)
        self.parser.add_argument("vrednost", type=str)

        super(Placilo, self).__init__()

    def get(self, id):
        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        return{"placilo": marshal(d, placilaPolja)}

    def put(self, id):
        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute("""UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(self.table_name, attribute, value, id))
        self.conn.commit()

        return 200

    def delete(self, id):
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
    def __init__(self):
        self.table_name = 'placila'
        self.conn = pg.connect('')
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

    def get(self):
        self.cur.execute("SELECT * FROM placila")
        rows = self.cur.fetchall()
        ds = {}
        i = 0
        for row in rows:
            ds[i] = {}
            for el, k in zip(row, placilaPolja):
                ds[i][k] = el
            i += 1

        return{"placila": [marshal(d, placilaPolja) for d in ds.values()]}

    def post(self):
        args = self.parser.parse_args()
        values = []
        for a in args.values():
            values.append(a)
        self.cur.execute('''INSERT INTO {0} (id, id_placnika, id_prejemnika, status)
                VALUES ({1}, {2}, {3}, '{4}')'''.format('placila', *values))
        self.conn.commit()
        placilo = {
            "id": args["id"],
            "id_placnika": args["id_placnika"],
            "id_prejemnika": args["id_prejemnika"],
            "status": args["status"],
        }

        return{"placilo": marshal(placilo, placilaPolja)}, 201


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5002)
