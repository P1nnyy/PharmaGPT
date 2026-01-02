import os

env_path = ".env"
new_client_id = "595268657090-pmb0alv4chj31qanr92tssg82ubc77cl.apps.googleusercontent.com"
new_client_secret = "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"

# Read existing lines
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        lines = f.readlines()
else:
    lines = []

new_lines = []
keys_updated = {"GOOGLE_CLIENT_ID": False, "GOOGLE_CLIENT_SECRET": False}

for line in lines:
    key = line.split("=")[0].strip()
    if key == "GOOGLE_CLIENT_ID":
        new_lines.append(f'GOOGLE_CLIENT_ID="{new_client_id}"\n')
        keys_updated["GOOGLE_CLIENT_ID"] = True
    elif key == "GOOGLE_CLIENT_SECRET":
        new_lines.append(f'GOOGLE_CLIENT_SECRET="{new_client_secret}"\n')
        keys_updated["GOOGLE_CLIENT_SECRET"] = True
    else:
        new_lines.append(line)

# Append if not found
if not keys_updated["GOOGLE_CLIENT_ID"]:
    new_lines.append(f'GOOGLE_CLIENT_ID="{new_client_id}"\n')
if not keys_updated["GOOGLE_CLIENT_SECRET"]:
    new_lines.append(f'GOOGLE_CLIENT_SECRET="{new_client_secret}"\n')

with open(env_path, "w") as f:
    f.writelines(new_lines)

print("ENV_UPDATED_SUCCESSFULLY")
