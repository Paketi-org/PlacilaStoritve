from flask import Flask
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from configparser import ConfigParser
import psycopg2 as pg

app = Flask(__name__)
api = Api(app)

placilaPolja = {
    "id": fields.Integer,
    "id_placnika": fields.Integer,
    "id_prejemnika": fields.Integer,
    "status": fields.String,
}

class Placilo(Resource):
    def __init__(self, config_file='database.ini', section='postgresql'):
        self.table_name = 'placila'
        self.db = self.get_config(config_file, section)
        self.conn = pg.connect(**self.db)
        self.cur = self.conn.cursor()

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("id_placnika", type=int)
        self.parser.add_argument("id_prejemnika", type=int)
        self.parser.add_argument("status", type=int)

        super(Placilo, self).__init__()

    def get_config(self, config_file, section):
        self.parser = ConfigParser()
        self.parser.read(config_file)
        db = {}
        if self.parser.has_section(section):
            params = self.parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('Section {0} not found in the {1} file'.format(section, config_file))

        return db

    def get(self, id):
        self.cur.execute("SELECT * FROM placila WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], placilaPolja):
            d[k] = el

        return{"placilo": marshal(d, placilaPolja)}

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
    def __init__(self, config_file='database.ini', section='postgresql'):
        self.table_name = 'placila'
        self.db = self.get_config(config_file, section)
        self.conn = pg.connect(**self.db)
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
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("id_placnika", type=int)
        self.parser.add_argument("id_prejemnika", type=int)
        self.parser.add_argument("status", type=str, help="status dostave")

    def get_config(self, config_file, section):
        self.parser = ConfigParser()
        self.parser.read(config_file)
        db = {}
        if self.parser.has_section(section):
            params = self.parser.items(section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('Section {0} not found in the {1} file'.format(section, config_file))

        return db

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


api.add_resource(ListPlacil, "/placila")
api.add_resource(Placilo, "/placila/<int:id>")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
