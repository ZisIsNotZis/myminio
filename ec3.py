from os import mkdir, rmdir, remove, listdir, stat
from functools import reduce
from time import time
import numpy as np


class EC(dict):
    def __init__(s, _):
        super().__init__(_)
        for _ in s:
            s[_] -= sum(stat(f'{_}{k}/{tni}').st_size for k in listdir(_)
                        for tni in listdir(f'{_}{k}'))

    def ls(s):
        return {k for s in s for k in listdir(s)}

    def stat(s, k):
        return {int(tni.split()[0])for s in s for tni in listdir(f'{s}{k}')}

    def get(s, k, t=9e9, ret=True):
        a = {}
        for s in s:
            try:
                for tni in listdir(f'{s}{k}'):
                    _, n, i = map(int, tni.split())
                    if _ <= t:
                        a.setdefault((_, n), {})[
                            i] = np.memmap(f'{s}{k}/{tni}')
            except FileNotFoundError:
                pass
        t = 0
        for (_, n), a in a.items():
            a = chk_xor(a, n, f'{k}/{_}.{n}',
                        lambda i: a[i].tofile(f'{s}{k}/{t} {n} {i}'))
            if a and _ > t:
                o = a
                t = _
        if ret:
            if t:
                return np.concatenate(o)
            raise FileNotFoundError

    def set(s, k, a, t=0, n=0):
        t = t or int(time())
        n = n or len(s)-1
        for i, (_, a) in enumerate(zip(sorted(s, key=s.__getitem__, reverse=True), split_xor(np.frombuffer(a, 'B'), n))):
            try:
                mkdir(f'{_}{k}/')
            except FileExistsError:
                pass
            a.tofile(f'{_}{k}/{t} {n} {i}')
            s[_] -= len(a)

    def rm(s, k, t=9e9):
        for s in s:
            try:
                for tni in listdir(f'{s}{k}'):
                    if int(tni.split()[0]) < t:
                        remove(f'{s}{k}/{tni}')
                try:
                    rmdir(f'{s}{k}')
                except OSError:
                    pass
            except FileNotFoundError:
                pass

    def fix(s):
        for k in s.ls():
            s.get(k, ret=False)


def split_xor(a, n):
    if len(a) % n:
        b = np.pad(a[(n-1)*(len(a)//n+1):], (0, -len(a) % n))
        a = a[:(n-1)*(len(a)//n+1)].reshape(n-1, -1)
        return *a, b, np.bitwise_xor.reduce(a) ^ b
    a = a.reshape(n, -1)
    return *a, np.bitwise_xor.reduce(a)


def chk_xor(a, n, k='', f=lambda _: None):
    if len(a) < n:
        print(f'WRN {k} {n+1-len(a)} shard mis')
        return
    if len(a) == n:
        i = [i for i in range(n+1)if i not in a][0]
        a[i] = reduce(np.bitwise_xor, a.values())
        f(i)
    elif (reduce(np.bitwise_xor, (a[i]for i in range(n))) != a[n]).any():
        print(f'WRN {k} shard mismatch')
        return
    return [a[i]for i in range(n)]
