void proc_a(float *p, int n, float val) {
    int i;
    for (i = 0; i < n; i++) {
        p[i] = val;
    }
}

void proc_b(float *p, int n, float val) {
    int i;
    for (i = 0; i < n; i++) {
        p[i] = val * 2.0f;
    }
}
