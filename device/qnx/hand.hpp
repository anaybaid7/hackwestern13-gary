// hand.hpp - hand signals: a thumbs up or an OK sign is a Sniff Test, hands-free.
// The same rules as gary_hands.py, function for function. Plain C++, no OpenCV
// or TFLite, so it is tested on its own:
//   c++ -std=c++20 qnx/hand_test.cpp -o /tmp/hand_test && /tmp/hand_test
//
//   1. A palm detector finds the surest hand in the frame   (decode_palm)
//   2. A square around the whole hand, fingers up            (palm_roi, roi_matrix)
//   3. A second model finds 21 points on it; plain rules say
//      "like" (thumbs up), "ok" or nothing                   (gesture)
//   4. A signal in 3 of 5 frames arms Gary; he sniffs once
//      the hand has left the frame                           (Trigger)
//
// The two models are Google's MediaPipe hand models (Apache-2.0), unchanged:
// models/hand_detector.tflite and models/hand_landmarks_detector.tflite.
#pragma once
#include <algorithm>
#include <cmath>
#include <deque>
#include <string>

namespace hand {

constexpr int kPalmSize = 192;   // the palm detector's input, pixels
constexpr int kHandSize = 224;   // the 21-point model's input, pixels
constexpr int kAnchors = 2016;   // the palm detector's anchors
constexpr float kMinPalmScore = 0.5f;
constexpr float kMinHandScore = 0.5f;
constexpr double kGiveUp = 6.0;  // seconds: armed this long with the hand still up, Gary forgets it
constexpr double kQuiet = 2.0;   // seconds after a sniff before the next signal counts
constexpr double kPi = 3.14159265358979323846;

// Everything in 0..1 of the square the palm detector saw.
struct Palm {
  float cx = 0.f, cy = 0.f, w = 0.f, h = 0.f;
  float wrist_x = 0.f, wrist_y = 0.f, middle_x = 0.f, middle_y = 0.f;
};

// The square around the whole hand, in frame pixels. rot turns the crop so the fingers point up.
struct Roi {
  float cx = 0.f, cy = 0.f, size = 0.f, rot = 0.f;
};

// Centre of the palm detector's anchor i: a 24 x 24 grid with 2 anchors a
// cell, then a 12 x 12 grid with 6 (strides 8, 16, 16, 16).
inline void anchor(int i, float* x, float* y) {
  const int cell = i < 1152 ? i / 2 : (i - 1152) / 6;
  const int grid = i < 1152 ? 24 : 12;
  *x = (static_cast<float>(cell % grid) + 0.5f) / static_cast<float>(grid);
  *y = (static_cast<float>(cell / grid) + 0.5f) / static_cast<float>(grid);
}

inline float sigmoid(float v) { return 1.f / (1.f + std::exp(-std::clamp(v, -50.f, 50.f))); }

// One anchor's 18 raw numbers -> the palm: its box, the wrist and the middle finger's knuckle.
inline Palm decode_palm(const float* row, int i) {
  float ax = 0.f, ay = 0.f;
  anchor(i, &ax, &ay);
  const float s = static_cast<float>(kPalmSize);
  Palm p;
  p.cx = row[0] / s + ax;
  p.cy = row[1] / s + ay;
  p.w = row[2] / s;
  p.h = row[3] / s;
  p.wrist_x = row[4] / s + ax;
  p.wrist_y = row[5] / s + ay;
  p.middle_x = row[8] / s + ax;
  p.middle_y = row[9] / s + ay;
  return p;
}

// `side` is the padded square's width in pixels, `pad` what was added on the left and the top.
inline Roi palm_roi(const Palm& p, float side, float pad_x, float pad_y) {
  double rot = kPi / 2 - std::atan2(-static_cast<double>(p.middle_y - p.wrist_y),
                                    static_cast<double>(p.middle_x - p.wrist_x));
  rot -= 2 * kPi * std::floor((rot + kPi) / (2 * kPi));
  const float w = p.w * side, h = p.h * side;
  Roi r;
  r.cx = p.cx * side - pad_x + 0.5f * h * static_cast<float>(std::sin(rot));
  r.cy = p.cy * side - pad_y - 0.5f * h * static_cast<float>(std::cos(rot));
  r.size = 2.6f * std::max(w, h);
  r.rot = static_cast<float>(rot);
  return r;
}

// The 2 x 3 matrix (row by row in m) that takes a pixel of the out x out crop to the frame.
inline void roi_matrix(const Roi& r, double m[6], int out = kHandSize) {
  const double s = static_cast<double>(r.size) / out;
  const double c = std::cos(static_cast<double>(r.rot)) * s, n = std::sin(static_cast<double>(r.rot)) * s;
  const double half = out / 2.0;
  m[0] = c;
  m[1] = -n;
  m[2] = r.cx - half * c + half * n;
  m[3] = n;
  m[4] = c;
  m[5] = r.cy - half * n - half * c;
}

// pts: the 21 points in the crop, x at pts[stride * k] and y at pts[stride * k + 1]
// (the model gives x, y, z: stride 3). rot: the crop's turn (palm_roi).
// -> "like" (thumbs up), "ok", or "".
// Points: 0 wrist; thumb 1-4; index 5-8; middle 9-12; ring 13-16; pinky 17-20.
inline std::string gesture(const float* pts, int stride, float rot) {
  auto d = [pts, stride](int a, int b) {
    return std::hypot(static_cast<double>(pts[stride * a] - pts[stride * b]),
                      static_cast<double>(pts[stride * a + 1] - pts[stride * b + 1]));
  };
  const double palm = d(0, 9);
  if (palm < 1e-6) return "";
  // A finger is out when its tip is well past its middle joint, seen from the
  // wrist, and folded when the tip is nearer the wrist than that joint.
  const int joints[4][2] = {{6, 8}, {10, 12}, {14, 16}, {18, 20}};
  bool out[4], folded[4];
  int n_folded = 0, n_out = 0;
  for (int f = 0; f < 4; ++f) {
    const double reach = d(joints[f][1], 0) / std::max(d(joints[f][0], 0), 1e-6);
    out[f] = reach > 1.15;
    folded[f] = reach < 1.0;
    n_out += out[f] ? 1 : 0;
    n_folded += folded[f] ? 1 : 0;
  }

  // OK: thumb tip on the index tip, the other three fingers out.
  if (d(4, 8) < 0.30 * palm && out[1] && out[2] && !folded[3]) return "ok";

  // Thumbs up: four fingers folded, the thumb straight, clear of the fist, and
  // pointing up in the picture (not sideways, not down).
  if (n_folded >= 3 && n_out == 0) {
    const bool straight = d(2, 4) > 0.85 * (d(2, 3) + d(3, 4));
    const bool clear = d(4, 17) > 1.0 * palm && d(4, 5) > 0.45 * palm;
    const double tx = static_cast<double>(pts[stride * 4] - pts[stride * 2]);
    const double ty = static_cast<double>(pts[stride * 4 + 1] - pts[stride * 2 + 1]);
    const double up = -(std::sin(static_cast<double>(rot)) * tx + std::cos(static_cast<double>(rot)) * ty);
    if (straight && clear && up > 0.5 * std::hypot(tx, ty)) return "like";
  }
  return "";
}

// Frames of (signal, hand in view) -> the moment to sniff. A signal in `need`
// of the last `window` frames arms Gary. He sniffs when the hand has then been
// out of view for window - need + 1 frames: by then the hand cannot hide the
// thing in front of him, or be taken for a friend.
class Trigger {
 public:
  Trigger(int window, int need) : window_(std::max(1, window)), need_(std::clamp(need, 1, std::max(1, window))) {}

  // signal: "like", "ok" or "". hand: a hand is in view. now: seconds, any clock.
  // Returns true: sniff now. *note is set to "like" or "ok" when Gary is armed,
  // and to "forgot" when he gives up on a hand that stayed up.
  bool update(const std::string& signal, bool hand, double now, std::string* note = nullptr) {
    if (!armed_.empty()) {
      gone_ = hand ? 0 : gone_ + 1;
      if (gone_ >= window_ - need_ + 1) {
        armed_.clear();
        seen_.clear();
        quiet_until_ = now + kQuiet;
        return true;
      }
      if (now - armed_at_ > kGiveUp) {
        armed_.clear();
        seen_.clear();
        if (note) *note = "forgot";
      }
      return false;
    }
    seen_.push_back(signal);
    while (static_cast<int>(seen_.size()) > window_) seen_.pop_front();
    if (now < quiet_until_ || signal.empty()) return false;
    if (static_cast<int>(std::count(seen_.begin(), seen_.end(), signal)) < need_) return false;
    armed_ = signal;
    armed_at_ = now;
    gone_ = 0;
    if (note) *note = signal;
    return false;
  }

  const std::string& armed() const { return armed_; }

 private:
  int window_, need_;
  std::deque<std::string> seen_;
  std::string armed_;
  double armed_at_ = 0.0, quiet_until_ = 0.0;
  int gone_ = 0;
};

}  // namespace hand
