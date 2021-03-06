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
def mandelbrot_set_(xmin, xmax, ymin, ymax, width, height, maxiter):
    r1 = np.linspace(xmin, xmax, width)
    r2 = np.linspace(ymin, ymax, height)
    n3 = np.empty((width, height))
    for i in range(width):
        for j in range(height):
            n3[i,j] = mandelbrot(r1[i],r2[j], maxiter)
    return (r1,r2,n3)

def mandelbrot_set(x, y, unscaled_width=2.5, N=1000, maxiter=100, scale=0.0):
    L = unscaled_width * (2**-scale) / 2
    
    m = mandelbrot_set_(x-L, x+L, y-L, y+L, N, N, maxiter)
    return m