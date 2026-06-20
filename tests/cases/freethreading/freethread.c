/* Simple C function for free-threading test */
int double_it(const double *in, double *out, int n) {
    for (int i = 0; i < n; i++) out[i] = in[i] * 2.0;
    return n;
}
