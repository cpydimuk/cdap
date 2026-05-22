/*
 * x86-64 setjmp / longjmp (System V AMD64 ABI, Linux).
 *
 * jmp_buf layout (8 quadwords, 64 bytes total):
 *   [0]  rbx
 *   [8]  rbp
 *   [16] r12
 *   [24] r13
 *   [32] r14
 *   [40] r15
 *   [48] rsp  (caller's stack pointer, i.e. value of rsp before the call)
 *   [56] rip  (return address back into the caller of my_setjmp)
 *
 * Only callee-saved registers + rsp + rip are preserved, which matches the
 * contract glibc gives for setjmp.
 */

    .intel_syntax noprefix
    .text

    .globl  my_setjmp
    .type   my_setjmp, @function
my_setjmp:
    mov     QWORD PTR [rdi +  0], rbx
    mov     QWORD PTR [rdi +  8], rbp
    mov     QWORD PTR [rdi + 16], r12
    mov     QWORD PTR [rdi + 24], r13
    mov     QWORD PTR [rdi + 32], r14
    mov     QWORD PTR [rdi + 40], r15

    /* caller's rsp = current rsp + 8 (skip over the saved return address) */
    lea     rax, [rsp + 8]
    mov     QWORD PTR [rdi + 48], rax

    /* return address sits at the top of the current stack */
    mov     rax, QWORD PTR [rsp]
    mov     QWORD PTR [rdi + 56], rax

    xor     eax, eax
    ret
    .size   my_setjmp, .-my_setjmp

    .globl  my_longjmp
    .type   my_longjmp, @function
my_longjmp:
    /* rdi = env, esi = val */
    mov     eax, esi
    test    eax, eax
    jnz     1f
    mov     eax, 1                  /* longjmp(env, 0) must return 1 */
1:
    mov     rbx, QWORD PTR [rdi +  0]
    mov     rbp, QWORD PTR [rdi +  8]
    mov     r12, QWORD PTR [rdi + 16]
    mov     r13, QWORD PTR [rdi + 24]
    mov     r14, QWORD PTR [rdi + 32]
    mov     r15, QWORD PTR [rdi + 40]
    mov     rsp, QWORD PTR [rdi + 48]
    mov     rdx, QWORD PTR [rdi + 56]
    jmp     rdx
    .size   my_longjmp, .-my_longjmp

    /* Mark stack as non-executable. */
    .section .note.GNU-stack,"",@progbits
