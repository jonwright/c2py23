int process_data(const double *data, int n, int stride, int verbose)
{
    int i;
    int result = 0;
    if (verbose) {
        /* side-effect to prove verbose was used */
        result += 1000;
    }
    for (i = 0; i < n; i += stride) {
        result += (int)data[i];
    }
    return result;
}
