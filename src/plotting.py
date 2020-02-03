import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np
import src.mandelbrot as mb

def mandelbrot_image(x, y, width=7, height=7, unscaled_width=2.5, N=1000, maxiter=100, scale=0.0, cmap='hot', dpi = 72):
    img_width = dpi * width
    img_height = dpi * height
    x,y,z = mb.mandelbrot_set(x, y, unscaled_width=unscaled_width, N=N, maxiter=maxiter, scale=scale)

    fig, ax = plt.subplots(figsize=(width, height), dpi=dpi)
#     ticks = np.arange(0,img_width,3*dpi)
#     x_ticks = xmin + (xmax-xmin)*ticks/img_width
#     plt.xticks(ticks, x_ticks/scale)
#     y_ticks = ymin + (ymax-ymin)*ticks/img_width
#     plt.yticks(ticks, y_ticks/scale)
    plt.axis('off')
    norm = colors.PowerNorm(0.3)
    ax.imshow(z.T, cmap=cmap, origin='lower', norm=norm)