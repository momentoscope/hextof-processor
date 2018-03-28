# makefile to compile the Cython code

DldFlashProcessorCy.so: DldFlashProcessorCy.c
	gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing \
	-I/usr/include/python3.6 -o DldFlashProcessorCy.so DldFlashProcessorCy.c
      
      
DldFlashProcessorCy.c: DldFlashProcessorCy.pyx
	~/.local/bin/cython -a DldFlashProcessorCy.pyx

clean:
	rm DldFlashProcessorCy.so DldFlashProcessorCy.so
