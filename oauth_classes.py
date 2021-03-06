import json
import pdb
from ok_crypto import Cipher
import SERVER_CONFIG as CONFIG
from datetime import datetime, timedelta
import pickle

class Client():
    def __init__(self, client_id, client_secret, _redirect_uris, services=[]):
        self.client_id = client_id
        self.client_secret = client_secret
        self._redirect_uris = _redirect_uris
        self.services = services
        self.default_scopes = ['tgt']

    def save(self):
        with open(CONFIG.clients_db_file, 'r') as db:
            clients = pickle.load(db)

        with open(CONFIG.clients_db_file, 'w') as db:

            clients[self.client_id] = {
                'client_id'     : self.client_id,
                'client_secret': Cipher.encrypt(self.client_secret, CONFIG.secret) ,
                '_redirect_uris': self._redirect_uris,
                'services' : self.services
            }

            pickle.dump(clients, db)
        
        return self

    @property
    def redirect_uris(self):
        if self._redirect_uris:
            return self._redirect_uris#.split()
        return []

    @property
    def default_redirect_uri(self):
        return self.redirect_uris[0]

    @staticmethod
    def get(client_id):
        with open(CONFIG.clients_db_file, 'r') as db:
            clients = pickle.load(db)

        if client_id not in clients:
            return None

        client = clients[client_id]

        client['client_secret'] = Cipher.decrypt(client['client_secret'], CONFIG.secret)

        return Client(**client)

class Grant():
    def __init__(self, user, password, client_id, redirect_uri):
        self.user = user
        self.password = password
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        # self.expires = expires
        # pdb.set_trace()
        self.scopes = ["tgt"]

    def encrypt_to_string(self, secret):
        code = json.dumps({
        	'user': self.user,
        	'password' : self.password,
        	'client_id' : self.client_id,
        	'redirect_uri' : self.redirect_uri,
        	})
        
        enc = Cipher.encrypt(code, secret)        
    	return  enc


    @staticmethod
    def decrypt(enc, secret):
    	code = Cipher.decrypt(enc, secret)

    	vals = json.loads(code)

    	user = vals['user']
    	password = vals['password']
    	client_id = vals['client_id']
    	redirect_uri = vals['redirect_uri']

        return Grant(user, password, client_id, redirect_uri)

    def delete(self):
    	#no need to delete since we never saved it
    	return True



class Token():
    def __init__(self, tgt, client_id, user, redirect_uri, expires, services=[]):
        self.tgt = tgt
        self.client_id = client_id
        self.user = user
        self.redirect_uri = redirect_uri
        self.expires = expires
        self.services = services
        self.scopes = ['tgt']

    def encrypt_to_string(self, secret):
        code = json.dumps({
        	'tgt': self.tgt,
        	'client_id' : self.client_id,
            'user' : self.user,
        	'redirect_uri' : self.redirect_uri,
            'expires' : self.expires.strftime(CONFIG.time_fmt),
            'services' : self.services
        	})

    	return Cipher.encrypt(code, secret)

    def get_client(self):
        return Client.get(self.client_id)


    @staticmethod
    def decrypt(enc, secret):
    	code = Cipher.decrypt(enc, secret)

    	vals = json.loads(code)

    	tgt = vals['tgt']
        client_id = vals['client_id']
        user = vals['user']
        redirect_uri = vals['redirect_uri']
    	expires = datetime.strptime( vals['expires'], CONFIG.time_fmt)
        services = vals['services']

        return Token(tgt, client_id, user, redirect_uri, expires, services)

