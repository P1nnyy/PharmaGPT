
import re

def test_regex():
    s = ".250"
    # Old regex
    old_match = re.search(r'-?\d+(\.\d+)?', s)
    if old_match:
        print(f"Old Regex match for '.250': {old_match.group()}")
    else:
        print("Old Regex no match")

    # New regex suggestion:
    # Matches:
    # 1. digits optional dot digits
    # 2. dot digits
    new_regex = r'-?(\d+\.\d+|\d+|\.\d+)'
    new_match = re.search(new_regex, s)
    if new_match:
        print(f"New Regex match for '.250': {new_match.group()}")
    else:
        print("New Regex no match")

    s2 = "2.75+.250"
    parts = s2.split('+')
    vals = []
    for p in parts:
        m = re.search(new_regex, p)
        if m:
            vals.append(float(m.group()))
    print(f"Parts parsed with new regex: {vals}, Sum: {sum(vals)}")

test_regex()
