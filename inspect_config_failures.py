import json

with open('eval_results.json') as f:
    data = json.load(f)

for case in data['per_case_results']:
    if 'config' in case['branch']:
        print(json.dumps(case, indent=2))
        print()