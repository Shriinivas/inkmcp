# Test hybrid execution
import random

# Generate some random points
points = [(random.randint(10, 200), random.randint(10, 200)) for _ in range(5)]
print(f"Generated {len(points)} random points")

# @inkscape
# Create circles at each point
for i, (x, y) in enumerate(points):
    circle = Circle()
    circle.set("id", f"point_{i}")
    circle.set("cx", str(x))
    circle.set("cy", str(y))
    circle.set("r", "10")
    circle.set("fill", "blue")
    svg.append(circle)

# @local
print(f"Created {len(points)} circles")

# Prepare colors for modification
colors = ["red", "green", "brown", "yellow", "purple"]

# @inkscape
# Modify the circles with different colors using helper function
for i, color in enumerate(colors):
    elem = get_element_by_id(f"point_{i}")
    if elem is not None:
        elem.set("fill", color)
        elem.set("r", "15")
        print(f"Set point_{i} to {color}")

# @local
print("Modified circles with different colors")
print("Test completed!")
