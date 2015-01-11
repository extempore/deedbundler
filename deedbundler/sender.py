# -*- coding: utf-8 -*-
import sqlite3
import zlib
import time
import hmac
import hashlib
import base64

class BundlerDB(object):
	subscribers = []

	def __init__(self, path):
		self.path = path

	def open_db(self):
		filename = self.path
		if os.path.exists(filename):
			self.db = sqlite3.connect(filename, timeout=15, check_same_thread = False)
			self.db.row_factory = sqlite3.Row
			return

		self.db = sqlite3.connect(filename, timeout=15, check_same_thread = False)
		self.db.row_factory = sqlite3.Row
		cursor = self.db.cursor()
		cursor.execute("""CREATE TABLE subscribers (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				url TEXT NOT NULL,
				hmac_secret TEXT NOT NULL)
				""")


		cursor.execute("""CREATE TABLE events (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				event TEXT NOT NULL,
				data_hash TEXT NOT NULL,
				data BLOB NOT NULL,
				)
				""")

		cursor.execute("""CREATE TABLE event_log (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				subscriber_id INTEGER NOT NULL,
				event TEXT NOT NULL,
				data_hash TEXT NOT NULL,
				ack INTEGER,
				)
				""")

		self._commit()

	def _commit(self):
		'''a commit wrapper to give it another few tries if it errors.
		which sometimes happens due to OperationalError: database is locked'''
		for i in xrange(15):
			try:
				self.db.commit()
			except:
				time.sleep(1)

	def queue_event(self, event, data, data_hash):
		cursor = self.db.cursor()
		insert = 'INSERT INTO events VALUES (NULL, ?, ?, ?)'


	def queue_deed(self, data):
		data['base64_deed'] = base64.b64encode(data['raw'])

	def post(self, data):
		post = {'data': data, 'sig': self.hmac(secret, data)}
			
		r = requests.post(url, data=data, headers=headers)


	def hmac(self, secret, data):
		h = hmac.new(secret, data, hashlib.sha256)
		return h.hexdigest()

