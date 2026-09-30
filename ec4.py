from os import mkdir, rmdir, remove, listdir, stat
from functools import reduce
from time import time
import numpy as np

"""
[x] raid 5
    [x] set
        [x] indivisible case
        [x] fast xor
        [x] zero pad
    [x] get
        [x] zero read
        [x] zero cat
        [x] shard miss fixing
        [x] shard lots of miss force fixing
        [x] shard mismatch detection
        [x] shard mismatch force fixing
    [x] rm
[x] raid0 (i.e. chk=0)
    [x] set
    [x] get
[x] ls
[x] version
    [x] ls version
    [x] version-filtered newest obj getting
    [x] version-filtered obj deletion
[x] quota
    [x] quota cli setting
    [x] dynamic bucket selection
    [x] quota report
[x] health
    [x] global scanning and fixing
    [x] health report
[x] snapshot
[x] error counting
"""


class EC(dict):
    e = 0

    def __init__(s, _):
        super().__init__(_)
        for S in s:
            s[S] -= sum(stat(f'{S}{k}/{_}').st_size for k in listdir(S) for _ in listdir(f'{S}{k}'))

    def ls(s):
        return {k for s in s for k in listdir(s)}

    def stat(s, k):
        return {int(_.split()[0])for s in s for _ in ls(f'{s}{k}')}

    def get(s, k, t=9e9, chk=0):
        a = {}
        t = max((T for s in s for _ in ls(f'{s}{k}')if (T := int(_.split()[0])) < t), default=0)
        if not t:
            raise FileNotFoundError
        for d in s:
            for _ in ls(f'{d}{k}'):
                T, n, i = map(int, _.split())
                if T == t:
                    a[i] = np.memmap(f'{d}{k}/{_}')
        a, e = cat(a, n, lambda i: a[i].tofile(f'{max(s, key=s.__getitem__)}{k}/{t} {n} {i}'), chk)
        s.e += e
        return a

    def set(s, k, a, t=0, n=0, chk=0):
        t = t or int(time())
        n = n or len(s)-1
        l = (len(a)//n).__ceil__()
        for i, (S, a) in enumerate(zip(sorted(s, key=s.__getitem__, reverse=1), split(a, n, chk))):
            try:
                mkdir(f'{S}{k}/')
            except FileExistsError:
                pass
            open(f'{S}{k}/{t} {n} {i}', 'wb').writelines((a, b'\0'*(l-len(a))))
            s[S] -= l

    def rm(s, k, t=9e9):
        for s in s:
            for _ in ls(f'{s}{k}'):
                if int(_.split()[0]) < t:
                    remove(f'{s}{k}/{_}')
            try:
                rmdir(f'{s}{k}')
            except (FileNotFoundError, OSError):
                pass

    def gets(s):
        s.e = 0
        for k in s.ls():
            s.get(k)

    def ln(s, k, t, T=0):
        T = T or int(time())
        for s in s:
            for _ in ls(f'{s}{k}'):
                _, ni = _.partition(' ')[::2]
                if int(_) == t:
                    link(f'{s}{k}/{_} {ni}', f'{s}{k}/{T} {ni}')


def split(a, n, chk=0):
    if len(a) % n:
        a, b = np.split(a, ((n-1)*(len(a)//n+1),))
        n -= 1
    else:
        b = 0
    a = a.reshape(n, -1)
    if not chk:
        if b is 0:
            return a
        return *a, b
    c = np.bitwise_xor.reduce(a)
    if b is 0:
        return *a, c
    c[:len(b)] ^= b
    return *a, b, c


def cat(a, n, f=lambda _: 0, chk=0):
    e = 0
    if len(a) < n:
        print(f'WRN {n+1-len(a)} shard mis')
        _ = np.empty(len(list(a.values())[0]), 'B')
        for i in range(n):
            if i not in a:
                a[i] = _
        e = 1
    elif len(a) == n:
        if chk or n in a:
            print(f'WRN 1 shard mis, fixed')
            i = [i for i in range(n+1)if i not in a][0]
            a[i] = reduce(np.bitwise_xor, a.values())
            if chk:
                f(i)
    elif len(a) > n and chk and (reduce(np.bitwise_xor, (a[i]for i in range(n))) != a[n]).any():
        print(f'WRN shard mismatch')
        e = 1
    return [a[i]for i in range(n)], e


def ls(_):
    try:
        return listdir(_)
    except FileNotFoundError:
        return ()
