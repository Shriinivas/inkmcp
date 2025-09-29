for i in range(3):
    print(f"Creating circle {i}")
    circle = inkex.Circle()
    circle.set("cx", str(i*70 + 50))
    circle.set("cy", "150")
    circle.set("r", "20")
    circle.set("fill", ["red", "green", "blue"][i])
    svg.append(circle)

print("Created 3 colored circles!")