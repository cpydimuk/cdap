#include <stdio.h>
#include <stdlib.h>
#include "myjmp.h"

static my_jmp_buf env;

static void deep_two(int depth) {
    printf("  deep_two(depth=%d): longjmp(env, %d)\n", depth, depth + 100);
    my_longjmp(env, depth + 100);
    printf("  unreachable\n");
    exit(2);
}

static void deep_one(int depth) {
    printf("  deep_one(depth=%d) -> deep_two\n", depth);
    deep_two(depth + 1);
    printf("  unreachable\n");
    exit(2);
}

int main(void) {
    /* Verify callee-saved registers survive across longjmp by holding a
       value across the setjmp/longjmp boundary in a local variable that
       the compiler is likely to allocate into a callee-saved register
       under -O2 (it must be marked volatile to be guaranteed correct
       per the C standard's setjmp rules). */
    volatile int counter = 0;

    int rc = my_setjmp(env);
    counter++;

    if (rc == 0) {
        printf("first call: my_setjmp returned 0 (counter=%d)\n", counter);
        deep_one(1);
        printf("unreachable\n");
        return 1;
    }

    printf("resumed: my_setjmp returned %d (counter=%d)\n", rc, counter);

    if (counter == 2 && rc == 102) {
        printf("PASS\n");
        return 0;
    }
    printf("FAIL: expected counter=2, rc=102\n");
    return 1;
}
