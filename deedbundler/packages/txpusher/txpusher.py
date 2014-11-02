import binascii
import os
import random
import re
import subprocess

import requests
from lxml import etree, html

__all__ = ['PUSHERS', 'WEB_PUSHERS', 'pushtx']


TIMEOUT = 7


class Pusher(object):
    def pushtx(self, transaction):
        transaction = transaction.strip()
        if not re.match('^[0-9a-fA-F]*$', transaction):
            transaction = binascii.hexlify(transaction)
        return self._pushhextx(transaction)

    def _pushhextx(self, transaction):
        raise NotImplementedError()

    def __str__(self):
        return self.NAME


class WebPusher(Pusher):
    def _pushhextx(self, transaction):
        try:
            res = self._post(transaction)
        except requests.exceptions.Timeout:
            return False
        return self._isok(res)

    def _post(self, transaction):
        r = requests.post(self.URL, data=self._post_data(transaction), timeout=TIMEOUT)
        return r


class Eligius(WebPusher):
    URL = 'http://eligius.st/~wizkid057/newstats/pushtxn.php'
    NAME = 'Eligius'

    def _post_data(self, transaction):
        return {'send': 'Push', 'transaction': transaction}

    def _isok(self, res):
        page = html.fromstring(res.text)
        try:
            pre = page.xpath('//pre')[0].text.strip().splitlines()[-1]
        except IndexError:
            return False
        return int(pre.split('=')[-1].strip()) > 0


class Blockchain(WebPusher):
    URL = 'https://blockchain.info/pushtx'
    NAME = 'Blockchain.info'

    def _post_data(self, transaction):
        return {'tx': transaction}

    def _isok(self, res):
        return res.status_code == 200


class Blockr(WebPusher):
    URL = 'http://btc.blockr.io/api/v1/tx/push'
    NAME = 'Blockr.io'

    def _post_data(self, transaction):
        return {'hex': transaction}

    def _isok(self, res):
        data = res.json()
        return data.get('status') == 'success'


class Coinbin(WebPusher):
    FORM = 'https://coinb.in/send-raw-transaction.html'
    URL = 'https://coinb.in/api/'
    NAME = 'Coinbin'

    def _post_data(self, transaction):
        res = requests.get(self.FORM, timeout=TIMEOUT)
        page = html.fromstring(res.text)
        data = {}
        for script in page.xpath('//script'):
            if script.text and 'apikey' in script.text:
                for statement in script.text.split(';'):
                    var, _, val = statement.strip().partition('=')
                    if var.startswith('var '):
                        var = var.replace('var ', '')
                        val = val.strip('"\'')
                        data[var] = val
        return {'rawtx': transaction,
                'setmodule': 'bitcoin',
                'request': 'sendrawtransaction',
                'key': data.get('apikey'),
                'uid': data.get('uid')}

    def _isok(self, res):
        page = etree.fromstring(res.text.encode('ascii'))
        for code in page.xpath('//result'):
            return int(code.text) > 0


class Daemon(Pusher):
    NAME = "local daemon"

    def _pushhextx(self, transaction):
        try:
            bitcoind = os.getenv('BITCOIND', '/usr/bin/bitcoind')
            args = [bitcoind, 'sendrawtransaction', transaction]
            subprocess.check_output(args, stderr=subprocess.STDOUT, shell=False)
        except subprocess.CalledProcessError:
            return False
        return True


WEB_PUSHERS = (Eligius, Blockchain, Coinbin, Blockr)
PUSHERS = WEB_PUSHERS + (Daemon, )


def pushtx(transaction, web_only=False, limit=None):
    pushes = {}
    pushers = WEB_PUSHERS if web_only else PUSHERS
    pushers = list(pushers)
    random.shuffle(pushers)
    for p in pushers:
        pi = p()
        success = pi.pushtx(transaction)
        pushes[str(pi)] = success
        if limit and sum(pushes.values()) >= limit:
            break
    return pushes

