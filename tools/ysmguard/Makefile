CC := gcc
CFLAGS := -O2

.PHONY: all clean

all: ysmguard
	@:

ysmguard: ysmguard.c
	$(CC) $(CFLAGS) -o $@ $^

clean:
	$(RM) ysmguard ysmguard.exe
