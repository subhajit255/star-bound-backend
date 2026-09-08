from detection.pipeline import detect_image

res1 = detect_image("test_images/mole.jpg")
print("mole.jpg points:")
for p in res1.points:
    print(f"  x={p.x:.1f}, y={p.y:.1f}, score={p.score:.3f}")

res2 = detect_image("test_images/mole_2.jpg")
print("mole_2.jpg points:")
for p in res2.points:
    print(f"  x={p.x:.1f}, y={p.y:.1f}, score={p.score:.3f}")
