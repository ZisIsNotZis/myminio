from os import mkdir, rmdir, remove, listdir
from functools import reduce
from time import time
from random import choice
import numpy as np


class EC(list):
    def write(d, k, a, n=9e9):
        t = int(time())
        n = min(n, len(d)-1)
        a = np.frombuffer(a, 'B')
        for i, a in enumerate(split_xor(a, n)):
            dk = f'{choice(d)}{k}/'
            try:
                mkdir(dk)
            except FileExistsError:
                pass
            dktni = open(f'{dk}{t}.{n}.{i}', 'ab')
            for a in (a if isinstance(a, list)else (a,)):
                a.tofile(dktni)

    def read(d, k):
        a = {}
        for d in d:
            try:
                for tni in listdir(f'{d}{k}'):
                    t, i, n = map(int, tni.split('.'))
                    a.setdefault((t, n), {})[i] = np.memmap(f'{d}{k}/{tni}')
            except FileNotFoundError:
                pass
        o = None
        T = 0
        for (t, n), a in a.items():
            if len(a) < n:
                print(f'WRN read {k}/{t}.{n} {n+1-len(a)} shard miss')
                continue
            if len(a) == n:
                print(f'INF read {k}/{t}.{n} 1 shard miss, fixed')
                i = [i for i in range(n+1)if i not in a][0]
                a[i] = reduce(np.bitwise_xor, a.values())
                a[i].tofile(f'{d}{k}/{t}.{n}.{i}')
            elif (reduce(np.bitwise_xor, (a[i]for i in range(n))) != a[n]).any():
                print(f'WRN read {k}/{t}.{n} shard mismatch')
                continue
            if t > T:
                o = [a[i]for i in range(n)]
                T = t
        if o:
            return o
        raise FileNotFoundError

    def list(d):
        kt = {}
        for d in d:
            for k in listdir(d):
                for tni in listdir(f'{d}{k}'):
                    kt.setdefault(k, set()).add(int(tni.split('.')[0]))
        return {k: list(t)for k, t in kt.items()}

    def remove(d, k, t=9e9):
        for d in d:
            rm = True
            try:
                for tni in listdir(f'{d}{k}'):
                    if int(tni.split('.')[0]) < t:
                        remove(f'{d}{k}/{tni}')
                    else:
                        rm = False
                if rm:
                    rmdir(f'{d}{k}')
            except FileNotFoundError:
                pass


def split_xor(a, n, cat=True):
    if not isinstance(a, list):
        a = [a]
    n = (sum(map(len, a))/n).__ceil__()
    A = []
    N = 0
    x = None
    for a in a:
        if N:
            A.append(a[:n-N])
            if N + len(a) < n:
                continue
            if cat:
                A = np.concatenate(A)
            yield A
            x = xor(x, A)
            a = a[n-N:]
        if len(a) > n:
            A = a[:len(a)//n*n].reshape(-1, n)
            yield from A
            A = np.bitwise_xor.reduce(A) if len(A) > 1 else A[0]
            x = xor(x, A)
            a = a[len(a)//n*n:]
        if len(a):
            A = [a]
            N = len(a)
        else:
            A = []
            N = 0
    if N:
        if cat:
            A.append(np.zeros(n-N, 'B'))
            A = np.concatenate(A)
        yield A
        x = xor(x, A)
    yield x


def xor(a, b):
    if a is None:
        return b
    if not isinstance(a, list):
        a = [a]
    if not isinstance(b, list):
        b = [b]
    o = []
    while a and b:
        n = min(len(a[0]), len(b[0]))
        a[0][:n] ^= b[0][:n]
        o.append(a[0][:n])
        if len(a[0]) == n:
            a.pop(0)
            if len(b[0]) == n:
                b.pop(0)
            else:
                b[0] = b[0][n:]
        else:
            a[0] = a[0][n:]
            b.pop(0)
    if a:
        o += a
    elif b:
        o += b
    return o if len(o) > 1 else o[0]
