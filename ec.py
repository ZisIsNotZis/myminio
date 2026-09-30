from os import mkdir, rmdir, remove, listdir
from random import choice
from functools import reduce
import numpy as np


class EC(list):
    def write(d, k, v, n=0):
        d.remove(k)
        print(f'INF write {k} {len(v)} {n}')
        n = n or len(d)-1
        v = np.frombuffer(v, 'B')
        if len(v) % n:
            v = v[:(n-1)*(len(v)//n+1)].reshape(n-1, -
                                                1), np.pad(v[(n-1)*(len(v)//n+1):], (0, v[0].shape[1]-v[1]))
            v = *v[0], v[1], np.bitwise_xor.reduce(v[0]) ^ v[1]
        else:
            v = v.reshape(n, -1)
            v = *v, np.bitwise_xor.reduce(v)
        for i, v in enumerate(v):
            _ = f'{choice(d)}{k}/'
            try:
                mkdir(_)
            except FileExistsError:
                pass
            v.tofile(f'{_}{i}.{n}')

    def read(d, k):
        v = {}
        for d in d:
            try:
                for _ in listdir(f'{d}{k}'):
                    i, n = map(int, _.split('.'))
                    v.setdefault(n, {})[i] = np.memmap(f'{d}{k}/{_}')
            except FileNotFoundError:
                pass
        o = None
        for n, v in v.items():
            if len(v) < n:
                print(f'WRN read {k} {n-len(v)}/{n+1} shard miss')
                continue
            if len(v) == n:
                print(f'INF read {k} 1/{n+1} shard mix, fix')
                i = [i for i in range(n+1)if i not in v][0]
                v[i] = reduce(np.bitwise_xor, v.values())
                v[i].tofile(f'{d}{k}/{i}.{n}')
            elif (reduce(np.bitwise_xor, (v[i]for i in range(n))) != v[n]).any():
                print(f'WRN read {k} {n+1} shard mismatch')
                continue
            else:
                print(f'INF read {k}')
            o = [v[i]for i in range(n)]
        if o:
            return np.concatenate(o)
        raise FileNotFoundError

    def list(d):
        print('INF list')
        return list({k for d in d for k in listdir(d)})

    def remove(d, k):
        print(f'INF remove {k}')
        for d in d:
            try:
                for _ in listdir(f'{d}{k}'):
                    remove(f'{d}{k}/{_}')
                rmdir(f'{d}{k}')
            except FileNotFoundError:
                pass
