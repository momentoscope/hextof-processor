
#  Copyright 2017-2018, Yves Acremann


#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


# makefile to compile the Cython code

DldFlashProcessorCy.so: DldFlashProcessorCy.c
	gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing \
	-I/usr/include/python3.5 -o DldFlashProcessorCy.so DldFlashProcessorCy.c
      
      
DldFlashProcessorCy.c: DldFlashProcessorCy.pyx
	~/.local/bin/cython -a DldFlashProcessorCy.pyx

clean:
	rm -f DldFlashProcessorCy.so
	rm -f DldFlashProcessorCy.html
	rm -f DldFlashProcessorCy.c
