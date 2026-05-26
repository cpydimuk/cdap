# Build the x86 setjmp/longjmp demo.
#
# Defaults to the host architecture (x86_64 on a typical 64-bit Linux).
# Override with `make ARCH=i386` to build the 32-bit version (requires
# a multilib toolchain, e.g. gcc-multilib on Debian/Ubuntu).

ARCH ?= $(shell uname -m)

CC      := gcc
CFLAGS  := -O2 -Wall -Wextra -std=c11
LDFLAGS :=

ifeq ($(ARCH),i386)
ASM_SRC  := setjmp_i386.S
CFLAGS   += -m32
LDFLAGS  += -m32
else ifeq ($(ARCH),i686)
ASM_SRC  := setjmp_i386.S
CFLAGS   += -m32
LDFLAGS  += -m32
else ifeq ($(ARCH),x86_64)
ASM_SRC  := setjmp_amd64.S
else
$(error Unsupported ARCH: $(ARCH). Use x86_64 or i386.)
endif

OBJS := test_setjmp.o $(ASM_SRC:.S=.o)

test_setjmp: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)

%.o: %.S
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.c myjmp.h
	$(CC) $(CFLAGS) -c $< -o $@

run: test_setjmp
	./test_setjmp

clean:
	rm -f *.o test_setjmp

.PHONY: run clean
