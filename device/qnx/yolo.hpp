// yolo.hpp - read a YOLO detector's output (models/make_model.py) into
// Detections. Plain C++, no OpenCV or TFLite, so it is tested on its own:
//   c++ -std=c++20 qnx/yolo_test.cpp -o /tmp/yolo_test && /tmp/yolo_test
#pragma once
#include <algorithm>
#include <string>
#include <vector>

struct Detection {
  std::string label;
  float score = 0.f;
  float x0 = 0.f, y0 = 0.f, x1 = 0.f, y1 = 0.f;  // 0..1
};

inline float overlap(const Detection& a, const Detection& b) {
  const float w = std::min(a.x1, b.x1) - std::max(a.x0, b.x0);
  const float h = std::min(a.y1, b.y1) - std::max(a.y0, b.y0);
  if (w <= 0.f || h <= 0.f) return 0.f;
  const float both = w * h;
  return both / ((a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - both);
}

// Both detectors' finds. Where they box the same thing, the extra (nature)
// model's name wins: SSD calls a squirrel a cat.
inline std::vector<Detection> merge(std::vector<Detection> main, const std::vector<Detection>& extra,
                                    float iou = 0.5f) {
  std::vector<Detection> out;
  for (auto& m : main) {
    bool covered = false;
    for (const auto& e : extra) covered = covered || overlap(m, e) > iou;
    if (!covered) out.push_back(std::move(m));
  }
  out.insert(out.end(), extra.begin(), extra.end());
  return out;
}

// out: [4+K, A] row-major (rows = cx, cy, w, h in 0..1, then one score per
// class), or [A, 4+K] when anchors_first. Keeps each anchor's best class if it
// scores at least min_score, then drops any box that overlaps a stronger box
// of the same thing by more than iou. Strongest first.
inline std::vector<Detection> decode_yolo(const float* out, int anchors, bool anchors_first,
                                          const std::vector<std::string>& labels, float min_score,
                                          float iou = 0.5f) {
  const int rows = static_cast<int>(labels.size()) + 4;
  auto at = [&](int row, int a) { return anchors_first ? out[a * rows + row] : out[row * anchors + a]; };
  std::vector<std::pair<int, Detection>> found;  // class id, box
  for (int a = 0; a < anchors; ++a) {
    int best = 0;
    for (int c = 1; c + 4 < rows; ++c)
      if (at(c + 4, a) > at(best + 4, a)) best = c;
    const float score = at(best + 4, a);
    if (score < min_score) continue;
    const float cx = at(0, a), cy = at(1, a), w = at(2, a), h = at(3, a);
    found.push_back({best, {labels[static_cast<size_t>(best)], score, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2}});
  }
  std::sort(found.begin(), found.end(), [](const auto& p, const auto& q) { return p.second.score > q.second.score; });
  std::vector<Detection> kept;
  std::vector<int> kept_class;
  for (const auto& [cls, d] : found) {
    bool covered = false;
    for (size_t k = 0; k < kept.size() && !covered; ++k)
      covered = kept_class[k] == cls && overlap(kept[k], d) > iou;
    if (covered) continue;
    kept.push_back(d);
    kept_class.push_back(cls);
  }
  return kept;
}
