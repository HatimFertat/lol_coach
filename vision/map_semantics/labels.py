import json

bush_names = [
    "top-lane alcove brush",
    "top-lane Tier 1 brush (blue)",
    "top-lane Tier 1 brush (red)",
    "top-lane Tier 2 brush (blue)",
    "top-lane Tier 2 brush (red)",
    "bot-lane alcove brush",
    "bot-lane Tier 1 brush (blue)",
    "bot-lane Tier 1 brush (red)",
    "bot-lane Tier 2 brush (blue)",
    "bot-lane Tier 2 brush (red)",
    "Blue-buff brush (blue)",
    "Blue-buff brush (red)",
    "Red-buff brush (blue)",
    "Red-buff brush (red)",
    "top-lane tri-brush (blue)",
    "top-lane tri-brush (red)",
    "bot-lane tri-brush (blue)",
    "bot-lane tri-brush (red)",
    "Krugs-camp brush (blue)",
    "Krugs-camp brush (red)",
    "Raptor-camp brush (blue)",
    "Raptor-camp brush (red)",
    "Gromp-camp brush (blue)",
    "Gromp-camp brush (red)",
    "Behind wolf-camp brush (blue)",
    "Behind wolf-camp brush (red)",
    "Behind red-buff brush (blue)",
    "Behind red-buff brush (red)",
    "top-side river brush",
    "bot-side river brush",
    "top-side river pixel brush",
    "bot-side river pixel brush",
    "Mid-lane top-side river brush",
    "Mid-lane bot-side river brush",
    "top-side jungle brush (blue)",
    "top-side jungle brush (red)",
    "bot-side jungle brush (blue)",
    "bot-side jungle brush (red)",
    "top-side jungle entrance brush (red)",
    "bot-side jungle entrance brush (blue)",
]

structure_names = [
    "top-lane tier 1",
    "top-lane tier 2",
    "top-lane tier 3",
    "bot-lane tier 1",
    "bot-lane tier 2",
    "bot-lane tier 3",
    "mid-lane tier 1",
    "mid-lane tier 2",
    "mid-lane tier 3",
    "Nexus turret 1",
    "Nexus turret 2",
    "Nexus",
]

pits = [
    "Dragon pit",
    "Baron pit"
]

rivers = [
    "top-side river",
    "bot-side river",
    "west jungle",
    "east jungle",
    "north jungle",
    "south jungle",
    "botlane",
    "toplane",
    "midlane",
    "top-lane alcove",
    "bot-lane alcove"
]

camps = [
    "Wolf",
    "Gromp",
    "Krugs",
    "Raptor",
    "Blue-buff",
    "Red-buff"
]

symmetrical = [structure_names, camps]
non_symmetrical = [pits, rivers]

mapping_jungle_orientation = {"blueside top-side": "west",
           "blueside bot-side": "south",
           "redside top-side": "north",
           "redside bot-side": "east"}

output = []
start_id = 10001
start_attr_id = 20001

for i, name in enumerate(bush_names):
    #side is the content of parenthesis if there are at the end, otherwise it's neutral
    side = "neutral"
    if "(" in name and ")" in name:
        side = name.split("(")[1].split(")")[0]
    #remove (blue) or (red) from name
    name = side + "side " + name if side != "neutral" else name
    name = name.replace(" (blue)", "").replace(" (red)", "")
    #replace the prefix with the mapping_jungle_orientation if it matches
    for key, value in mapping_jungle_orientation.items():
        if key.lower() in name.lower():
            #remove from name
            print(key, '|', value, '|', name)
            name = name.replace(key, "")
            print(name)
            name = value + name
            break
    bush = {
        "name": f"{name}",
        "id": start_id + i,
        "color": "#83e070",
        "type": "any",
        "attributes": [
            {
                "id": start_attr_id + i,
                "name": "side",
                "input_type": "text",
                "mutable": False,
                "values": [side],
                "default_value": "neutral"
            }
        ]
    }
    output.append(bush)

start_id = 11001
start_attr_id = 21001

colors = {
    "blueside": "#32b7fa",
    "redside": "#fa3253",
    "neutral": "#fafa37",
    "river": "#33ddff",
}
for element in symmetrical:
    for i, name in enumerate(element):
        for side in ["blueside", "redside"]:
            color = colors[side]
            bush = {
                "name": f"{side + " " + name}",
                "id": start_id + i,
                "color": color,
                "type": "any",
                "attributes": [
                    {
                        "id": start_attr_id + i,
                        "name": "side",
                        "input_type": "text",
                        "mutable": False,
                        "values": [side],
                        "default_value": "neutral"
                    }
                ]
            }
            output.append(bush)

start_id = 101
start_attr_id = 201
for element in non_symmetrical:
    for i, name in enumerate(element):
        color = colors["river"] if "river" in name.lower() else colors["neutral"]
        bush = {
            "name": f"{name}",
            "id": start_id + i,
            "color": color,
            "type": "any",
            "attributes": [
                {
                    "id": start_attr_id + i,
                    "name": "side",
                    "input_type": "text",
                }
            ]
        }

# Save to JSON file or print
with open("bush_labels.json", "w") as f:
    json.dump(output, f, indent=2)
