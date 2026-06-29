import mlx.core as mx
import mlx.nn as nn

def test():
    rope = nn.RoPE(32, traditional=True)
    # The table might be precomputed on first call or fixed.
    # In some versions, it's [8192, 32]
    x = mx.zeros((1, 1, 2, 32))
    try:
        y = rope(x, offset=8191)
        mx.eval(y)
        print("Offset 8191, len 2: OK")
    except Exception as e:
        print(f"Offset 8191, len 2: FAILED: {e}")

    try:
        y = rope(x, offset=8192)
        mx.eval(y)
        print("Offset 8192, len 2: OK")
    except Exception as e:
        print(f"Offset 8192, len 2: FAILED: {e}")

if __name__ == "__main__":
    test()
