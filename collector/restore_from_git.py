import sys, json, subprocess

# 1. Load OLD predictions (before today's ingestion)
out = subprocess.check_output(['git', 'show', '6cf3bb1:collector/data/predictions.json'])
old_data = json.loads(out.decode('utf-8'))
old_map = { f"{m['home']} - {m['away']}": m for m in old_data }

# 2. Load NEW predictions (current file)
import os
path = r'c:\Users\zakro\ZCodeProject\collector\data\predictions.json'
with open(path, 'r', encoding='utf-8') as f:
    new_data = json.load(f)

# 3. Merge: Restore old predictions but keep new results
restored_data = []
for nm in new_data:
    key = f"{nm['home']} - {nm['away']}"
    if key in old_map:
        # We take the old match as base (all old probabilities, predictions, stats)
        merged = old_map[key].copy()
        # We bring over the ACTUAL match results from the new file
        merged['status'] = nm.get('status', merged.get('status'))
        merged['realScore'] = nm.get('realScore')
        merged['liveScore'] = nm.get('liveScore')
        merged['liveClock'] = nm.get('liveClock')
        merged['htScore'] = nm.get('htScore')
        merged['analysis'] = nm.get('analysis')
        restored_data.append(merged)
    else:
        # Match wasn't predicted previously, keep the new one
        restored_data.append(nm)

# 4. Save merged file
with open(path, 'w', encoding='utf-8') as f:
    json.dump(restored_data, f, ensure_ascii=False, indent=2)

print(f'Successfully restored predictions for {len(restored_data)} matches from commit 6cf3bb1!')
