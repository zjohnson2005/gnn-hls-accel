import ctypes
libc = ctypes.CDLL("libc.so.6", use_errno=True)
print("syscall gettid", libc.syscall(186))
