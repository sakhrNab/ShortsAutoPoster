# utils.py

def create_gradient(color_start, color_end, length):
    r1, g1, b1 = color_start
    r2, g2, b2 = color_end
    gradient = []
    for i in range(length):
        ratio = i / max(length - 1, 1)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        gradient.append((r, g, b))
    return gradient
