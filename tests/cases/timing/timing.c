double weighted_sum(const double *data, int n, double weight)
{
    int i;
    double s = 0.0;
    for (i = 0; i < n; i++) {
        s += data[i] * weight;
    }
    return s;
}
