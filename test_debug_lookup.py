print("Testing element lookup...")
print("Looking for layer1...")
el = get_element_by_id("layer1")
print("layer1 found:", el is not None)

print("Looking for point_0...")
el = get_element_by_id("point_0") 
print("point_0 found:", el is not None)

print("Listing all IDs in document:")
for e in svg.iter():
    eid = e.get("id")
    if eid:
        print(f"  - {eid}")

print("Now trying to modify point_1...")
for e in svg.iter():
    if e.get("id") == "point_1":
        print("Found point_1 via iteration!")
        e.set("fill", "red")
        e.set("r", "20")
        print("Modified successfully")
        break
