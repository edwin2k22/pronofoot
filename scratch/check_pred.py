import json

def main():
    try:
        with open('old_predictions.json', encoding='utf-8') as f:
            old = json.load(f)
            p_old = [m for m in old if m['home'] == 'Brazil' and m['away'] == 'Japan']
            pred = p_old[0]['prediction']
            print("OLD:")
            print("  score_exact:", pred['score_exact'])
            print("  dixonColes:", pred.get('dixonColes'))
            print("  ensemble:", pred.get('ensemble'))
    except Exception:
        pass

    try:
        with open('collector/data/predictions.json', encoding='utf-8') as f:
            new = json.load(f)
            p_new = [m for m in new if m['home'] == 'Brazil' and m['away'] == 'Japan']
            pred = p_new[0]['prediction']
            print("\nNEW:")
            print("  score_exact:", pred['score_exact'])
            print("  dixonColes:", pred.get('dixonColes'))
            print("  ensemble:", pred.get('ensemble'))
    except Exception:
        pass

if __name__ == '__main__':
    main()
