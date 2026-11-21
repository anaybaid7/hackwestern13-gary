## Model benchmark: gary_world.tflite

Median 17 ms a photo on this machine.

| Thing | Photos | Hit at 0.3 | 0.4 | 0.5 | Median score when right | Most common wrong answer | SSD at 0.5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| street lamp | 10 | 90% | 90% | 90% | 0.91 | clock (1) | can't name it |
| bird | 8 | 100% | 100% | 88% | 0.84 | too faint (1) | 100% |
| bicycle | 8 | 75% | 75% | 75% | 0.85 | nothing (1) | 75% |
| bottle | 7 | 71% | 71% | 57% | 0.86 | vase (2) | 29% |
| bench | 8 | 50% | 50% | 50% | 0.85 | couch (1) | 38% |
| trash can | 4 | 50% | 50% | 50% | 0.63 | too faint (1) | can't name it |
| flower | 7 | 71% | 71% | 43% | 0.56 | too faint (2) | can't name it |
| dog | 8 | 75% | 62% | 38% | 0.50 | too faint (3) | 50% |
| tree | 8 | 50% | 38% | 12% | 0.32 | too faint (6) | can't name it |

Overall at 0.5: 39 of 68 photos (57%).

SSD MobileNet v2: median 12 ms a photo.
