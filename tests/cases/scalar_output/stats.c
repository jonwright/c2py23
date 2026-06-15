void stats(const double *data, int n, double *minval, double *maxval)
{
    int i;
    double mn = data[0];
    double mx = data[0];
    for (i = 1; i < n; i++) {
        if (data[i] < mn) mn = data[i];
        if (data[i] > mx) mx = data[i];
    }
    *minval = mn;
    *maxval = mx;
}
