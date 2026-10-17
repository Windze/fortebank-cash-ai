import sys
import os
import glob
from backend.detector import VideoAnalyzer

def main():
    analyzer = VideoAnalyzer()

    test_videos = [
        ('18', 'Нарушение - посторонние'),
        ('20', 'Нарушение - телефон'),
        ('15', 'Нарушение - сумка'),
        ('3', 'Без нарушения')
    ]

    candidates = glob.glob('open/videos/*')

    for target_num, label in test_videos:
        matches = [c for c in candidates if os.path.basename(c).split('.')[0].replace('X-','').replace('Х-','') == target_num]
        if not matches:
            print(f"File for {target_num} not found!")
            continue
        found = matches[0]
        print(f"\n==========================================")
        print(f"Testing {os.path.basename(found)} (Expected: {label})")
        res = analyzer.analyze_video(found)
        print(f"Result verdict: {res['verdict']}")
        print(f"Violations detected: {len(res['violations'])}")
        for v in res['violations']:
            print(f"  * {v['timecode_sec']}s: {v['type']}")
            if v['evidence_frames']:
                print(f"    Evidence frame length: {len(v['evidence_frames'][0]['image_base64'])} chars")

if __name__ == '__main__':
    main()
