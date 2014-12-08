from flask import Flask
from subprocess import Popen, PIPE
import base64
import json
import pycurl
import StringIO
import sys
import getpass
from flask import Flask
from subprocess import Popen, PIPE
from base64 import urlsafe_b64encode
# import gssapi
import os
import subprocess
import lib.krb5 as krb5
import lib.krb5_ctypes as krb5_ctypes
import lib.gss as gss
import binascii
import ctypes

# For testing
def acquire_creds(realm, service):
    # Get a context, and load the credential cache.
    ctx = krb5.Context()
    ccache = ctx.cc_default()

    # Get principal names.
    principal = ccache.get_principal()

    #zephyr = ctx.build_principal('ATHENA.MIT.EDU', ['zephyr', 'zephyr'])
    service = ctx.build_principal(realm, service)
    creds = ccache.get_credentials(principal, zephyr)
    return creds

# Get a ticket for a specific service.
def get_service_ticket(userid, service, tgt, realm='ATHENA.MIT.EDU'):
    # use davidben's handy c library wrappers to get the service ticket
    ctx = krb5.Context()
    ccache = krb5.CCache(ctx)

    # create a new in-memory ccache to hold the credentials
    krb5.krb5_cc_new_unique(ctx._handle,                # context
            krb5_ctypes.ctypes.c_char_p('MEMORY'),      # type
            krb5_ctypes.ctypes.c_char_p(),              # hint (blank)
            ccache._handle)
    #ccache = ctx.cc_default()

    # TODO: store tgt in ccache

    # Get principal names.
    principal = ccache.get_principal()

    service = ctx.build_principal(realm, service)
    creds = ccache.get_credentials(principal, zephyr)

    return ticket

# Get a ticket-granting ticket. This part works.
def get_tgt(userid, passwd, realm='ATHENA.MIT.EDU'):
    tmp_dir = os.path.join('/tmp', urlsafe_b64encode(userid + '@' + realm))
    if not os.path.exists(tmp_dir):
        os.mkdirs(tmp_dir)

    tgt_file = os.path.join(tmp_dir, 'krb5cc')
    keytab_file = os.path.join('/etc', urlsafe_b64encode(userid + '@' + realm))

    KINIT_PATH = '/usr/bin/kinit'
    kinit_args = [KINIT_PATH, '-f', '-c', tgt_file, userid + '@' + realm]
    print ' '.join(kinit_args)

    # exec kinit
    kinit = subprocess.Popen(kinit_args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    print kinit.communicate(passwd + '\n')    # write password
    retcode = kinit.wait()                        # wait for completion

    if str(retcode) == '0':
        # get the generated tgt
        tgt = open(tgt_file, 'r').read()
        # delete cached tgt
        os.remove(tgt_file)
    else:
        raise Exception("Error: kinit returned code " + str(retcode))

    return tgt

SERIALIZE = 1
DESERIALIZE = 2
def serialize_or_deserialize_cred(context_obj, arg,s_or_d):
	"""helper function for (de)serialization"""

	context = context_obj._handle

	PTR = krb5_ctypes.ctypes.POINTER # takes type and outputs type
	ptr = krb5_ctypes.ctypes.pointer # takes var and outputs var

	auth_context = krb5_ctypes.krb5_auth_context()
	krb5.krb5_auth_con_init(context,ptr(auth_context))
	try:
		# we don't need replay protection for this data
		# and we don't want to have to maintain a replay cache
		krb5.krb5_auth_con_setflags(context, auth_context, 0)

		enctype = krb5_ctypes.krb5_enctype()			

		# we use aes128 becasue its fast on modern computers
		# and we don't care about encryption security here because for all
		# we care, we could return the data unencrypted
		krb5.krb5_string_to_enctype("aes128-cts",ptr(enctype))


		# kerberos only exports/imports encrypted creds
		# but we do encryption at another layer of our design
		# so we just use dummy encryption keys and salts here
		string = krb5_ctypes.krb5_data()
		string.data = ctypes.cast(ctypes.c_char_p("asdf"),PTR(ctypes.c_char))
		string.length=5 # we include the null terminator
		
		salt = krb5_ctypes.krb5_data()
		salt.data = ctypes.cast(ctypes.c_char_p("asdf"),PTR(ctypes.c_char))
		salt.length=5 # we include the null terminator
		
		key = krb5_ctypes.krb5_keyblock()
		krb5.krb5_c_string_to_key(context, enctype, ptr(string), ptr(salt),
					  ptr(key))
		try:
			if s_or_d == SERIALIZE:
				# setup pcreds
				pcreds = ptr(arg._handle)
			
				# setup ppdata
				pdata = PTR(krb5_ctypes.krb5_data)()
				ppdata = ptr(pdata)


				krb5.krb5_auth_con_setsendsubkey(context, auth_context, key)
			
				krb5.krb5_mk_1cred(context, auth_context, pcreds, ppdata, None)
				try:
					encoded_cred = binascii.hexlify(bytearray(
						  [pdata.contents.data[i]
						   for i in range(pdata.contents.length)] ))
					return encoded_cred
				finally:
					krb5.krb5_free_data(context, pdata)
			elif s_or_d == DESERIALIZE:
				# setup pcreddata
				databytes = list(binascii.unhexlify(arg))
				c_databytes = (ctypes.c_char*len(databytes))(*databytes)
				creddata = krb5_ctypes.krb5_data()
				creddata.data = ctypes.cast(c_databytes, PTR(ctypes.c_char))
				creddata.length = len(databytes)
				pcreddata = ptr(creddata)

				# setup pppcreds
				ppcreds = PTR(PTR(krb5_ctypes.krb5_creds))()
				pppcreds = ptr(ppcreds)

				krb5.krb5_auth_con_setrecvsubkey(context, auth_context, key)
			
				krb5.krb5_rd_cred(context, auth_context, pcreddata, 
						  pppcreds, None)
				try:
					creds = pcreds.contents[0]
					creds_obj = krb5.Credentials(context_obj)
					krb5.krb5_copy_creds(context, ptr(creds),
							     ptr(creds_obj._handle))
						
				finally:
					krb5.krb5_free_tgt_creds(context, ppcreds)
		finally:
			krb5.krb5_free_keyblock_contents(context,ptr(key))
	finally:
		krb5.krb5_auth_con_free(context, auth_context)

def serialize_cred(context_obj, creds_obj)
	"""Takes a Context and Credentials object (krb5.py) and returns a hex serialized
	version of the credentials object suitable for important with deserialize_cred"""
	return serialize_or_deserialize_cred(context_obj,creds_obj,SERIALIZE)

def deserialize_cred(context_obj, encoded_cred):
	"""Takes a Context object (krb5.py) and a hex encoded Credential object created by
	serailize_cred and returns a Credentials object created via deserialization."""
	return serialize_or_deserialize_cred(context_obj,encoded_cred,DESERIALIZE)



if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise "Error: format is <username> <service>"
    uname, service = sys.argv[1:]
    passwd = getpass.getpass()
    tgt = get_tgt(uname, passwd)
    print 'TGT generation success. Ticket is as follows:'
    print
    print tgt
    print
    sbc_ticket = get_service_ticket(uname, service, tgt)
    print
    print svc_ticket

