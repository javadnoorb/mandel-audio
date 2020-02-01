import matplotlib.pyplot as plt
from matplotlib import colors
import numpy as np
import src.mandelbrot as mb

def mandelbrot_image(xmin, xmax, ymin, ymax, scale=1.0, width=3, height=3, maxiter=80, cmap='hot'):
    dpi = 72
    img_width = dpi * width
    img_height = dpi * height
    x,y,z = mb.mandelbrot_set(xmin, xmax, ymin, ymax, img_width, img_height, maxiter, scale=scale)
    
    fig, ax = plt.subplots(figsize=(width, height), dpi=72)
    ticks = np.arange(0,img_width,3*dpi)
    x_ticks = xmin + (xmax-xmin)*ticks/img_width
    plt.xticks(ticks, x_ticks)
    y_ticks = ymin + (ymax-ymin)*ticks/img_width
    plt.yticks(ticks, y_ticks)
    
    norm = colors.PowerNorm(0.3)
    ax.imshow(z.T,cmap=cmap,origin='lower',norm=norm)