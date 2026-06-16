#include <stdlib.h>
#include "../kissfft/kiss_fft.h"
#include "../kissfft/kiss_fftr.h"

void kissfft_rfft_forward(const float *data, float *spec, int n) {
    kiss_fftr_cfg cfg = kiss_fftr_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fftr(cfg, data, (kiss_fft_cpx *)spec);
        free(cfg);
    }
}

void kissfft_cfft_forward(const float *fin, float *fout, int n) {
    kiss_fft_cfg cfg = kiss_fft_alloc(n, 0, NULL, NULL);
    if (cfg) {
        kiss_fft(cfg, (const kiss_fft_cpx *)fin, (kiss_fft_cpx *)fout);
        free(cfg);
    }
}
