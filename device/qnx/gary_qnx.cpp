// gary_qnx.cpp - Gary the Goat device loop for QNX 8 on a Raspberry Pi 5.
//
//   QNX Camera API -> TFLite object detector -> quest match -> sound + log
//
// Camera capture uses the RpiCam wrapper from QNX's AI workshop (Apache-2.0):
//   https://github.com/qnx/QNX-AI-workshop
// The TFLite calls are the ones that workshop's handtracking.cpp uses.
//
// It reads the same files as gary_device.py (models/, quests.tsv, sounds/) and
// appends to the same finds.jsonl, so the two versions are interchangeable.
//
// Run it from the project folder (the one that holds models/ and quests.tsv):
//   ./qnx/build/gary                          camera unit 5 = USB webcam
//   ./qnx/build/gary --image test/pets.jpg    model self-test, no camera
// Keys:  Enter = "Ask Gary" (he says what he sees),  q + Enter = quit.
// No keyboard?  kill -USR1 $(cat gary.pid)  asks Gary from any other program,
// which is how a hardware button can be wired in later.
//
// Threads:
//   camera thread  - owned by the camera library; shrinks each frame and
//                    leaves the newest one in a one-slot handoff
//   main thread    - runs the model and makes every decision
//   audio thread   - plays queued clips, so sound never delays a decision
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

#ifndef EOK
#define EOK 0
#endif

extern char** environ;

using Clock = std::chrono::steady_clock;

static double ms_between(Clock::time_point a, Clock::time_point b) {
  return std::chrono::duration<double, std::milli>(b - a).count();
}

// ---------------------------------------------------------------------------
// Detector: SSD-style TFLite model with the standard four outputs
//   0 boxes [1,N,4] (ymin,xmin,ymax,xmax in 0..1)   1 classes [1,N]
//   2 scores [1,N]                                    3 count [1]
// ---------------------------------------------------------------------------
struct Detection {
  std::string label;
  float score = 0.f;
  float x0 = 0.f, y0 = 0.f, x1 = 0.f, y1 = 0.f;
};

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
    if (!in || !in->dims || in->dims->size != 4 || in->dims->data[3] != 3) {
      fprintf(stderr, "error: model input is not [1,H,W,3]\n");
      return false;
    }
    in_h = in->dims->data[1];
    in_w = in->dims->data[2];
    if (in->type == kTfLiteFloat32) {
      float_input_ = true;
    } else if (in->type == kTfLiteUInt8) {
      float_input_ = false;
    } else {
      fprintf(stderr, "error: model input must be uint8 or float32\n");
      return false;
    }

    if (interp_->outputs().size() < 4) {
      fprintf(stderr, "error: model does not have the 4 detection outputs\n");
      return false;
    }
    const TfLiteTensor* boxes = interp_->output_tensor(0);
    const TfLiteTensor* scores = interp_->output_tensor(2);
    const bool boxes_ok = boxes && boxes->dims && boxes->dims->size == 3 && boxes->dims->data[2] == 4;
    const bool scores_ok = scores && scores->dims && scores->dims->size == 2;
    if (!boxes_ok || !scores_ok) {
      fprintf(stderr, "error: model outputs are not in the order boxes, classes, scores, count\n");
      return false;
    }
    capacity_ = scores->dims->data[1];
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

    if (float_input_) {
      float* dst = interp_->typed_input_tensor<float>(0);
      cv::Mat rgb;
      cv::cvtColor(small, rgb, cv::COLOR_BGR2RGB);
      cv::Mat in_mat(in_h, in_w, CV_32FC3, dst);
      rgb.convertTo(in_mat, CV_32F, 1.0 / 127.5, -1.0);
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
  int capacity_ = 0;
};

// ---------------------------------------------------------------------------
// Quests: quests.tsv = id <TAB> label <TAB> points <TAB> text, '#' = comment
// ---------------------------------------------------------------------------
struct Quest {
  std::string id, label, text;
  int points = 0;
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
  if (!f) {
    fprintf(stderr, "error: cannot open quests file %s\n", path.c_str());
    return quests;
  }
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
    q.points = std::atoi(parts[2].c_str());
    q.text = parts.size() > 3 ? trimmed(parts[3]) : "Find a " + q.label;
    quests.push_back(q);
  }
  return quests;
}

// ---------------------------------------------------------------------------
// Find log: append-only finds.jsonl. State is rebuilt from it at start-up, so
// pulling the power never loses a completed quest.
// ---------------------------------------------------------------------------
static std::string json_escape(const std::string& s) {
  std::string out;
  for (const char c : s) {
    if (c == '"' || c == '\\') out.push_back('\\');
    if (static_cast<unsigned char>(c) >= 0x20) out.push_back(c);
  }
  return out;
}

class FindLog {
 public:
  explicit FindLog(std::string path) : path_(std::move(path)) {
    std::ifstream f(path_);
    for (std::string line; std::getline(f, line);) {
      // Lines are written by this program or by gary_device.py, both as
      //   {"ts": "...", "quest_id": "demo-1", ..., "points": 10}
      static const std::string id_key = "\"quest_id\": \"";
      static const std::string pts_key = "\"points\": ";
      const size_t a = line.find(id_key);
      const size_t p = line.find(pts_key);
      if (a == std::string::npos || p == std::string::npos) continue;  // torn last line
      const size_t b = line.find('"', a + id_key.size());
      if (b == std::string::npos) continue;
      done_.insert(line.substr(a + id_key.size(), b - (a + id_key.size())));
      points_ += std::atoi(line.c_str() + p + pts_key.size());
    }
  }

  bool done(const std::string& id) const { return done_.count(id) > 0; }
  int points() const { return points_; }

  void add(const Quest& q, float score, bool friend_bonus, int points) {
    char stamp[40];
    const std::time_t now = std::time(nullptr);
    std::tm tm_utc{};
    gmtime_r(&now, &tm_utc);
    std::strftime(stamp, sizeof stamp, "%Y-%m-%dT%H:%M:%S+00:00", &tm_utc);

    char line[512];
    const int len = std::snprintf(
        line, sizeof line,
        "{\"ts\": \"%s\", \"quest_id\": \"%s\", \"label\": \"%s\", \"score\": %.3f, "
        "\"friend\": %s, \"points\": %d}\n",
        stamp, json_escape(q.id).c_str(), json_escape(q.label).c_str(),
        static_cast<double>(score), friend_bonus ? "true" : "false", points);

    const int fd = open(path_.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) {
      fprintf(stderr, "warn: cannot write %s: %s\n", path_.c_str(), strerror(errno));
    } else {
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
      fsync(fd);  // on disk before Gary celebrates
      close(fd);
    }
    done_.insert(q.id);
    points_ += points;
  }

 private:
  std::string path_;
  std::set<std::string> done_;
  int points_ = 0;
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
static std::atomic<bool> g_ask{false};

// Frame handoff: one slot, newest wins. Frames the model misses are dropped.
static std::mutex g_frame_mtx;
static std::condition_variable g_frame_cv;
static cv::Mat g_frame;
static Clock::time_point g_frame_stamp;
static bool g_frame_ready = false;

// Signal handlers only flip a flag; the main loop does the work.
static void on_stop_signal(int) { g_run.store(false); }  // Ctrl-C, kill
static void on_ask_signal(int) { g_ask.store(true); }    // kill -USR1 = Ask Gary

static void install_handler(int sig, void (*fn)(int)) {
  struct sigaction sa;
  std::memset(&sa, 0, sizeof sa);
  sa.sa_handler = fn;
  sigemptyset(&sa.sa_mask);
  sa.sa_flags = SA_RESTART;  // interrupted reads and writes carry on
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
      g_ask.store(true);
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

static double percentile(std::vector<double> v, double pct) {
  if (v.empty()) return 0.0;
  std::sort(v.begin(), v.end());
  const size_t i = static_cast<size_t>(std::lround(pct / 100.0 * static_cast<double>(v.size() - 1)));
  return v[std::min(i, v.size() - 1)];
}

struct Options {
  int unit = 5;  // USB camera on a Raspberry Pi 5 (CAM/DISP 0 is 3, CAM/DISP 1 is 4)
  std::string model = "models/ssd_mobilenet_v2_coco_quant_postprocess.tflite";
  std::string labels = "models/coco_labels.txt";
  std::string quests = "quests.tsv";
  std::string log = "finds.jsonl";
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
      "  --quests PATH     quests.tsv\n"
      "  --log PATH        finds.jsonl\n"
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
      "While it runs: Enter = Ask Gary, q + Enter = quit.\n"
      "From another program: kill -USR1 $(cat gary.pid) = Ask Gary.\n");
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
    else if (a == "--quests") text = &o.quests;
    else if (a == "--log") text = &o.log;
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
  Detector detector;
  if (!detector.load(opt.model, opt.labels, opt.threads)) return 1;
  const cv::Mat img = cv::imread(opt.image, cv::IMREAD_COLOR);
  if (img.empty()) {
    fprintf(stderr, "error: cannot read image %s\n", opt.image.c_str());
    return 1;
  }
  const auto t0 = Clock::now();
  auto found = detector.detect(img, std::min(0.3f, opt.threshold));
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
  install_handler(SIGUSR1, on_ask_signal);
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

  Detector detector;
  if (!detector.load(opt.model, opt.labels, opt.threads)) return 1;

  const std::vector<Quest> quests = load_quests(opt.quests);
  if (quests.empty()) {
    fprintf(stderr, "error: no quests loaded from %s\n", opt.quests.c_str());
    return 1;
  }
  FindLog log(opt.log);
  Stability stable(opt.window, opt.need);

  int already = 0;
  for (const auto& q : quests) {
    if (!detector.knows(q.label))
      printf("WARNING: quest %s wants '%s', which this model cannot see.\n", q.id.c_str(),
             q.label.c_str());
    if (log.done(q.id)) ++already;
  }
  printf("Gary is awake. Model input %dx%d. %zu quests, %d already done, %d points.\n",
         detector.in_w, detector.in_h, quests.size(), already, log.points());
  for (const auto& q : quests)
    printf("  [%s] %s  (%s, %d pts)\n", log.done(q.id) ? "x" : " ", q.text.c_str(),
           q.label.c_str(), q.points);
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
  const int in_w = detector.in_w, in_h = detector.in_h;
  auto on_frame = [in_w, in_h](const cv::Mat& bgr) {
    if (!g_run.load() || bgr.empty()) return;
    const auto arrived = Clock::now();
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

  std::map<std::string, float> confirmed;
  // Per-frame timings: frame-to-decision ms, model ms. Only the most recent
  // kKeepTimings are kept, so a device left on for days does not grow.
  constexpr size_t kKeepTimings = 200000;
  std::vector<std::pair<double, double>> timings;
  size_t dropped = 0, frames_total = 0, window_start = 0;
  auto last_report = Clock::now();
  int empty_waits = 0;

  auto answer_ask = [&] {
    if (!g_ask.exchange(false)) return;
    std::vector<std::pair<std::string, float>> seen(confirmed.begin(), confirmed.end());
    std::sort(seen.begin(), seen.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    if (seen.size() > 3) seen.resize(3);
    if (seen.empty()) {
      printf("\nGary sees nothing he can name.\n");
      speaker.play({"nothing"});
    } else {
      std::vector<std::string> clips{"ask"};
      printf("\nGary sees:");
      for (const auto& s : seen) {
        printf(" %s (%.0f%%)", s.first.c_str(), s.second * 100.f);
        clips.push_back(clip_name(s.first));
      }
      printf("\n");
      speaker.play(clips);
    }
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
      if (!got) {  // no frame for half a second: stay responsive to the keys
        lk.unlock();
        if (++empty_waits == 6) {
          printf("No frames from camera unit %d yet. Is the webcam in a blue USB port?\n", opt.unit);
          fflush(stdout);
        }
        answer_ask();
        continue;
      }
      frame = std::move(g_frame);
      stamp = g_frame_stamp;
      g_frame_ready = false;
    }
    empty_waits = 0;

    const auto t0 = Clock::now();
    const auto detections = detector.detect(frame, std::min(0.3f, opt.threshold));
    const double model_ms = ms_between(t0, Clock::now());

    std::map<std::string, float> best;
    for (const auto& d : detections)
      if (d.score >= opt.threshold) best[d.label] = std::max(best[d.label], d.score);
    confirmed = stable.update(best);

    const bool friend_here = confirmed.count(opt.friend_label) > 0;
    for (const auto& q : quests) {
      if (log.done(q.id)) continue;
      const auto hit = confirmed.find(q.label);
      if (hit == confirmed.end()) continue;
      const bool bonus = friend_here && q.label != opt.friend_label;
      const int points = q.points * (bonus ? 2 : 1);
      log.add(q, hit->second, bonus, points);
      printf("\nFOUND: %s  (+%d points%s)  total %d\n", q.text.c_str(), points,
             bonus ? ", friend bonus" : "", log.points());
      std::vector<std::string> clips{bonus ? "friend" : "found"};
      if (speaker.has(clip_name(q.label))) clips.push_back(clip_name(q.label));
      const bool all_done = std::all_of(quests.begin(), quests.end(),
                                        [&](const Quest& x) { return log.done(x.id); });
      if (all_done) {
        clips.push_back("done");
        printf("All of today's quests are done. Gary is very pleased.\n");
      }
      speaker.play(clips);
      fflush(stdout);
    }

    // The decision is made: stop the clock. "Frame" = the frame reaching this
    // program; time inside the camera and the USB link is not included.
    timings.emplace_back(ms_between(stamp, Clock::now()), model_ms);
    ++frames_total;
    answer_ask();

    const auto now = Clock::now();
    const double since = ms_between(last_report, now) / 1000.0;
    if (since >= 5.0 && timings.size() > window_start) {
      std::vector<double> lat;
      double model_sum = 0;
      for (size_t i = window_start; i < timings.size(); ++i) {
        lat.push_back(timings[i].first);
        model_sum += timings[i].second;
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
      lat.push_back(t.first);
      model_sum += t.second;
    }
    printf("\n%zu frames. Model: mean %.0f ms. Frame-to-decision: p50 %.0f ms, p95 %.0f ms, max %.0f ms.\n",
           frames_total, model_sum / static_cast<double>(timings.size()), percentile(lat, 50),
           percentile(lat, 95), percentile(lat, 100));
    if (FILE* f = fopen("latency.csv", "w")) {
      fprintf(f, "frame,frame_to_decision_ms,model_ms\n");
      for (size_t i = 0; i < timings.size(); ++i)
        fprintf(f, "%zu,%.2f,%.2f\n", dropped + i, timings[i].first, timings[i].second);
      fclose(f);
    }
  }
  int done = 0;
  for (const auto& q : quests)
    if (log.done(q.id)) ++done;
  printf("Points: %d. Quests done: %d of %zu.\n", log.points(), done, quests.size());
  return 0;
}
