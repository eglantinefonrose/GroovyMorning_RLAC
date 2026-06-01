import mlx.core as mx
import mlx.nn as nn

rope = nn.RoPE(32, traditional=True)
x = mx.zeros((1, 1, 1, 32))
try:
    y = rope(x, offset=8191)
    print("Offset 8191 OK")
    y = rope(x, offset=8192)
    print("Offset 8192 OK")
    y = rope(x, offset=10000)
    print("Offset 10000 OK")
except Exception as e:
    print(f"Failed: {e}")
