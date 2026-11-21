// Checks yolo.hpp with a hand-made output. Run from device/:
//   c++ -std=c++20 -Wall -Wextra -Werror qnx/yolo_test.cpp -o /tmp/yolo_test && /tmp/yolo_test
#include <cassert>
#include <cstdio>

#include "yolo.hpp"

int main() {
  const std::vector<std::string> labels = {"person", "bottle", "tree"};
  const int A = 4, R = 7;  // 4 anchors, 4 box rows + 3 classes
  // anchor 0, 1: the same bottle twice, overlapping -> one bottle
  // anchor 2: a person beside it                    -> kept, another thing
  // anchor 3: a tree too faint to count             -> dropped
  const float boxes[A][4] = {{0.5f, 0.5f, 0.2f, 0.4f}, {0.51f, 0.5f, 0.2f, 0.4f}, {0.2f, 0.5f, 0.3f, 0.8f}, {0.8f, 0.2f, 0.1f, 0.1f}};
  const float scores[A][3] = {{0.f, 0.9f, 0.f}, {0.f, 0.8f, 0.f}, {0.7f, 0.f, 0.f}, {0.f, 0.f, 0.3f}};
  float rows_first[R * A], anchors_first[A * R];
  for (int a = 0; a < A; ++a)
    for (int r = 0; r < R; ++r) {
      const float v = r < 4 ? boxes[a][r] : scores[a][r - 4];
      rows_first[r * A + a] = v;
      anchors_first[a * R + r] = v;
    }
  for (bool af : {false, true}) {
    const auto got = decode_yolo(af ? anchors_first : rows_first, A, af, labels, 0.5f);
    assert(got.size() == 2);
    assert(got[0].label == "bottle" && got[0].score > 0.89f);
    assert(got[0].x0 > 0.39f && got[0].x0 < 0.41f && got[0].y1 > 0.69f && got[0].y1 < 0.71f);
    assert(got[1].label == "person");
  }
  // the nature model's name wins for the same box; a box elsewhere is kept
  const std::vector<Detection> ssd = {{"cat", 0.98f, 0.1f, 0.1f, 0.5f, 0.5f}, {"bottle", 0.9f, 0.6f, 0.6f, 0.9f, 0.9f}};
  const std::vector<Detection> nature = {{"squirrel", 0.7f, 0.12f, 0.1f, 0.5f, 0.52f}};
  const auto both = merge(ssd, nature);
  assert(both.size() == 2 && both[0].label == "bottle" && both[1].label == "squirrel");
  std::puts("yolo_test ok");
  return 0;
}
