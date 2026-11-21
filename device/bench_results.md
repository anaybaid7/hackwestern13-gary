## Model benchmark: gary_detector.tflite

Median 17 ms a photo on this machine.

| Thing | Photos | Hit at 0.3 | 0.4 | 0.5 | Median score when right | Most common wrong answer | SSD at 0.5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| butterfly | 8 | 100% | 100% | 100% | 0.85 | - | can't name it |
| squirrel | 8 | 88% | 88% | 88% | 0.87 | nothing (1) | can't name it |
| tree | 8 | 88% | 88% | 88% | 0.73 | flower (1) | can't name it |
| bicycle | 8 | 75% | 75% | 75% | 0.83 | nothing (2) | 75% |
| flower | 7 | 86% | 71% | 71% | 0.67 | too faint (1) | can't name it |
| rabbit | 7 | 71% | 71% | 71% | 0.75 | too faint (1) | can't name it |
| bird | 8 | 88% | 75% | 62% | 0.69 | too faint (2) | 100% |
| duck | 10 | 60% | 60% | 60% | 0.65 | goose (2) | can't name it |
| deer | 9 | 67% | 56% | 56% | 0.61 | tree (2) | can't name it |
| cup | 8 | 88% | 75% | 50% | 0.53 | too faint (3) | 62% |
| street lamp | 10 | 50% | 40% | 40% | 0.65 | tree (2) | can't name it |
| bottle | 8 | 62% | 38% | 38% | 0.47 | too faint (3) | 38% |
| mushroom | 10 | 30% | 30% | 30% | 0.79 | nothing (4) | can't name it |
| bench | 8 | 25% | 25% | 25% | 0.51 | nothing (3) | 38% |
| dog | 8 | 62% | 50% | 25% | 0.50 | too faint (3) | 50% |
| trash can | 4 | 25% | 25% | 25% | 0.41 | tree (3) | can't name it |
| goose | 9 | 44% | 44% | 11% | 0.47 | bird (4) | can't name it |
| backpack | 3 | 0% | 0% | 0% | - | nothing (2) | 0% |

Overall at 0.5: 74 of 141 photos (52%).

SSD MobileNet v2: median 12 ms a photo.
