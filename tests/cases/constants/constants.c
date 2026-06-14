double scale_and_sum(const double *data, int n, int factor)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * (double)factor;
    }
    return s;
}
