// Stand-ins for TFLite and the QNX camera, so gary_qnx.cpp can be built and
// exercised on a Linux laptop. Used only by host_test/run.sh. Never on the Pi.
//
// The pretend model follows a script by run number (one run per frame):
//   runs   1-29   a bottle
//   runs  30-59   a backpack (plus a class the label file marks n/a)
//   runs  60-61   a laptop for two frames only: too brief to count
//   runs  62-89   nothing
//   runs  90+     a laptop and a person, plus a bottle too weak to count
//
// Environment:
//   GARY_FAKE_PRESSES=15,45,75   press the button on those runs
//   GARY_FAKE_QUIT=130           stop Gary on that run
//   GARY_FAKE_MODEL_MS=12        how long the pretend model takes
//   GARY_FAKE_FRAME_MS=33        time between pretend camera frames
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <set>
#include <string>
#include <thread>
#include <unistd.h>

#include <opencv2/core.hpp>

#include "rpi_cam.hpp"
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/interpreter_builder.h"
#include "tensorflow/lite/model_builder.h"

static int env_int(const char* name, int fallback) {
  const char* v = std::getenv(name);
  return v && *v ? std::atoi(v) : fallback;
}

static std::set<long> env_list(const char* name) {
  std::set<long> out;
  const char* v = std::getenv(name);
  std::string item;
  for (const char* p = v ? v : ""; ; ++p) {
    if (*p == ',' || *p == '\0') {
      if (!item.empty()) out.insert(std::atol(item.c_str()));
      item.clear();
      if (*p == '\0') break;
    } else {
      item.push_back(*p);
    }
  }
  return out;
}

namespace tflite {
Interpreter::Interpreter() {
  input_.assign(300 * 300 * 3, 0);
  out_[0].assign(20 * 4, 0.f);
  out_[1].assign(20, 0.f);
  out_[2].assign(20, 0.f);
  out_[3].assign(1, 0.f);
  in_dims_ = {4, {1, 300, 300, 3}};
  in_t_ = {kTfLiteUInt8, &in_dims_};
  out_dims_[0] = {3, {1, 20, 4}};
  out_dims_[1] = {2, {1, 20}};
  out_dims_[2] = {2, {1, 20}};
  out_dims_[3] = {1, {1}};
  for (int i = 0; i < 4; ++i) out_t_[i] = {kTfLiteFloat32, &out_dims_[i]};
  in_ids_ = {0};
  out_ids_ = {1, 2, 3, 4};
}
TfLiteStatus Interpreter::AllocateTensors() { return kTfLiteOk; }
TfLiteStatus Interpreter::Invoke() {
  static const int model_ms = env_int("GARY_FAKE_MODEL_MS", 12);
  static const std::set<long> presses = env_list("GARY_FAKE_PRESSES");
  static const long quit_at = env_int("GARY_FAKE_QUIT", -1);
  usleep(static_cast<useconds_t>(model_ms) * 1000);
  const long f = frame_++;  // run 0 is Gary's warm-up
  auto set = [&](int slot, int cls, float score) {
    out_[1][slot] = static_cast<float>(cls);
    out_[2][slot] = score;
    out_[0][slot * 4 + 0] = 0.1f;
    out_[0][slot * 4 + 1] = 0.2f;
    out_[0][slot * 4 + 2] = 0.6f;
    out_[0][slot * 4 + 3] = 0.7f;
  };
  // Class ids are line numbers in models/coco_labels.txt, counted from 0.
  if (f < 30) { set(0, 43, 0.91f); out_[3][0] = 1; }                               // bottle
  else if (f < 60) { set(0, 26, 0.88f); set(1, 11, 0.99f); out_[3][0] = 2; }       // backpack + n/a
  else if (f < 62) { set(0, 72, 0.95f); out_[3][0] = 1; }                          // laptop, 2 frames
  else if (f < 90) { out_[3][0] = 0; }                                             // nothing
  else { set(0, 72, 0.93f); set(1, 0, 0.8f); set(2, 43, 0.2f); out_[3][0] = 3; }   // laptop + person
  if (presses.count(f)) raise(SIGUSR1);  // the button
  if (f == quit_at) raise(SIGINT);
  return kTfLiteOk;
}
std::unique_ptr<FlatBufferModel> FlatBufferModel::BuildFromFile(const char* filename) {
  if (access(filename, R_OK) != 0) return nullptr;
  return std::make_unique<FlatBufferModel>();
}
TfLiteStatus InterpreterBuilder::operator()(std::unique_ptr<Interpreter>* interpreter) {
  *interpreter = std::make_unique<Interpreter>();
  return kTfLiteOk;
}
TfLiteStatus InterpreterBuilder::operator()(std::unique_ptr<Interpreter>* interpreter, int) {
  return (*this)(interpreter);
}
}  // namespace tflite

static std::thread g_thread;
static std::atomic<bool> g_on{false};
RpiCam::RpiCam(camera_unit_t camera_id) : id_(camera_id) {}
int RpiCam::init() {
  width_ = 1280;
  height_ = 720;
  return EOK;
}
int RpiCam::start(FrameCb callback) {
  cb_ = callback;
  g_on = true;
  g_thread = std::thread([this] {
    const int frame_ms = env_int("GARY_FAKE_FRAME_MS", 33);
    while (g_on) {
      cv::Mat img(height_, width_, CV_8UC3, cv::Scalar(30, 60, 90));
      cb_(img);
      std::this_thread::sleep_for(std::chrono::milliseconds(frame_ms));
    }
  });
  return EOK;
}
int RpiCam::stop() {
  g_on = false;
  if (g_thread.joinable()) g_thread.join();
  return EOK;
}
std::pair<int, int> RpiCam::get_frame_size() const { return {width_, height_}; }
void RpiCam::cam_cb(camera_handle_t, camera_buffer_t*, void*) {}
