#pragma once
#include <memory>
namespace tflite {
class FlatBufferModel {
 public:
  static std::unique_ptr<FlatBufferModel> BuildFromFile(const char* filename);
};
}
