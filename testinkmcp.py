# @inkscape

x = []
for i in range(4):
    circle = inkex.Circle()
    circle.set("cx", f"{150 + i * 50}")
    circle.set("cy", "100")
    circle.set("r", "25")
    circle.set("fill", "none")
    circle.set("stroke", "red")
    svg.append(circle)
    x.append(circle.get("id"))

# @local
print("IDs from Inkscape:", x)
