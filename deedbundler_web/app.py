# -*- coding: utf-8 -*-
import re
import json
import zlib
import sqlite3
import base64
from datetime import datetime
from urllib import quote_plus

from bottle import Bottle, HTTPError, request, response, template, static_file, TEMPLATE_PATH, BaseTemplate

config_path = '/home/deedbot/app/config/deeds_config.json'
with open(config_path) as f:
	CONFIG = json.loads(f.read())

def get_db():
	db_path = '{0}/{1}'.format(CONFIG['db_path'], CONFIG['db_name'])
	db = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
	db.row_factory = sqlite3.Row
	return db


def timestamp(s):
	return datetime.fromtimestamp(int(s)).strftime('%Y/%m/%d %H:%M:%S')

def bundle_url(a, short=False, length=None):
	host = CONFIG['hostname']
	path = 'bundle' if not short else 'b'
	addr = a if length is None else a[:length]
	url = 'http://{0}/{1}/{2}'.format(host, path, addr)
	return url

def deed_url(h, short=False, length=None):
	host = CONFIG['hostname']
	path = 'deed' if not short else 'd'
	dhash = h if length is None else h[:length]
	url = 'http://{0}/{1}/{2}'.format(host, path, dhash)
	return url

def bundle_page_url(page):
	host = CONFIG['hostname']
	path = 'bundles'
	if page > 0:
		url = 'http://{0}/{1}/{2}'.format(host, path, page)
	else:
		url = 'http://{0}/{1}'.format(host, path)
	return url

def otc_url(name):
	url = 'http://bitcoin-otc.com/viewratingdetail.php?nick={0}'
	return url.format(quote_plus(name))

app = Bottle()
TEMPLATE_PATH.append('/home/deedbot/app/deedbundler/deedbundler_web/templates/')

BaseTemplate.defaults['date'] = timestamp
BaseTemplate.defaults['deed_url'] = deed_url
BaseTemplate.defaults['bundle_url'] = bundle_url
BaseTemplate.defaults['bundle_page_url'] = bundle_page_url
BaseTemplate.defaults['otc_url'] = otc_url

@app.get('/')
def index():
	db = get_db()
	cursor = db.cursor()

	pend_sel = 'SELECT b58_hash, otc_name, created_at, title FROM deeds WHERE bundled_at = 0 ORDER BY created_at DESC'
	cursor.execute(pend_sel)
	pending = cursor.fetchall()

	limit = CONFIG['bundles_per_page_index']
	bundle_sel = """SELECT address, num_deeds, created_at, confirmed_at, txid 
			FROM bundles ORDER BY created_at DESC LIMIT ?"""
	cursor.execute(bundle_sel, (limit,))
	bundles = cursor.fetchall()

	data = {
		'pending_deeds': pending,
		'recent_bundles': bundles,
		}

	return template('index.tpl', **data)

@app.get('/d/<deed_hash>')
@app.get('/deed/<deed_hash>')
@app.get('/deed/<deed_hash>/<format>')
def deed(deed_hash, format=None):
	db = get_db()
	cursor = db.cursor()
	dh = len(deed_hash)
	if dh < 8 or dh > 64 or not validate_address(deed_hash):
		raise HTTPError(status=404)

	if dh > 29:
		sel = 'SELECT * FROM deeds WHERE b58_hash = ? LIMIT 1'
	else:
		deed_hash += '%'
		sel = 'SELECT * FROM deeds WHERE b58_hash LIKE ? ORDER BY created_at DESC'

	rows = cursor.execute(sel, (deed_hash,)).fetchall()
	if not rows:
		raise HTTPError(status=404)

	# get the most recent deed that matched a partial hash
	row = rows.pop(0)

	# decompress deed
	raw_deed = zlib.decompress(row['deed'])
	b64_deed = base64.b64encode(raw_deed)

	if format == 'raw':
		response.content_type = "text/plain"
		return raw_deed
	elif format == 'base64':
		response.content_type = "text/plain"
		return b64_deed

	data = {
		'b58_hash': row['b58_hash'],
		'deed_hash': row['deed_hash'],
		'deed_title': row['title'],
		'raw_deed': raw_deed,
		'base64_deed': b64_deed,
		'created_at': row['created_at'],
		'fingerprint': row['fingerprint'],
		'otc_name': row['otc_name'],
		'bundled_at': row['bundled_at'],
		'bundle_address': row['bundle_address'],
		'canonical': deed_url(row['b58_hash']),
		}

	# append other deeds that matched a partial hash
	if rows:
		data['autocomplete'] = []
		for r in rows:
			s = (r['b58_hash'], r['created_at'], r['otc_name'])
			data['autocomplete'].append(s)

	if format == 'json':
		del data['raw_deed']
		return data


	return template('deed.tpl', **data)

@app.get('/b/<address>')
@app.get('/bundle/<address>')
@app.get('/bundle/<address>/<format>')
def bundle(address, format=None):
	db = get_db()
	cursor = db.cursor()
	al = len(address)
	if al < 8 or al > 35 or not validate_address(address):
		raise HTTPError(status=404)

	if al > 24:
		sel = 'SELECT * FROM bundles WHERE address = ? LIMIT 1'
	else:
		address += '%'
		sel = 'SELECT * FROM bundles WHERE address LIKE ? ORDER BY created_at DESC'

	rows = cursor.execute(sel, (address,)).fetchall()
	if not rows:
		raise HTTPError(status=404)

	# get the most recent bundle that matched a partial address
	row = rows.pop(0)

	deed_hashes = row['deed_hashes'].split(',')

	sel_deeds = """SELECT b58_hash, title, otc_name, created_at FROM deeds
		      WHERE bundle_address = ? ORDER BY created_at ASC""".format(row['address'])
	cursor.execute(sel_deeds, (row['address'],))
	deeds = []
	for d in cursor.fetchall():
		deed = {
			'b58_hash': d['b58_hash'],
			'title': d['title'],
			'otc_name': d['otc_name'],
			'created_at': d['created_at'],
			}
		deeds.append(deed)

        full_bundle_url = 'http://{0}/raw_bundles/{1}/{2}.rbundle'.format(CONFIG['hostname'], address[0:2], address)

	data = {
		'address': row['address'],
		'deeds': deeds,
		'lite_bundle': row['deed_hashes'],
		'full_bundle': full_bundle_url,
		'num_deeds': row['num_deeds'],
		'created_at': row['created_at'],
		'txid': row['txid'],
		'confirmed_at': row['confirmed_at'],
		'canonical': bundle_url(row['address']),
		}

	# append other bundles that matched a partial address
	if rows:
		data['autocomplete'] = []
		for r in rows:
			s = (r['address'], r['created_at'])
			data['autocomplete'].append(s)

	if format == 'json':
		return data

	return template('bundle.tpl', **data)

@app.get('/bundles')
@app.get('/bundles/<page:int>')
def bundles(page=0):
	db = get_db()
	cursor = db.cursor()
	per_page = CONFIG['bundles_per_page']
	offset = page * per_page

	count_sel = 'SELECT count(id) FROM bundles'
	cursor.execute(count_sel)
	total = cursor.fetchone()[0]
	if (offset >= total):
		raise HTTPError(status=404)

	bundle_sel = """SELECT address, num_deeds, created_at, confirmed_at, txid 
			FROM bundles ORDER BY created_at DESC LIMIT ? OFFSET ?"""
	cursor.execute(bundle_sel, (per_page, offset))
	bundles = cursor.fetchall()
	if not bundles:
		raise HTTPError(status=404)

	links = []
	max_page = (total / per_page)
	if  max_page > 0:
		for i in xrange(1, max_page + 1):
			links.append(bundle_page_url(i))

	data = {'bundles': bundles, 'page': page, 'links': links}

	return template('bundles.tpl', **data)

ADDRESS_RX = re.compile('[0-9a-zA-Z]+$')
def validate_address(s):
	return ADDRESS_RX.match(s)


if __name__ == '__main__':

	app.run(host='127.0.0.1', port=8080, debug=True)
