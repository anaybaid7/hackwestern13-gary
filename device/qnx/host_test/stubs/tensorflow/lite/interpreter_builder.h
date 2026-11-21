#pragma once
#include <memory>
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/model_builder.h"
namespace tflite {
class OpResolver {};
class InterpreterBuilder {
 public:
  InterpreterBuilder(const FlatBufferModel&, const OpResolver&) {}
  TfLiteStatus operator()(std::unique_ptr<Interpreter>* interpreter);
  TfLiteStatus operator()(std::unique_ptr<Interpreter>* interpreter, int num_threads);
};
}
