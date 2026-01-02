# Test if get_element_by_id exists in second block
import random

points = [(100, 100)]

# @inkscape
# Block 1
circle = Circle()
circle.set("id", "test1")
svg.append(circle)

# @local
print("Block 1 done")

# @inkscape
# Block 2
print("Has get_element_by_id:", "get_element_by_id" in dir())
print("Type:", type(get_element_by_id) if "get_element_by_id" in dir() else "NOT FOUND")

# Manual iteration
found_manual = None
for e in svg.iter():
    if e.get("id") == "test1":
        found_manual = e
        break

print("Manual iteration found:", found_manual is not None)

# Using helper
found_helper = get_element_by_id("test1")
print("Helper found:", found_helper is not None)

if found_manual and not found_helper:
    print("PROBLEM: Manual works but helper doesn't!")
