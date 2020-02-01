from numba import jit
import numpy as np
from src.plotting import *

@jit
def mandelbrot(creal, cimag, maxiter):
    real = creal
    imag = cimag
    for n in range(maxiter):
        real2 = real*real
        imag2 = imag*imag
        if real2 + imag2 > 4.0:
            return n
        imag = 2* real*imag + cimag
        real = real2 - imag2 + creal       
    return 0


@jit
def mandelbrot_set(xmin, xmax, ymin, ymax, width, height, maxiter, scale=1.0):
    scale = np.float(scale)
    r1 = np.linspace(xmin / scale, xmax / scale, width)
    r2 = np.linspace(ymin / scale, ymax / scale, height)
    n3 = np.empty((width, height))
    for i in range(width):
        for j in range(height):
            n3[i,j] = mandelbrot(r1[i],r2[j], maxiter)
    return (r1,r2,n3)
