import numpy as np
from functools import reduce
from math import ceil

def load(a, b, i, j):
	return [a[i%len(a)][i//len(a):i//len(a)+(j-i-1)//len(a)+1]for i in range(i,i+len(a))], [b[i//len(a):i//len(a)+ceil((j-i)/len(a))]for b in b]

def chk(a, b, mis=-1):
	l = len(a[-1])
	o = np.empty_like(a[0]) if mis<0 else a[mis] if mis<len(a) else b[0]
	reduce(lambda a,b:np.bitwise_xor(a,b,o[:l]), (a[:l]for i,a in enumerate(a)if i!=mis))
	if l < len(o):
		reduce(lambda a,b:np.bitwise_xor(a,b,o[l:len(o)]), (a[l:len(o)]for i,a in enumerate(a) if len(a)>l and i!=mis))
	if mis < 0:
		assert (o == b[0]).all()
	elif mis < len(a):
		o ^= b[0][:len(o)]
	return a

def cat(a):
	l = len(a[-1])
	o = np.empty(sum(map(len,a)), a[0].dtype)
	np.stack([a[:l]for a in a], 1, o[:l*len(a)].reshape(-1,len(a)))
	if l * len(a) < len(o):
		np.stack([a[l:]for a in a if len(a)>l], 1, o[l*len(a):].reshape(len(a[0])-l,-1))
	return o

def read(a, b, i, j):
	return cat(chk(*load(a, b, i, j), 2))

def write(a, b, i, v):
	a, b = load(a, b, i, i+len(v))
	for i in range(len(a)):
		a[i][:] = v[i::len(a)]
	chk(a, b, len(a))

def resize(a, b, l):
	for i in range(len(a)):
		a[i]._mmap.resize((l-i)//len(a))
		a[i] = np.frombuffer(a[i]._mmap, a[i].dtype)
	for i in range(len(b)):
		b[i]._mmap.resize(l//len(a))
		b[i] = np.frombuffer(b[i]._mmap, b[i].dtype)

a,b = np.arange(3*8).reshape(8,3).T, np.arange(1*8).reshape(1,8)
print(read(a, b, 2, 13))
write(a, b, 2, -np.arange(13-2))
print(read(a, b, 2, 13))