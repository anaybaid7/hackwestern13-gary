// gary_qnx.cpp - Gary the Goat device loop for QNX 8 on a Raspberry Pi 5.
//
//   QNX Camera API -> TFLite object detector -> SNIFF TEST -> journal + sound
//
// The camera and the model run all the time, so Gary always knows what is in
// view. Nothing is recorded until someone presses the button. That press is
// the Sniff Test: Gary names what he sees, writes one line in journal.jsonl,
// and reacts. A friend in the frame marks the find as Herd Mode.
//
// Camera capture uses the RpiCam wrapper from QNX's AI workshop (Apache-2.0):
//   https://github.com/qnx/QNX-AI-workshop
// The TFLite calls are the ones that workshop's handtracking.cpp uses.
//
// It reads and writes the same files as gary_device.py, so the two versions
// are interchangeable. Each journal line is an Event from contract/README.md.
// The device records facts only: XP, stages and the map belong to the backend.
//
// Run it from the device folder (the one that holds models/ and quests.tsv):
//   ./qnx/build/gary                          camera unit 5 = USB webcam
//   ./qnx/build/gary --image test/pets.jpg    model self-test, no camera
// Keys:  Enter = Sniff Test,  q + Enter = quit.
// From another program:
//   kill -USR1 $(cat gary.pid)   Sniff Test (how a hardware button is wired in)
//   kill -HUP  $(cat gary.pid)   reload quests.tsv (sync.py does this)
//
// Threads:
//   camera thread  - owned by the camera library; shrinks each frame and
//                    leaves the newest one in a one-slot handoff
//   main thread    - runs the model and answers every sniff
//   audio thread   - plays queued clips, so sound never delays an answer
//   key thread     - watches stdin for Enter / q

#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <deque>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#if __has_include(<opencv2/imgcodecs.hpp>)
#include <opencv2/imgcodecs.hpp>
#define GARY_HAS_IMGCODECS 1
#endif

#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/interpreter_builder.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/model_builder.h"

#include "rpi_cam.hpp"
#include "yolo.hpp"  // Detection, decode_yolo

#ifndef EOK
#define EOK 0
#endif

extern char** environ;

using Clock = std::chrono::steady_clock;

static double ms_between(Clock::time_point a, Clock::time_point b) {
  return std::chrono::duration<double, std::milli>(b - a).count();
}

// ---------------------------------------------------------------------------
// Detector: a TFLite model of either kind
//   SSD, four outputs: 0 boxes [1,N,4] (ymin,xmin,ymax,xmax in 0..1)
//                      1 classes [1,N]   2 scores [1,N]   3 count [1]
//   YOLO (models/make_model.py), one output [1, 4+K, A]; see yolo.hpp
// Input [1,H,W,3] or [1,3,H,W], uint8 or float32.
// ---------------------------------------------------------------------------

class Detector {
 public:
  bool load(const std::string& model_path, const std::string& labels_path, int threads) {
    std::ifstream lf(labels_path);
    if (!lf) {
      fprintf(stderr, "error: cannot open labels file %s\n", labels_path.c_str());
      fprintf(stderr, "       run Gary from the project folder, the one that holds models/\n");
      return false;
    }
    for (std::string line; std::getline(lf, line);) {
      while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
      labels_.push_back(line);
    }

    model_ = tflite::FlatBufferModel::BuildFromFile(model_path.c_str());
    if (!model_) {
      fprintf(stderr, "error: cannot load model %s\n", model_path.c_str());
      return false;
    }
    tflite::ops::builtin::BuiltinOpResolverWithXNNPACK resolver;
    if (tflite::InterpreterBuilder(*model_, resolver)(&interp_, std::max(1, threads)) != kTfLiteOk ||
        !interp_) {
      fprintf(stderr, "error: cannot build an interpreter for %s\n", model_path.c_str());
      return false;
    }
    if (interp_->AllocateTensors() != kTfLiteOk) {
      fprintf(stderr, "error: AllocateTensors failed\n");
      return false;
    }

    const TfLiteTensor* in = interp_->input_tensor(0);
    if (!in || !in->dims || in->dims->size != 4 || (in->dims->data[3] != 3 && in->dims->data[1] != 3)) {
      fprintf(stderr, "error: model input is not [1,H,W,3] or [1,3,H,W]\n");
      return false;
    }
    nchw_ = in->dims->data[3] != 3;
    in_h = in->dims->data[nchw_ ? 2 : 1];
    in_w = in->dims->data[nchw_ ? 3 : 2];
    if (in->type == kTfLiteFloat32) {
      float_input_ = true;
    } else if (in->type == kTfLiteUInt8) {
      float_input_ = false;
    } else {
      fprintf(stderr, "error: model input must be uint8 or float32\n");
      return false;
    }

    if (interp_->outputs().size() == 1) {
      const TfLiteTensor* o = interp_->output_tensor(0);
      const int rows = static_cast<int>(labels_.size()) + 4;
      if (!o || !o->dims || o->dims->size != 3 || o->type != kTfLiteFloat32 ||
          (o->dims->data[1] != rows && o->dims->data[2] != rows)) {
        fprintf(stderr, "error: the YOLO output does not match %s (%zu names, so %d rows)\n",
                labels_path.c_str(), labels_.size(), rows);
        return false;
      }
      yolo_ = true;
      anchors_first_ = o->dims->data[1] != rows;
      capacity_ = anchors_first_ ? o->dims->data[1] : o->dims->data[2];
    } else if (interp_->outputs().size() < 4) {
      fprintf(stderr, "error: model has neither 1 (YOLO) nor 4 (SSD) detection outputs\n");
      return false;
    }
    const TfLiteTensor* boxes = yolo_ ? nullptr : interp_->output_tensor(0);
    const TfLiteTensor* scores = yolo_ ? nullptr : interp_->output_tensor(2);
    const bool boxes_ok = boxes && boxes->dims && boxes->dims->size == 3 && boxes->dims->data[2] == 4;
    const bool scores_ok = scores && scores->dims && scores->dims->size == 2;
    if (!yolo_ && (!boxes_ok || !scores_ok)) {
      fprintf(stderr, "error: model outputs are not in the order boxes, classes, scores, count\n");
      return false;
    }
    if (!yolo_) capacity_ = scores->dims->data[1];
    if (capacity_ <= 0) return false;

    // One throwaway run, so the first real frame is not slowed by lazy setup.
    const size_t in_bytes = static_cast<size_t>(in_w) * in_h * 3 * (float_input_ ? sizeof(float) : 1);
    void* in_mem = float_input_ ? static_cast<void*>(interp_->typed_input_tensor<float>(0))
                                : static_cast<void*>(interp_->typed_input_tensor<uint8_t>(0));
    if (!in_mem) {
      fprintf(stderr, "error: cannot reach the model's input tensor\n");
      return false;
    }
    std::memset(in_mem, 0, in_bytes);
    if (interp_->Invoke() != kTfLiteOk) {
      fprintf(stderr, "error: the model failed its warm-up run\n");
      return false;
    }
    return true;
  }

  bool knows(const std::string& label) const {
    return std::find(labels_.begin(), labels_.end(), label) != labels_.end();
  }

  // bgr: any size. Returns everything scoring at least min_score.
  std::vector<Detection> detect(const cv::Mat& bgr, float min_score) {
    std::vector<Detection> out;
    if (!interp_ || bgr.empty()) return out;

    cv::Mat small;
    if (bgr.cols == in_w && bgr.rows == in_h)
      small = bgr;  // already shrunk by the camera callback; shares the pixels
    else
      cv::resize(bgr, small, cv::Size(in_w, in_h), 0, 0, cv::INTER_LINEAR);

    if (float_input_ && nchw_) {
      // [1,3,H,W]: one plane per colour, written straight into the tensor
      float* dst = interp_->typed_input_tensor<float>(0);
      cv::Mat rgb, scaled;
      cv::cvtColor(small, rgb, cv::COLOR_BGR2RGB);
      rgb.convertTo(scaled, CV_32F, yolo_ ? 1.0 / 255.0 : 1.0 / 127.5, yolo_ ? 0.0 : -1.0);
      const size_t plane = static_cast<size_t>(in_w) * in_h;
      std::vector<cv::Mat> planes = {cv::Mat(in_h, in_w, CV_32F, dst), cv::Mat(in_h, in_w, CV_32F, dst + plane),
                                     cv::Mat(in_h, in_w, CV_32F, dst + 2 * plane)};
      cv::split(scaled, planes);
    } else if (float_input_) {
      float* dst = interp_->typed_input_tensor<float>(0);
      cv::Mat rgb;
      cv::cvtColor(small, rgb, cv::COLOR_BGR2RGB);
      cv::Mat in_mat(in_h, in_w, CV_32FC3, dst);
      rgb.convertTo(in_mat, CV_32F, yolo_ ? 1.0 / 255.0 : 1.0 / 127.5, yolo_ ? 0.0 : -1.0);
      if (in_mat.data != reinterpret_cast<uchar*>(dst))
        std::memcpy(dst, in_mat.data, static_cast<size_t>(in_w) * in_h * 3 * sizeof(float));
    } else {
      // Convert BGR to RGB straight into the input tensor's own memory.
      uint8_t* dst = interp_->typed_input_tensor<uint8_t>(0);
      cv::Mat in_mat(in_h, in_w, CV_8UC3, dst);
      cv::cvtColor(small, in_mat, cv::COLOR_BGR2RGB);
      if (in_mat.data != dst) std::memcpy(dst, in_mat.data, static_cast<size_t>(in_w) * in_h * 3);
    }

    if (interp_->Invoke() != kTfLiteOk) return out;

    if (yolo_) {
      const float* raw = interp_->typed_output_tensor<float>(0);
      if (!raw) return out;
      for (auto& d : decode_yolo(raw, capacity_, anchors_first_, labels_, min_score))
        if (!d.label.empty() && d.label != "n/a") out.push_back(std::move(d));
      return out;
    }
    const float* boxes = interp_->typed_output_tensor<float>(0);
    const float* classes = interp_->typed_output_tensor<float>(1);
    const float* scores = interp_->typed_output_tensor<float>(2);
    const float* count = interp_->typed_output_tensor<float>(3);
    if (!boxes || !classes || !scores || !count) return out;

    const int n = std::clamp(static_cast<int>(std::lround(count[0])), 0, capacity_);
    for (int i = 0; i < n; ++i) {
      if (scores[i] < min_score) continue;
      const int cid = static_cast<int>(std::lround(classes[i]));
      if (cid < 0 || cid >= static_cast<int>(labels_.size())) continue;
      const std::string& label = labels_[static_cast<size_t>(cid)];
      if (label.empty() || label == "n/a") continue;
      Detection d;
      d.label = label;
      d.score = scores[i];
      d.y0 = boxes[i * 4 + 0];
      d.x0 = boxes[i * 4 + 1];
      d.y1 = boxes[i * 4 + 2];
      d.x1 = boxes[i * 4 + 3];
      out.push_back(d);
    }
    return out;
  }

  int in_w = 0, in_h = 0;

 private:
  // The model owns the mapped file and must outlive the interpreter, so it is
  // declared first (members are destroyed in reverse order).
  std::unique_ptr<tflite::FlatBufferModel> model_;
  std::unique_ptr<tflite::Interpreter> interp_;
  std::vector<std::string> labels_;
  bool float_input_ = false;
  bool nchw_ = false;           // input [1,3,H,W] rather than [1,H,W,3]
  bool yolo_ = false;           // one YOLO output rather than SSD's four
  bool anchors_first_ = false;  // YOLO output [1,A,4+K] rather than [1,4+K,A]
  int capacity_ = 0;            // SSD: boxes per run. YOLO: anchors
};

// ---------------------------------------------------------------------------
// Quests: quests.tsv = id <TAB> target <TAB> xp <TAB> text [<TAB> herd]
// '#' starts a comment. A quest marked "herd" needs a friend in the frame.
// ---------------------------------------------------------------------------
struct Quest {
  std::string id, label, text;
  int xp = 0;
  bool herd = false;
};

static std::vector<std::string> split_tabs(const std::string& line) {
  std::vector<std::string> parts;
  size_t start = 0;
  for (;;) {
    const size_t tab = line.find('\t', start);
    if (tab == std::string::npos) {
      parts.push_back(line.substr(start));
      break;
    }
    parts.push_back(line.substr(start, tab - start));
    start = tab + 1;
  }
  return parts;
}

static std::string trimmed(std::string s) {
  while (!s.empty() && (s.back() == ' ' || s.back() == '\r' || s.back() == '\n')) s.pop_back();
  size_t i = 0;
  while (i < s.size() && s[i] == ' ') ++i;
  return s.substr(i);
}

static std::vector<Quest> load_quests(const std::string& path) {
  std::vector<Quest> quests;
  std::ifstream f(path);
  if (!f) return quests;  // no quests yet; sniffing still works
  for (std::string line; std::getline(f, line);) {
    const std::string t = trimmed(line);
    if (t.empty() || t[0] == '#') continue;
    const auto parts = split_tabs(line);
    if (parts.size() < 3) {
      fprintf(stderr, "skipping bad quest line (use TABs between columns): %s\n", line.c_str());
      continue;
    }
    Quest q;
    q.id = trimmed(parts[0]);
    q.label = trimmed(parts[1]);
    std::transform(q.label.begin(), q.label.end(), q.label.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    q.xp = std::atoi(parts[2].c_str());
    q.text = parts.size() > 3 ? trimmed(parts[3]) : "Find a " + q.label;
    q.herd = parts.size() > 4 && trimmed(parts[4]) == "herd";
    quests.push_back(q);
  }
  return quests;
}

// ---------------------------------------------------------------------------
// Journal: append-only journal.jsonl, one JSON event per line. It is the
// device's only output: sync.py uploads it, and a button or buzzer script can
// watch it. State is rebuilt from it at start-up, so pulling the power loses
// nothing.
// ---------------------------------------------------------------------------
static std::string json_escape(const std::string& s) {
  std::string out;
  for (const char c : s) {
    if (c == '"' || c == '\\') out.push_back('\\');
    if (static_cast<unsigned char>(c) >= 0x20) out.push_back(c);
  }
  return out;
}

// The value of "key": "value" in one journal line, or "" if absent or null.
static std::string json_string_field(const std::string& line, const std::string& key) {
  const std::string pattern = "\"" + key + "\": \"";
  const size_t at = line.find(pattern);
  if (at == std::string::npos) return "";
  std::string out;
  for (size_t i = at + pattern.size(); i < line.size(); ++i) {
    if (line[i] == '\\' && i + 1 < line.size()) {
      out.push_back(line[++i]);
      continue;
    }
    if (line[i] == '"') return out;
    out.push_back(line[i]);
  }
  return "";  // a torn last line
}

class Journal {
 public:
  Journal(std::string path, std::string device)
      : path_(std::move(path)), device_(std::move(device)) {
    // Lines are written by this program or by gary_device.py, both as
    //   {"id": "...", "ts": "...", "type": "discovery", ..., "label": "bench", ...}
    std::ifstream f(path_);
    for (std::string line; std::getline(f, line);) {
      if (line.find("\"type\": \"discovery\"") == std::string::npos) continue;
      const std::string label = json_string_field(line, "label");
      const std::string quest = json_string_field(line, "quest_id");
      if (!label.empty()) seen_.insert(label);
      if (!quest.empty()) done_.insert(quest);
    }
    close_torn_line();
  }

  bool done(const std::string& quest_id) const { return done_.count(quest_id) > 0; }
  bool seen(const std::string& label) const { return seen_.count(label) > 0; }
  size_t kinds() const { return seen_.size(); }

  // quest_id is empty when the sniff completed no quest.
  void add_discovery(const std::string& label, float score, bool friend_here, bool is_new,
                     const std::string& quest_id, double latency_ms) {
    const std::string quest_json =
        quest_id.empty() ? std::string("null") : "\"" + json_escape(quest_id) + "\"";
    char body[512];
    std::snprintf(body, sizeof body,
                  "\"label\": \"%s\", \"score\": %.3f, \"friend\": %s, \"new\": %s, "
                  "\"quest_id\": %s, \"latency_ms\": %.1f",
                  json_escape(label).c_str(), static_cast<double>(score),
                  friend_here ? "true" : "false", is_new ? "true" : "false", quest_json.c_str(),
                  latency_ms);
    append("discovery", body);
    seen_.insert(label);
    if (!quest_id.empty()) done_.insert(quest_id);
  }

  void add_miss(bool friend_here, double latency_ms) {
    char body[96];
    std::snprintf(body, sizeof body, "\"friend\": %s, \"latency_ms\": %.1f",
                  friend_here ? "true" : "false", latency_ms);
    append("miss", body);
  }

 private:
  // If the power went mid-write, the file ends without a newline. End that
  // line now, so the next event starts on a line of its own.
  void close_torn_line() {
    const int fd = open(path_.c_str(), O_RDWR | O_APPEND);
    if (fd < 0) return;  // no journal yet
    char last = '\n';
    const off_t size = lseek(fd, 0, SEEK_END);
    if (size > 0 && pread(fd, &last, 1, size - 1) == 1 && last != '\n') {
      if (write(fd, "\n", 1) == 1) fsync(fd);
    }
    close(fd);
  }

  void append(const char* type, const char* body) {
    ++seq_;
    const auto now = std::chrono::system_clock::now();
    const long long epoch_ms =
        std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
    const std::time_t secs = std::chrono::system_clock::to_time_t(now);
    std::tm tm_utc{};
    gmtime_r(&secs, &tm_utc);
    char stamp[32];
    std::strftime(stamp, sizeof stamp, "%Y-%m-%dT%H:%M:%SZ", &tm_utc);

    const std::string device = json_escape(device_);
    char line[900];
    const int len = std::snprintf(
        line, sizeof line,
        "{\"id\": \"%s-%lld-%d\", \"ts\": \"%s\", \"type\": \"%s\", \"device\": \"%s\", %s}\n",
        device.c_str(), epoch_ms, seq_, stamp, type, device.c_str(), body);

    const int fd = open(path_.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
      fprintf(stderr, "warn: cannot write %s: %s\n", path_.c_str(), strerror(errno));
      return;
    }
    const size_t n = static_cast<size_t>(std::clamp(len, 0, static_cast<int>(sizeof line) - 1));
    for (size_t off = 0; off < n;) {
      const ssize_t w = write(fd, line + off, n - off);
      if (w < 0 && errno == EINTR) continue;
      if (w <= 0) {
        fprintf(stderr, "warn: write to %s failed: %s\n", path_.c_str(), strerror(errno));
        break;
      }
      off += static_cast<size_t>(w);
    }
    fsync(fd);  // on disk before Gary reacts
    close(fd);
  }

  std::string path_, device_;
  std::set<std::string> seen_;  // labels Gary has sniffed before
  std::set<std::string> done_;  // quest ids already completed
  int seq_ = 0;
};

// ---------------------------------------------------------------------------
// Stability: a label only counts once it appears in `need` of the last
// `window` frames. Removes one-frame flickers.
// ---------------------------------------------------------------------------
class Stability {
 public:
  Stability(int window, int need) : window_(std::max(1, window)), need_(std::max(1, need)) {}

  std::map<std::string, float> update(const std::map<std::string, float>& best) {
    history_.push_back(best);
    while (static_cast<int>(history_.size()) > window_) history_.pop_front();
    std::map<std::string, int> counts;
    std::map<std::string, float> top;
    for (const auto& frame : history_)
      for (const auto& kv : frame) {
        counts[kv.first] += 1;
        top[kv.first] = std::max(top[kv.first], kv.second);
      }
    std::map<std::string, float> confirmed;
    for (const auto& kv : counts)
      if (kv.second >= need_) confirmed[kv.first] = top[kv.first];
    return confirmed;
  }

 private:
  int window_, need_;
  std::deque<std::map<std::string, float>> history_;
};

// ---------------------------------------------------------------------------
// Speaker: plays sounds/<name>.wav through a command-line player (mmrplay on
// QNX). play() only queues; one audio thread runs the player, one clip at a
// time. A clip that overruns its time limit is stopped, so a stuck player can
// never block Gary.
// ---------------------------------------------------------------------------
static std::string shell_quote(const std::string& s) {
  std::string out = "'";
  for (const char c : s) {
    if (c == '\'')
      out += "'\\''";
    else
      out.push_back(c);
  }
  out.push_back('\'');
  return out;
}

class Speaker {
 public:
  Speaker(std::string folder, std::string command, bool mute, int clip_timeout_s)
      : folder_(std::move(folder)),
        command_(std::move(command)),
        mute_(mute),
        clip_timeout_s_(std::max(1, clip_timeout_s)) {
    if (!mute_) worker_ = std::thread([this] { run(); });
  }

  ~Speaker() {
    {
      std::lock_guard<std::mutex> lk(mtx_);
      stop_ = true;
    }
    cv_.notify_all();
    if (worker_.joinable()) worker_.join();
  }

  Speaker(const Speaker&) = delete;
  Speaker& operator=(const Speaker&) = delete;

  std::string path_of(const std::string& name) const { return folder_ + "/" + name + ".wav"; }
  bool has(const std::string& name) const { return access(path_of(name).c_str(), R_OK) == 0; }

  // Queues the clips that exist, in order, and returns at once.
  void play(const std::vector<std::string>& names) {
    if (mute_) return;
    std::vector<std::string> paths;
    for (const auto& n : names)
      if (has(n)) paths.push_back(path_of(n));
    if (paths.empty()) return;
    {
      std::lock_guard<std::mutex> lk(mtx_);
      if (queue_.size() >= kMaxQueued) queue_.pop_front();  // drop the stalest
      queue_.push_back(std::move(paths));
    }
    cv_.notify_one();
  }

 private:
  static constexpr size_t kMaxQueued = 4;

  bool stopping() {
    std::lock_guard<std::mutex> lk(mtx_);
    return stop_;
  }

  void run() {
    for (;;) {
      std::vector<std::string> batch;
      {
        std::unique_lock<std::mutex> lk(mtx_);
        cv_.wait(lk, [this] { return stop_ || !queue_.empty(); });
        if (stop_) return;
        batch = std::move(queue_.front());
        queue_.pop_front();
      }
      for (const auto& path : batch) {
        if (stopping()) return;
        play_one(path);
      }
    }
  }

  void play_one(const std::string& path) {
    // "exec" makes the shell become the player, so the pid below is the player.
    std::string cmd = "exec " + command_ + " " + shell_quote(path) + " >/dev/null 2>&1";
    std::string sh = "sh", flag = "-c";
    char* const argv[] = {sh.data(), flag.data(), cmd.data(), nullptr};
    pid_t pid = -1;
    const int rc = posix_spawn(&pid, "/bin/sh", nullptr, nullptr, argv, environ);
    if (rc != 0) {
      if (!warned_.exchange(true))
        fprintf(stderr, "warn: cannot start the audio player: %s\n", strerror(rc));
      return;
    }

    int status = 0;
    auto reaped = [&](int tries) {  // poll for the player to finish
      for (int i = 0; i < tries; ++i) {
        const pid_t r = waitpid(pid, &status, WNOHANG);
        if (r == pid) return true;
        if (r < 0 && errno != EINTR) return true;  // nothing left to wait for
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
      }
      return false;
    };

    const auto deadline = Clock::now() + std::chrono::seconds(clip_timeout_s_);
    for (;;) {
      if (reaped(1)) break;
      const bool overdue = Clock::now() >= deadline;
      if (overdue || stopping()) {
        kill(pid, SIGTERM);
        if (!reaped(30)) {
          kill(pid, SIGKILL);
          waitpid(pid, &status, 0);
        }
        if (overdue && !warned_.exchange(true))
          fprintf(stderr, "warn: stopped a sound after %d s: %s\n", clip_timeout_s_, path.c_str());
        return;
      }
    }
    if (!(WIFEXITED(status) && WEXITSTATUS(status) == 0) && !warned_.exchange(true))
      fprintf(stderr, "warn: the audio player failed. Try it by hand:  %s %s\n", command_.c_str(),
              path.c_str());
  }

  std::string folder_, command_;
  bool mute_;
  int clip_timeout_s_;
  std::mutex mtx_;
  std::condition_variable cv_;
  std::deque<std::vector<std::string>> queue_;
  bool stop_ = false;
  std::atomic<bool> warned_{false};
  std::thread worker_;
};

static std::string clip_name(std::string label) {
  std::replace(label.begin(), label.end(), ' ', '_');
  return label;
}

// ---------------------------------------------------------------------------
// Shared state between threads
// ---------------------------------------------------------------------------
static std::atomic<bool> g_run{true};
static std::atomic<bool> g_ask{false};      // the button was pressed
static std::atomic<long long> g_ask_ns{0};  // when, on the monotonic clock
static std::atomic<bool> g_reload{false};   // quests.tsv changed

static long long mono_ns() {
  timespec ts{};
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return static_cast<long long>(ts.tv_sec) * 1000000000LL + ts.tv_nsec;
}

// The button: Enter, or kill -USR1 from another program.
static void press_button() {
  g_ask_ns.store(mono_ns());
  g_ask.store(true);
}

// Frame handoff: one slot, newest wins. Frames the model misses are dropped.
static std::mutex g_frame_mtx;
static std::condition_variable g_frame_cv;
static cv::Mat g_frame;
static Clock::time_point g_frame_stamp;
static bool g_frame_ready = false;

// Signal handlers only flip a flag; the main loop does the work.
static void on_stop_signal(int) { g_run.store(false); }    // Ctrl-C, kill
static void on_sniff_signal(int) { press_button(); }       // kill -USR1 = Sniff Test
static void on_reload_signal(int) { g_reload.store(true); }  // kill -HUP = reload quests

static void install_handler(int sig, void (*fn)(int)) {
  struct sigaction sa;
  std::memset(&sa, 0, sizeof sa);
  sa.sa_handler = fn;
  sigemptyset(&sa.sa_mask);
#ifdef SA_RESTART
  sa.sa_flags = SA_RESTART;  // interrupted reads and writes carry on
#endif  // QNX has none; the journal write and the key poll retry on EINTR themselves
  sigaction(sig, &sa, nullptr);
}

// gary.pid lets another program find Gary:  kill -USR1 $(cat gary.pid)
struct PidFile {
  PidFile() {
    if (FILE* f = fopen("gary.pid", "w")) {
      fprintf(f, "%d\n", static_cast<int>(getpid()));
      fclose(f);
    }
  }
  ~PidFile() { unlink("gary.pid"); }
};

// Reads stdin without ever blocking for long, so the thread can be joined.
static void key_loop() {
  std::string pending;
  char buf[256];
  while (g_run.load()) {
    pollfd p{};
    p.fd = STDIN_FILENO;
    p.events = POLLIN;
    const int r = poll(&p, 1, 200);
    if (r < 0) {
      if (errno == EINTR) continue;
      return;
    }
    if (r == 0) continue;
    const ssize_t n = read(STDIN_FILENO, buf, sizeof buf);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return;  // stdin closed (started from a script): run without keys
    pending.append(buf, static_cast<size_t>(n));
    for (size_t nl; (nl = pending.find('\n')) != std::string::npos;) {
      std::string line = pending.substr(0, nl);
      pending.erase(0, nl + 1);
      if (!line.empty() && line.back() == '\r') line.pop_back();
      if (line == "q" || line == "Q") {
        g_run.store(false);
        g_frame_cv.notify_all();
        return;
      }
      press_button();
    }
  }
}

// QNX always runs the highest-priority ready thread. Ordinary programs sit at
// priority 10, so a decision thread at, say, 20 is never kept waiting by them.
// Threads created after this call inherit the setting by default.
static void raise_priority(int priority) {
  if (priority <= 0) return;
  sched_param sp{};
  sp.sched_priority = priority;
  const int rc = pthread_setschedparam(pthread_self(), SCHED_RR, &sp);
  if (rc == 0)
    printf("decision thread: round-robin priority %d\n", priority);
  else
    printf("warn: could not set priority %d: %s\n", priority, strerror(rc));
}

// quests.tsv is written by sync.py. Until it exists, use the seed quests.
static std::string quests_file(const std::string& explicit_path) {
  if (!explicit_path.empty()) return explicit_path;
  return access("quests.tsv", R_OK) == 0 ? "quests.tsv" : "quests.seed.tsv";
}

static double percentile(std::vector<double> v, double pct) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  const size_t i = static_cast<size_t>(std::lround(pct / 100.0 * static_cast<double>(v.size() - 1)));
  return v[std::min(i, v.size() - 1)];
}

struct Options {
  int unit = 5;  // USB camera on a Raspberry Pi 5 (CAM/DISP 0 is 3, CAM/DISP 1 is 4)
  // Two models on every frame: SSD for everyday things and people, and an Open
  // Images YOLO for nature (squirrel, tree, duck), which SSD cannot name.
  std::string model = "models/ssd_mobilenet_v2_coco_quant_postprocess.tflite";
  std::string labels = "models/coco_labels.txt";
  std::string extra_model = "models/gary_detector.tflite";  // "none" = SSD alone, faster
  std::string extra_labels = "models/gary_nature_labels.txt";
  std::string quests;  // empty = quests.tsv, or quests.seed.tsv until sync.py has run
  std::string log = "journal.jsonl";
  std::string device = "gary-01";
  std::string sounds = "sounds";
  std::string audio_cmd = "mmrplay";
  std::string friend_label = "person";
  std::string image;
  float threshold = 0.5f;
  int window = 5, need = 3, threads = 3, priority = 0, clip_timeout = 10;
  bool mute = false;
};

static void usage() {
  printf(
      "Gary the Goat (QNX). Run from the project folder.\n"
      "  --unit N          camera unit (default 5 = USB camera on a Pi 5; 3 and 4 = Pi cameras)\n"
      "  --image PATH      run the model once on a picture and exit (no camera needed)\n"
      "  --model PATH      TFLite detector\n"
      "  --labels PATH     label file, one name per line\n"
      "  --extra-model P   a second detector, run on the same frames (default the\n"
      "                    nature model; \"none\" for one model only)\n"
      "  --extra-labels P  its label file (\"n/a\" lines are ignored)\n"
      "  --quests PATH     quests file (default quests.tsv, or quests.seed.tsv\n"
      "                    until sync.py has run)\n"
      "  --log PATH        the journal (default journal.jsonl)\n"
      "  --device NAME     name written into every journal line (default gary-01)\n"
      "  --sounds DIR      folder of WAV clips\n"
      "  --audio-cmd CMD   player command (default mmrplay)\n"
      "  --clip-timeout S  stop a clip that plays longer than S seconds (default 10)\n"
      "  --threshold X     minimum confidence (default 0.5)\n"
      "  --window N        frames remembered (default 5)\n"
      "  --need N          frames needed to confirm (default 3)\n"
      "  --threads N       TFLite threads (default 3)\n"
      "  --priority N      run the decision thread at round-robin priority N (try 20)\n"
      "  --friend-label L  label that earns the friend bonus (default person)\n"
      "  --mute            no sound\n"
      "While it runs: Enter = Sniff Test, q + Enter = quit.\n"
      "From another program: kill -USR1 $(cat gary.pid) = Sniff Test,\n"
      "                      kill -HUP  $(cat gary.pid) = reload quests.tsv.\n");
}

static bool parse(int argc, char** argv, Options& o) {
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--mute") {
      o.mute = true;
      continue;
    }
    std::string* text = nullptr;
    int* whole = nullptr;
    float* real = nullptr;
    if (a == "--unit") whole = &o.unit;
    else if (a == "--window") whole = &o.window;
    else if (a == "--need") whole = &o.need;
    else if (a == "--threads") whole = &o.threads;
    else if (a == "--priority") whole = &o.priority;
    else if (a == "--clip-timeout") whole = &o.clip_timeout;
    else if (a == "--threshold") real = &o.threshold;
    else if (a == "--image") text = &o.image;
    else if (a == "--model") text = &o.model;
    else if (a == "--labels") text = &o.labels;
    else if (a == "--extra-model") text = &o.extra_model;
    else if (a == "--extra-labels") text = &o.extra_labels;
    else if (a == "--quests") text = &o.quests;
    else if (a == "--log") text = &o.log;
    else if (a == "--device") text = &o.device;
    else if (a == "--sounds") text = &o.sounds;
    else if (a == "--audio-cmd") text = &o.audio_cmd;
    else if (a == "--friend-label") text = &o.friend_label;
    else {
      fprintf(stderr, "unknown option %s\n\n", a.c_str());
      usage();
      return false;
    }
    if (i + 1 >= argc) {
      fprintf(stderr, "missing value for %s\n", a.c_str());
      return false;
    }
    const char* v = argv[++i];
    if (text) *text = v;
    if (whole) *whole = std::atoi(v);
    if (real) *real = static_cast<float>(std::atof(v));
  }
  return true;
}

// Model self-test: one picture in, detections out. Separates "is it the model"
// from "is it the camera" when something misbehaves.
static int run_image(const Options& opt) {
#ifdef GARY_HAS_IMGCODECS
  Detector detector, extra;
  if (!detector.load(opt.model, opt.labels, opt.threads)) return 1;
  const bool has_extra = opt.extra_model != "none";
  if (has_extra && !extra.load(opt.extra_model, opt.extra_labels, opt.threads)) return 1;
  const cv::Mat img = cv::imread(opt.image, cv::IMREAD_COLOR);
  if (img.empty()) {
    fprintf(stderr, "error: cannot read image %s\n", opt.image.c_str());
    return 1;
  }
  const auto t0 = Clock::now();
  auto found = detector.detect(img, std::min(0.3f, opt.threshold));
  if (has_extra) found = merge(std::move(found), extra.detect(img, std::min(0.3f, opt.threshold)));
  const double ms = ms_between(t0, Clock::now());
  std::sort(found.begin(), found.end(),
            [](const Detection& a, const Detection& b) { return a.score > b.score; });
  printf("%s (%dx%d): %zu detections, model + resize %.0f ms\n", opt.image.c_str(), img.cols,
         img.rows, found.size(), ms);
  for (const auto& d : found)
    printf("  %-14s %3.0f%%   x %.2f-%.2f  y %.2f-%.2f\n", d.label.c_str(), d.score * 100.f, d.x0,
           d.x1, d.y0, d.y1);
  return 0;
#else
  (void)opt;
  fprintf(stderr, "--image is not available: this OpenCV has no imgcodecs module\n");
  return 1;
#endif
}

int main(int argc, char** argv) {
  for (int i = 1; i < argc; ++i)
    if (!std::strcmp(argv[i], "--help") || !std::strcmp(argv[i], "-h")) {
      usage();
      return 0;
    }
  Options opt;
  if (!parse(argc, argv, opt)) return 1;
  if (!opt.image.empty()) return run_image(opt);

  install_handler(SIGINT, on_stop_signal);
  install_handler(SIGTERM, on_stop_signal);
  install_handler(SIGUSR1, on_sniff_signal);
  install_handler(SIGHUP, on_reload_signal);
  PidFile pid_file;

  // Started first, so the audio and key threads stay at normal priority.
  Speaker speaker(opt.sounds, opt.audio_cmd, opt.mute, opt.clip_timeout);
  std::thread keys(key_loop);
  struct KeysGuard {
    std::thread& t;
    ~KeysGuard() {
      g_run.store(false);
      if (t.joinable()) t.join();
    }
  } keys_guard{keys};

  // From here on, new threads inherit the priority: the model's workers do.
  raise_priority(opt.priority);

  Detector detector, extra;
  if (!detector.load(opt.model, opt.labels, opt.threads)) return 1;
  const bool has_extra = opt.extra_model != "none";
  if (has_extra && !extra.load(opt.extra_model, opt.extra_labels, opt.threads)) return 1;
  auto knows = [&](const std::string& label) { return detector.knows(label) || (has_extra && extra.knows(label)); };

  std::vector<Quest> quests = load_quests(quests_file(opt.quests));
  Journal journal(opt.log, opt.device);
  Stability stable(opt.window, opt.need);

  auto print_quests = [&] {
    int already = 0;
    for (const auto& q : quests) {
      if (!knows(q.label))
        printf("WARNING: quest %s wants '%s', which this model cannot see.\n", q.id.c_str(),
               q.label.c_str());
      if (journal.done(q.id)) ++already;
    }
    printf("%zu quests, %d done.\n", quests.size(), already);
    for (const auto& q : quests)
      printf("  [%s] %s  (%s%s)\n", journal.done(q.id) ? "x" : " ", q.text.c_str(),
             q.label.c_str(), q.herd ? ", needs a friend" : "");
  };
  printf("Gary is awake. Model input %dx%d. %zu kinds of thing in the journal. ", detector.in_w,
         detector.in_h, journal.kinds());
  print_quests();
  printf("Press Enter to sniff. q + Enter quits.\n");
  fflush(stdout);

  RpiCam cam(static_cast<camera_unit_t>(opt.unit));
  int err = cam.init();
  if (err != EOK) {
    fprintf(stderr, "error: camera unit %d did not open: %s\n", opt.unit, strerror(err));
    fprintf(stderr, "       USB webcam = --unit 5, Pi cameras = --unit 3 or 4\n");
    return 1;
  }

  // Runs on the camera library's thread, so it stays short: shrink the frame
  // to the model's size (into memory we own) and leave it in the slot.
  // the larger of the two inputs, so neither model is fed an enlarged image
  const int in_w = std::max(detector.in_w, has_extra ? extra.in_w : 0);
  const int in_h = std::max(detector.in_h, has_extra ? extra.in_h : 0);
  auto on_frame = [in_w, in_h](const cv::Mat& bgr) {
    if (!g_run.load() || bgr.empty()) return;
    const auto arrived = Clock::now();
#ifdef GARY_HAS_IMGCODECS
    // GARY_SAVE_FRAME=frame.jpg: keep one camera frame, to check what the model is given
    static std::atomic<int> seen{0};
    if (const char* path = std::getenv("GARY_SAVE_FRAME"); path && seen.fetch_add(1) == 30) cv::imwrite(path, bgr);
#endif
    cv::Mat small;
    cv::resize(bgr, small, cv::Size(in_w, in_h), 0, 0, cv::INTER_LINEAR);
    {
      std::lock_guard<std::mutex> lk(g_frame_mtx);
      g_frame = std::move(small);
      g_frame_stamp = arrived;
      g_frame_ready = true;
    }
    g_frame_cv.notify_one();
  };
  err = cam.start(on_frame);
  if (err != EOK) {
    fprintf(stderr, "error: camera start failed: %s\n", strerror(err));
    return 1;
  }

  speaker.play({"hello"});

  std::map<std::string, float> confirmed;  // what Gary is sure he sees right now
  // Per-frame timings: frame-to-decision ms, model ms. Only the most recent
  // kKeepTimings are kept, so a device left on for days does not grow.
  constexpr size_t kKeepTimings = 200000;
  struct Timing {
    double frame_to_decision_ms, model_ms, t_ms;  // t_ms: since Gary started
  };
  std::vector<Timing> timings;
  size_t dropped = 0, frames_total = 0, window_start = 0;
  const auto started = Clock::now();
  auto last_report = started;
  int empty_waits = 0;
  std::vector<double> sniff_ms;  // button press to answer
  int discoveries = 0, fresh = 0, misses = 0;

  // The Sniff Test: name what is in view right now and write it down.
  auto handle_sniff = [&] {
    if (g_reload.exchange(false)) {
      quests = load_quests(quests_file(opt.quests));
      printf("\nQuests reloaded: ");
      print_quests();
      fflush(stdout);
    }
    if (!g_ask.exchange(false)) return;
    const long long pressed = g_ask_ns.load();
    auto latency = [pressed] { return static_cast<double>(mono_ns() - pressed) / 1e6; };
    const bool friend_here = confirmed.count(opt.friend_label) > 0;

    // The surest thing in view, leaving the friend out.
    std::string label;
    float score = 0.f;
    for (const auto& kv : confirmed) {
      if (kv.first == opt.friend_label) continue;
      if (label.empty() || kv.second > score) {
        label = kv.first;
        score = kv.second;
      }
    }
    if (label.empty()) {
      const double ms = latency();
      journal.add_miss(friend_here, ms);
      sniff_ms.push_back(ms);
      ++misses;
      printf("\nSNIFF: nothing Gary can name%s.  [%.1f ms]\n",
             friend_here ? " (he does see a friend)" : "", ms);
      speaker.play({"nothing"});
      fflush(stdout);
      return;
    }

    // An open quest's target wins if it is in view. A herd quest only
    // completes with a friend in the frame, so a quest that can be finished
    // right now is preferred over a herd quest that cannot. Among equals the
    // surest target wins, then the earlier line of the file (sync.py puts the
    // active quest first). gary_device.py: choose_quest() is the same rule.
    const Quest* quest = nullptr;
    float quest_score = 0.f;
    bool quest_doable = false;
    for (const auto& q : quests) {
      if (journal.done(q.id) || q.label == opt.friend_label) continue;
      const auto hit = confirmed.find(q.label);
      if (hit == confirmed.end()) continue;
      const bool doable = friend_here || !q.herd;
      const bool better = !quest || (doable && !quest_doable) ||
                          (doable == quest_doable && hit->second > quest_score);
      if (better) {
        quest = &q;
        quest_score = hit->second;
        quest_doable = doable;
      }
    }
    if (quest) {
      label = quest->label;
      score = quest_score;
    }
    const Quest* completed = (quest && quest_doable) ? quest : nullptr;
    const bool is_new = !journal.seen(label);
    const double ms = latency();
    journal.add_discovery(label, score, friend_here, is_new,
                          completed ? completed->id : std::string(), ms);
    sniff_ms.push_back(ms);
    ++discoveries;
    if (is_new) ++fresh;

    std::string line = "\nSNIFF: " + label + " (" +
                       std::to_string(static_cast<int>(std::lround(score * 100.f))) + "%).";
    std::vector<std::string> clips;
    if (completed) {
      line += " Quest complete: " + completed->text + ".";
      clips.push_back("quest");
    } else if (is_new) {
      line += " New discovery.";
      clips.push_back("new");
    } else {
      line += " Gary has seen one before.";
      clips.push_back("again");
    }
    if (friend_here) {
      line += " Herd Mode: a friend is in frame.";
      clips.push_back("herd");
    } else if (quest && quest->herd) {
      line += " That quest needs a friend in frame.";
    }
    if (speaker.has(clip_name(label))) clips.push_back(clip_name(label));  // a spoken label
    if (completed && std::all_of(quests.begin(), quests.end(),
                                 [&](const Quest& x) { return journal.done(x.id); })) {
      line += " All of today's quests are done.";
      clips.push_back("done");
    }
    printf("%s  [%.1f ms]\n", line.c_str(), ms);
    speaker.play(clips);
    fflush(stdout);
  };

  while (g_run.load()) {
    cv::Mat frame;
    Clock::time_point stamp;
    {
      std::unique_lock<std::mutex> lk(g_frame_mtx);
      const bool got = g_frame_cv.wait_for(lk, std::chrono::milliseconds(500),
                                           [] { return g_frame_ready || !g_run.load(); });
      if (!g_run.load()) break;
      if (!got) {  // no frame for half a second: stay responsive to the button
        lk.unlock();
        if (++empty_waits == 6) {
          printf("No frames from camera unit %d yet. Is the webcam in a blue USB port?\n", opt.unit);
          fflush(stdout);
        }
        handle_sniff();
        continue;
      }
      frame = std::move(g_frame);
      stamp = g_frame_stamp;
      g_frame_ready = false;
    }
    empty_waits = 0;

    const auto t0 = Clock::now();
    auto detections = detector.detect(frame, std::min(0.3f, opt.threshold));
    if (has_extra) detections = merge(std::move(detections), extra.detect(frame, std::min(0.3f, opt.threshold)));
    const double model_ms = ms_between(t0, Clock::now());

    std::map<std::string, float> best;
    for (const auto& d : detections)
      if (d.score >= opt.threshold) best[d.label] = std::max(best[d.label], d.score);
    confirmed = stable.update(best);

    // Gary now knows what is in view: stop the clock. "Frame" = the frame
    // reaching this program; time inside the camera and USB link is not included.
    const auto decided = Clock::now();
    timings.push_back({ms_between(stamp, decided), model_ms, ms_between(started, decided)});
    ++frames_total;
    handle_sniff();

    const auto now = Clock::now();
    const double since = ms_between(last_report, now) / 1000.0;
    if (since >= 5.0 && timings.size() > window_start) {
      std::vector<double> lat;
      double model_sum = 0;
      for (size_t i = window_start; i < timings.size(); ++i) {
        lat.push_back(timings[i].frame_to_decision_ms);
        model_sum += timings[i].model_ms;
      }
      std::string seen;
      for (const auto& kv : confirmed) seen += (seen.empty() ? "" : ", ") + kv.first;
      printf("%.1f fps | model %.0f ms | frame-to-decision p50 %.0f ms, p95 %.0f ms, max %.0f ms | sees: %s\n",
             static_cast<double>(lat.size()) / since, model_sum / static_cast<double>(lat.size()),
             percentile(lat, 50), percentile(lat, 95), percentile(lat, 100),
             seen.empty() ? "-" : seen.c_str());
      fflush(stdout);
      if (timings.size() > kKeepTimings) {
        const size_t cut = timings.size() - kKeepTimings / 2;
        timings.erase(timings.begin(), timings.begin() + static_cast<std::ptrdiff_t>(cut));
        dropped += cut;
      }
      window_start = timings.size();
      last_report = now;
    }
  }

  g_run.store(false);
  cam.stop();  // no more callbacks after this returns

  if (!timings.empty()) {
    std::vector<double> lat;
    double model_sum = 0;
    for (const auto& t : timings) {
      lat.push_back(t.frame_to_decision_ms);
      model_sum += t.model_ms;
    }
    const double seconds = std::max(1e-3, (timings.back().t_ms - timings.front().t_ms) / 1000.0);
    const double fps =
        timings.size() > 1 ? static_cast<double>(timings.size() - 1) / seconds : 0.0;
    printf("\n%zu frames, %.1f per second. Model: mean %.0f ms. Frame-to-decision: p50 %.0f ms, p95 %.0f ms, max %.0f ms.\n",
           frames_total, fps, model_sum / static_cast<double>(timings.size()),
           percentile(lat, 50), percentile(lat, 95), percentile(lat, 100));
    // t_ms is the time since Gary started. gary_numbers.py turns this file into
    // the table for the judges (issue #14).
    if (FILE* f = fopen("latency.csv", "w")) {
      fprintf(f, "frame,frame_to_decision_ms,model_ms,t_ms\n");
      for (size_t i = 0; i < timings.size(); ++i)
        fprintf(f, "%zu,%.2f,%.2f,%.1f\n", dropped + i, timings[i].frame_to_decision_ms,
                timings[i].model_ms, timings[i].t_ms);
      fclose(f);
    }
  }
  if (!sniff_ms.empty())
    printf("Sniffs: %zu (%d discoveries, %d new, %d misses). Answered in p50 %.0f ms, max %.0f ms.\n",
           sniff_ms.size(), discoveries, fresh, misses, percentile(sniff_ms, 50),
           percentile(sniff_ms, 100));
  int done = 0;
  for (const auto& q : quests)
    if (journal.done(q.id)) ++done;
  printf("Quests done: %d of %zu.\n", done, quests.size());
  return 0;
}
