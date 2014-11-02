# -*- coding: utf-8 -*-
import sqlite3
import zlib
import time


class BundlerDB(object):

	def __init__(self, path):
		self.db = sqlite3.connect(path, check_same_thread=False)

	def queue_deeds(self, deeds):
		if not deeds:
			return

		cursor = self.db.cursor()
		insert = 'INSERT INTO deeds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
		timestamp = int(time.time())

		for deed in deeds:
			(fingerprint, otc_name, deed_hash, b58_hash, deed_text, title) = deed
			# compress deed before storing, need to uncompress when reading
			deed_blob = sqlite3.Binary(zlib.compress(deed_text))
			row = (None, fingerprint, otc_name, deed_hash, b58_hash, deed_blob, title, timestamp, 0, None)
			cursor.execute(insert, row)

		self._commit()
