import numpy as np

class Vec(np.ndarray):
	def __new__(s, f, type='f', cap=32):
		if isinstance(f, str):
			try:
				f = np.memmap(f)
				n = len(f)
				f = f._mmap
			except FileNotFoundError:
				f = np.memmap(f, type, 'w+', shape=cap)._mmap
				n = 0
		else:
			n = f.size() // np.dtype(type).itemsize
		s = np.frombuffer(f, type).view(s)
		s.f = f
		s.n = n
		return s
	def __iadd__(s, dat):
		if not hasattr(dat, '__iter__'):
			dat = dat,
		if s.n + len(dat) >= len(s):
			n = s.n
			s = s.f
			s.resize(s.size()*2)
			s = Vec(s)
			s.n = n
		s[s.n:s.n+len(dat)] = dat
		s.n += len(dat)
		return s

a = Vec('a')
print(a)
a += range(3)
print(a)