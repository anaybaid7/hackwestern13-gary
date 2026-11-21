// Stub of the TFLite C++ API surface used by gary_qnx.cpp. Linux test only.
#pragma once
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>
typedef enum { kTfLiteOk = 0, kTfLiteError = 1 } TfLiteStatus;
typedef enum { kTfLiteNoType = 0, kTfLiteFloat32 = 1, kTfLiteInt32 = 2, kTfLiteUInt8 = 3 } TfLiteType;
struct TfLiteIntArray { int size; int data[8]; };
struct TfLiteTensor { TfLiteType type; TfLiteIntArray* dims; };
namespace tflite {
class Interpreter {
 public:
  Interpreter();
  TfLiteStatus AllocateTensors();
  TfLiteStatus Invoke();
  template <class T> T* typed_input_tensor(int) { return reinterpret_cast<T*>(input_.data()); }
  template <class T> T* typed_output_tensor(int i) { return reinterpret_cast<T*>(out_[i].data()); }
  TfLiteTensor* input_tensor(size_t) { return &in_t_; }
  const TfLiteTensor* output_tensor(size_t i) const { return &out_t_[i]; }
  const std::vector<int>& inputs() const { return in_ids_; }
  const std::vector<int>& outputs() const { return out_ids_; }
 private:
  std::vector<uint8_t> input_;
  std::vector<float> out_[4];
  TfLiteIntArray in_dims_, out_dims_[4];
  TfLiteTensor in_t_, out_t_[4];
  std::vector<int> in_ids_, out_ids_;
  long frame_ = 0;
};
}  // namespace tflite
