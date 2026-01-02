print("Checking for get_element_by_id...")
if "get_element_by_id" in globals():
    print("Function exists")
    el = get_element_by_id("point_1")
    if el:
        print("Found element")
        el.set("fill", "brown")
        print("Set fill to brown")
    else:
        print("Element not found")
else:
    print("Function NOT in globals")
