/*
 * i386 setjmp / longjmp (System V i386 ABI, Linux).
 *
 * jmp_buf layout (6 dwords, 24 bytes total):
 *   [0]  ebx
 *   [4]  esi
 *   [8]  edi
 *   [12] ebp
 *   [16] esp  (caller's stack pointer)
 *   [20] eip  (return address)
 *
 * Arguments arrive on the stack: [esp+4] is the first arg, [esp+8] the second.
 */

    .intel_syntax noprefix
    .text

    .globl  my_setjmp
    .type   my_setjmp, @function
my_setjmp:
    mov     eax, DWORD PTR [esp + 4]    /* env */
    mov     DWORD PTR [eax +  0], ebx
    mov     DWORD PTR [eax +  4], esi
    mov     DWORD PTR [eax +  8], edi
    mov     DWORD PTR [eax + 12], ebp

    lea     ecx, [esp + 4]              /* caller's esp */
    mov     DWORD PTR [eax + 16], ecx

    mov     ecx, DWORD PTR [esp]        /* return address */
    mov     DWORD PTR [eax + 20], ecx

    xor     eax, eax
    ret
    .size   my_setjmp, .-my_setjmp

    .globl  my_longjmp
    .type   my_longjmp, @function
my_longjmp:
    mov     edx, DWORD PTR [esp + 4]    /* env */
    mov     eax, DWORD PTR [esp + 8]    /* val */
    test    eax, eax
    jnz     1f
    mov     eax, 1
1:
    mov     ebx, DWORD PTR [edx +  0]
    mov     esi, DWORD PTR [edx +  4]
    mov     edi, DWORD PTR [edx +  8]
    mov     ebp, DWORD PTR [edx + 12]
    mov     esp, DWORD PTR [edx + 16]
    mov     ecx, DWORD PTR [edx + 20]
    jmp     ecx
    .size   my_longjmp, .-my_longjmp

    .section .note.GNU-stack,"",@progbits
