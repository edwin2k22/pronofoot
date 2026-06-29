import sys, os, json
sys.path.insert(0, os.path.abspath('.'))
from collector.http_cache import get_json

def main():
    data = get_json('https://worldcup26.ir/get/games', ttl=0)
    for g in data.get('games', []):
        if 'Brazil' in str(g) and 'Japan' in str(g):
            with open('scratch/brazil_japan.json', 'w', encoding='utf-8') as f:
                json.dump(g, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
