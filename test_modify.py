for e in svg.iter():
    if e.get("id") == "point_0":
        e.set("fill", "red")
        e.set("r", "20")
        print("Modified point_0")
        break
