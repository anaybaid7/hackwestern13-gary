// Checks hand.hpp with numbers from three real photos: the same numbers as
// test/hand_vectors.json, which tests/test_device.py feeds to gary_hands.py.
// So the Python Gary and the QNX Gary agree. Run from device/:
//   c++ -std=c++20 -Wall -Wextra -Werror qnx/hand_test.cpp -o /tmp/hand_test && /tmp/hand_test
// Written by a script from the photos' numbers; edit the rules in hand.hpp, not here.
#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>

#include "hand.hpp"

static bool near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

struct Case {
  int w, h, anchor;
  const char* signal;
  float row[18];
  float roi[4];
  double matrix[6];
  float points[63];
};

static const Case kCases[] = {
  {  // a thumbs up
    960, 720, 786, "like",
    {
      -0.1939f, -0.2645f, 25.347f, 25.3464f, -8.7637f, 2.7672f, 7.0636f, -5.8202f, 7.0432f,
      0.4324f, 7.0437f, 6.5324f, 6.959f, 12.5558f, -3.9086f, -5.3737f, 1.4698f, -13.0848f,
    },
    {441.716f, 529.418f, 329.511f, 1.424f},
    {0.21495, -1.45524, 580.62903, 1.45524, 0.21495, 342.35677},
    {
      116.71f, 182.8f, -0.0f, 90.66f, 163.02f, -3.13f, 70.73f, 139.8f, -7.71f,
      52.88f, 120.94f, -11.64f, 32.2f, 117.34f, -14.94f, 96.48f, 125.23f, -12.94f,
      110.75f, 83.94f, -16.34f, 105.78f, 99.05f, -15.95f, 101.23f, 114.9f, -15.08f,
      123.39f, 129.23f, -12.93f, 129.21f, 88.98f, -15.09f, 121.96f, 101.46f, -13.02f,
      119.14f, 116.7f, -11.83f, 144.79f, 133.27f, -12.51f, 145.97f, 97.27f, -12.84f,
      139.62f, 107.44f, -9.01f, 137.28f, 121.37f, -7.1f, 161.73f, 136.23f, -12.28f,
      160.38f, 107.54f, -11.54f, 154.47f, 115.84f, -8.18f, 152.57f, 126.78f, -6.2f,
    },
  },
  {  // an OK sign
    500, 400, 639, "ok",
    {
      -1.8078f, -0.0915f, 35.3388f, 35.2843f, -11.0873f, 18.046f, 0.1052f, -18.1182f, -4.7409f,
      -17.3965f, -8.8068f, -16.0625f, -12.3366f, -14.1781f, -0.7647f, 9.845f, 9.8127f, 1.785f,
    },
    {159.64f, 185.788f, 239.273f, 0.177f},
    {1.05146, -0.18828, 62.96348, 0.18828, 1.05146, 46.93743},
    {
      114.05f, 196.48f, 0.0f, 133.14f, 175.66f, -2.86f, 148.6f, 151.18f, -5.65f,
      166.12f, 135.02f, -9.02f, 177.32f, 116.57f, -12.12f, 109.26f, 118.07f, -1.27f,
      132.27f, 93.32f, -9.2f, 152.6f, 96.78f, -15.73f, 167.18f, 106.98f, -18.84f,
      100.39f, 112.47f, -3.51f, 109.29f, 73.16f, -8.4f, 121.42f, 46.35f, -12.8f,
      131.75f, 25.13f, -15.61f, 90.29f, 115.89f, -6.94f, 89.81f, 76.48f, -11.89f,
      93.48f, 48.99f, -15.56f, 98.38f, 27.4f, -17.44f, 80.79f, 126.83f, -10.69f,
      71.83f, 97.6f, -14.41f, 66.98f, 74.92f, -15.59f, 64.94f, 56.38f, -15.95f,
    },
  },
  {  // an open hand
    960, 720, 1677, "",
    {
      13.5967f, 0.2609f, 81.8473f, 81.8477f, 5.8657f, 33.9246f, 9.2864f, -28.333f, 19.3459f,
      -30.8004f, 26.6776f, -27.7787f, 31.7487f, -22.2082f, -2.5509f, 28.9355f, -5.9409f, 7.547f,
    },
    {389.704f, 280.984f, 1064.02f, 0.205f},
    {4.6503, -0.96851, -22.65653, 0.96851, 4.6503, -348.32396},
    {
      87.99f, 205.12f, 0.0f, 60.91f, 176.74f, -11.76f, 56.71f, 140.22f, -17.64f,
      57.67f, 110.38f, -21.91f, 51.67f, 82.12f, -26.35f, 114.31f, 114.64f, -13.32f,
      145.47f, 83.81f, -20.41f, 161.69f, 66.49f, -25.96f, 174.75f, 51.7f, -30.03f,
      133.34f, 128.6f, -11.89f, 168.25f, 95.69f, -18.62f, 188.83f, 75.42f, -23.66f,
      205.79f, 58.43f, -27.53f, 146.06f, 147.5f, -11.65f, 175.42f, 117.16f, -18.92f,
      194.6f, 98.61f, -22.85f, 211.09f, 82.25f, -25.33f, 154.56f, 168.83f, -12.29f,
      176.52f, 147.53f, -18.87f, 191.07f, 132.01f, -21.76f, 204.2f, 116.48f, -23.69f,
    },
  },
};

int main() {
  // the palm detector's anchors: 24 x 24 cells of 2, then 12 x 12 cells of 6
  float ax = 0.f, ay = 0.f;
  hand::anchor(0, &ax, &ay);
  assert(near(ax, 0.5 / 24, 1e-6) && near(ay, 0.5 / 24, 1e-6));
  hand::anchor(1151, &ax, &ay);
  assert(near(ax, 23.5 / 24, 1e-6) && near(ay, 23.5 / 24, 1e-6));
  hand::anchor(1152, &ax, &ay);
  assert(near(ax, 0.5 / 12, 1e-6) && near(ay, 0.5 / 12, 1e-6));
  hand::anchor(2015, &ax, &ay);
  assert(near(ax, 11.5 / 12, 1e-6) && near(ay, 11.5 / 12, 1e-6));
  assert(near(hand::sigmoid(0.f), 0.5, 1e-6) && hand::sigmoid(100.f) > 0.99f && hand::sigmoid(-100.f) < 0.01f);

  for (const Case& c : kCases) {
    const float side = static_cast<float>(c.w > c.h ? c.w : c.h);
    const hand::Palm palm = hand::decode_palm(c.row, c.anchor);
    const hand::Roi roi = hand::palm_roi(palm, side, (side - static_cast<float>(c.w)) / 2.f,
                                         (side - static_cast<float>(c.h)) / 2.f);
    assert(near(roi.cx, c.roi[0], 0.1) && near(roi.cy, c.roi[1], 0.1));
    assert(near(roi.size, c.roi[2], 0.1) && near(roi.rot, c.roi[3], 1e-3));
    double m[6];
    hand::roi_matrix(roi, m);
    for (int k = 0; k < 6; ++k) assert(near(m[k], c.matrix[k], k % 3 == 2 ? 0.2 : 1e-3));
    // the crop's middle is the square's middle
    assert(near(m[0] * 112 + m[1] * 112 + m[2], roi.cx, 1e-3) && near(m[3] * 112 + m[4] * 112 + m[5], roi.cy, 1e-3));
    assert(hand::gesture(c.points, 3, roi.rot) == std::string(c.signal));
    // The same hand turned upside down or on its side is not a thumbs up: the thumb must point up.
    if (std::string(c.signal) == "like") {
      assert(hand::gesture(c.points, 3, roi.rot + static_cast<float>(hand::kPi)).empty());
      assert(hand::gesture(c.points, 3, roi.rot + static_cast<float>(hand::kPi / 2)).empty());
    }
  }
  const float nothing[63] = {};
  assert(hand::gesture(nothing, 3, 0.f).empty());  // no hand at all: no signal, no crash

  // Three thumbs up arm Gary; he sniffs when the hand has been gone for three frames.
  {
    hand::Trigger t(5, 3);
    std::string note;
    assert(!t.update("like", true, 0.0, &note) && !t.update("like", true, 0.1, &note) && note.empty());
    assert(!t.update("like", true, 0.2, &note) && note == "like" && t.armed() == "like");
    assert(!t.update("like", true, 0.3) && !t.update("", true, 0.4));       // still up, or changing: wait
    assert(!t.update("", false, 0.5) && !t.update("", false, 0.6));        // lowered: two frames
    assert(!t.update("", true, 0.7));                                       // back in view: start again
    assert(!t.update("", false, 0.8) && !t.update("", false, 0.9));
    assert(t.update("", false, 1.0) && t.armed().empty());                  // gone for three: sniff, once
    assert(!t.update("", false, 1.1));
    // for two seconds after a sniff no signal counts
    note.clear();
    assert(!t.update("like", true, 1.2, &note) && !t.update("like", true, 1.3, &note));
    assert(!t.update("like", true, 1.4, &note) && note.empty() && t.armed().empty());
    assert(!t.update("like", true, 3.1, &note) && note == "like");
  }
  // A flicker is enough (3 of 5); two signals mixed are not.
  {
    hand::Trigger t(5, 3);
    std::string note;
    t.update("ok", true, 0.0, &note);
    t.update("", true, 0.1, &note);
    t.update("ok", true, 0.2, &note);
    t.update("", true, 0.3, &note);
    assert(note.empty());
    t.update("ok", true, 0.4, &note);
    assert(note == "ok");
    hand::Trigger mixed(5, 3);
    note.clear();
    for (int k = 0; k < 4; ++k) mixed.update(k % 2 ? "ok" : "like", true, 0.1 * k, &note);
    assert(note.empty() && mixed.armed().empty());
  }
  // A hand that stays up is forgotten, and lowering it later is not a sniff.
  {
    hand::Trigger t(5, 3);
    std::string note;
    for (int k = 0; k < 3; ++k) t.update("like", true, 0.1 * k, &note);
    assert(t.armed() == "like");
    assert(!t.update("like", true, 5.0, &note) && t.armed() == "like");
    assert(!t.update("like", true, 6.5, &note) && note == "forgot" && t.armed().empty());
    for (int k = 0; k < 5; ++k) assert(!t.update("", false, 7.0 + 0.1 * k));
  }
  printf("hand.hpp: ok\n");
  return 0;
}
