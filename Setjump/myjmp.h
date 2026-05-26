#ifndef MYJMP_H
#define MYJMP_H

#if defined(__x86_64__)
typedef unsigned long my_jmp_buf[8];
#elif defined(__i386__)
typedef unsigned long my_jmp_buf[6];
#else
#error "Unsupported architecture: this setjmp/longjmp only targets x86 / x86_64."
#endif

int  my_setjmp(my_jmp_buf env);
void my_longjmp(my_jmp_buf env, int val) __attribute__((noreturn));

#endif
