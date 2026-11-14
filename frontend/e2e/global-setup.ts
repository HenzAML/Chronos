import { DB_URL, py } from './env.ts'

const CREATE_DB = `
import sys, psycopg2
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1]); name = u.path.lstrip("/")
c = psycopg2.connect(u._replace(path="/postgres").geturl()); c.autocommit = True
cur = c.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
cur.fetchone() or cur.execute('CREATE DATABASE "%s"' % name)
`

export default function setup() {
  py('-c', CREATE_DB, DB_URL)
  py('-m', 'flask', '--app', 'wsgi', 'db', 'upgrade')
}
