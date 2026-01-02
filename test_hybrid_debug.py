# Test hybrid execution - debug version
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
# Check what was created
print(f"Inkscape created: {inkscape_result['elements_created']}")
print(f"ID mapping: {inkscape_result['id_mapping']}")
print(f"Execution successful: {inkscape_result['execution_successful']}")

# @inkscape
# Debug: check if we can find the elements
print("Checking for elements in second block...")
for i in range(5):
    elem_id = f"point_{i}"
    el = svg.getElementById(elem_id)
    print(f"getElementById('{elem_id}'): {el}")
    if el:
        print(f"  Found! Tag: {el.tag}, ID: {el.get('id')}")
    else:
        print(f"  NOT FOUND!")

# @local
print("Debug output complete")
