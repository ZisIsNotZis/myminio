from sys import argv
from flask import Flask, request, jsonify, send_file, abort, Response
from ec4 import EC
import numpy as np

Flask = Flask(__name__)

EC = EC({(_ := i.rpartition('/'))[0]+'/': int(_[2]) for i in argv[1:]})


@Flask.get('/obj')
def ls():
    return jsonify(list(EC.ls()))


@Flask.get('/obj/<k>')
def stat(k):
    return jsonify(list(EC.stat(k)))


@Flask.get('/obj/<k>/<int:t>')
def get(k, t):
    return b''.join(EC.get(k, int(t)))


@Flask.post('/obj/<k>/<int:t>')
def set(k, t):
    EC.set(k, np.frombuffer(request.get_data(), 'B'), t)
    return b''


@Flask.put('/obj/<k>/<int:t>')
def snap(k, t):
    EC.snap(k, t, int(request.get_data()))
    return b''


@Flask.delete('/obj/<k>/<int:t>')
def rm(k, t):
    EC.rm(k, t)
    return b''


@Flask.get('/objs')
def gets():
    EC.gets()
    return EC.e


@Flask.get('/ec')
def ec():
    return EC


Flask.run()
